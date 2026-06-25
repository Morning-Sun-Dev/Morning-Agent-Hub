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
| Orchestrator | 10010 | Intent 분석, 플랜 생성, 에이전트 조율 |
| Web Research | 10011 | Tavily MCP 기반 웹/뉴스 검색 |
| Internal RAG | 10012 | Supabase pgvector 기반 사내 문서 검색/인덱싱 |
| File Management | 10013 | Google Drive 파일 관리 |
| **Report Writing** | **10014** | **양식 기반 보고서 작성 (FastAPI)** |

## 보고서 작성 에이전트

다른 에이전트에서 수집한 데이터를 지정된 양식에 맞춰 마크다운 보고서로 작성합니다.

**지원 양식:**

| ID | 이름 | 용도 |
|----|------|------|
| `executive_summary` | 임원 요약 보고서 | 핵심 결론, 권고사항 중심 |
| `research_report` | 조사 보고서 | 웹/RAG 조사 결과 정리 |
| `technical_report` | 기술 보고서 | 기술 분석, 아키텍처 |
| `meeting_minutes` | 회의록 | 논의, 결정, 액션 아이템 |
| `general` | 일반 보고서 | 범용 양식 |

**워크플로우 예시:**

```
"AI 트렌드 조사 후 조사 보고서로 작성"
  → web_research → report_writing

"사내 문서 검색 후 임원 보고서 작성"
  → internal_rag → report_writing

"조사 → 보고서 → Drive 저장"
  → web_research → report_writing → file_management
```

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
python backend/main.py
```

### 방법 2: 개별 시작

각 터미널에서 순서대로 실행:

```bash
cd web_research_agent && python agent_server.py      # :10011
cd internal_rag_agent && python agent_server.py      # :10012
cd file_management_agent && python agent_server.py   # :10013
cd report_writing_agent && python agent_server.py    # :10014 (FastAPI)
cd orchestrator_agent && python agent_server.py      # :10010
python backend/main.py                               # :8000
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
  -d '{"query": "AI 트렌드를 조사해서 조사 보고서로 작성해줘"}'
```

### CLI 테스트

```bash
python test_client.py
```

## 파일 구조

```
CHAP11_final-project/
├── README.md
├── requirements.txt
├── start_agents.py             # 에이전트 일괄 시작
├── test_client.py              # CLI 테스트 클라이언트
├── backend/
│   └── main.py                 # FastAPI REST API 게이트웨이 (:8000)
├── common/                     # 공통 스키마, 설정
├── orchestrator_agent/         # Host Agent (:10010)
├── web_research_agent/         # Remote Agent (:10011)
├── internal_rag_agent/         # Remote Agent (:10012)
├── file_management_agent/      # Remote Agent (:10013)
└── report_writing_agent/       # Remote Agent (:10014, FastAPI)
    ├── agent.py
    ├── agent_executor.py
    ├── agent_server.py
    └── templates.py            # 보고서 양식 정의
```
