# A2A 프로토콜 실전형 멀티 에이전트 시스템

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────┐
│              사용자 (CLI / FastAPI Backend / test_client.py)             │
└─────────────────────────────────────┬───────────────────────────────────┘
                                      │ A2A Request / REST API
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Orchestrator Agent (Port: 10010)                      │
│  • Intent 분석 (LLM)  • Plan 생성  • A2A Client로 Remote Agent 호출      │
│  • 병렬/순차 실행  • 실행 Trace 추적                                      │
└─────────────────────────────────────┬───────────────────────────────────┘
                                      │ A2A Protocol
          ┌───────────┬───────────┬───┴───┬───────────┐
          ▼           ▼           ▼       ▼           ▼
   Web Research  Internal RAG  File Mgmt  Report    (Infrastructure)
   (Port:10011)  (Port:10012)  (Port:10013) Writing
                                              (Port:10014)
```

## 에이전트 구성

| 에이전트 | 포트 | 역할 |
|---------|------|------|
| Orchestrator | 10010 | Intent 분석, 플랜 생성, 에이전트 조율, 실행 Trace |
| Web Research | 10011 | Tavily MCP 기반 웹/뉴스 검색, 출처 추출 |
| Internal RAG | 10012 | Supabase pgvector 기반 사내 문서 검색/인덱싱 |
| File Management | 10013 | Google Drive 파일 관리 |
| **Report Writing** | **10014** | **양식 기반 보고서 작성 (FastAPI)** |

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

## 환경 설정

### 1. 패키지 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정 (.env)

```bash
copy .env.example .env
```

```env
OPENAI_API_KEY=your_openai_key
TAVILY_API_KEY=your_tavily_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
REPORT_AGENT_URL=http://localhost:10014
# credentials.json 파일 필요 (Google Cloud Console에서 발급)
```

## 실행 방법

### 방법 1: 일괄 시작 (Windows)

```bash
python start_agents.py
```

모든 에이전트를 별도 콘솔 창에서 시작합니다. 이후 FastAPI 백엔드를 실행합니다:

```bash
python -m backend.api.main
```

### 방법 2: 개별 시작

각 터미널에서 순서대로 실행:

```bash
cd ai_llm/web_research_agent && python agent_server.py      # :10011
cd ai_llm/internal_rag_agent && python agent_server.py      # :10012
cd ai_llm/file_management_agent && python agent_server.py   # :10013
cd ai_llm/report_writing_agent && python agent_server.py    # :10014
cd ai_llm/orchestrator_agent && python agent_server.py      # :10010
python -m backend.api.main                                  # :8000
```

### FastAPI 백엔드 API

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/health` | GET | 에이전트 상태 확인 |
| `/api/chat` | POST | 오케스트레이터에 질문 전달 |
| `/api/report-templates` | GET | 보고서 양식 목록 |
| `/docs` | GET | Swagger API 문서 |

**사용 예:**

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "AI 트렌드를 조사해서 조사 보고서로 작성해줘"}'
```

### CLI 테스트

```bash
python test_client.py
```

## 파일 구조

```
Morning-Agent-Hub/
├── AGENTS.md                    # 저장소 전체 작업 기준
├── README.md
├── requirements.txt
├── start_agents.py             # 에이전트 일괄 시작
├── test_client.py              # CLI 테스트 클라이언트
├── .github/                    # CI, PR/Issue 템플릿, GitHub 작업 기준
├── backend/
│   ├── AGENTS.md               # 백엔드 작업 기준
│   ├── main.py                 # FastAPI 게이트웨이 (:8000)
│   └── api/                    # REST API (세션, 채팅, 파일 업로드)
├── frontend/                   # Vue.js 웹 UI, 프론트 작업 기준 포함
├── common/                     # 공통 스키마, 설정, A2A 클라이언트
├── tests/                      # 백엔드/계약 회귀 테스트
└── ai_llm/
    ├── orchestrator_agent/     # Host Agent (:10010)
    ├── web_research_agent/     # Remote Agent (:10011)
    ├── internal_rag_agent/     # Remote Agent (:10012)
    ├── file_management_agent/  # Remote Agent (:10013)
    └── report_writing_agent/   # Remote Agent (:10014)
```
