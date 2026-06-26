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
from a2a.types import MessageSendParams, SendMessageRequest, TextPart, Message
from uuid import uuid4
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

try:
    from .models import IntentPlan, PlanStep, TraceStep, AgentResult
    from .report_context_builder import build_report_query
    from .plan_normalizer import normalize_plan
except ImportError:
    from models import IntentPlan, PlanStep, TraceStep, AgentResult
    from report_context_builder import build_report_query
    from plan_normalizer import normalize_plan

logger = logging.getLogger(__name__)
load_dotenv()

AGENT_URLS = {
    "internal_rag": os.getenv("RAG_AGENT_URL", "http://localhost:10012"),
    "web_research": os.getenv("WEB_AGENT_URL", "http://localhost:10011"),
    "file_management": os.getenv("FILE_AGENT_URL", "http://localhost:10013"),
    "report_writing": os.getenv("REPORT_AGENT_URL", "http://localhost:10014"),
}

SYSTEM_PROMPT = """당신은 사용자 요청을 분석하고 적절한 에이전트에게 작업을 위임하는 Orchestrator입니다.

사용 가능한 에이전트:
- internal_rag: 사내 문서 검색(RAG), 문서 인덱싱/저장 (storage_ref로 파일 직접 다운로드 후 인덱싱)
- web_research: 외부 웹 검색, 최신 뉴스, 트렌드 정보
- file_management: Google Drive 파일 목록 조회, 검색, 업로드 (파일 관리 전문)
- report_writing: 보고서 작성 전문 (조사/임원/기술/회의록 등 양식에 맞춰 마크다운 보고서 생성)

핵심 원칙:
1. 사용자의 원래 의도를 그대로 에이전트에게 전달하세요.
2. 에이전트가 스스로 판단할 수 있도록 자연어로 요청하세요.
3. 이전 에이전트 결과가 필요한 단계는 depends_on에 이전 step 인덱스를 설정하세요.
4. 독립적으로 실행 가능한 단계는 depends_on을 null로 설정하세요.
5. "하나만", "전부", "3개" 같은 조건도 그대로 전달하세요.

의도 분류 기준:
- INTERNAL_SEARCH: 사내 문서 검색
- WEB_SEARCH: 외부 웹 검색
- FILE_OPERATION: 파일 관리
- HYBRID: 둘 이상의 에이전트 필요
- DIRECT: 에이전트 없이 직접 답변 가능 (인사, 간단한 질문)

=== 파일 인덱싱 워크플로우 (2단계) ===
사용자: "보고서 폴더 파일 중 하나만 DB에 인덱싱해줘"
→ plan: [
    {"agent": "file_management", "query": "보고서 폴더의 파일 목록을 검색해줘", "depends_on": null},
    {"agent": "internal_rag", "query": "다음 파일들 중 하나만 인덱싱해줘", "depends_on": 0}
  ]

=== 보고서 작성 워크플로우 ===
사용자: "AI 트렌드를 조사해서 조사 보고서 형식으로 정리해줘"
→ plan: [
    {"agent": "web_research", "query": "2026년 AI 에이전트 트렌드를 조사해줘", "depends_on": null},
    {"agent": "report_writing", "query": "조사 결과를 research_report 양식의 조사 보고서로 작성해줘", "depends_on": 0}
  ]

report_writing 호출 시 Orchestrator가 upstream 결과를 [REPORT_CONTEXT] JSON으로 전달합니다.
- file_management가 읽은 **양식 파일 전문** → format_example (LLM이 형식 그대로 따라 작성)
- web_research 조사 결과 → content (본문에 쓸 내용)
plan의 query에는 보고서 주제(예: SQL)만 명확히 적으세요.

사용자: "웹 조사 후 보고서 작성하고 Drive에 저장해줘"
→ plan: [
    {"agent": "web_research", "query": "[주제]를 조사해줘", "depends_on": null},
    {"agent": "report_writing", "query": "조사 결과를 research_report 양식 보고서로 작성해줘", "depends_on": 0},
    {"agent": "file_management", "query": "작성된 보고서를 Google Drive에 .md 파일로 저장해줘", "depends_on": 1}
  ]

report_writing 양식 종류:
- executive_summary: 임원 요약 보고서
- research_report: 조사 보고서 (기본)
- technical_report: 기술 보고서
- meeting_minutes: 회의록
- general: 일반 보고서

=== 드라이브 파일 양식 + 주제 보고서 워크플로우 (중요) ===
사용자가 특정 파일(예: test.txt)을 "양식/형식 참고"로 언급하고 별도 주제(예: SQL) 보고서를 요청하면:
- 참고 파일 = **구조·양식만** (본문 내용·주제로 사용 금지)
- 보고서 **주제** = 사용자가 명시한 주제 (예: SQL) — 반드시 web_research로 조사

사용자: "드라이브 test.txt 양식 참고해서 SQL 보고서 작성하고 저장해줘"
→ plan: [
    {"agent": "file_management", "query": "test.txt 파일을 찾아 내용을 조회해줘 (보고서 양식 참고용)", "depends_on": null},
    {"agent": "web_research", "query": "SQL(Structured Query Language) 핵심 개념, 특징, 활용 사례를 조사해줘", "depends_on": null},
    {"agent": "report_writing", "query": "보고서 주제: SQL. test.txt 문서 구조·양식만 따르고 본문은 web_research 조사 결과 사용. technical_report 형식으로 작성", "depends_on": 1},
    {"agent": "file_management", "query": "작성된 SQL 보고서를 Google Drive에 .md 파일로 저장해줘", "depends_on": 2}
  ]

report_writing은 반드시 upstream(web_research, file_management 등) step 완료 **후** 실행되어야 합니다.
depends_on을 null로 두면 병렬 실행되어 ReportContext sources=0 이 됩니다 — 마지막 upstream step 인덱스를 depends_on에 설정하세요.

주의: internal_rag는 사내 문서 **검색**용입니다. Drive 파일 양식 참고는 file_management로 파일 내용을 조회하세요.
양식 참고 요청에 web_research(주제 조사) 단계를 빠뜨리지 마세요.
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
                logger.info(f"[ORCHESTRATOR] [INIT] {name} 연결 완료: {agent_card.name}")
            except Exception as e:
                logger.error(f"[ORCHESTRATOR] [ERROR] {name} 연결 실패 ({url}): {e}")
        self.initialized = True
        logger.info(f"[ORCHESTRATOR] [INIT] 초기화 완료 (연결된 에이전트: {len(self.remote_agents)}개)")

    async def close(self) -> None:
        if self.httpx_client:
            await self.httpx_client.aclose()

    def _extract_response(self, result) -> tuple[Optional[str], List[Dict[str, Any]]]:
        """A2A 응답에서 텍스트와 artifacts 추출"""
        content = None
        artifacts: List[Dict[str, Any]] = []

        if not result:
            return content, artifacts

        PRIMARY_ARTIFACTS = ("web_search_result", "report_result", "orchestrator_result", "file_operation_result")
        SKIP_AS_PRIMARY = ("web_search_sources", "execution_trace", "file_content", "file_list")

        if hasattr(result, "artifacts") and result.artifacts:
            for artifact in result.artifacts:
                artifact_data: Dict[str, Any] = {"name": artifact.name}
                for part in artifact.parts:
                    if hasattr(part, "root"):
                        part_root = part.root
                        if hasattr(part_root, "text"):
                            artifact_data["text"] = part_root.text
                        elif hasattr(part_root, "data"):
                            artifact_data["data"] = part_root.data
                artifacts.append(artifact_data)

            for preferred in PRIMARY_ARTIFACTS:
                for artifact_data in artifacts:
                    if artifact_data.get("name") == preferred and artifact_data.get("text"):
                        content = artifact_data["text"]
                        break
                if content:
                    break

            if not content:
                for artifact_data in reversed(artifacts):
                    if artifact_data.get("name") in SKIP_AS_PRIMARY:
                        continue
                    if artifact_data.get("text"):
                        content = artifact_data["text"]
                        break

            for artifact_data in artifacts:
                if artifact_data.get("name") != "file_content":
                    continue
                data = artifact_data.get("data")
                if isinstance(data, dict) and data.get("content"):
                    filename = data.get("filename", "file")
                    file_body = data["content"]
                    if content:
                        content = f"[파일: {filename}]\n{file_body}\n\n{content}"
                    else:
                        content = f"[파일: {filename}]\n{file_body}"
                    break

        if not content and hasattr(result, "history") and result.history:
            for msg in reversed(result.history):
                if hasattr(msg, "role") and "agent" in str(msg.role):
                    for part in msg.parts:
                        if hasattr(part, "root") and hasattr(part.root, "text"):
                            content = part.root.text
                            break
                if content:
                    break

        return content, artifacts

    def _format_prev_content(self, prev_result: AgentResult, next_agent: str) -> str:
        """다음 단계에 전달할 이전 에이전트 결과 포맷"""
        if not prev_result or not prev_result.success:
            return ""

        parts: List[str] = []
        summary = prev_result.content or ""

        if prev_result.agent == "web_research":
            for artifact in prev_result.artifacts:
                name = artifact.get("name")
                text = artifact.get("text", "")
                if name == "web_search_result" and text:
                    summary = text
                elif name == "web_search_sources" and text and text not in summary:
                    try:
                        sources = json.loads(text)
                        if isinstance(sources, list):
                            source_lines = [
                                f"- {s.get('title', '')} ({s.get('url', '')})"
                                for s in sources
                                if isinstance(s, dict)
                            ]
                            if source_lines:
                                parts.append("출처:\n" + "\n".join(source_lines))
                    except json.JSONDecodeError:
                        parts.append(f"출처:\n{text}")

        if summary:
            parts.insert(0, summary)

        combined = "\n\n".join(p for p in parts if p)
        limit = 8000 if next_agent == "report_writing" else 2000
        return combined[:limit]

    async def _call_agent(self, agent_name: str, query: str, step_index: int = 0) -> AgentResult:
        """단일 에이전트 호출 및 결과 반환"""
        start_ms = int(time.time() * 1000)

        if agent_name not in self.remote_agents:
            return AgentResult(
                agent=agent_name,
                success=False,
                content=f"에이전트 '{agent_name}'를 찾을 수 없습니다.",
                trace=TraceStep(step=step_index, agent=agent_name, status="failed", message="에이전트 없음"),
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

            result = response.root.result if hasattr(response, "root") else response.result
            content, artifacts = self._extract_response(result)

            duration_ms = int(time.time() * 1000) - start_ms
            success = content is not None
            status = "completed" if success else "failed"

            return AgentResult(
                agent=agent_name,
                success=success,
                content=content,
                artifacts=artifacts,
                trace=TraceStep(
                    step=step_index,
                    agent=agent_name,
                    status=status,
                    message=f"{agent_name} 완료",
                    duration_ms=duration_ms,
                ),
            )
        except Exception as e:
            duration_ms = int(time.time() * 1000) - start_ms
            return AgentResult(
                agent=agent_name,
                success=False,
                content=None,
                trace=TraceStep(
                    step=step_index,
                    agent=agent_name,
                    status="failed",
                    message=str(e),
                    duration_ms=duration_ms,
                ),
            )

    def _build_step_query(
        self,
        step: PlanStep,
        step_index: int,
        prev_result: Optional[AgentResult],
        results: List[Optional[AgentResult]],
        file_list: List[Dict[str, Any]],
        report_metadata: Dict[str, Any],
        user_query: str = "",
    ) -> str:
        """에이전트 간 컨텍스트를 포함한 쿼리 생성"""
        if step.agent == "report_writing":
            query = build_report_query(step, step_index, results, user_query=user_query)
            upstream_count = len([
                r for r in results[:step_index]
                if r and r.success and (r.content or r.artifacts)
            ])
            logger.info(
                f"[ORCHESTRATOR] ReportContext 전달: {upstream_count}개 upstream 소스"
            )
            if upstream_count == 0:
                logger.warning(
                    "[ORCHESTRATOR] ReportContext upstream 비어 있음 — "
                    "report_writing depends_on 또는 실행 순서 확인"
                )
            return query

        query = step.query

        if step.agent == "internal_rag" and file_list:
            files_text = "\n".join(
                f"- {f.get('filename', f.get('name', 'unknown'))} ({f.get('storage_ref', '')})"
                for f in file_list
            )
            query = f"{query}\n\n사용 가능한 파일 목록:\n{files_text}"
        elif step.agent == "file_management" and report_metadata and prev_result and prev_result.content:
            filename = report_metadata.get("filename_suggestion", "report.md")
            title = report_metadata.get("title", "보고서")
            query = (
                f"{query}\n\n"
                f"저장할 파일명: {filename}\n"
                f"보고서 제목: {title}\n"
                f"아래 보고서 내용을 Google Drive에 업로드해주세요:\n\n"
                f"{prev_result.content[:8000]}"
            )
        elif prev_result and prev_result.success and prev_result.content and step.depends_on is not None:
            prev_content = self._format_prev_content(prev_result, step.agent)
            if "[이전 결과]" in query or "[검색 결과]" in query:
                query = query.replace("[이전 결과]", prev_content)
                query = query.replace("[검색 결과]", prev_content)
            else:
                query = f"{query}\n\n[이전 에이전트 결과]:\n{prev_content}"

        return query

    def _update_artifact_context(
        self,
        result: AgentResult,
        file_list: List[Dict[str, Any]],
        report_metadata: Dict[str, Any],
    ) -> None:
        """에이전트 결과에서 다음 단계용 컨텍스트 추출"""
        if result.agent == "file_management" and result.success:
            for artifact in result.artifacts:
                artifact_data = artifact.get("data")
                if artifact.get("name") == "file_list" and isinstance(artifact_data, dict):
                    files = artifact_data.get("files", [])
                    if files:
                        file_list.extend(files)

        if result.agent == "report_writing" and result.success:
            for artifact in result.artifacts:
                if artifact.get("name") == "report_document":
                    artifact_data = artifact.get("data")
                    if isinstance(artifact_data, dict):
                        report_metadata.clear()
                        report_metadata.update(artifact_data)

    async def execute_plan(self, plan: IntentPlan, user_query: str = "") -> List[AgentResult]:
        """
        Plan 실행 — 독립 단계는 병렬(asyncio.gather), 의존 단계는 순차

        depends_on=None  → asyncio.gather로 병렬 실행
        depends_on=N     → step N 완료 후 순차 실행
        """
        steps = normalize_plan(plan.plan)
        if len(steps) != len(plan.plan) or any(
            a.depends_on != b.depends_on for a, b in zip(steps, plan.plan)
        ):
            logger.info("[ORCHESTRATOR] Plan depends_on 자동 보정 적용")
        results: List[Optional[AgentResult]] = [None] * len(steps)
        file_list: List[Dict[str, Any]] = []
        report_metadata: Dict[str, Any] = {}
        previous_step_failed = False

        independent = [i for i, s in enumerate(steps) if s.depends_on is None]
        dependent_map: Dict[int, List[int]] = {}
        for i, s in enumerate(steps):
            if s.depends_on is not None:
                dependent_map.setdefault(s.depends_on, []).append(i)

        async def run_step(i: int) -> AgentResult:
            nonlocal previous_step_failed
            if previous_step_failed:
                return AgentResult(
                    agent=steps[i].agent,
                    success=False,
                    content="이전 단계 실패로 스킵됨",
                    trace=TraceStep(
                        step=i,
                        agent=steps[i].agent,
                        status="skipped",
                        message="이전 단계 실패로 스킵됨",
                    ),
                )

            dep_idx = steps[i].depends_on
            prev_result = results[dep_idx] if dep_idx is not None and results[dep_idx] else None
            query = self._build_step_query(
                steps[i], i, prev_result, results, file_list, report_metadata, user_query
            )
            result = await self._call_agent(steps[i].agent, query, i)

            if not result.success:
                previous_step_failed = True
            else:
                self._update_artifact_context(result, file_list, report_metadata)

            return result

        if independent:
            parallel_results = await asyncio.gather(*[run_step(i) for i in independent])
            for i, result in zip(independent, parallel_results):
                results[i] = result

        for dep_on in sorted(dependent_map.keys()):
            if results[dep_on] and not results[dep_on].success:
                previous_step_failed = True
            for i in dependent_map[dep_on]:
                results[i] = await run_step(i)

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

        yield {
            "is_task_complete": False,
            "require_user_input": False,
            "content": "🤔 질문을 분석하고 있습니다...",
            "trace": trace,
        }

        try:
            plan = await self.analyze_intent(query)
            logger.info(f"[ORCHESTRATOR] Intent: {plan.intent}, Plan steps: {len(plan.plan)}")
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Intent 분석 실패: {e}")
            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": f"분석 중 오류가 발생했습니다: {str(e)}",
                "trace": trace,
            }
            return

        if plan.intent == "DIRECT" and plan.direct_answer:
            trace.append(
                TraceStep(step=0, agent="orchestrator", status="completed", message="직접 답변").model_dump()
            )
            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": plan.direct_answer,
                "trace": trace,
            }
            return

        if not plan.plan:
            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": "처리할 작업이 없습니다.",
                "trace": trace,
            }
            return

        yield {
            "is_task_complete": False,
            "require_user_input": False,
            "content": f"📋 {len(plan.plan)}개 에이전트에 요청 중...",
            "trace": trace,
        }

        results = await self.execute_plan(plan, user_query=query)
        all_artifacts: List[Dict[str, Any]] = []

        for r in results:
            trace.append(r.trace.model_dump())
            all_artifacts.extend(r.artifacts)

        yield {
            "is_task_complete": False,
            "require_user_input": False,
            "content": "📝 결과를 정리하고 있습니다...",
            "trace": trace,
        }

        last_agent = plan.plan[-1].agent if plan.plan else None
        last_result = results[-1] if results else None

        if last_agent == "report_writing" and last_result and last_result.success:
            report_result = next(
                (r for r in reversed(results) if r.agent == "report_writing" and r.success),
                None,
            )
            final_response = report_result.content if report_result else "보고서를 생성하지 못했습니다."
        else:
            final_response = await self.generate_final_response(query, results)

        yield {
            "is_task_complete": True,
            "require_user_input": False,
            "content": final_response,
            "trace": trace,
            "artifacts": all_artifacts,
        }
