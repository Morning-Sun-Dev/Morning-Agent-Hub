from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ── 요청 ──────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None   # 없으면 새 세션 생성


# ── 응답 ──────────────────────────────────────────

class ChatResponse(BaseModel):
    answer: str
    session_id: str


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
