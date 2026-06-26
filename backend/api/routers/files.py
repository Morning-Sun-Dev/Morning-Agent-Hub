import sys
import os
from uuid import uuid4
from typing import Any

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


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_drive_file(file_info: dict[str, Any]) -> dict[str, Any]:
    """Keep existing Drive keys and add UI-friendly file artifact aliases."""
    file_item = dict(file_info)

    file_id = file_item.get("file_id") or file_item.get("id")
    storage_ref = file_item.get("storage_ref")
    filename = file_item.get("filename") or file_item.get("name") or file_id or storage_ref or "파일"
    mime_type = file_item.get("mime_type") or file_item.get("mimeType")
    size = _optional_int(file_item.get("size"))
    open_url = (
        file_item.get("open_url")
        or file_item.get("openUrl")
        or file_item.get("web_view_link")
        or file_item.get("webViewLink")
    )
    download_url = (
        file_item.get("download_url")
        or file_item.get("downloadUrl")
        or file_item.get("web_content_link")
        or file_item.get("webContentLink")
    )

    file_item.update(
        {
            "file_id": _optional_str(file_id),
            "storage_ref": _optional_str(storage_ref),
            "filename": _optional_str(filename),
            "mime_type": _optional_str(mime_type),
            "size": size,
            "id": _optional_str(storage_ref or file_id or filename),
            "name": _optional_str(filename),
            "kind": file_item.get("kind") or "drive",
            "status": file_item.get("status")
            or ("downloadable" if open_url or download_url else "pending"),
            "open_url": _optional_str(open_url),
            "download_url": _optional_str(download_url),
        }
    )
    return file_item


def _download_action(file_item: dict[str, Any]) -> dict[str, Any]:
    download_url = file_item.get("download_url")
    open_url = file_item.get("open_url")
    action_url = download_url or open_url
    return {
        "available": bool(action_url),
        "method": "open_url",
        "url": action_url,
        "fallback_open_url": open_url,
    }


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
        normalized_files = [
            _normalize_drive_file(file_item)
            for file_item in files
            if isinstance(file_item, dict)
        ]
        return {"files": normalized_files, "count": len(normalized_files)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/{file_id}")
async def get_file_info(file_id: str):
    """Google Drive 파일 메타데이터 조회"""
    try:
        gdrive = get_gdrive_client()
        file_info = gdrive.get_file_info(file_id)
        if file_info is None:
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")

        return {"file": _normalize_drive_file(file_info)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/{file_id}/download")
async def get_file_download(file_id: str):
    """UI가 사용할 수 있는 Google Drive 다운로드 액션 조회"""
    try:
        gdrive = get_gdrive_client()
        file_info = gdrive.get_file_info(file_id)
        if file_info is None:
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")

        file_item = _normalize_drive_file(file_info)
        return {
            "file": file_item,
            "download": _download_action(file_item),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/files/{file_id}")
async def delete_file(file_id: str):
    """Google Drive 파일 삭제"""
    try:
        gdrive = get_gdrive_client()
        deleted = gdrive.delete_file(file_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")

        return {"message": "삭제 완료", "file_id": file_id, "deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
