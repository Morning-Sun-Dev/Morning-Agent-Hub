import json
import sys
import os
from uuid import uuid4
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

# common 패키지 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from common.a2a_client import A2AClientWrapper
from common.config import get_agent_urls
from backend.api.db import get_supabase
from backend.api.schemas import ChatRequest, ChatResponse

router = APIRouter()

# A2A 클라이언트 (앱 시작 시 초기화)
_a2a_client: A2AClientWrapper = None


async def get_a2a_client() -> A2AClientWrapper:
    global _a2a_client
    if _a2a_client is None:
        _a2a_client = A2AClientWrapper(timeout=120.0)
        await _a2a_client.initialize({"orchestrator": "http://localhost:10010"})
    return _a2a_client


# ── 대화 기록 헬퍼 ─────────────────────────────────

def _load_history(session_id: str, limit: int = 10) -> str:
    """최근 N개 메시지를 텍스트로 반환"""
    sb = get_supabase()
    rows = (
        sb.table("chat_messages")
        .select("role, content")
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )
    rows.reverse()  # 오래된 순으로
    if not rows:
        return ""
    lines = [
        f"{'사용자' if r['role'] == 'user' else '어시스턴트'}: {r['content']}"
        for r in rows
    ]
    return "\n".join(lines)


def _save_message(session_id: str, role: str, content: str) -> None:
    sb = get_supabase()
    sb.table("chat_messages").insert({
        "id": uuid4().hex,
        "session_id": session_id,
        "role": role,
        "content": content,
    }).execute()


def _ensure_session(session_id: str | None, first_message: str) -> str:
    """세션이 없으면 새로 생성, 있으면 그대로 반환"""
    sb = get_supabase()
    if session_id:
        return session_id

    new_id = uuid4().hex
    title = first_message[:40]  # 첫 메시지 앞 40자를 제목으로
    sb.table("chat_sessions").insert({
        "id": new_id,
        "title": title,
    }).execute()
    return new_id


# ── 엔드포인트 ─────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """일반 요청/응답"""
    session_id = _ensure_session(req.session_id, req.message)

    # 이전 대화 불러오기
    history = _load_history(session_id)
    prompt = f"[이전 대화]\n{history}\n\n[현재 질문]\n{req.message}" if history else req.message

    # user 메시지 저장
    _save_message(session_id, "user", req.message)

    try:
        client = await get_a2a_client()
        response = await client.send_message("orchestrator", prompt)

        if not response.success:
            raise HTTPException(status_code=500, detail=response.error)

        answer = ""
        if response.artifacts:
            answer = response.artifacts[0].get("text", "")

        # assistant 메시지 저장
        _save_message(session_id, "assistant", answer)

        return ChatResponse(answer=answer, session_id=session_id)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/stream")
async def chat_stream(message: str, session_id: str | None = None):
    """SSE — A2A blocking send_message 결과를 스트리밍으로 반환"""
    resolved_session_id = _ensure_session(session_id, message)
    history = _load_history(resolved_session_id)
    prompt = f"[이전 대화]\n{history}\n\n[현재 질문]\n{message}" if history else message

    _save_message(resolved_session_id, "user", message)

    async def generate() -> AsyncIterator[str]:
        try:
            client = await get_a2a_client()

            # 처리 중 상태 전송
            yield f"data: {json.dumps({'type': 'status', 'state': 'working'})}\n\n"

            response = await client.send_message("orchestrator", prompt)

            if not response.success:
                yield f"data: {json.dumps({'type': 'error', 'content': response.error})}\n\n"
                yield "data: [DONE]\n\n"
                return

            answer = ""
            if response.artifacts:
                answer = response.artifacts[0].get("text", "")

            _save_message(resolved_session_id, "assistant", answer)

            yield f"data: {json.dumps({'type': 'answer', 'content': answer, 'session_id': resolved_session_id})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
