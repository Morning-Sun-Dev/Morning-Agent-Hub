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

## 작업 기준 문서

팀원이 같은 기준으로 작업할 수 있도록 폴더별 `AGENTS.md`를 둡니다. Codex와 다른 코딩 에이전트는 가까운 `AGENTS.md`를 우선 참고하므로, 공통 규칙은 루트에 두고 세부 규칙은 담당 폴더에 둡니다.

| 위치 | 용도 |
|------|------|
| `AGENTS.md` | 저장소 전체 작업 규칙, 검증, PR 기준 |
| `ai_llm/AGENTS.md` | A2A 에이전트 공통 규칙 |
| `ai_llm/*_agent/AGENTS.md` | 개별 에이전트 책임과 artifact 규칙 |
| `backend/AGENTS.md` | FastAPI 라우트, 스키마, SSE 계약 |
| `frontend/AGENTS.md` | Vue UI, API adapter, 화면 테스트 기준 |
| `common/AGENTS.md` | 공유 계약 모델 변경 기준 |
| `tests/AGENTS.md` | 회귀 테스트 배치와 실행 기준 |
| `.github/AGENTS.md` | PR 템플릿, 이슈 템플릿, CI 변경 기준 |

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
| `/api/capabilities` | GET | 에이전트 기능 및 UI 지원 상태 목록 |
| `/api/report-templates` | GET | 보고서 양식 목록 |
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

### 통합 Smoke

백엔드와 에이전트들을 실행한 뒤 로컬 REST/SSE 계약을 한 번에 확인합니다.

```bash
python scripts/smoke_system.py
python scripts/smoke_system.py --file ./sample.pdf
python scripts/smoke_system.py --skip-chat --json
```

## 파일 구조

```
Morning-Agent-Hub/
├── AGENTS.md                    # 저장소 전체 작업 기준
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
