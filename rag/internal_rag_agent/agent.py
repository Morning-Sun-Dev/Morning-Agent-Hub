import os
import io
import logging
from typing import TypedDict, Literal, List, Dict, Any, AsyncIterator, Optional
from dotenv import load_dotenv

from pydantic import BaseModel, Field

from supabase import create_client, Client

from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

# M-005 Document Parser
from document_parser import validate_file_format

# M-006 Indexing Service
from indexing_service import index_document, IndexJobStatus

# M-007 RAG Search Service
from rag_search_service import (
    Source,
    search_documents,
    search_documents_by_metadata,
    extract_sql_filters,
    answer_from_documents,
    build_list_response,
)


logger = logging.getLogger(__name__)

load_dotenv()


INTENT_SEARCH = "search"    # 검색 (기본)
INTENT_INDEX = "index"      # 문서 인덱싱


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = None


def get_supabase() -> Client:
    """Supabase 클라이언트 싱글톤"""
    global supabase
    if supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL, SUPABASE_KEY 환경변수 필요")
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return supabase


llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


# ============================================================================
# Google Drive 읽기 전용 헬퍼 (storage_ref 기반)
# ============================================================================

# Google Drive API
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# 프로젝트 루트 기준 경로 (file_management_agent와 공유)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CREDENTIALS_PATH = os.path.join(_PROJECT_ROOT, 'file_management_agent', 'credentials.json')
_TOKEN_PATH = os.path.join(_PROJECT_ROOT, 'file_management_agent', 'token.json')


class _GDriveReadOnlyClient:
    """
    Google Drive 읽기 전용 클라이언트

    File Agent가 반환한 storage_ref (file_id)로만 접근 가능.
    목록 조회, 검색, 생성, 삭제 등 불가.
    """

    def __init__(self):
        self.service = None
        self._initialized = False

    def _ensure_initialized(self):
        if self._initialized:
            return

        creds = None
        if os.path.exists(_TOKEN_PATH):
            creds = Credentials.from_authorized_user_file(_TOKEN_PATH, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(_CREDENTIALS_PATH):
                    raise FileNotFoundError(f"credentials.json not found: {_CREDENTIALS_PATH}")
                flow = InstalledAppFlow.from_client_secrets_file(_CREDENTIALS_PATH, SCOPES)
                creds = flow.run_local_server(port=0)

            with open(_TOKEN_PATH, 'w') as token:
                token.write(creds.to_json())

        self.service = build('drive', 'v3', credentials=creds)
        self._initialized = True
        logger.info("[RAG AGENT] [INIT] Google Drive 읽기 전용 클라이언트 초기화 완료")

    def download_file(self, file_id: str) -> tuple[bytes, str, str]:
        """
        file_id로 파일 다운로드 (읽기 전용)

        Args:
            file_id: Google Drive 파일 ID

        Returns:
            (file_bytes, filename, mime_type)
        """
        self._ensure_initialized()

        # 파일 메타데이터 조회
        info = self.service.files().get(
            fileId=file_id,
            fields='id, name, mimeType'
        ).execute()

        filename = info['name']
        mime_type = info['mimeType']

        logger.info(f"[RAG AGENT] [DOWNLOAD] 파일 다운로드 시작: {filename} ({mime_type})")

        # Google Docs 형식인 경우 PDF로 export
        google_export_mapping = {
            'application/vnd.google-apps.document': 'application/pdf',
            'application/vnd.google-apps.spreadsheet': 'application/pdf',
            'application/vnd.google-apps.presentation': 'application/pdf',
        }

        if mime_type in google_export_mapping:
            export_mime = google_export_mapping[mime_type]
            request = self.service.files().export_media(fileId=file_id, mimeType=export_mime)
            mime_type = export_mime
        else:
            request = self.service.files().get_media(fileId=file_id)

        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        file_bytes = buffer.getvalue()
        logger.info(f"[RAG AGENT] [DOWNLOAD] 파일 다운로드 완료: {filename}, {len(file_bytes)} bytes")

        return file_bytes, filename, mime_type


_gdrive_client = _GDriveReadOnlyClient()


def download_by_storage_ref(storage_ref: str) -> tuple[bytes, str, str]:
    """
    storage_ref로 파일 다운로드

    Args:
        storage_ref: 저장소 참조 (예: gdrive://file/abc123)

    Returns:
        (file_bytes, filename, mime_type)

    Raises:
        ValueError: 지원하지 않는 프로토콜
    """
    if storage_ref.startswith("gdrive://file/"):
        file_id = storage_ref.replace("gdrive://file/", "")
        return _gdrive_client.download_file(file_id)
    elif storage_ref.startswith("gdrive://"):
        file_id = storage_ref.replace("gdrive://", "")
        return _gdrive_client.download_file(file_id)
    else:
        raise ValueError(f"지원하지 않는 storage_ref 프로토콜: {storage_ref}")


# ============================================================================
# State 정의
# ============================================================================

class RAGState(TypedDict):
    """RAG 에이전트 상태"""
    intent: str                      # 인텐트: search, index
    raw_input: str                   # 원본 입력
    question: str                    # 검색 질문
    search_type: str                 # 검색 방식: vector, sql
    search_results: List[Dict]       # 검색 결과
    sources: List[Dict]              # 출처 정보
    index_request: Optional[Dict]    # 인덱싱 요청 데이터
    index_result: Optional[Dict]     # 인덱싱 결과
    answer: str                      # 최종 답변


# ============================================================================
# Intent Router용 구조화된 출력 스키마 (Pydantic)
# ============================================================================

class FileInfo(BaseModel): # [ 1 ]
    """인덱싱할 파일 정보"""
    filename: str = Field(description="파일명")
    storage_ref: str = Field(description="Google Drive 파일 참조 (gdrive://file/xxx 형식)")


class IntentClassification(BaseModel): # [ 2 ]
    """
    사용자 요청의 의도 분류 결과

    - search: 문서 검색, 질문 답변, 정보 조회
    - index: 문서 인덱싱, 저장, 등록
    """
    intent: Literal["search", "index"] = Field(description="search: 문서 검색, index: 문서 인덱싱")
    question: Optional[str] = Field(default=None, description="search일 때 검색 질문")
    files: Optional[List[FileInfo]] = Field(default=None, description="index일 때 인덱싱할 파일 목록")


class SearchTypeClassification(BaseModel): # [ 3 ]
    """
    검색 방식 분류 결과

    - vector: 의미 기반 벡터 검색
    - sql: 메타데이터 조건 검색
    """
    search_type: Literal["vector", "sql"] = Field(description="vector: 의미 기반 검색, sql: 메타데이터 조건 검색")


# ============================================================================
# 노드 함수들
# ============================================================================

def intent_router(state: RAGState) -> RAGState:
    """
    자연어 입력을 분석하여 인텐트 결정 (검색 vs 인덱싱)

    LangChain의 structured output (bind_tools)를 사용하여 구조화된 출력 보장
    """
    logger.info("[RAG AGENT] [INTENT ROUTER] 시작")
    raw_input = state.get("raw_input", "") # [ 1 ]

    messages = [
        {
            "role": "system",
            "content": """사용자 요청을 분석하여 의도를 파악하고 필요한 정보를 추출하세요.

## 의도 분류
1. search - 문서 검색, 질문 답변, 정보 조회
2. index - 문서 인덱싱, 저장, 등록 요청

## 중요: 파일 선택 규칙 (index인 경우)
요청에 여러 파일이 있을 때, 사용자 의도에 따라 선택하세요:
- "하나만", "첫 번째만", "한 개" → 첫 번째 파일 1개만 선택
- "3개만", "세 개" → 처음 3개만 선택
- "전부", "모든", "다" → 모든 파일 선택
- 수량 지정 없음 → 모든 파일 선택

파일 정보는 "filename (gdrive://file/xxx)" 형식에서 추출하세요.

## 응답 규칙
- search: question 필드에 검색 질문 작성, files는 null
- index: files 배열에 선택된 파일 정보 작성, question은 null"""
        },
        {
            "role": "user",
            "content": raw_input
        }
    ]

    structured_llm = llm.with_structured_output(IntentClassification) # [ 2 ]
    result = structured_llm.invoke(messages)

    if result.intent == "index": # [ 3 ]
        files = result.files or []
        if files:
            files_dict = [f.model_dump() for f in files]
            logger.info(f"[RAG AGENT] [INTENT ROUTER] INDEX: {len(files_dict)}개 파일 선택됨")
            return {
                "intent": INTENT_INDEX,
                "index_request": {"files": files_dict},
                "question": "",
            }
        else:
            logger.warning(f"[RAG AGENT] [INTENT ROUTER] INDEX 의도지만 files가 비어있음")
            return {
                "intent": INTENT_SEARCH,
                "question": raw_input,
                "index_request": None,
            }
    else:
        question = result.question or raw_input # [ 4 ]
        logger.info(f"[RAG AGENT] [INTENT ROUTER] SEARCH: {question[:50]}...")
        return {
            "intent": INTENT_SEARCH,
            "question": question,
            "index_request": None,
        }


def search_router(state: RAGState) -> RAGState:
    logger.info("[RAG AGENT] [SEARCH ROUTER] 시작")
    question = state["question"]

    messages = [
        {
            "role": "system",
            "content": """사용자 질문을 분석하여 적절한 검색 방식을 선택하세요.

검색 방식:
1. vector - 의미 기반 검색 (기본값, 대부분 질문에 적합)
   - 내용 검색: "AI 트렌드", "휴가 규정", "보안 정책"
   - 파일 위치/출처 요청: "원본 파일 위치", "문서 찾아줘"
   - 정보 조회: "~에 대해 알려줘", "~가 뭐야?"

2. sql - 메타데이터 조건 검색 (내용이 아닌 속성으로 필터할 때)
   - 파일 형식 필터: "PDF 문서만", "Excel 파일 목록"
   - 파일명 검색: "SPRi 파일 목록", "Brief 문서들"
   - 날짜 필터: "오늘 인덱싱된 문서", "이번 주 문서", "12월 문서"
   - 목록 조회: "인덱싱된 모든 파일", "문서 목록"

중요: 문서 내용에 대한 질문은 항상 vector를 선택하세요."""
        },
        {
            "role": "user",
            "content": question
        }
    ]

    structured_llm = llm.with_structured_output(SearchTypeClassification)
    result: SearchTypeClassification = structured_llm.invoke(messages)
    logger.info(f"[RAG AGENT] [SEARCH ROUTER] 검색 방식: {result.search_type}")
    return {"search_type": result.search_type}


def vector_search(state: RAGState) -> RAGState:
    """벡터 유사도 검색 — M-007 search_documents() 위임"""
    logger.info("[RAG AGENT] [VECTOR SEARCH] 시작")
    results, sources = search_documents(state["question"], get_supabase())
    return {"search_results": results, "sources": [s.to_dict() for s in sources]}


def sql_search(state: RAGState) -> RAGState:
    """SQL 메타데이터 검색 — M-007 search_documents_by_metadata() 위임"""
    logger.info("[RAG AGENT] [SQL SEARCH] 시작")
    filters = extract_sql_filters(state["question"])
    logger.info(f"[RAG AGENT] [SQL SEARCH] 추출된 조건: {filters}")
    results, sources = search_documents_by_metadata(get_supabase(), filters)
    return {"search_results": results, "sources": [s.to_dict() for s in sources]}


def generate(state: RAGState) -> RAGState:
    """답변 생성 — M-007 answer_from_documents() / build_list_response() 위임"""
    logger.info("[RAG AGENT] [GENERATE] 시작")
    question = state["question"]
    search_type = state.get("search_type", "vector")
    search_results = state.get("search_results", [])
    raw_sources = state.get("sources", [])
    sources = [Source(**s) for s in raw_sources]  # dict → Source 객체

    if not search_results:
        return {"answer": "관련 문서를 찾을 수 없습니다. 다른 검색어로 시도해주세요.", "sources": raw_sources}

    if search_type == "sql":
        answer = build_list_response(search_results, sources)      # M-007
    else:
        answer = answer_from_documents(question, search_results, sources)  # M-007

    return {"answer": answer, "sources": raw_sources}


def index_document_node(state: RAGState) -> RAGState:
    """문서 인덱싱 — M-006 index_document() 위임"""
    logger.info("[RAG AGENT] [INDEX] 시작")

    index_request = state.get("index_request", {})
    if not index_request:
        return {"index_result": {"status": "error", "message": "인덱싱 요청 데이터가 없습니다."}, "answer": "인덱싱 요청 데이터가 없습니다."}

    files_to_index = index_request.get("files", [])
    if not files_to_index:
        return {"index_result": {"status": "error", "message": "인덱싱할 파일이 없습니다."}, "answer": "인덱싱할 파일이 없습니다."}

    logger.info(f"[RAG AGENT] [INDEX] {len(files_to_index)}개 파일 처리")
    sb = get_supabase()
    all_results = []

    for file_info in files_to_index:
        storage_ref = file_info.get("storage_ref", "")
        filename = file_info.get("filename", "")
        logger.info(f"[RAG AGENT] [INDEX] 파일 처리 중: {filename} ({storage_ref})")

        try:
            file_bytes, downloaded_filename, mime_type = download_by_storage_ref(storage_ref)
            # M-006: 파싱(M-005) + 청크 분할 + 임베딩 + 저장 + 중복 방지(F-011)
            job = index_document(
                sb=sb,
                storage_ref=storage_ref,
                filename=downloaded_filename or filename,
                file_bytes=file_bytes,
                mime_type=mime_type,
            )
            all_results.append(job.to_dict())
            logger.info(f"[RAG AGENT] [INDEX] {job.status.value}: {job.filename}, 청크 {job.chunk_count}개")
        except Exception as e:
            logger.error(f"[RAG AGENT] [INDEX] [ERROR] 다운로드 실패: {filename}, {e}")
            all_results.append({"status": "error", "filename": filename, "storage_ref": storage_ref, "chunk_count": 0, "error": str(e)})

    success_count = sum(1 for r in all_results if r.get("status") == IndexJobStatus.SUCCESS.value)
    skip_count = sum(1 for r in all_results if r.get("status") == IndexJobStatus.SKIPPED.value)

    answer_parts = [f"✅ 문서 인덱싱 완료 ({success_count}/{len(all_results)}개 성공, {skip_count}개 중복 스킵)"]
    for r in all_results:
        if r.get("status") == IndexJobStatus.SUCCESS.value:
            answer_parts.append(f"  {r['filename']}: {r['chunk_count']}개 청크")
        elif r.get("status") == IndexJobStatus.SKIPPED.value:
            answer_parts.append(f"  {r['filename']}: 이미 인덱싱됨 (스킵)")
        else:
            answer_parts.append(f"  {r.get('filename', 'unknown')}: {r.get('error', '알 수 없는 오류')}")

    return {"index_result": {"status": "success", "results": all_results}, "answer": "\n".join(answer_parts)}


# ============================================================================
# 조건부 엣지를 위한 라우팅 함수
# ============================================================================

def route_intent(state: RAGState) -> Literal["search_router", "index_document_node"]: # [ 1 ]
    """인텐트에 따라 검색/인덱싱 분기"""
    intent = state.get("intent", INTENT_SEARCH)

    if intent == INTENT_INDEX:
        return "index_document_node"
    else:
        return "search_router"


def route_search(state: RAGState) -> Literal["vector_search", "sql_search"]: # [ 2 ]
    """검색 방식에 따라 분기"""
    search_type = state.get("search_type", "vector")

    if search_type == "sql":
        return "sql_search"
    else:
        return "vector_search"


# ============================================================================
# LangGraph 그래프 생성
# ============================================================================

def create_rag_graph():
    """
    RAG 에이전트 그래프 생성

    그래프 구조:

        START
          │
          ▼
      intent_router
          │
          ├──────────────────┐
          │                  │
          ▼                  ▼
    search_router     index_document_node
          │                  │
       ┌──┴──┐              │
       │     │              │
       ▼     ▼              │
    vector  sql             │
       │     │              │
       └──┬──┘              │
          │                  │
          ▼                  │
       generate              │
          │                  │
          ├──────────────────┘
          │
          ▼
         END
    """

    graph_builder = StateGraph(RAGState)

    graph_builder.add_node("intent_router", intent_router)
    graph_builder.add_node("search_router", search_router)
    graph_builder.add_node("vector_search", vector_search)
    graph_builder.add_node("sql_search", sql_search)
    graph_builder.add_node("generate", generate)
    graph_builder.add_node("index_document_node", index_document_node)

    graph_builder.add_edge(START, "intent_router")

    graph_builder.add_conditional_edges(
        "intent_router",
        route_intent,
        {
            "search_router": "search_router",
            "index_document_node": "index_document_node"
        }
    )

    graph_builder.add_conditional_edges(
        "search_router",
        route_search,
        {
            "vector_search": "vector_search",
            "sql_search": "sql_search"
        }
    )

    graph_builder.add_edge("vector_search", "generate")
    graph_builder.add_edge("sql_search", "generate")
    graph_builder.add_edge("generate", END)
    graph_builder.add_edge("index_document_node", END)

    return graph_builder.compile()


graph = create_rag_graph()

class InternalRAGAgent:
    """
    Internal RAG 에이전트

    독립적인 LangGraph 에이전트로 실행 가능하며,
    A2A 프로토콜 래퍼에서도 사용됩니다.

    지원 기능:
    1. 검색 (자연어 질문) → vector/sql 라우팅
    2. 인덱싱 (구조화된 JSON 요청) → 문서 임베딩 & 저장
    """

    NODE_MESSAGES = { # [ 1 ]
        "intent_router": "🎯 요청 분석 중...",
        "search_router": "🔍 검색 방식 결정 중...",
        "vector_search": "📊 벡터 유사도 검색 중...",
        "sql_search": "🗃️ 메타데이터 검색 중...",
        "generate": "📝 답변 생성 중...",
        "index_document_node": "📥 문서 인덱싱 중...",
    }

    def __init__(self):
        self.graph = create_rag_graph()

    async def stream(
        self,
        query: str
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        LangGraph 스트리밍 실행

        각 노드 실행 시 상태를 yield합니다.

        Args:
            query: 자연어 질문 또는 JSON 형식의 요청
                   - 자연어: "휴가 규정 알려줘" → 검색
                   - JSON: {"intent": "index", "content": "...", ...} → 인덱싱

        Yields:
            Dict with is_task_complete, require_user_input, content
        """
        inputs = {"raw_input": query} # [ 2 ]
        final_state = None

        async for event in self.graph.astream(inputs, stream_mode="updates"):
            for node_name, node_output in event.items():
                message = self.NODE_MESSAGES.get(node_name, f"처리 중: {node_name}")
                yield {
                    "is_task_complete": False,
                    "require_user_input": False,
                    "content": message,
                }

                if node_name in ("generate", "index_document_node"):
                    final_state = node_output

        answer = final_state.get("answer", "처리 결과가 없습니다.") if final_state else "처리 결과가 없습니다." # [ 3 ]
        yield {
            "is_task_complete": True,
            "require_user_input": False,
            "content": answer,
        }


if __name__ == "__main__":
    import asyncio

    async def test():
        try:
            png_bytes = graph.get_graph().draw_mermaid_png()
            with open("rag_graph.png", "wb") as f:
                f.write(png_bytes)
            print("그래프 이미지 저장: rag_graph.png")
        except Exception as e:
            print(f"(그래프 시각화 생략: {e})")

        print("\n" + "=" * 60)
        print("Internal RAG Agent 테스트")
        print("=" * 60)

        agent = InternalRAGAgent()
        query = "AI 트렌드 관련 내용이 담긴 문서 찾아줘"

        print(f"\n👤 Query: {query}")
        print("-" * 60)

        async for chunk in agent.stream(query):
            content = chunk.get("content", "")
            is_complete = chunk.get("is_task_complete", False)

            if not is_complete:
                print(f"{content}")
            else:
                print(f"\n💬 {content}")

    asyncio.run(test())
