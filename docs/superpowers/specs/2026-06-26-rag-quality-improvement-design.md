# RAG 품질 개선 (검색 오류 수정 + 기초 고도화) Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 항상 "답변할 수 없습니다"를 반환하는 RAG 검색 버그를 수정하고, 쿼리 재작성·멀티 쿼리·배치 INSERT로 검색 품질과 인덱싱 성능을 개선한다.

**Branch:** `feat/rag-quality-improvement`

---

## 문제 진단

현재 RAG는 문서 인덱싱은 정상 동작하지만 검색 시 항상 빈 결과를 반환한다.

**근본 원인 (추정):** Supabase `match_documents` RPC에 유사도 threshold가 하드코딩되어 있거나 기본값이 너무 높아 (예: 0.8) 모든 결과가 필터링됨.

**연쇄 문제:**
- `search_documents()` → 빈 리스트 반환
- `generate()` 노드 → `if not search_results:` 분기 → "관련 문서를 찾을 수 없습니다" 반환

---

## 변경 대상 파일

| 파일 | 변경 내용 |
|------|----------|
| `ai_llm/internal_rag_agent/indexing_service.py` | 청크 크기 500→800, 오버랩 50→150, 배치 INSERT |
| `ai_llm/internal_rag_agent/rag_search_service.py` | threshold 0.3 적용, match_count 10, 쿼리 재작성, 멀티 쿼리 |
| `ai_llm/internal_rag_agent/agent.py` | 검색 실패 메시지 개선 |
| Supabase SQL (대시보드) | `match_documents` RPC threshold 파라미터화 |

---

## Section 1: Supabase RPC 수정

`match_documents` 함수가 `match_threshold` 파라미터를 외부에서 받도록 수정한다.

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
    id, content, filename, storage_ref,
    chunk_index, document_type, created_at,
    1 - (embedding <=> query_embedding) AS similarity
  FROM documents
  WHERE 1 - (embedding <=> query_embedding) > match_threshold
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;
```

**실행 위치:** Supabase 대시보드 → SQL Editor

---

## Section 2: 인덱싱 개선 (indexing_service.py)

### 2-1. 청크 크기 조정

```python
# 변경 전
chunk_size: int = 500,
chunk_overlap: int = 50,

# 변경 후
chunk_size: int = 800,
chunk_overlap: int = 150,
```

500자는 한 문장이 잘리는 경우가 많아 맥락 손실이 크다. 800자로 늘려 단락 단위 맥락을 보존한다.

### 2-2. 배치 INSERT

```python
# 변경 전 — 청크 수만큼 N번 DB 요청
for i, (chunk, embedding) in enumerate(zip(chunks, embeddings_list)):
    row = {"content": chunk, "embedding": embedding, ...}
    sb.table("documents").insert(row).execute()

# 변경 후 — 1번 DB 요청
rows = []
for i, (chunk, embedding) in enumerate(zip(chunks, embeddings_list)):
    row = {
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
```

---

## Section 3: 검색 품질 개선 (rag_search_service.py)

### 3-1. search_documents() 시그니처 변경

```python
def search_documents(
    query: str,
    sb: Client,
    filters: Optional[Dict[str, Any]] = None,
    match_count: int = 10,          # 5 → 10
    match_threshold: float = 0.3,   # 신규 파라미터
) -> Tuple[List[Dict[str, Any]], List[Source]]:
```

RPC 호출 시 `match_threshold` 전달:
```python
response = sb.rpc("match_documents", {
    "query_embedding": query_embedding,
    "match_count": match_count,
    "match_threshold": match_threshold,
}).execute()
```

### 3-2. 쿼리 재작성 (rewrite_query)

사용자의 구어체 질문을 검색에 최적화된 키워드 중심 문장으로 변환한 뒤 임베딩한다.

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

### 3-3. 멀티 쿼리 생성 (generate_multi_queries)

재작성된 쿼리에서 표현을 달리한 3개 쿼리를 추가 생성한다.

```python
def generate_multi_queries(rewritten_query: str) -> List[str]:
    """재작성된 쿼리에서 3개 쿼리 변형 생성 (gpt-4o-mini)"""
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
    queries = lines[:3] if len(lines) >= 3 else lines
    logger.info(f"[RAG SEARCH] 멀티 쿼리 생성: {len(queries)}개")
    return queries
```

### 3-4. search_documents() 내부 — 멀티 쿼리 병렬 실행 + 중복 제거

```python
def search_documents(query, sb, filters=None, match_count=10, match_threshold=0.3):
    # 1. 쿼리 재작성
    rewritten = rewrite_query(query)

    # 2. 멀티 쿼리 생성 (재작성 쿼리 포함 총 4개)
    multi_queries = [rewritten] + generate_multi_queries(rewritten)

    # 3. 각 쿼리 임베딩 + 벡터 검색 (순차 실행 — Supabase 클라이언트가 비동기 미지원)
    seen_refs: Dict[str, Dict] = {}   # storage_ref+chunk_index → result (중복 제거)
    for q in multi_queries:
        q_embedding = _embeddings.embed_query(q)
        try:
            resp = sb.rpc("match_documents", {
                "query_embedding": q_embedding,
                "match_count": match_count,
                "match_threshold": match_threshold,
            }).execute()
            for r in (resp.data or []):
                key = f"{r.get('storage_ref')}:{r.get('chunk_index')}"
                if key not in seen_refs or r.get("similarity", 0) > seen_refs[key].get("similarity", 0):
                    seen_refs[key] = r
        except Exception as e:
            logger.error(f"[RAG SEARCH] 멀티 쿼리 검색 오류 ({q[:30]}): {e}")

    # 4. 유사도 내림차순 정렬, 상위 match_count개 선택
    results = sorted(seen_refs.values(), key=lambda r: r.get("similarity", 0), reverse=True)[:match_count]
    ...
```

---

## Section 4: 메시지 개선 (agent.py)

```python
# 변경 전
"관련 문서를 찾을 수 없습니다. 다른 검색어로 시도해주세요."

# 변경 후
"현재 인덱싱된 문서에서 관련 내용을 찾지 못했습니다. "
"문서가 인덱싱되어 있는지 확인하거나, 다른 표현으로 질문해 보세요."
```

---

## 데이터 흐름 (변경 후 검색 경로)

```
사용자 질문
  └→ rewrite_query()          # 구어체 → 검색 최적화 쿼리
       └→ generate_multi_queries()  # 3개 변형 쿼리 생성
            └→ 4개 쿼리 순차 벡터 검색 (match_threshold=0.3, match_count=10)
                 └→ 중복 제거 (storage_ref + chunk_index 키)
                      └→ 유사도 내림차순 정렬, 상위 10개
                           └→ answer_from_documents()  # gpt-4o 답변 생성
```

---

## 오류 처리

- 쿼리 재작성 실패 시: 원본 질문 그대로 사용 (fallback)
- 멀티 쿼리 생성 실패 시: 재작성 쿼리 1개만 사용 (fallback)
- 개별 쿼리 검색 실패 시: 해당 쿼리 스킵, 나머지 결과 사용
- 배치 INSERT 실패 시: `IndexJobStatus.ERROR` 반환 (기존 동작 유지)

---

## 테스트 시나리오

1. **기존 인덱싱 문서에 대한 검색** — 결과 반환 확인 (현재 실패 케이스)
2. **구어체 질문** — "우리 회사 휴가 어떻게 돼?" → 재작성 후 검색 성공 확인
3. **유사도 낮은 질문** — 전혀 관련 없는 질문 → "찾지 못했습니다" 메시지 확인
4. **문서 인덱싱** — 배치 INSERT 후 chunk_count 동일 확인

---

## 제약 사항

- Supabase RPC 수정은 대시보드에서 수동 실행 필요 (코드 자동화 불가)
- 기존 인덱싱 데이터는 재인덱싱 불필요 (임베딩 모델 변경 없음)
- 멀티 쿼리로 LLM 호출이 검색당 2회 추가됨 (gpt-4o-mini, 비용 미미)
