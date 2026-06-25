import sys
import os
from uuid import uuid4

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

# 프로젝트 루트 경로 추가
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "ai_llm", "file_management_agent"))
sys.path.insert(0, os.path.join(ROOT, "ai_llm", "internal_rag_agent"))

from gdrive_client import get_gdrive_client
from indexing_service import index_document
from backend.api.db import get_supabase_service

router = APIRouter()

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}
MIME_MAP = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md":  "text/markdown",
}


class UploadResult(BaseModel):
    filename: str
    storage_ref: str
    index_status: str
    index_message: str


@router.post("/files/upload", response_model=UploadResult)
async def upload_and_index(file: UploadFile = File(...)):
    """파일을 Google Drive에 업로드하고 벡터 DB에 인덱싱합니다."""
    filename = file.filename or f"upload_{uuid4().hex}"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 파일 형식입니다. 지원: PDF, TXT, MD")

    mime_type = MIME_MAP.get(ext, "application/octet-stream")
    file_bytes = await file.read()

    # ── Step 1: Google Drive 업로드 ──────────────────
    try:
        gdrive = get_gdrive_client()
        upload_result = gdrive.upload_file(
            content=file_bytes,
            filename=filename,
            mime_type=mime_type,
        )
        storage_ref = upload_result.get("storage_ref")
        if not storage_ref:
            raise ValueError("storage_ref를 받지 못했습니다")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google Drive 업로드 실패: {str(e)}")

    # ── Step 2: 벡터 DB 인덱싱 ──────────────────────
    try:
        sb = get_supabase_service()
        job = index_document(
            sb=sb,
            storage_ref=storage_ref,
            filename=filename,
            file_bytes=file_bytes,
            mime_type=mime_type,
        )
        if job.error:
            index_message = job.error
        elif job.status.value == "skipped":
            index_message = "이미 인덱싱됨 (스킵)"
        else:
            index_message = f"{job.chunk_count}개 청크 저장 완료"
        return UploadResult(
            filename=filename,
            storage_ref=storage_ref,
            index_status=job.status.value,
            index_message=index_message,
        )
    except Exception as e:
        # 인덱싱 실패해도 업로드는 성공했으므로 부분 성공으로 반환
        return UploadResult(
            filename=filename,
            storage_ref=storage_ref,
            index_status="error",
            index_message=f"인덱싱 실패: {str(e)}",
        )


@router.get("/files")
async def list_files():
    """Google Drive 파일 목록"""
    try:
        gdrive = get_gdrive_client()
        files = gdrive.list_files()
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/files/{file_id}")
async def delete_file(file_id: str):
    """Google Drive 파일 삭제"""
    try:
        gdrive = get_gdrive_client()
        gdrive.delete_file(file_id)
        return {"message": "삭제 완료", "file_id": file_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
