"""
FastAPI 백엔드 게이트웨이 (통합)

A2A 오케스트레이터 에이전트와 REST API로 통신하는 통합 백엔드 서버입니다.
채팅 히스토리(Supabase), 파일 업로드/인덱싱, 세션 관리 포함.

실행 (프로젝트 루트에서):
    python -m uvicorn backend.main:app --reload --port 8000
"""

import os
import sys
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

# uvicorn --reload 가 subprocess를 spawn할 때 sys.path가 달라지는 문제 방지
# 항상 project root를 sys.path 맨 앞에 보장
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from a2a.client import A2ACardResolver
from common.capabilities import list_capabilities
from common.contracts import CapabilityDescriptor

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[BACKEND] FastAPI 게이트웨이 시작")
    yield
    # 채팅 라우터 A2A 클라이언트 종료
    from backend.api.routers.chat import _a2a_client as _chat_a2a
    if _chat_a2a:
        await _chat_a2a.close()
    logger.info("[BACKEND] FastAPI 게이트웨이 종료")


app = FastAPI(
    title="Multi-Agent System API",
    description="A2A 오케스트레이터 기반 멀티 에이전트 시스템 REST API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vue dev server
        "http://localhost:3000",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 확장 라우터 (세션, 파일, SSE 채팅) ────────────────
from backend.api.routers import chat as _chat, sessions as _sessions, files as _files

app.include_router(_chat.router, prefix="/api", tags=["chat"])
app.include_router(_sessions.router, prefix="/api", tags=["sessions"])
app.include_router(_files.router, prefix="/api", tags=["files"])


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


@app.get("/api/report-templates", response_model=List[ReportTemplateInfo])
async def list_report_templates():
    """사용 가능한 보고서 양식 목록"""
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root / "ai_llm" / "report_writing_agent"))

    from templates import list_templates

    return list_templates()


@app.get("/api/capabilities", response_model=list[CapabilityDescriptor])
async def capabilities():
    """에이전트 기능과 현재 UI 지원 상태 목록"""
    return list_capabilities()


@app.get("/")
async def root():
    return {
        "service": "Morning Agent Hub API",
        "docs": "/docs",
        "endpoints": {
            "health": "GET /api/health",
            "chat": "POST /api/chat",
            "chat_stream": "GET /api/chat/stream",
            "sessions": "GET /api/sessions",
            "session_messages": "GET /api/sessions/{id}/messages",
            "files_upload": "POST /api/files/upload",
            "files_list": "GET /api/files",
            "report_templates": "GET /api/report-templates",
            "capabilities": "GET /api/capabilities",
        },
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
        "backend.main:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()
