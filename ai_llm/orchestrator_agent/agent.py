import os
import json
import logging
import asyncio
import time
import httpx
from typing import AsyncIterator, Dict, Any, List, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from a2a.client import A2AClient, A2ACardResolver
from a2a.types import MessageSendParams, SendMessageRequest, Part, TextPart, Message
from uuid import uuid4
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

try:
    from .models import IntentPlan, PlanStep, TraceStep, AgentResult
except ImportError:
    from models import IntentPlan, PlanStep, TraceStep, AgentResult

logger = logging.getLogger(__name__)
load_dotenv()

AGENT_URLS = {
    "internal_rag": os.getenv("RAG_AGENT_URL", "http://localhost:10012"),
    "web_research": os.getenv("WEB_AGENT_URL", "http://localhost:10011"),
    "file_management": os.getenv("FILE_AGENT_URL", "http://localhost:10013"),
}

SYSTEM_PROMPT = """당신은 사용자 요청을 분석하고 적절한 에이전트에게 작업을 위임하는 Orchestrator입니다.

사용 가능한 에이전트:
- internal_rag: 사내 문서 검색(RAG), 문서 인덱싱/저장
- web_research: 외부 웹 검색, 최신 뉴스, 트렌드 정보
- file_management: Google Drive 파일 목록 조회, 검색

핵심 원칙:
1. 사용자의 원래 의도를 그대로 에이전트에게 전달하세요.
2. 에이전트가 스스로 판단할 수 있도록 자연어로 요청하세요.
3. 이전 에이전트 결과가 필요한 단계는 depends_on에 이전 step 인덱스를 설정하세요.
4. 독립적으로 실행 가능한 단계는 depends_on을 null로 설정하세요.

의도 분류 기준:
- INTERNAL_SEARCH: 사내 문서 검색
- WEB_SEARCH: 외부 웹 검색
- FILE_OPERATION: 파일 관리
- HYBRID: 둘 이상의 에이전트 필요
- DIRECT: 에이전트 없이 직접 답변 가능 (인사, 간단한 질문)
"""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def _send_with_retry(client, request):
    """A2A 메시지 전송 — 실패 시 최대 3회 재시도 (0.5s ~ 4s 지수 백오프)"""
    return await client.send_message(request)


class OrchestratorAgent:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 필요합니다")

        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.httpx_client = None
        self.remote_agents: Dict[str, A2AClient] = {}
        self.initialized = False

    async def initialize(self) -> None:
        if self.initialized:
            return
        self.httpx_client = httpx.AsyncClient(timeout=120.0)
        for name, url in AGENT_URLS.items():
            try:
                card_resolver = A2ACardResolver(httpx_client=self.httpx_client, base_url=url)
                agent_card = await card_resolver.get_agent_card()
                self.remote_agents[name] = A2AClient(httpx_client=self.httpx_client, agent_card=agent_card)
                logger.info(f"[ORCHESTRATOR] [INIT] {name} 연결 완료")
            except Exception as e:
                logger.error(f"[ORCHESTRATOR] [ERROR] {name} 연결 실패: {e}")
        self.initialized = True

    async def close(self) -> None:
        if self.httpx_client:
            await self.httpx_client.aclose()

    async def _call_agent(self, agent_name: str, query: str, step_index: int = 0) -> AgentResult:
        """단일 에이전트 호출 및 결과 반환"""
        start_ms = int(time.time() * 1000)

        if agent_name not in self.remote_agents:
            return AgentResult(
                agent=agent_name,
                success=False,
                content=f"에이전트 '{agent_name}'를 찾을 수 없습니다.",
                trace=TraceStep(step=step_index, agent=agent_name, status="failed", message="에이전트 없음")
            )

        try:
            client = self.remote_agents[agent_name]
            message = Message(
                kind="message",
                role="user",
                parts=[TextPart(kind="text", text=query)],
                message_id=uuid4().hex,
            )
            request = SendMessageRequest(id=uuid4().hex, params=MessageSendParams(message=message))
            response = await _send_with_retry(client, request)

            content = None
            result = response.root.result if hasattr(response, "root") else response.result
            if result and hasattr(result, "artifacts") and result.artifacts:
                for artifact in result.artifacts:
                    for part in artifact.parts:
                        if hasattr(part, "root") and hasattr(part.root, "text"):
                            content = part.root.text

            duration_ms = int(time.time() * 1000) - start_ms
            success = content is not None
            status = "completed" if success else "failed"

            return AgentResult(
                agent=agent_name,
                success=success,
                content=content,
                trace=TraceStep(step=step_index, agent=agent_name, status=status, message=f"{agent_name} 완료", duration_ms=duration_ms)
            )
        except Exception as e:
            duration_ms = int(time.time() * 1000) - start_ms
            return AgentResult(
                agent=agent_name,
                success=False,
                content=None,
                trace=TraceStep(step=step_index, agent=agent_name, status="failed", message=str(e), duration_ms=duration_ms)
            )

    async def execute_plan(self, plan: IntentPlan) -> List[AgentResult]:
        """
        Plan 실행 — 독립 단계는 병렬(asyncio.gather), 의존 단계는 순차

        depends_on=None  → asyncio.gather로 병렬 실행
        depends_on=N     → step N 완료 후 순차 실행
        """
        steps = plan.plan
        results: List[Optional[AgentResult]] = [None] * len(steps)

        independent = [i for i, s in enumerate(steps) if s.depends_on is None]
        dependent_map: Dict[int, List[int]] = {}
        for i, s in enumerate(steps):
            if s.depends_on is not None:
                dependent_map.setdefault(s.depends_on, []).append(i)

        # 독립 단계 병렬 실행
        if independent:
            tasks = [self._call_agent(steps[i].agent, steps[i].query, i) for i in independent]
            parallel_results = await asyncio.gather(*tasks)
            for i, result in zip(independent, parallel_results):
                results[i] = result

        # 의존 단계 순차 실행
        for dep_on, step_indices in dependent_map.items():
            prev_result = results[dep_on]
            for i in step_indices:
                step = steps[i]
                query = step.query
                if prev_result and prev_result.success and prev_result.content:
                    query = f"{query}\n\n[이전 에이전트 결과]:\n{prev_result.content[:2000]}"
                result = await self._call_agent(step.agent, query, i)
                results[i] = result
                prev_result = result

        return [r for r in results if r is not None]

    async def generate_final_response(self, query: str, results: List[AgentResult]) -> str:
        """에이전트 결과를 통합해 최종 답변 생성"""
        results_text = json.dumps(
            [{"agent": r.agent, "success": r.success, "content": r.content} for r in results],
            ensure_ascii=False,
            indent=2,
        )
        final_llm = ChatOpenAI(model="gpt-4o")
        messages = [
            {"role": "system", "content": "여러 에이전트의 결과를 통합하여 사용자에게 명확한 답변을 제공하세요."},
            {
                "role": "user",
                "content": f"원본 질문: {query}\n\n에이전트 결과:\n{results_text}\n\n위 정보를 바탕으로 답변해주세요.",
            },
        ]
        response = await final_llm.ainvoke(messages)
        return response.content

    async def analyze_intent(self, query: str) -> IntentPlan:
        """Pydantic structured output으로 Intent 분류"""
        structured_llm = self.llm.with_structured_output(IntentPlan)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]
        return structured_llm.invoke(messages)

    async def stream(self, query: str, session_id: str = "default") -> AsyncIterator[Dict[str, Any]]:
        """스트리밍 처리 — TraceStep 포함 (F-017)"""
        if not self.initialized:
            await self.initialize()

        trace: List[Dict] = []

        yield {"is_task_complete": False, "require_user_input": False, "content": "🤔 질문을 분석하고 있습니다...", "trace": trace}

        try:
            plan = await self.analyze_intent(query)
            logger.info(f"[ORCHESTRATOR] Intent: {plan.intent}, Plan steps: {len(plan.plan)}")
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Intent 분석 실패: {e}")
            yield {"is_task_complete": True, "require_user_input": False, "content": f"분석 중 오류가 발생했습니다: {str(e)}", "trace": trace}
            return

        if plan.intent == "DIRECT" and plan.direct_answer:
            trace.append(TraceStep(step=0, agent="orchestrator", status="completed", message="직접 답변").model_dump())
            yield {"is_task_complete": True, "require_user_input": False, "content": plan.direct_answer, "trace": trace}
            return

        if not plan.plan:
            yield {"is_task_complete": True, "require_user_input": False, "content": "처리할 작업이 없습니다.", "trace": trace}
            return

        yield {"is_task_complete": False, "require_user_input": False, "content": f"📋 {len(plan.plan)}개 에이전트에 요청 중...", "trace": trace}

        results = await self.execute_plan(plan)

        for r in results:
            trace.append(r.trace.model_dump())

        yield {"is_task_complete": False, "require_user_input": False, "content": "📝 결과를 정리하고 있습니다...", "trace": trace}

        final_response = await self.generate_final_response(query, results)

        yield {"is_task_complete": True, "require_user_input": False, "content": final_response, "trace": trace}
