"""
FastAPI 백엔드 게이트웨이

A2A 오케스트레이터 에이전트와 REST API로 통신하는 통합 백엔드 서버입니다.
프론트엔드 또는 외부 클라이언트에서 HTTP로 멀티 에이전트 시스템을 사용할 수 있습니다.

실행:
    cd backend
    python main.py

또는:
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from a2a.client import A2AClient, A2ACardResolver
from a2a.types import Message, MessageSendParams, SendMessageRequest, TextPart

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:10010")

AGENT_HEALTH_URLS = {
    "orchestrator": ORCHESTRATOR_URL,
    "web_research": os.getenv("WEB_AGENT_URL", "http://localhost:10011"),
    "internal_rag": os.getenv("RAG_AGENT_URL", "http://localhost:10012"),
    "file_management": os.getenv("FILE_AGENT_URL", "http://localhost:10013"),
    "report_writing": os.getenv("REPORT_AGENT_URL", "http://localhost:10014"),
}


class ChatRequest(BaseModel):
    query: str = Field(..., description="사용자 질문 또는 작업 요청")
    session_id: str = Field(default="default", description="세션 ID")


class ChatResponse(BaseModel):
    success: bool
    response: str
    session_id: str


class AgentStatus(BaseModel):
    name: str
    url: str
    online: bool
    agent_name: Optional[str] = None
    description: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    orchestrator_url: str
    agents: List[AgentStatus]


class ReportTemplateInfo(BaseModel):
    id: str
    name: str
    description: str
    section_count: int


_a2a_client: Optional[A2AClient] = None
_httpx_client: Optional[httpx.AsyncClient] = None


async def get_a2a_client() -> A2AClient:
    global _a2a_client, _httpx_client

    if _a2a_client is None:
        _httpx_client = httpx.AsyncClient(timeout=600.0)
        card_resolver = A2ACardResolver(
            httpx_client=_httpx_client,
            base_url=ORCHESTRATOR_URL,
        )
        agent_card = await card_resolver.get_agent_card()
        _a2a_client = A2AClient(
            httpx_client=_httpx_client,
            agent_card=agent_card,
        )
        logger.info(f"[BACKEND] 오케스트레이터 연결: {agent_card.name}")

    return _a2a_client


def extract_response_text(result: Any) -> str:
    """A2A Task 결과에서 텍스트 추출"""
    if not result:
        return ""

    if hasattr(result, "artifacts") and result.artifacts:
        for artifact in result.artifacts:
            if artifact.parts:
                for part in artifact.parts:
                    if hasattr(part, "root") and hasattr(part.root, "text"):
                        return part.root.text

    if hasattr(result, "history") and result.history:
        for msg in reversed(result.history):
            if hasattr(msg, "role") and "agent" in str(msg.role):
                for part in msg.parts:
                    if hasattr(part, "root") and hasattr(part.root, "text"):
                        return part.root.text

    return ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await get_a2a_client()
    except Exception as e:
        logger.warning(f"[BACKEND] 오케스트레이터 초기 연결 실패 (시작 후 재시도 가능): {e}")
    yield
    global _httpx_client
    if _httpx_client:
        await _httpx_client.aclose()


app = FastAPI(
    title="Multi-Agent System API",
    description="A2A 오케스트레이터 기반 멀티 에이전트 시스템 REST API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """시스템 및 에이전트 상태 확인"""
    agents: List[AgentStatus] = []

    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in AGENT_HEALTH_URLS.items():
            status = AgentStatus(name=name, url=url, online=False)
            try:
                resolver = A2ACardResolver(httpx_client=client, base_url=url)
                card = await resolver.get_agent_card()
                status.online = True
                status.agent_name = card.name
                status.description = card.description
            except Exception:
                pass
            agents.append(status)

    all_online = all(a.online for a in agents)
    return HealthResponse(
        status="healthy" if all_online else "degraded",
        orchestrator_url=ORCHESTRATOR_URL,
        agents=agents,
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """오케스트레이터에 질문을 전달하고 응답을 받습니다"""
    try:
        client = await get_a2a_client()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"오케스트레이터에 연결할 수 없습니다: {e}. "
                   f"에이전트 서버가 실행 중인지 확인하세요 ({ORCHESTRATOR_URL})",
        )

    message = Message(
        kind="message",
        role="user",
        parts=[TextPart(kind="text", text=request.query)],
        message_id=uuid4().hex,
    )

    a2a_request = SendMessageRequest(
        id=uuid4().hex,
        params=MessageSendParams(message=message),
    )

    try:
        response = await client.send_message(a2a_request)
        result = response.root.result if hasattr(response, "root") else response.result
        response_text = extract_response_text(result)

        if not response_text:
            return ChatResponse(
                success=False,
                response="응답을 받지 못했습니다.",
                session_id=request.session_id,
            )

        return ChatResponse(
            success=True,
            response=response_text,
            session_id=request.session_id,
        )

    except Exception as e:
        logger.error(f"[BACKEND] A2A 호출 실패: {e}")
        raise HTTPException(status_code=500, detail=f"에이전트 호출 실패: {str(e)}")


@app.get("/api/report-templates", response_model=List[ReportTemplateInfo])
async def list_report_templates():
    """사용 가능한 보고서 양식 목록"""
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root / "report_writing_agent"))

    from templates import list_templates

    return list_templates()


@app.get("/")
async def root():
    return {
        "service": "Multi-Agent System API",
        "docs": "/docs",
        "health": "/api/health",
        "chat": "POST /api/chat",
        "report_templates": "GET /api/report-templates",
    }


def main():
    import uvicorn

    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "8000"))

    logger.info("=" * 60)
    logger.info("[BACKEND] FastAPI 게이트웨이 시작")
    logger.info(f"[BACKEND] http://{host}:{port}")
    logger.info(f"[BACKEND] API 문서: http://{host}:{port}/docs")
    logger.info(f"[BACKEND] 오케스트레이터: {ORCHESTRATOR_URL}")
    logger.info("=" * 60)

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()
