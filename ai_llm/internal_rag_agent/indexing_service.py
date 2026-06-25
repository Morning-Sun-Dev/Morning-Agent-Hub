"""파일 업로드 API용 문서 인덱싱 서비스"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter

from agent import extract_text_from_bytes, get_embedding


class IndexStatus(str, Enum):
    success = "success"
    error = "error"


@dataclass
class IndexJob:
    status: IndexStatus
    chunk_count: int = 0
    error: Optional[str] = None


def index_document(
    sb,
    storage_ref: str,
    filename: str,
    file_bytes: bytes,
    mime_type: str,
) -> IndexJob:
    """업로드된 파일 바이트를 벡터 DB에 인덱싱"""
    try:
        content = extract_text_from_bytes(file_bytes, mime_type)
        if not content:
            return IndexJob(status=IndexStatus.error, error="텍스트 추출 결과가 비어있습니다.")

        mime_to_doctype = {
            "application/pdf": "pdf",
            "text/plain": "text",
            "text/markdown": "markdown",
        }
        document_type = mime_to_doctype.get(mime_type)
        if not document_type and filename and "." in filename:
            document_type = filename.rsplit(".", 1)[-1].lower()

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = text_splitter.split_text(content)

        for i, chunk in enumerate(chunks):
            data = {
                "content": chunk,
                "embedding": get_embedding(chunk),
                "filename": filename,
                "storage_ref": storage_ref,
                "chunk_index": i,
            }
            if document_type:
                data["document_type"] = document_type
            sb.table("documents").insert(data).execute()

        return IndexJob(status=IndexStatus.success, chunk_count=len(chunks))
    except Exception as e:
        return IndexJob(status=IndexStatus.error, error=str(e))
