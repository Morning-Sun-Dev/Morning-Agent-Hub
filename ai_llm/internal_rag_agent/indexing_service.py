"""
M-006 Indexing Service

역할: 청크 분할, 임베딩 생성, 벡터 DB 저장, 인덱싱 상태 업데이트, 중복 인덱싱 방지

관련 기능: F-008, F-009, F-010, F-011
인터페이스: index_document(), chunk_documents(), embed_chunks(), IndexJob, IndexJobStatus
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, List, Optional

from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from supabase import Client

from document_parser import parse_document, ParsedDocument

logger = logging.getLogger(__name__)

_embeddings = OpenAIEmbeddings(model="text-embedding-3-small")


# ============================================================================
# 데이터 모델
# ============================================================================

class IndexJobStatus(str, Enum):
    """인덱싱 작업 상태값"""
    SUCCESS = "success"
    SKIPPED = "skipped"   # 중복 인덱싱 방지로 스킵 (F-011)
    ERROR = "error"


@dataclass
class IndexJob:
    """
    인덱싱 작업 결과

    Attributes:
        status: success | skipped | error
        filename: 처리된 파일명
        storage_ref: 저장소 참조 (gdrive://file/xxx)
        chunk_count: 생성된 청크 수 (success인 경우)
        error: 오류 메시지 (error인 경우)
    """
    status: IndexJobStatus
    filename: str
    storage_ref: str
    chunk_count: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "filename": self.filename,
            "storage_ref": self.storage_ref,
            "chunk_count": self.chunk_count,
            "error": self.error,
        }


# ============================================================================
# 공개 인터페이스
# ============================================================================

def chunk_documents(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> List[str]:
    """
    텍스트를 청크로 분할

    Args:
        text: 원본 텍스트
        chunk_size: 청크 크기 (문자 수, 기본 500)
        chunk_overlap: 청크 간 겹침 (기본 50)

    Returns:
        청크 문자열 리스트
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks = splitter.split_text(text)
    logger.info(f"[INDEXING] 청크 분할 완료: {len(chunks)}개 (size={chunk_size}, overlap={chunk_overlap})")
    return chunks


def embed_chunks(chunks: List[str]) -> List[List[float]]:
    """
    청크 리스트를 임베딩 벡터로 변환

    Args:
        chunks: 청크 텍스트 리스트

    Returns:
        임베딩 벡터 리스트 (각 벡터는 1536차원)
    """
    logger.info(f"[INDEXING] 임베딩 생성 시작: {len(chunks)}개 청크")
    result = _embeddings.embed_documents(chunks)
    logger.info(f"[INDEXING] 임베딩 생성 완료")
    return result


def _is_already_indexed(sb: Client, storage_ref: str) -> bool:
    """
    중복 인덱싱 여부 확인 (F-011 중복 인덱싱 방지)

    Args:
        sb: Supabase 클라이언트
        storage_ref: 저장소 참조

    Returns:
        True: 이미 인덱싱됨
    """
    result = (
        sb.table("documents")
        .select("id")
        .eq("storage_ref", storage_ref)
        .limit(1)
        .execute()
    )
    return bool(result.data)


def index_document(
    sb: Client,
    storage_ref: str,
    filename: str,
    file_bytes: bytes,
    mime_type: str = "",
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> IndexJob:
    """
    단일 문서 인덱싱

    M-006 Indexing Service 핵심 인터페이스

    내부 흐름:
      1. 중복 체크 (F-011)
      2. M-005 Document Parser로 텍스트 추출 및 형식 검증
      3. 청크 분할 (chunk_documents)
      4. 임베딩 생성 (embed_chunks)
      5. Supabase documents 테이블에 저장

    Args:
        sb: Supabase 클라이언트
        storage_ref: 저장소 참조 (gdrive://file/xxx)
        filename: 파일명
        file_bytes: 파일 바이너리
        mime_type: MIME 타입
        chunk_size: 청크 크기 (기본 500)
        chunk_overlap: 청크 겹침 (기본 50)

    Returns:
        IndexJob — status: success | skipped | error
    """
    logger.info(f"[INDEXING] 인덱싱 시작: {filename} ({storage_ref})")

    # 중복 인덱싱 방지 (F-011)
    if _is_already_indexed(sb, storage_ref):
        logger.info(f"[INDEXING] 이미 인덱싱된 파일 스킵: {filename}")
        return IndexJob(
            status=IndexJobStatus.SKIPPED,
            filename=filename,
            storage_ref=storage_ref,
        )

    # M-005: 파싱 (형식 검증 + 텍스트 추출)
    try:
        parsed: ParsedDocument = parse_document(file_bytes, filename, mime_type)
    except ValueError as e:
        logger.error(f"[INDEXING] 파싱 실패: {filename}, {e}")
        return IndexJob(
            status=IndexJobStatus.ERROR,
            filename=filename,
            storage_ref=storage_ref,
            error=str(e),
        )

    # 청크 분할 + 임베딩 + Supabase 저장
    try:
        chunks = chunk_documents(parsed.text, chunk_size, chunk_overlap)
        embeddings_list = embed_chunks(chunks)

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings_list)):
            row: Dict[str, Any] = {
                "content": chunk,
                "embedding": embedding,
                "filename": parsed.filename or filename,
                "storage_ref": storage_ref,
                "chunk_index": i,
            }
            if parsed.document_type:
                row["document_type"] = parsed.document_type

            sb.table("documents").insert(row).execute()

        logger.info(f"[INDEXING] 인덱싱 완료: {filename}, {len(chunks)}개 청크")
        return IndexJob(
            status=IndexJobStatus.SUCCESS,
            filename=parsed.filename or filename,
            storage_ref=storage_ref,
            chunk_count=len(chunks),
        )

    except Exception as e:
        logger.error(f"[INDEXING] 저장 실패: {filename}, {e}")
        return IndexJob(
            status=IndexJobStatus.ERROR,
            filename=filename,
            storage_ref=storage_ref,
            error=str(e),
        )
