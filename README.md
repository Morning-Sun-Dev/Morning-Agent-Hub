# A2A 프로토콜 실전형 멀티 에이전트 시스템

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────┐
│         사용자 (Vue Frontend / FastAPI Backend / test_client.py)         │
└─────────────────────────────────────┬───────────────────────────────────┘
                                      │ REST / A2A
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Orchestrator Agent (Port: 10010)                      │
│  • Intent 분석 · Plan 생성 · plan_normalizer (depends_on 자동 보정)       │
│  • upstream 결과 → ReportContext 취합 · A2A Remote Agent 호출             │
└─────────────────────────────────────┬───────────────────────────────────┘
                                      │ A2A Protocol
          ┌───────────┬───────────┬───┴───┬───────────┐
          ▼           ▼           ▼       ▼           ▼
   Web Research  Internal RAG  File Mgmt  Report
   (Port:10011)  (Port:10012)  (Port:10013) Writing
                                              (Port:10014)
```

## 에이전트 구성

| 에이전트 | 포트 | 역할 |
|---------|------|------|
| Orchestrator | 10010 | Intent 분석, 플랜 생성·실행, ReportContext 취합, Trace |
| Web Research | 10011 | Tavily MCP 웹/뉴스 검색, 출처 추출 |
| Internal RAG | 10012 | Supabase pgvector 사내 문서 검색·인덱싱 |
| File Management | 10013 | Google Drive 파일 검색·읽기·업로드 |
| Report Writing | 10014 | 양식 예시(`format_example`) 기반 보고서 작성 |

## 보고서 작성 흐름

Orchestrator가 upstream 결과를 `[REPORT_CONTEXT]` JSON으로 Report Agent에 전달합니다.

| 필드 | 출처 | 용도 |
|------|------|------|
| `format_example` | Drive 양식 파일 전문 (`test.txt` 등) | **형식·구조** 그대로 mimic |
| `sources` (content) | `web_research` 등 | **본문**에 쓸 조사 자료 |
| `report_topic` | 사용자 질문 | 보고서 주제 (예: SQL) |

**내장 양식** (`executive_summary`, `research_report`, `technical_report`, `meeting_minutes`, `general`)은 Drive 양식 파일이 없을 때만 사용됩니다.

### 워크플로우 예시

```
"AI 트렌드 조사 후 조사 보고서로 작성"
  → web_research → report_writing

"test.txt 양식 참고해서 SQL 보고서 작성하고 Drive에 저장"
  → file_management (test.txt 읽기)
  → web_research (SQL 조사)
  → report_writing (양식 mimic + SQL 본문)
  → file_management (Drive 저장)
```

> `report_writing`은 upstream 완료 **후** 실행되어야 합니다. `plan_normalizer`가 `depends_on`을 자동 보정합니다.

## 환경 설정

### 1. 패키지 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 변수 (.env)

```bash
copy .env.example .env
```

```env
OPENAI_API_KEY=your_openai_key
TAVILY_API_KEY=your_tavily_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# 에이전트 URL (선택, 기본값 localhost)
ORCHESTRATOR_AGENT_URL=http://localhost:10010
WEB_AGENT_URL=http://localhost:10011
RAG_AGENT_URL=http://localhost:10012
FILE_AGENT_URL=http://localhost:10013
REPORT_AGENT_URL=http://localhost:10014
```

Google Drive 연동 시 `ai_llm/file_management_agent/credentials.json`이 필요합니다.

## 실행 방법

### 에이전트 일괄 시작 (Windows)

```bash
python start_agents.py
python start_agents.py --agent report   # 특정 에이전트만
```

### FastAPI 백엔드

```bash
python -m backend.api.main
```

기본 포트: **8000** · Swagger: http://localhost:8000/docs

### Vue 프론트엔드

```bash
cd frontend
npm install
npm run dev
```

기본 포트: **5173**

### 에이전트 개별 시작

```bash
cd ai_llm/web_research_agent && python agent_server.py      # :10011
cd ai_llm/internal_rag_agent && python agent_server.py      # :10012
cd ai_llm/file_management_agent && python agent_server.py   # :10013
cd ai_llm/report_writing_agent && python agent_server.py    # :10014
cd ai_llm/orchestrator_agent && python agent_server.py      # :10010
```

## FastAPI API (`backend.api.main`)

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/health` | GET | 서버 상태 |
| `/api/chat` | POST | 오케스트레이터에 질문 (동기) |
| `/api/chat/stream` | GET | SSE 스트리밍 (`message`, `session_id` 쿼리) |
| `/api/sessions` | GET | 채팅 세션 목록 |
| `/api/sessions/{id}/messages` | GET | 세션 대화 기록 |
| `/api/files/upload` | POST | 파일 Drive 업로드 + RAG 인덱싱 |
| `/docs` | GET | Swagger UI |

**POST /api/chat 예시:**

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"AI 트렌드를 조사해서 조사 보고서로 작성해줘\"}"
```

**GET /api/chat/stream 예시 (프론트엔드 사용):**

```bash
curl -N "http://localhost:8000/api/chat/stream?message=안녕하세요"
```

### CLI 테스트 (A2A 직접)

```bash
python test_client.py
```

## 테스트

```bash
python -m pytest ai_llm -v --tb=short
```

## 파일 구조

```
CHAP11_final-project/
├── README.md
├── requirements.txt
├── start_agents.py             # 에이전트 일괄 시작
├── stop_agents.py
├── test_client.py              # A2A CLI 테스트
├── backend/
│   ├── main.py                 # (레거시) 이전 FastAPI 게이트웨이 — 사용하지 않음
│   └── api/                    # 현재 REST API (main.py)
│       ├── main.py
│       └── routers/            # chat, sessions, files
├── frontend/                   # Vue.js 웹 UI
├── common/                     # A2A 클라이언트 래퍼 등
├── docs/                       # 에이전트 평가·설계 문서
└── ai_llm/
    ├── shared/                   # ReportContext 등 공통 계약
    ├── orchestrator_agent/     # Host Agent (:10010)
    │   ├── plan_normalizer.py
    │   └── report_context_builder.py
    ├── web_research_agent/     # (:10011)
    ├── internal_rag_agent/     # (:10012)
    ├── file_management_agent/  # (:10013)
    └── report_writing_agent/   # (:10014)
```
