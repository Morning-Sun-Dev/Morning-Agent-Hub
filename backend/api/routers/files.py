import json
import base64
import sys
import os
from uuid import uuid4

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from common.a2a_client import A2AClientWrapper

router = APIRouter()

# A2A 클라이언트 (파일 관리 + RAG 에이전트)
_a2a_client: Optional[A2AClientWrapper] = None

SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
}

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


async def get_a2a_client() -> A2AClientWrapper:
    global _a2a_client
    if _a2a_client is None:
        _a2a_client = A2AClientWrapper(timeout=120.0)
        await _a2a_client.initialize({
            "file_management": "http://localhost:10013",
            "internal_rag": "http://localhost:10012",
        })
    return _a2a_client


class UploadResult(BaseModel):
    filename: str
    storage_ref: str
    index_status: str        # success | skipped | error
    index_message: str


# ── 파일 업로드 + 인덱싱 ───────────────────────────────

@router.post("/files/upload", response_model=UploadResult)
async def upload_and_index(file: UploadFile = File(...)):
    """
    파일을 Google Drive에 업로드하고 벡터 DB에 인덱싱합니다.

    지원 형식: PDF, TXT, MD
    """
    # 포맷 검증
    ext = os.path.splitext(file.filename or "")[1].lower()
    mime = file.content_type or ""

    if ext not in SUPPORTED_EXTENSIONS and mime not in SUPPORTED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다. 지원 형식: PDF, TXT, MD"
        )

    file_bytes = await file.read()
    filename = file.filename or f"upload_{uuid4().hex}{ext}"

    client = await get_a2a_client()

    # ── Step 1: File Management Agent → Google Drive 업로드 ──
    file_b64 = base64.b64encode(file_bytes).decode("utf-8")

    upload_message = json.dumps({
        "action": "upload",
        "filename": filename,
        "mime_type": mime or "application/octet-stream",
        "content_base64": file_b64,
    }, ensure_ascii=False)

    upload_response = await client.send_message("file_management", upload_message)

    if not upload_response.success:
        raise HTTPException(status_code=500, detail=f"파일 업로드 실패: {upload_response.error}")

    # storage_ref 파싱
    storage_ref = None
    if upload_response.artifacts:
        artifact_text = upload_response.artifacts[0].get("text", "")
        try:
            result = json.loads(artifact_text)
            storage_ref = result.get("storage_ref")
        except (json.JSONDecodeError, AttributeError):
            # JSON 파싱 실패 시 텍스트에서 직접 추출
            if "gdrive://file/" in artifact_text:
                start = artifact_text.find("gdrive://file/")
                storage_ref = artifact_text[start:].split()[0].rstrip('",}')

    if not storage_ref:
        raise HTTPException(status_code=500, detail="storage_ref를 받지 못했습니다")

    # ── Step 2: RAG Agent → 벡터 DB 인덱싱 ──
    index_message = json.dumps({
        "intent": "index",
        "content": f"{filename} 파일을 인덱싱해줘",
        "files": {filename: storage_ref},
    }, ensure_ascii=False)

    index_response = await client.send_message("internal_rag", index_message)

    index_status = "success"
    index_message_text = "인덱싱 완료"

    if not index_response.success:
        index_status = "error"
        index_message_text = index_response.error or "인덱싱 실패"
    elif index_response.artifacts:
        artifact_text = index_response.artifacts[0].get("text", "")
        if "skipped" in artifact_text.lower() or "중복" in artifact_text:
            index_status = "skipped"
            index_message_text = "이미 인덱싱된 파일입니다"
        else:
            index_message_text = artifact_text[:100]

    return UploadResult(
        filename=filename,
        storage_ref=storage_ref,
        index_status=index_status,
        index_message=index_message_text,
    )


# ── 업로드된 파일 목록 ─────────────────────────────────

@router.get("/files")
async def list_files():
    """Google Drive에 업로드된 파일 목록"""
    client = await get_a2a_client()
    response = await client.send_message("file_management", "업로드된 파일 목록을 보여줘")

    if not response.success:
        raise HTTPException(status_code=500, detail=response.error)

    if response.artifacts:
        text = response.artifacts[0].get("text", "")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"message": text}

    return {"files": []}


# ── 파일 삭제 ──────────────────────────────────────────

@router.delete("/files/{file_id}")
async def delete_file(file_id: str):
    """Google Drive에서 파일 삭제"""
    client = await get_a2a_client()
    message = f"gdrive://file/{file_id} 파일을 삭제해줘"
    response = await client.send_message("file_management", message)

    if not response.success:
        raise HTTPException(status_code=500, detail=response.error)

    return {"message": "삭제 완료", "file_id": file_id}
