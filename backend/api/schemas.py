from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from common.contracts import (
    ArtifactEnvelope,
    ChatRequestContract,
    ChatResponseContract,
    FileArtifactContract,
    PlanStepContract,
    ProgressItemContract,
    RunStatus,
    SourceContract,
)


# ── 요청 ──────────────────────────────────────────

class ChatRequest(ChatRequestContract):
    pass


# ── 응답 ──────────────────────────────────────────

class ChatResponse(ChatResponseContract):
    run_id: str = ""
    status: RunStatus = "completed"
    plan: list[PlanStepContract] = Field(default_factory=list)
    progress: list[ProgressItemContract] = Field(default_factory=list)
    sources: list[SourceContract] = Field(default_factory=list)
    files: list[FileArtifactContract] = Field(default_factory=list)
    artifacts: list[ArtifactEnvelope] = Field(default_factory=list)
    error: Optional[str] = None


class MessageOut(BaseModel):
    id: str
    session_id: str
    role: str          # 'user' | 'assistant'
    content: str
    created_at: datetime


class SessionOut(BaseModel):
    id: str
    title: Optional[str]
    created_at: datetime
