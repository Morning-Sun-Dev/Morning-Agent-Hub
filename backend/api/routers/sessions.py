from fastapi import APIRouter, HTTPException
from typing import List

from backend.api.db import get_supabase
from backend.api.schemas import SessionOut, MessageOut

router = APIRouter()


@router.get("/sessions", response_model=List[SessionOut])
async def list_sessions():
    """세션 목록 (최신순)"""
    sb = get_supabase()
    rows = (
        sb.table("chat_sessions")
        .select("*")
        .order("created_at", desc=True)
        .execute()
        .data
    )
    return rows


@router.get("/sessions/{session_id}/messages", response_model=List[MessageOut])
async def get_messages(session_id: str):
    """특정 세션의 전체 대화 기록"""
    sb = get_supabase()
    rows = (
        sb.table("chat_messages")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at")
        .execute()
        .data
    )
    if not rows:
        # 세션 존재 여부 확인
        session = sb.table("chat_sessions").select("id").eq("id", session_id).execute().data
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
    return rows


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """세션 및 메시지 삭제 (CASCADE)"""
    sb = get_supabase()
    result = sb.table("chat_sessions").delete().eq("id", session_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
    return {"message": "삭제 완료"}
