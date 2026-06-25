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

    async def analyze_intent(self, query: str) -> IntentPlan:
        """Pydantic structured output으로 Intent 분류"""
        structured_llm = self.llm.with_structured_output(IntentPlan)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]
        return structured_llm.invoke(messages)

    async def stream(self, query: str, session_id: str = "default") -> AsyncIterator[Dict[str, Any]]:
        """스트리밍 처리 (Task 3~5에서 순차 확장 예정)"""
        if not self.initialized:
            await self.initialize()

        yield {"is_task_complete": False, "require_user_input": False, "content": "🤔 질문을 분석하고 있습니다...", "trace": []}

        try:
            plan = await self.analyze_intent(query)
            logger.info(f"[ORCHESTRATOR] Intent: {plan.intent}, Plan steps: {len(plan.plan)}")
        except Exception as e:
            yield {"is_task_complete": True, "require_user_input": False, "content": f"분석 중 오류: {str(e)}", "trace": []}
            return

        if plan.intent == "DIRECT" and plan.direct_answer:
            yield {"is_task_complete": True, "require_user_input": False, "content": plan.direct_answer, "trace": []}
            return

        yield {"is_task_complete": True, "require_user_input": False, "content": f"[Plan] intent={plan.intent}, steps={len(plan.plan)}", "trace": []}
