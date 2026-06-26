# RAG 품질 개선 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 항상 빈 결과를 반환하던 RAG 검색 버그를 수정하고 (Supabase RPC threshold 파라미터화), 배치 INSERT·쿼리 재작성·멀티 쿼리로 인덱싱 성능과 검색 품질을 개선한다.

**Architecture:** Supabase `match_documents` RPC에 `match_threshold` 파라미터를 추가해 근본 원인을 수정하고, `indexing_service.py`의 청크 크기와 INSERT 방식을 개선한다. `rag_search_service.py`에 `rewrite_query()`, `generate_multi_queries()` 함수를 추가하고 `search_documents()`가 이를 활용하도록 수정한다.

**Tech Stack:** Python, LangChain (ChatOpenAI, OpenAIEmbeddings), Supabase (pgvector), LangGraph, pytest, unittest.mock

**Branch:** `feat/rag-quality-improvement`

---

## 파일 구조

| 파일 | 변경 종류 | 변경 내용 |
|------|-----------|----------|
| `ai_llm/internal_rag_agent/indexing_service.py` | Modify | 청크 기본값 800/150, 배치 INSERT |
| `ai_llm/internal_rag_agent/rag_search_service.py` | Modify | threshold 파라미터, rewrite_query, generate_multi_queries, 멀티쿼리 검색 |
| `ai_llm/internal_rag_agent/agent.py` | Modify | 검색 실패 메시지 개선 |
| `ai_llm/internal_rag_agent/tests/test_indexing_service.py` | Create | 배치 INSERT 단위 테스트 |
| `ai_llm/internal_rag_agent/tests/test_rag_search_service.py` | Create | rewrite_query, multi_queries, search_documents 단위 테스트 |
| Supabase SQL (수동) | Manual | match_documents RPC threshold 파라미터화 |

---

## Task 1: Supabase match_documents RPC 수정 (수동)

**Files:**
- Supabase 대시보드 → SQL Editor (코드 파일 없음)

이 Task는 자동화 불가능한 수동 DB 작업입니다. 아래 SQL을 Supabase 대시보드에서 실행하세요.

- [ ] **Step 1: Supabase 대시보드 SQL Editor에서 RPC 수정**

Supabase 프로젝트 → SQL Editor → New Query에서 아래 SQL 실행:

```sql
CREATE OR REPLACE FUNCTION match_documents(
  query_embedding vector(1536),
  match_count int DEFAULT 10,
  match_threshold float DEFAULT 0.3
)
RETURNS TABLE (
  id bigint,
  content text,
  filename text,
  storage_ref text,
  chunk_index int,
  document_type text,
  created_at timestamptz,
  similarity float
)
LANGUAGE sql STABLE
AS $$
  SELECT
    id,
    content,
    filename,
    storage_ref,
    chunk_index,
    document_type,
    created_at,
    1 - (embedding <=> query_embedding) AS similarity
  FROM documents
  WHERE 1 - (embedding <=> query_embedding) > match_threshold
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;
```

- [ ] **Step 2: RPC 동작 확인**

SQL Editor에서 아래 쿼리로 RPC가 파라미터를 받는지 확인 (테스트용 임베딩 — 실제 실행 불필요, 파라미터 수락 여부만 확인):

```sql
-- 함수 시그니처 확인
SELECT proname, pronargs, proargnames
FROM pg_proc
WHERE proname = 'match_documents';
```

Expected: `proargnames`에 `{query_embedding,match_count,match_threshold}` 포함

---

## Task 2: indexing_service.py — 청크 크기 조정 + 배치 INSERT

**Files:**
- Modify: `ai_llm/internal_rag_agent/indexing_service.py`
- Create: `ai_llm/internal_rag_agent/tests/__init__.py`
- Create: `ai_llm/internal_rag_agent/tests/test_indexing_service.py`

- [ ] **Step 1: tests 디렉토리 및 __init__.py 생성**

```bash
mkdir -p ai_llm/internal_rag_agent/tests
touch ai_llm/internal_rag_agent/tests/__init__.py
```

- [ ] **Step 2: 실패하는 테스트 작성**

`ai_llm/internal_rag_agent/tests/test_indexing_service.py`:

```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch, call
from indexing_service import chunk_documents, index_document, IndexJobStatus


def test_chunk_documents_default_size():
    text = "a" * 1000
    chunks = chunk_documents(text)
    # 기본 청크 크기 800 적용 확인 — 1000자 텍스트는 2청크 이하로 분할
    assert len(chunks) <= 2


def test_chunk_documents_custom_size():
    text = "a" * 1000
    chunks = chunk_documents(text, chunk_size=200, chunk_overlap=20)
    assert len(chunks) > 2


def test_index_document_batch_insert():
    """배치 INSERT: sb.table().insert()가 1번만 호출되어야 한다"""
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []

    dummy_bytes = b"hello world " * 100
    with patch("indexing_service.parse_document") as mock_parse, \
         patch("indexing_service.embed_chunks") as mock_embed:

        mock_parse.return_value = MagicMock(
            text="hello world " * 100,
            filename="test.txt",
            document_type="text",
        )
        mock_embed.return_value = [[0.1] * 1536, [0.2] * 1536]

        with patch("indexing_service.chunk_documents") as mock_chunk:
            mock_chunk.return_value = ["chunk1", "chunk2"]
            job = index_document(mock_sb, "gdrive://file/abc", "test.txt", dummy_bytes, "text/plain")

    assert job.status == IndexJobStatus.SUCCESS
    assert job.chunk_count == 2
    # insert가 정확히 1번 호출되어야 함 (배치)
    insert_calls = mock_sb.table.return_value.insert.call_args_list
    assert len(insert_calls) == 1
    # insert에 전달된 rows가 리스트여야 함
    rows_arg = insert_calls[0][0][0]
    assert isinstance(rows_arg, list)
    assert len(rows_arg) == 2
```

- [ ] **Step 3: 테스트 실행 — 실패 확인**

```bash
cd ai_llm/internal_rag_agent
python -m pytest tests/test_indexing_service.py -v
```

Expected: FAIL — `test_index_document_batch_insert` 실패 (현재 N번 insert 호출)

- [ ] **Step 4: indexing_service.py — 청크 기본값 수정**

`ai_llm/internal_rag_agent/indexing_service.py`의 `chunk_documents()` 함수 기본값 변경:

```python
def chunk_documents(
    text: str,
    chunk_size: int = 800,    # 500 → 800
    chunk_overlap: int = 150, # 50 → 150
) -> List[str]:
```

- [ ] **Step 5: indexing_service.py — index_document() 배치 INSERT 수정**

`ai_llm/internal_rag_agent/indexing_service.py`의 `index_document()` 함수에서 개별 INSERT 루프를 배치로 교체:

```python
    # 청크 분할 + 임베딩 + Supabase 저장
    try:
        chunks = chunk_documents(parsed.text, chunk_size, chunk_overlap)
        embeddings_list = embed_chunks(chunks)

        rows = []
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
            rows.append(row)

        sb.table("documents").insert(rows).execute()

        logger.info(f"[INDEXING] 인덱싱 완료: {filename}, {len(chunks)}개 청크")
        return IndexJob(
            status=IndexJobStatus.SUCCESS,
            filename=parsed.filename or filename,
            storage_ref=storage_ref,
            chunk_count=len(chunks),
        )
```

- [ ] **Step 6: 테스트 실행 — 통과 확인**

```bash
cd ai_llm/internal_rag_agent
python -m pytest tests/test_indexing_service.py -v
```

Expected: 3개 PASS

- [ ] **Step 7: 커밋**

```bash
git add ai_llm/internal_rag_agent/indexing_service.py \
        ai_llm/internal_rag_agent/tests/__init__.py \
        ai_llm/internal_rag_agent/tests/test_indexing_service.py
git commit -m "feat(rag): 청크 크기 800/150 조정 및 배치 INSERT 적용"
```

---

## Task 3: rag_search_service.py — rewrite_query + generate_multi_queries 추가

**Files:**
- Modify: `ai_llm/internal_rag_agent/rag_search_service.py`
- Create: `ai_llm/internal_rag_agent/tests/test_rag_search_service.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`ai_llm/internal_rag_agent/tests/test_rag_search_service.py`:

```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch


def test_rewrite_query_returns_string():
    """rewrite_query는 문자열을 반환해야 한다"""
    from rag_search_service import rewrite_query

    with patch("rag_search_service._llm") as mock_llm:
        mock_llm.invoke.return_value = MagicMock(content="휴가 정책 연차 규정")
        result = rewrite_query("우리 회사 휴가 어떻게 돼?")

    assert isinstance(result, str)
    assert len(result) > 0


def test_rewrite_query_fallback_on_error():
    """rewrite_query LLM 실패 시 원본 질문 반환"""
    from rag_search_service import rewrite_query

    with patch("rag_search_service._llm") as mock_llm:
        mock_llm.invoke.side_effect = Exception("LLM error")
        result = rewrite_query("원본 질문")

    assert result == "원본 질문"


def test_generate_multi_queries_returns_list():
    """generate_multi_queries는 최대 3개 쿼리 리스트를 반환해야 한다"""
    from rag_search_service import generate_multi_queries

    with patch("rag_search_service._llm") as mock_llm:
        mock_llm.invoke.return_value = MagicMock(content="쿼리1\n쿼리2\n쿼리3")
        result = generate_multi_queries("휴가 정책 연차 규정")

    assert isinstance(result, list)
    assert len(result) == 3
    assert result[0] == "쿼리1"


def test_generate_multi_queries_fallback_on_error():
    """generate_multi_queries LLM 실패 시 빈 리스트 반환"""
    from rag_search_service import generate_multi_queries

    with patch("rag_search_service._llm") as mock_llm:
        mock_llm.invoke.side_effect = Exception("LLM error")
        result = generate_multi_queries("쿼리")

    assert result == []
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
cd ai_llm/internal_rag_agent
python -m pytest tests/test_rag_search_service.py::test_rewrite_query_returns_string \
                 tests/test_rag_search_service.py::test_rewrite_query_fallback_on_error \
                 tests/test_rag_search_service.py::test_generate_multi_queries_returns_list \
                 tests/test_rag_search_service.py::test_generate_multi_queries_fallback_on_error -v
```

Expected: FAIL — `ImportError: cannot import name 'rewrite_query'`

- [ ] **Step 3: rewrite_query() 구현**

`ai_llm/internal_rag_agent/rag_search_service.py`에 `extract_sql_filters()` 함수 바로 위에 추가:

```python
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
```

- [ ] **Step 4: generate_multi_queries() 구현**

`ai_llm/internal_rag_agent/rag_search_service.py`에 `rewrite_query()` 바로 아래에 추가:

```python
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
```

- [ ] **Step 5: 테스트 실행 — 통과 확인**

```bash
cd ai_llm/internal_rag_agent
python -m pytest tests/test_rag_search_service.py::test_rewrite_query_returns_string \
                 tests/test_rag_search_service.py::test_rewrite_query_fallback_on_error \
                 tests/test_rag_search_service.py::test_generate_multi_queries_returns_list \
                 tests/test_rag_search_service.py::test_generate_multi_queries_fallback_on_error -v
```

Expected: 4개 PASS

---

## Task 4: rag_search_service.py — search_documents() 멀티 쿼리 통합

**Files:**
- Modify: `ai_llm/internal_rag_agent/rag_search_service.py`
- Modify: `ai_llm/internal_rag_agent/tests/test_rag_search_service.py` (테스트 추가)

- [ ] **Step 1: 실패하는 테스트 추가**

`ai_llm/internal_rag_agent/tests/test_rag_search_service.py` 끝에 추가:

```python
def test_search_documents_multi_query_dedup():
    """멀티 쿼리 결과에서 동일 storage_ref+chunk_index는 중복 제거되어야 한다"""
    from rag_search_service import search_documents

    mock_sb = MagicMock()
    # 두 쿼리 모두 동일한 청크 반환
    dup_result = {
        "id": 1, "content": "내용", "filename": "test.txt",
        "storage_ref": "gdrive://file/abc", "chunk_index": 0,
        "document_type": "text", "created_at": None, "similarity": 0.85,
    }
    mock_sb.rpc.return_value.execute.return_value.data = [dup_result]

    with patch("rag_search_service.rewrite_query", return_value="재작성 쿼리"), \
         patch("rag_search_service.generate_multi_queries", return_value=["변형1", "변형2"]), \
         patch("rag_search_service._embeddings") as mock_emb:

        mock_emb.embed_query.return_value = [0.1] * 1536
        results, sources = search_documents("테스트 질문", mock_sb)

    # 3개 쿼리(재작성1 + 변형2)가 모두 같은 청크를 반환해도 중복 제거 후 1개
    assert len(results) == 1
    assert results[0]["storage_ref"] == "gdrive://file/abc"


def test_search_documents_threshold_rpc_param():
    """search_documents는 match_threshold를 RPC에 전달해야 한다"""
    from rag_search_service import search_documents

    mock_sb = MagicMock()
    mock_sb.rpc.return_value.execute.return_value.data = []

    with patch("rag_search_service.rewrite_query", return_value="쿼리"), \
         patch("rag_search_service.generate_multi_queries", return_value=[]), \
         patch("rag_search_service._embeddings") as mock_emb:

        mock_emb.embed_query.return_value = [0.1] * 1536
        search_documents("질문", mock_sb, match_threshold=0.3)

    # RPC 호출 시 match_threshold=0.3 전달 확인
    call_kwargs = mock_sb.rpc.call_args_list[0][0][1]
    assert call_kwargs["match_threshold"] == 0.3
    assert call_kwargs["match_count"] == 10
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
cd ai_llm/internal_rag_agent
python -m pytest tests/test_rag_search_service.py::test_search_documents_multi_query_dedup \
                 tests/test_rag_search_service.py::test_search_documents_threshold_rpc_param -v
```

Expected: FAIL

- [ ] **Step 3: search_documents() 함수 전체 교체**

`ai_llm/internal_rag_agent/rag_search_service.py`의 `search_documents()` 함수를 아래로 교체:

```python
def search_documents(
    query: str,
    sb: Client,
    filters: Optional[Dict[str, Any]] = None,
    match_count: int = 10,
    match_threshold: float = 0.3,
) -> Tuple[List[Dict[str, Any]], List[Source]]:
    """
    벡터 유사도 기반 문서 검색 — 쿼리 재작성 + 멀티 쿼리 병렬 실행 + 중복 제거

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

    # 2. 각 쿼리 순차 실행 — storage_ref:chunk_index 기준 중복 제거 (높은 유사도 우선)
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
        )
        for r in results
    ]

    logger.info(f"[RAG SEARCH] 최종 검색 결과: {len(results)}개 (쿼리 {len(all_queries)}개 사용)")
    return results, sources
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
cd ai_llm/internal_rag_agent
python -m pytest tests/test_rag_search_service.py -v
```

Expected: 6개 PASS

- [ ] **Step 5: 커밋**

```bash
git add ai_llm/internal_rag_agent/rag_search_service.py \
        ai_llm/internal_rag_agent/tests/test_rag_search_service.py
git commit -m "feat(rag): 쿼리 재작성 + 멀티 쿼리 검색 + threshold 파라미터화"
```

---

## Task 5: agent.py — 검색 실패 메시지 개선

**Files:**
- Modify: `ai_llm/internal_rag_agent/agent.py:382-383`

- [ ] **Step 1: generate() 노드의 실패 메시지 수정**

`ai_llm/internal_rag_agent/agent.py`의 `generate()` 함수:

```python
def generate(state: RAGState) -> RAGState:
    """답변 생성 — M-007 answer_from_documents() / build_list_response() 위임"""
    logger.info("[RAG AGENT] [GENERATE] 시작")
    question = state["question"]
    search_type = state.get("search_type", "vector")
    search_results = state.get("search_results", [])
    raw_sources = state.get("sources", [])
    sources = [Source(**s) for s in raw_sources]

    if not search_results:
        return {
            "answer": (
                "현재 인덱싱된 문서에서 관련 내용을 찾지 못했습니다. "
                "문서가 인덱싱되어 있는지 확인하거나, 다른 표현으로 질문해 보세요."
            ),
            "sources": raw_sources,
        }

    if search_type == "sql":
        answer = build_list_response(search_results, sources)
    else:
        answer = answer_from_documents(question, search_results, sources)

    return {"answer": answer, "sources": raw_sources}
```

- [ ] **Step 2: 커밋**

```bash
git add ai_llm/internal_rag_agent/agent.py
git commit -m "fix(rag): 검색 실패 시 더 명확한 안내 메시지로 개선"
```

---

## Task 6: 통합 테스트 + PR

**Files:**
- 없음 (서버 실행 후 수동 테스트)

- [ ] **Step 1: RAG 에이전트 서버 실행**

터미널 1:
```bash
cd ai_llm/internal_rag_agent
python agent_server.py
```

Expected: `[RAG AGENT] 서버 시작` 로그 확인

- [ ] **Step 2: 검색 테스트 — 기존 인덱싱 문서 조회**

터미널 2:
```bash
python test_client.py --agent rag --query "인덱싱된 문서 내용 요약해줘"
```

Expected: 이전에는 "답변할 수 없습니다"였던 응답이 실제 문서 내용 기반 답변으로 변경

- [ ] **Step 3: 검색 테스트 — 구어체 질문**

```bash
python test_client.py --agent rag --query "우리 회사 AI 관련 자료 있어?"
```

Expected: 쿼리 재작성 로그(`[RAG SEARCH] 쿼리 재작성:`) + 멀티 쿼리 로그 + 답변 반환

- [ ] **Step 4: 인덱싱 테스트 — 새 문서 인덱싱**

Google Drive 파일 1개로 인덱싱 요청 후 로그에서 INSERT가 1번만 실행되는지 확인:
```
[INDEXING] 인덱싱 완료: xxx.pdf, N개 청크
```
(N번의 `[INDEXING] 저장 중` 로그 대신 한 번에 완료)

- [ ] **Step 5: PR 생성**

```bash
git push origin feat/rag-quality-improvement
```

PR 제목: `feat: RAG 검색 버그 수정 및 쿼리 재작성·멀티쿼리·배치 INSERT 고도화`

PR description은 아래 내용 포함:
- 근본 원인: Supabase match_documents RPC threshold 하드코딩 문제
- 수정: threshold 파라미터화 (0.3), match_count 10으로 증가
- 개선: 쿼리 재작성 + 멀티 쿼리 (4개 쿼리 병렬 검색 + 중복 제거)
- 개선: 배치 INSERT (N번 → 1번 DB 요청)
- 개선: 청크 크기 500→800, 오버랩 50→150
