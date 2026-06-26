"""
M-007 RAG Search Service

역할: 벡터 검색, 관련 청크 조회, 근거 정리, 문서 기반 답변 생성, 출처 정보 반환

관련 기능: F-009, F-010, F-014, F-015, F-020
인터페이스: search_documents(), answer_from_documents(), Source 객체
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Any, List, Optional, Tuple

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from supabase import Client

logger = logging.getLogger(__name__)

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
_answer_llm = ChatOpenAI(model="gpt-4o")
_embeddings = OpenAIEmbeddings(model="text-embedding-3-small")


# ============================================================================
# 데이터 모델
# ============================================================================

@dataclass
class Source:
    """
    검색 결과 출처 정보 (F-010 답변 근거 표시)

    Attributes:
        filename: 파일명
        storage_ref: 저장소 참조 (gdrive://file/xxx)
        chunk_index: 청크 인덱스
        similarity: 코사인 유사도 (벡터 검색 시)
        url: Google Drive 웹 URL
        document_type: 파일 형식
        created_at: 인덱싱 일시
        pages: 청크에서 추출한 페이지 번호 목록 (예: [13, 14])
    """
    filename: str
    storage_ref: str
    chunk_index: int = 0
    similarity: float = 0.0
    url: Optional[str] = None
    document_type: Optional[str] = None
    created_at: Optional[str] = None
    pages: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "storage_ref": self.storage_ref,
            "chunk_index": self.chunk_index,
            "similarity": self.similarity,
            "url": self.url,
            "document_type": self.document_type,
            "created_at": self.created_at,
            "pages": self.pages,
        }


# ============================================================================
# 내부 헬퍼
# ============================================================================

def _storage_ref_to_url(storage_ref: str) -> Optional[str]:
    """storage_ref → Google Drive 웹 URL 변환"""
    if not storage_ref:
        return None
    file_id: Optional[str] = None
    if storage_ref.startswith("gdrive://file/"):
        file_id = storage_ref.replace("gdrive://file/", "")
    elif storage_ref.startswith("gdrive://"):
        file_id = storage_ref.replace("gdrive://", "")
    return f"https://drive.google.com/file/d/{file_id}/view" if file_id else None


def _extract_pages(content: str) -> List[int]:
    """
    청크 텍스트에서 페이지 번호 추출

    인덱싱 시 삽입된 '[페이지 N]' 마커를 파싱하여 페이지 번호 목록 반환.
    예: '[페이지 13]\n...[페이지 14]\n...' → [13, 14]
    """
    matches = re.findall(r'\[페이지\s+(\d+)\]', content)
    return sorted({int(m) for m in matches})


def _build_source_section(sources: List[Source]) -> str:
    """
    출처 섹션 텍스트 생성 (F-010)

    파일명, 페이지 번호, Drive URL을 포함한 출처 정보를 마크다운으로 반환.
    동일 파일의 여러 청크는 페이지 번호를 합산하여 하나로 묶어 표시.
    """
    # 파일명 기준으로 페이지 번호 집계
    file_pages: Dict[str, List[int]] = {}
    file_meta: Dict[str, Source] = {}
    for s in sources:
        if not s.filename:
            continue
        if s.filename not in file_pages:
            file_pages[s.filename] = []
            file_meta[s.filename] = s
        file_pages[s.filename].extend(s.pages)

    lines = ["\n\n**출처:**"]
    for filename, meta in file_meta.items():
        pages = sorted(set(file_pages[filename]))
        page_str = f"p.{pages[0]}" if len(pages) == 1 else f"p.{pages[0]}–{pages[-1]}" if pages else ""
        line = f"- **{filename}**"
        if page_str:
            line += f" ({page_str})"
        if meta.url:
            line += f"\n  파일 위치: {meta.url}"
        lines.append(line)
    return "\n".join(lines)


# ============================================================================
# 공개 인터페이스
# ============================================================================

def search_documents(
    query: str,
    sb: Client,
    filters: Optional[Dict[str, Any]] = None,
    match_count: int = 10,
    match_threshold: float = 0.3,
) -> Tuple[List[Dict[str, Any]], List[Source]]:
    """
    벡터 유사도 기반 문서 검색 — 쿼리 재작성 + 멀티 쿼리 + 중복 제거

    M-007 RAG Search Service 핵심 인터페이스

    Args:
        query: 자연어 검색 질의
        sb: Supabase 클라이언트
        filters: 추가 후처리 필터 (document_type, filename_contains)
        match_count: 최종 반환할 최대 결과 수 (기본 10)
        match_threshold: 유사도 최소값 (기본 0.3)

    Returns:
        (raw_results, sources)
    """
    logger.info(f"[RAG SEARCH] 벡터 검색 시작: {query[:50]}...")

    # 1. 쿼리 재작성 + 멀티 쿼리 생성
    rewritten = rewrite_query(query)
    extra_queries = generate_multi_queries(rewritten)
    all_queries = [rewritten] + extra_queries

    # 2. 각 쿼리 순차 실행 — storage_ref:chunk_index 키로 중복 제거 (높은 유사도 우선)
    seen: Dict[str, Dict] = {}
    for q in all_queries:
        q_embedding = _embeddings.embed_query(q)
        try:
            response = sb.rpc("match_documents", {
                "query_embedding": q_embedding,
                "match_count": match_count,
                "match_threshold": match_threshold,
            }).execute()
            for r in (response.data or []):
                key = f"{r.get('storage_ref')}:{r.get('chunk_index')}"
                if key not in seen or r.get("similarity", 0) > seen[key].get("similarity", 0):
                    seen[key] = r
        except Exception as e:
            logger.error(f"[RAG SEARCH] 쿼리 검색 오류 ({q[:30]}): {e}")

    # 3. 유사도 내림차순 정렬, 상위 match_count개
    results: List[Dict] = sorted(seen.values(), key=lambda r: r.get("similarity", 0), reverse=True)[:match_count]

    # 4. 후처리 필터
    if filters and results:
        doc_type = filters.get("document_type")
        kw = (filters.get("filename_contains") or "").lower()
        if doc_type:
            results = [r for r in results if r.get("document_type") == doc_type]
        if kw:
            results = [r for r in results if kw in (r.get("filename") or "").lower()]

    sources = [
        Source(
            filename=r.get("filename", ""),
            storage_ref=r.get("storage_ref", ""),
            chunk_index=r.get("chunk_index", 0),
            similarity=r.get("similarity", 0.0),
            url=_storage_ref_to_url(r.get("storage_ref", "")),
            document_type=r.get("document_type"),
            pages=_extract_pages(r.get("content", "")),
        )
        for r in results
    ]

    logger.info(f"[RAG SEARCH] 최종 검색 결과: {len(results)}개 (쿼리 {len(all_queries)}개 사용)")
    return results, sources


def rewrite_query(question: str) -> str:
    """사용자 질문을 검색 최적화 쿼리로 재작성 (gpt-4o-mini). 실패 시 원본 반환."""
    try:
        messages = [
            {
                "role": "system",
                "content": (
                    "사용자 질문을 문서 검색에 최적화된 한국어 키워드 중심 문장으로 재작성하세요. "
                    "구어체 표현을 제거하고 핵심 명사와 동사만 남기세요. "
                    "재작성된 문장만 출력하세요."
                ),
            },
            {"role": "user", "content": question},
        ]
        response = _llm.invoke(messages)
        rewritten = response.content.strip()
        logger.info(f"[RAG SEARCH] 쿼리 재작성: '{question[:30]}' → '{rewritten[:50]}'")
        return rewritten
    except Exception as e:
        logger.warning(f"[RAG SEARCH] 쿼리 재작성 실패, 원본 사용: {e}")
        return question


def generate_multi_queries(rewritten_query: str) -> List[str]:
    """재작성된 쿼리에서 표현을 달리한 3개 변형 쿼리 생성. 실패 시 빈 리스트 반환."""
    try:
        messages = [
            {
                "role": "system",
                "content": (
                    "주어진 검색 쿼리를 의미는 같지만 표현을 달리한 3개의 한국어 쿼리로 변환하세요. "
                    "각 쿼리는 줄바꿈으로 구분하고, 번호나 불릿 없이 쿼리만 출력하세요."
                ),
            },
            {"role": "user", "content": rewritten_query},
        ]
        response = _llm.invoke(messages)
        lines = [line.strip() for line in response.content.strip().splitlines() if line.strip()]
        queries = lines[:3]
        logger.info(f"[RAG SEARCH] 멀티 쿼리 생성: {len(queries)}개")
        return queries
    except Exception as e:
        logger.warning(f"[RAG SEARCH] 멀티 쿼리 생성 실패: {e}")
        return []


def extract_sql_filters(question: str) -> Dict[str, Any]:
    """
    자연어 질문에서 SQL 필터 조건 추출 (LLM 사용)

    Args:
        question: 사용자 질문

    Returns:
        filters dict (document_type, filename_contains, created_after, created_before, list_all)
    """
    today = date.today().isoformat()
    messages = [
        {
            "role": "user",
            "content": f"""다음 질문에서 검색 조건을 JSON으로 추출하세요.
질문: {question}

사용 가능한 필드:
1. document_type: 파일 형식 (허용 값: pdf, text, markdown, docx, doc, xlsx, xls)
2. filename_contains: 파일명에 포함된 키워드 (예: "SPRi", "Brief", "AI")
3. created_after: 이 날짜 이후 인덱싱된 문서 (ISO 형식: "YYYY-MM-DD")
4. created_before: 이 날짜 이전 인덱싱된 문서 (ISO 형식: "YYYY-MM-DD")
5. list_all: true면 모든 문서 목록 반환

예시:
- "PDF 문서만" -> {{"document_type": "pdf"}}
- "파일명에 AI가 들어간 파일 목록" -> {{"filename_contains": "AI"}}
- "인덱싱된 모든 파일" -> {{"list_all": true}}
- "2025년 12월 문서" -> {{"created_after": "2025-12-01", "created_before": "2025-12-31"}}

참고: 오늘 날짜는 {today}입니다.
조건을 추출할 수 없으면 빈 객체 {{}}를 반환하세요.
JSON만 응답:""",
        }
    ]
    try:
        response = _llm.invoke(messages)
        return json.loads(response.content.strip())
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"[RAG SEARCH] 필터 추출 실패: {e}")
        return {}


def search_documents_by_metadata(
    sb: Client,
    filters: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Source]]:
    """
    메타데이터 조건 기반 SQL 검색

    Args:
        sb: Supabase 클라이언트
        filters: extract_sql_filters()가 반환한 조건 dict

    Returns:
        (raw_results, sources)
    """
    logger.info(f"[RAG SEARCH] SQL 검색 시작: {filters}")

    try:
        query = sb.table("documents").select(
            "storage_ref, filename, document_type, created_at, content"
        )
        if filters.get("document_type"):
            query = query.eq("document_type", filters["document_type"])
        if filters.get("filename_contains"):
            query = query.ilike("filename", f"%{filters['filename_contains']}%")
        if filters.get("created_after"):
            query = query.gte("created_at", filters["created_after"])
        if filters.get("created_before"):
            query = query.lte("created_at", filters["created_before"])
        if not filters.get("list_all"):
            query = query.eq("chunk_index", 0)

        resp = query.order("created_at", desc=True).limit(20).execute()
        results: List[Dict] = resp.data or []
    except Exception as e:
        logger.error(f"[RAG SEARCH] SQL 검색 오류: {e}")
        results = []

    sources = [
        Source(
            filename=r.get("filename", ""),
            storage_ref=r.get("storage_ref", ""),
            url=_storage_ref_to_url(r.get("storage_ref", "")),
            document_type=r.get("document_type"),
            created_at=r.get("created_at"),
        )
        for r in results
    ]

    logger.info(f"[RAG SEARCH] SQL 검색 결과: {len(results)}개")
    return results, sources


def answer_from_documents(
    query: str,
    search_results: List[Dict[str, Any]],
    sources: List[Source],
) -> str:
    """
    검색 결과를 기반으로 LLM 답변 생성 (F-009 문서 기반 답변, F-010 답변 근거 표시)

    M-007 RAG Search Service 핵심 인터페이스

    Args:
        query: 사용자 질문
        search_results: search_documents()의 raw_results
        sources: search_documents()의 Source 리스트

    Returns:
        최종 답변 문자열 (출처 섹션 포함)
    """
    logger.info("[RAG SEARCH] 답변 생성 시작")

    if not search_results:
        return "관련 문서를 찾을 수 없습니다. 다른 검색어로 시도해주세요."

    context_parts = [
        f"[{r.get('filename', 'unknown')}]\n{r.get('content', '')}"
        for r in search_results
    ]
    context = "\n\n---\n\n".join(context_parts)

    messages = [
        {
            "role": "user",
            "content": f"""당신은 사내 문서 기반 RAG 전문가입니다.
아래 참고 문서를 바탕으로 질문에 정확하게 답변하세요.

## 참고 문서
{context}

## 질문
{query}

## 지시사항
- 반드시 참고 문서에 있는 정보만 사용하세요. 학습 데이터나 일반 지식을 사용하지 마세요.
- 문서에 등급·단계·항목 번호가 있다면 해당 번호와 명칭을 그대로 인용하세요.
- 목록, 표, 조건 등 구조화된 정보는 원문의 구조를 유지하여 답변하세요.
- 문서에서 답을 찾을 수 없는 경우 "문서에서 관련 내용을 찾지 못했습니다."라고 답하세요.

## 답변 형식 (마크다운)
- 핵심 요약을 첫 문단에 1~2문장으로 먼저 제시하세요.
- 세부 내용은 `##` 소제목과 목록(`-`, `1.`)으로 구분하세요.
- 중요 용어, 기준값, 단계명은 **굵게** 표시하세요.
- 코드·명령어가 있으면 백틱(`` ` ``)으로 감싸세요.
""",
        }
    ]

    response = _answer_llm.invoke(messages)
    return response.content + _build_source_section(sources)


def build_list_response(
    search_results: List[Dict[str, Any]],
    sources: List[Source],
) -> str:
    """
    SQL 검색 결과를 목록 형태 텍스트로 변환 (LLM 호출 없이)

    Args:
        search_results: search_documents_by_metadata()의 raw_results
        sources: Source 리스트

    Returns:
        마크다운 형식 목록 문자열
    """
    lines = [f"**검색 결과: {len(search_results)}개 문서**\n"]
    seen: set = set()

    for i, s in enumerate(sources, 1):
        if s.filename in seen:
            continue
        seen.add(s.filename)

        created_at = s.created_at or ""
        if created_at:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                created_at = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass

        lines.append(f"{i}. **{s.filename}**")
        if s.document_type:
            lines.append(f"   - 형식: {s.document_type}")
        if created_at:
            lines.append(f"   - 인덱싱: {created_at}")
        if s.url:
            lines.append(f"   - 위치: {s.url}")
        lines.append("")

    return "\n".join(lines)
