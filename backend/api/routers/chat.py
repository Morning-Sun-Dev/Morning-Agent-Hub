import asyncio
import json
import sys
import os
from uuid import uuid4
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from common.a2a_client import A2AClientWrapper
from backend.api.db import get_supabase_service as get_supabase
from backend.api.schemas import ChatRequest, ChatResponse

router = APIRouter()

_a2a_client: A2AClientWrapper = None


async def get_a2a_client() -> A2AClientWrapper:
    global _a2a_client
    if _a2a_client is None:
        _a2a_client = A2AClientWrapper(timeout=120.0)
        await _a2a_client.initialize({"orchestrator": "http://localhost:10010"})
    return _a2a_client


# ── Supabase 헬퍼 (동기) ───────────────────────────

def _ensure_session_sync(session_id: str | None, first_message: str) -> str:
    if session_id:
        return session_id
    sb = get_supabase()
    new_id = uuid4().hex
    sb.table("chat_sessions").insert({
        "id": new_id,
        "title": first_message[:40],
    }).execute()
    return new_id


def _load_history_sync(session_id: str, limit: int = 10) -> str:
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
    rows.reverse()
    if not rows:
        return ""
    return "\n".join([
        f"{'사용자' if r['role'] == 'user' else '어시스턴트'}: {r['content']}"
        for r in rows
    ])


def _save_message_sync(session_id: str, role: str, content: str) -> None:
    sb = get_supabase()
    sb.table("chat_messages").insert({
        "id": uuid4().hex,
        "session_id": session_id,
        "role": role,
        "content": content,
    }).execute()


# ── 비동기 래퍼 ────────────────────────────────────

async def _ensure_session(session_id, message):
    return await asyncio.to_thread(_ensure_session_sync, session_id, message)

async def _load_history(session_id):
    return await asyncio.to_thread(_load_history_sync, session_id)

async def _save_message(session_id, role, content):
    await asyncio.to_thread(_save_message_sync, session_id, role, content)


# ── 엔드포인트 ─────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    session_id = await _ensure_session(req.session_id, req.message)
    history = await _load_history(session_id)
    prompt = f"[이전 대화]\n{history}\n\n[현재 질문]\n{req.message}" if history else req.message

    await _save_message(session_id, "user", req.message)

    try:
        client = await get_a2a_client()
        response = await client.send_message("orchestrator", prompt)

        if not response.success:
            raise HTTPException(status_code=500, detail=response.error)

        answer = response.artifacts[0].get("text", "") if response.artifacts else ""
        await _save_message(session_id, "assistant", answer)

        return ChatResponse(answer=answer, session_id=session_id)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/stream")
async def chat_stream(message: str, session_id: str | None = None):
    """SSE 스트리밍"""

    async def generate() -> AsyncIterator[str]:
        try:
            # Supabase 작업을 스레드에서 실행
            resolved_id = await _ensure_session(session_id, message)
            history = await _load_history(resolved_id)
            prompt = f"[이전 대화]\n{history}\n\n[현재 질문]\n{message}" if history else message

            await _save_message(resolved_id, "user", message)

            yield f"data: {json.dumps({'type': 'status', 'state': 'working'})}\n\n"

            client = await get_a2a_client()
            response = await client.send_message("orchestrator", prompt)

            if not response.success:
                yield f"data: {json.dumps({'type': 'error', 'content': response.error})}\n\n"
                yield "data: [DONE]\n\n"
                return

            answer = response.artifacts[0].get("text", "") if response.artifacts else ""
            await _save_message(resolved_id, "assistant", answer)

            yield f"data: {json.dumps({'type': 'answer', 'content': answer, 'session_id': resolved_id})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
