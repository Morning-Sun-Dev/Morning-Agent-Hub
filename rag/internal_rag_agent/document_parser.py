"""
M-005 Document Parser

역할: PDF/TXT/MD 문서 텍스트 추출, 파일 형식 검증, 파싱 실패 처리,
      페이지/청크 단위 소스 메타데이터 생성

관련 기능: F-008, F-009, F-010, F-011, F-019
인터페이스: parse_document(), ParsedDocument, validate_file_format()
"""

import io
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from pypdf import PdfReader

logger = logging.getLogger(__name__)


# ============================================================================
# 지원 형식 정의
# ============================================================================

SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}

SUPPORTED_EXTENSIONS = {"pdf", "txt", "md", "docx", "doc", "xlsx", "xls"}

MIME_TO_DOCTYPE: Dict[str, str] = {
    "application/pdf": "pdf",
    "text/plain": "text",
    "text/markdown": "markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-excel": "xls",
}


# ============================================================================
# 데이터 모델
# ============================================================================

@dataclass
class ParsedDocument:
    """
    파싱된 문서 결과

    Attributes:
        text: 전체 추출된 텍스트
        filename: 파일명
        mime_type: MIME 타입
        document_type: pdf | text | markdown | docx | doc | xlsx | xls
        page_count: 페이지 수 (PDF 전용, 나머지는 0)
        chunk_source_metadata: 페이지/섹션 단위 소스 메타데이터 리스트
            각 항목: {"page_number": int, "char_offset": int, "char_count": int}
    """
    text: str
    filename: str
    mime_type: str
    document_type: Optional[str] = None
    page_count: int = 0
    chunk_source_metadata: List[Dict[str, Any]] = field(default_factory=list)


# ============================================================================
# 내부 파싱 함수
# ============================================================================

def _extract_text_from_pdf(pdf_bytes: bytes) -> tuple[str, int, List[Dict[str, Any]]]:
    """
    PDF 바이너리에서 텍스트 및 페이지 메타데이터 추출

    Returns:
        (full_text, page_count, page_metadata_list)
    """
    try:
        pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
        text_parts: List[str] = []
        page_metadata: List[Dict[str, Any]] = []
        cumulative_offset = 0

        for page_num, page in enumerate(pdf_reader.pages, 1):
            page_text = page.extract_text() or ""
            if page_text:
                block = f"[페이지 {page_num}]\n{page_text}"
                text_parts.append(block)
                page_metadata.append({
                    "page_number": page_num,
                    "char_offset": cumulative_offset,
                    "char_count": len(block),
                })
                cumulative_offset += len(block) + 2  # "\n\n" separator

        full_text = "\n\n".join(text_parts)
        logger.info(f"[DOC PARSER] PDF 추출 완료: {len(pdf_reader.pages)}페이지, {len(full_text)}자")
        return full_text, len(pdf_reader.pages), page_metadata

    except Exception as e:
        logger.error(f"[DOC PARSER] PDF 추출 실패: {e}")
        raise


def _resolve_doctype(mime_type: str, filename: str) -> Optional[str]:
    """MIME 타입 또는 확장자로 document_type 결정"""
    doc_type = MIME_TO_DOCTYPE.get(mime_type)
    if not doc_type and filename and "." in filename:
        doc_type = filename.rsplit(".", 1)[-1].lower()
    return doc_type


# ============================================================================
# 공개 인터페이스
# ============================================================================

def validate_file_format(mime_type: str = "", filename: str = "") -> bool:
    """
    파일 형식 지원 여부 확인 (F-019 미지원 형식 안내용)

    Args:
        mime_type: 파일 MIME 타입
        filename: 파일명 (확장자 기반 폴백)

    Returns:
        True: 지원 형식, False: 미지원 형식
    """
    if mime_type and mime_type.lower() in SUPPORTED_MIME_TYPES:
        return True
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        return ext in SUPPORTED_EXTENSIONS
    return False


def parse_document(
    file_bytes: bytes,
    filename: str = "",
    mime_type: str = "",
) -> ParsedDocument:
    """
    파일 바이너리를 파싱하여 ParsedDocument 반환

    M-005 Document Parser 핵심 인터페이스

    Args:
        file_bytes: 파일 바이너리 데이터
        filename: 파일명
        mime_type: MIME 타입

    Returns:
        ParsedDocument

    Raises:
        ValueError: 미지원 형식이거나 파싱/디코딩 실패 시
    """
    logger.info(f"[DOC PARSER] 파싱 시작: {filename} (mime={mime_type})")

    # 형식 검증 (F-019)
    if not validate_file_format(mime_type, filename):
        raise ValueError(
            f"지원하지 않는 파일 형식입니다. "
            f"(mime={mime_type}, file={filename}) "
            f"지원 형식: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    doc_type = _resolve_doctype(mime_type, filename)
    page_count = 0
    chunk_source_metadata: List[Dict[str, Any]] = []

    try:
        is_pdf = "pdf" in mime_type.lower() or (filename and filename.lower().endswith(".pdf"))

        if is_pdf:
            text, page_count, chunk_source_metadata = _extract_text_from_pdf(file_bytes)
        else:
            # TXT / MD 등 텍스트 파일
            for encoding in ("utf-8", "cp949", "latin-1"):
                try:
                    text = file_bytes.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("텍스트 디코딩 실패: 지원하지 않는 인코딩")

        if not text or not text.strip():
            raise ValueError("텍스트 추출 결과가 비어 있습니다.")

    except ValueError:
        raise
    except Exception as e:
        logger.error(f"[DOC PARSER] 파싱 오류: {filename}, {e}")
        raise ValueError(f"파일 파싱 중 오류 발생: {e}") from e

    logger.info(
        f"[DOC PARSER] 파싱 완료: {filename}, {len(text)}자"
        + (f", {page_count}페이지" if page_count else "")
    )

    return ParsedDocument(
        text=text,
        filename=filename,
        mime_type=mime_type,
        document_type=doc_type,
        page_count=page_count,
        chunk_source_metadata=chunk_source_metadata,
    )
