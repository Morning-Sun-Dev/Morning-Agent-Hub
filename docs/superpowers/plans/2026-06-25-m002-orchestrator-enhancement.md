# M-002 Orchestrator Agent Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Orchestrator Agent를 Pydantic 구조화 출력 기반 Intent 분류, 병렬 에이전트 실행, TraceStep 추적, 자동 재시도로 고도화한다.

**Architecture:** 기존 JSON 문자열 파싱 방식의 Intent 분류를 Pydantic structured output으로 교체하고, 독립 에이전트는 asyncio.gather로 병렬 실행하며, 각 단계를 TraceStep으로 기록해 F-017 실행 과정 표시를 지원한다.

**Tech Stack:** Python 3.11+, OpenAI (gpt-4o-mini), Pydantic v2, asyncio, tenacity, a2a-sdk, pytest, pytest-asyncio

---

## 파일 구조

```
ai_llm/orchestrator_agent/
├── models.py          # 신규: Pydantic 모델 (IntentPlan, TraceStep, AgentResult)
├── agent.py           # 수정: 고도화 로직 전면 교체
├── agent_executor.py  # 수정: TraceStep artifacts 반환 추가
├── agent_server.py    # 유지
└── tests/
    └── test_agent.py  # 신규: 단위 테스트
```

---

## Task 1: Pydantic 모델 정의

**Files:**
- Create: `ai_llm/orchestrator_agent/models.py`
- Create: `ai_llm/orchestrator_agent/tests/__init__.py`
- Create: `ai_llm/orchestrator_agent/tests/test_agent.py`

- [ ] **Step 1: models.py 생성**

```python
# ai_llm/orchestrator_agent/models.py
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    """단일 에이전트 실행 단계"""
    agent: Literal["internal_rag", "web_research", "file_management"]
    query: str = Field(description="에이전트에 전달할 자연어 요청")
    depends_on: Optional[int] = Field(
        default=None,
        description="의존하는 이전 step 인덱스 (0부터 시작). None이면 독립 실행 가능"
    )


class IntentPlan(BaseModel):
    """Intent 분류 및 실행 계획"""
    intent: Literal["INTERNAL_SEARCH", "WEB_SEARCH", "FILE_OPERATION", "HYBRID", "DIRECT"]
    plan: List[PlanStep] = Field(default_factory=list)
    direct_answer: Optional[str] = Field(
        default=None,
        description="DIRECT intent일 때 직접 답변"
    )


class TraceStep(BaseModel):
    """에이전트 실행 과정 단계 (F-017)"""
    step: int
    agent: str
    status: Literal["started", "completed", "failed", "skipped"]
    message: str
    duration_ms: Optional[int] = None


class AgentResult(BaseModel):
    """단일 에이전트 실행 결과"""
    agent: str
    success: bool
    content: str
    trace: TraceStep
```

- [ ] **Step 2: tests/__init__.py 생성**

```python
# ai_llm/orchestrator_agent/tests/__init__.py
```

- [ ] **Step 3: 모델 테스트 작성**

```python
# ai_llm/orchestrator_agent/tests/test_agent.py
import pytest
from models import IntentPlan, PlanStep, TraceStep, AgentResult


def test_intent_plan_direct():
    plan = IntentPlan(intent="DIRECT", direct_answer="안녕하세요!")
    assert plan.intent == "DIRECT"
    assert plan.direct_answer == "안녕하세요!"
    assert plan.plan == []


def test_plan_step_independent():
    step = PlanStep(agent="web_research", query="AI 트렌드 검색", depends_on=None)
    assert step.depends_on is None


def test_plan_step_dependent():
    step = PlanStep(agent="internal_rag", query="파일 인덱싱", depends_on=0)
    assert step.depends_on == 0


def test_trace_step():
    trace = TraceStep(step=0, agent="web_research", status="completed", message="검색 완료", duration_ms=1200)
    assert trace.status == "completed"
    assert trace.duration_ms == 1200


def test_agent_result():
    trace = TraceStep(step=0, agent="web_research", status="completed", message="완료")
    result = AgentResult(agent="web_research", success=True, content="결과", trace=trace)
    assert result.success is True
```

- [ ] **Step 4: 테스트 실행 (PASS 확인)**

```bash
cd ai_llm/orchestrator_agent
pytest tests/test_agent.py -v
```

Expected: 5 passed

- [ ] **Step 5: 커밋**

```bash
git add ai_llm/orchestrator_agent/models.py ai_llm/orchestrator_agent/tests/
git commit -m "[F-002][M-002] Pydantic 모델 정의 (IntentPlan, TraceStep, AgentResult)"
```

---

## Task 2: Intent 분류 고도화 (Pydantic structured output)

**Files:**
- Modify: `ai_llm/orchestrator_agent/agent.py`

기존 `analyze_intent`는 JSON 문자열을 파싱하는 방식이다. 이를 `with_structured_output(IntentPlan)`으로 교체한다.

- [ ] **Step 1: 테스트 먼저 작성**

```python
# ai_llm/orchestrator_agent/tests/test_agent.py 에 추가

from unittest.mock import AsyncMock, MagicMock, patch
from models import IntentPlan, PlanStep


@pytest.mark.asyncio
async def test_analyze_intent_returns_intent_plan():
    """analyze_intent가 IntentPlan을 반환하는지 확인"""
    mock_plan = IntentPlan(
        intent="WEB_SEARCH",
        plan=[PlanStep(agent="web_research", query="AI 트렌드")]
    )

    with patch("agent.ChatOpenAI") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm
        mock_structured = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured
        mock_structured.invoke.return_value = mock_plan

        from agent import OrchestratorAgent
        orch = OrchestratorAgent.__new__(OrchestratorAgent)
        orch.llm = mock_llm

        result = await orch.analyze_intent("최신 AI 트렌드 알려줘")

    assert isinstance(result, IntentPlan)
    assert result.intent == "WEB_SEARCH"


@pytest.mark.asyncio
async def test_analyze_intent_direct():
    """직접 답변 가능한 경우 DIRECT 반환 확인"""
    mock_plan = IntentPlan(intent="DIRECT", direct_answer="안녕하세요!")

    with patch("agent.ChatOpenAI") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm
        mock_structured = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured
        mock_structured.invoke.return_value = mock_plan

        from agent import OrchestratorAgent
        orch = OrchestratorAgent.__new__(OrchestratorAgent)
        orch.llm = mock_llm

        result = await orch.analyze_intent("안녕")

    assert result.intent == "DIRECT"
    assert result.direct_answer == "안녕하세요!"
```

- [ ] **Step 2: 테스트 실행 (FAIL 확인)**

```bash
pytest tests/test_agent.py::test_analyze_intent_returns_intent_plan -v
```

Expected: FAIL (agent.py에 analyze_intent 미구현)

- [ ] **Step 3: agent.py 상단 imports 교체**

기존 `agent.py` 상단의 import를 아래로 교체한다:

```python
# ai_llm/orchestrator_agent/agent.py
import os
import json
import logging
import asyncio
import time
import httpx
from typing import AsyncIterator, Dict, Any, List, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from a2a.client import A2AClient, A2ACardResolver
from a2a.types import MessageSendParams, SendMessageRequest, Part, TextPart, Message
from uuid import uuid4

from models import IntentPlan, PlanStep, TraceStep, AgentResult

logger = logging.getLogger(__name__)
load_dotenv()

AGENT_URLS = {
    "internal_rag": os.getenv("RAG_AGENT_URL", "http://localhost:10012"),
    "web_research": os.getenv("WEB_AGENT_URL", "http://localhost:10011"),
    "file_management": os.getenv("FILE_AGENT_URL", "http://localhost:10013"),
}

SYSTEM_PROMPT = """당신은 사용자 요청을 분석하고 적절한 에이전트에게 작업을 위임하는 Orchestrator입니다.

사용 가능한 에이전트:
- internal_rag: 사내 문서 검색(RAG), 문서 인덱싱/저장
- web_research: 외부 웹 검색, 최신 뉴스, 트렌드 정보
- file_management: Google Drive 파일 목록 조회, 검색

핵심 원칙:
1. 사용자의 원래 의도를 그대로 에이전트에게 전달하세요.
2. 에이전트가 스스로 판단할 수 있도록 자연어로 요청하세요.
3. 이전 에이전트 결과가 필요한 단계는 depends_on에 이전 step 인덱스를 설정하세요.
4. 독립적으로 실행 가능한 단계는 depends_on을 null로 설정하세요.

의도 분류 기준:
- INTERNAL_SEARCH: 사내 문서 검색
- WEB_SEARCH: 외부 웹 검색
- FILE_OPERATION: 파일 관리
- HYBRID: 둘 이상의 에이전트 필요
- DIRECT: 에이전트 없이 직접 답변 가능 (인사, 간단한 질문)
"""
```

- [ ] **Step 4: OrchestratorAgent 클래스 및 analyze_intent 구현**

```python
class OrchestratorAgent:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 필요합니다")

        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.httpx_client = None
        self.remote_agents: Dict[str, A2AClient] = {}
        self.initialized = False

    async def initialize(self) -> None:
        if self.initialized:
            return
        self.httpx_client = httpx.AsyncClient(timeout=120.0)
        for name, url in AGENT_URLS.items():
            try:
                card_resolver = A2ACardResolver(httpx_client=self.httpx_client, base_url=url)
                agent_card = await card_resolver.get_agent_card()
                self.remote_agents[name] = A2AClient(httpx_client=self.httpx_client, agent_card=agent_card)
                logger.info(f"[ORCHESTRATOR] [INIT] {name} 연결 완료")
            except Exception as e:
                logger.error(f"[ORCHESTRATOR] [ERROR] {name} 연결 실패: {e}")
        self.initialized = True

    async def close(self) -> None:
        if self.httpx_client:
            await self.httpx_client.aclose()

    async def analyze_intent(self, query: str) -> IntentPlan:
        """Pydantic structured output으로 Intent 분류"""
        structured_llm = self.llm.with_structured_output(IntentPlan)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]
        return structured_llm.invoke(messages)
```

- [ ] **Step 5: 테스트 실행 (PASS 확인)**

```bash
pytest tests/test_agent.py::test_analyze_intent_returns_intent_plan tests/test_agent.py::test_analyze_intent_direct -v
```

Expected: 2 passed

- [ ] **Step 6: 커밋**

```bash
git add ai_llm/orchestrator_agent/agent.py ai_llm/orchestrator_agent/tests/test_agent.py
git commit -m "[F-002][M-002] Intent 분류 Pydantic structured output 적용"
```

---

## Task 3: 병렬 에이전트 실행 (asyncio.gather)

**Files:**
- Modify: `ai_llm/orchestrator_agent/agent.py`

독립 단계(`depends_on=None`)는 asyncio.gather로 동시 실행하고, 의존성 있는 단계는 순차 실행한다.

- [ ] **Step 1: 테스트 작성**

```python
# ai_llm/orchestrator_agent/tests/test_agent.py 에 추가

@pytest.mark.asyncio
async def test_parallel_execution_independent_steps():
    """독립 단계 2개가 병렬로 실행되는지 확인 (순차보다 빠름)"""
    call_times = []

    async def mock_call(agent_name, query):
        call_times.append(time.time())
        await asyncio.sleep(0.1)
        return AgentResult(
            agent=agent_name,
            success=True,
            content=f"{agent_name} 결과",
            trace=TraceStep(step=0, agent=agent_name, status="completed", message="완료")
        )

    from agent import OrchestratorAgent
    orch = OrchestratorAgent.__new__(OrchestratorAgent)
    orch.remote_agents = {"web_research": MagicMock(), "internal_rag": MagicMock()}

    plan = IntentPlan(
        intent="HYBRID",
        plan=[
            PlanStep(agent="web_research", query="웹 검색", depends_on=None),
            PlanStep(agent="internal_rag", query="문서 검색", depends_on=None),
        ]
    )

    start = time.time()
    with patch.object(orch, "_call_agent", side_effect=mock_call):
        results = await orch.execute_plan(plan)
    elapsed = time.time() - start

    assert len(results) == 2
    assert elapsed < 0.15  # 병렬이면 0.1초, 순차면 0.2초


@pytest.mark.asyncio
async def test_sequential_execution_dependent_steps():
    """의존성 있는 단계는 순차 실행되는지 확인"""
    execution_order = []

    async def mock_call(agent_name, query):
        execution_order.append(agent_name)
        await asyncio.sleep(0.05)
        return AgentResult(
            agent=agent_name,
            success=True,
            content=f"{agent_name} 결과",
            trace=TraceStep(step=0, agent=agent_name, status="completed", message="완료")
        )

    from agent import OrchestratorAgent
    orch = OrchestratorAgent.__new__(OrchestratorAgent)
    orch.remote_agents = {"file_management": MagicMock(), "internal_rag": MagicMock()}

    plan = IntentPlan(
        intent="HYBRID",
        plan=[
            PlanStep(agent="file_management", query="파일 목록", depends_on=None),
            PlanStep(agent="internal_rag", query="인덱싱", depends_on=0),
        ]
    )

    with patch.object(orch, "_call_agent", side_effect=mock_call):
        results = await orch.execute_plan(plan)

    assert execution_order == ["file_management", "internal_rag"]
```

- [ ] **Step 2: 테스트 실행 (FAIL 확인)**

```bash
pytest tests/test_agent.py::test_parallel_execution_independent_steps -v
```

Expected: FAIL (execute_plan 미구현)

- [ ] **Step 3: _call_agent 및 execute_plan 구현**

```python
# agent.py OrchestratorAgent 클래스 내부에 추가

async def _call_agent(self, agent_name: str, query: str, step_index: int = 0) -> AgentResult:
    """단일 에이전트 호출"""
    start_ms = int(time.time() * 1000)
    trace_started = TraceStep(step=step_index, agent=agent_name, status="started", message=f"{agent_name} 호출 중")

    if agent_name not in self.remote_agents:
        return AgentResult(
            agent=agent_name,
            success=False,
            content=f"에이전트 '{agent_name}'를 찾을 수 없습니다.",
            trace=TraceStep(step=step_index, agent=agent_name, status="failed", message="에이전트 없음")
        )

    try:
        client = self.remote_agents[agent_name]
        message = Message(
            kind="message",
            role="user",
            parts=[TextPart(kind="text", text=query)],
            message_id=uuid4().hex,
        )
        request = SendMessageRequest(id=uuid4().hex, params=MessageSendParams(message=message))
        response = await client.send_message(request)

        content = ""
        result = response.root.result if hasattr(response, "root") else response.result
        if result and hasattr(result, "artifacts") and result.artifacts:
            for artifact in result.artifacts:
                for part in artifact.parts:
                    if hasattr(part, "root") and hasattr(part.root, "text"):
                        content = part.root.text

        duration_ms = int(time.time() * 1000) - start_ms
        success = bool(content)
        status = "completed" if success else "failed"

        return AgentResult(
            agent=agent_name,
            success=success,
            content=content or "응답을 받지 못했습니다.",
            trace=TraceStep(step=step_index, agent=agent_name, status=status, message=f"{agent_name} 완료", duration_ms=duration_ms)
        )
    except Exception as e:
        duration_ms = int(time.time() * 1000) - start_ms
        return AgentResult(
            agent=agent_name,
            success=False,
            content=f"에이전트 호출 실패: {str(e)}",
            trace=TraceStep(step=step_index, agent=agent_name, status="failed", message=str(e), duration_ms=duration_ms)
        )


async def execute_plan(self, plan: IntentPlan) -> List[AgentResult]:
    """
    Plan 실행 — 독립 단계는 병렬, 의존 단계는 순차

    depends_on=None  → asyncio.gather로 병렬 실행
    depends_on=N     → step N 완료 후 순차 실행
    """
    steps = plan.plan
    results: List[Optional[AgentResult]] = [None] * len(steps)

    # 실행 그룹 구성: {depends_on → [step_index, ...]}
    # depends_on=None인 것들은 같이 묶어서 병렬 실행
    # depends_on=N인 것들은 N번 결과 나온 뒤 실행
    independent = [i for i, s in enumerate(steps) if s.depends_on is None]
    dependent_map: Dict[int, List[int]] = {}
    for i, s in enumerate(steps):
        if s.depends_on is not None:
            dependent_map.setdefault(s.depends_on, []).append(i)

    # 1. 독립 단계 병렬 실행
    if independent:
        tasks = [self._call_agent(steps[i].agent, steps[i].query, i) for i in independent]
        parallel_results = await asyncio.gather(*tasks)
        for i, result in zip(independent, parallel_results):
            results[i] = result

    # 2. 의존 단계 순차 실행
    for dep_on, step_indices in dependent_map.items():
        prev_result = results[dep_on]
        for i in step_indices:
            step = steps[i]
            query = step.query
            # 이전 결과를 쿼리에 컨텍스트로 추가
            if prev_result and prev_result.success:
                query = f"{query}\n\n[이전 에이전트 결과]:\n{prev_result.content[:2000]}"
            result = await self._call_agent(step.agent, query, i)
            results[i] = result
            prev_result = result

    return [r for r in results if r is not None]
```

- [ ] **Step 4: 테스트 실행 (PASS 확인)**

```bash
pytest tests/test_agent.py::test_parallel_execution_independent_steps tests/test_agent.py::test_sequential_execution_dependent_steps -v
```

Expected: 2 passed

- [ ] **Step 5: 커밋**

```bash
git add ai_llm/orchestrator_agent/agent.py ai_llm/orchestrator_agent/tests/test_agent.py
git commit -m "[F-020][M-002] 병렬/순차 에이전트 실행 구현 (asyncio.gather)"
```

---

## Task 4: TraceStep 실행 과정 기록 (F-017)

**Files:**
- Modify: `ai_llm/orchestrator_agent/agent.py` (stream 메서드)
- Modify: `ai_llm/orchestrator_agent/agent_executor.py`

- [ ] **Step 1: 테스트 작성**

```python
# ai_llm/orchestrator_agent/tests/test_agent.py 에 추가

@pytest.mark.asyncio
async def test_stream_yields_trace_in_final_response():
    """stream 최종 응답에 trace 목록이 포함되는지 확인"""
    from agent import OrchestratorAgent
    orch = OrchestratorAgent.__new__(OrchestratorAgent)
    orch.initialized = True
    orch.llm = MagicMock()
    orch.remote_agents = {}

    mock_plan = IntentPlan(intent="DIRECT", direct_answer="안녕하세요!")

    with patch.object(orch, "analyze_intent", return_value=mock_plan):
        chunks = []
        async for chunk in orch.stream("안녕"):
            chunks.append(chunk)

    final = chunks[-1]
    assert final["is_task_complete"] is True
    assert "trace" in final
    assert isinstance(final["trace"], list)
```

- [ ] **Step 2: 테스트 실행 (FAIL 확인)**

```bash
pytest tests/test_agent.py::test_stream_yields_trace_in_final_response -v
```

Expected: FAIL

- [ ] **Step 3: generate_final_response 및 stream 구현**

```python
# agent.py OrchestratorAgent 클래스 내부에 추가

async def generate_final_response(self, query: str, results: List[AgentResult]) -> str:
    """에이전트 결과를 통합해 최종 답변 생성"""
    results_text = json.dumps(
        [{"agent": r.agent, "success": r.success, "content": r.content} for r in results],
        ensure_ascii=False, indent=2
    )
    final_llm = ChatOpenAI(model="gpt-4o")
    messages = [
        {"role": "system", "content": "여러 에이전트의 결과를 통합하여 사용자에게 명확한 답변을 제공하세요."},
        {"role": "user", "content": f"원본 질문: {query}\n\n에이전트 결과:\n{results_text}\n\n위 정보를 바탕으로 답변해주세요."}
    ]
    response = await final_llm.ainvoke(messages)
    return response.content


async def stream(self, query: str, session_id: str = "default") -> AsyncIterator[Dict[str, Any]]:
    """스트리밍 처리 — TraceStep 포함"""
    if not self.initialized:
        await self.initialize()

    trace: List[Dict] = []

    yield {"is_task_complete": False, "require_user_input": False, "content": "🤔 질문을 분석하고 있습니다...", "trace": trace}

    try:
        plan = await self.analyze_intent(query)
        logger.info(f"[ORCHESTRATOR] Intent: {plan.intent}, Plan: {len(plan.plan)}개")
    except Exception as e:
        yield {"is_task_complete": True, "require_user_input": False, "content": f"분석 중 오류: {str(e)}", "trace": trace}
        return

    # DIRECT 즉시 응답
    if plan.intent == "DIRECT" and plan.direct_answer:
        trace.append(TraceStep(step=0, agent="orchestrator", status="completed", message="직접 답변").model_dump())
        yield {"is_task_complete": True, "require_user_input": False, "content": plan.direct_answer, "trace": trace}
        return

    if not plan.plan:
        yield {"is_task_complete": True, "require_user_input": False, "content": "처리할 작업이 없습니다.", "trace": trace}
        return

    yield {"is_task_complete": False, "require_user_input": False, "content": f"📋 {len(plan.plan)}개 에이전트에 요청 중...", "trace": trace}

    results = await self.execute_plan(plan)

    for r in results:
        trace.append(r.trace.model_dump())

    yield {"is_task_complete": False, "require_user_input": False, "content": "📝 결과를 정리하고 있습니다...", "trace": trace}

    final_response = await self.generate_final_response(query, results)

    yield {"is_task_complete": True, "require_user_input": False, "content": final_response, "trace": trace}
```

- [ ] **Step 4: agent_executor.py — trace를 artifact로 반환**

```python
# agent_executor.py execute 메서드의 elif is_complete 블록 교체

elif is_complete:
    trace = item.get("trace", [])
    # 최종 답변 artifact
    await updater.add_artifact(
        parts=[Part(root=TextPart(text=content))],
        name="orchestrator_result"
    )
    # trace artifact (F-017)
    if trace:
        import json
        trace_json = json.dumps(trace, ensure_ascii=False)
        await updater.add_artifact(
            parts=[Part(root=TextPart(text=trace_json))],
            name="execution_trace"
        )
    await updater.complete()
    break
```

- [ ] **Step 5: 테스트 실행 (PASS 확인)**

```bash
pytest tests/test_agent.py::test_stream_yields_trace_in_final_response -v
```

Expected: 1 passed

- [ ] **Step 6: 커밋**

```bash
git add ai_llm/orchestrator_agent/agent.py ai_llm/orchestrator_agent/agent_executor.py ai_llm/orchestrator_agent/tests/test_agent.py
git commit -m "[F-017][M-002] TraceStep 실행 과정 기록 및 artifact 반환 구현"
```

---

## Task 5: 자동 재시도 및 오류 메시지 (F-018)

**Files:**
- Modify: `ai_llm/orchestrator_agent/agent.py`

- [ ] **Step 1: 테스트 작성**

```python
# ai_llm/orchestrator_agent/tests/test_agent.py 에 추가

@pytest.mark.asyncio
async def test_call_agent_retries_on_failure():
    """_call_agent가 실패 시 최대 2회 재시도하는지 확인"""
    call_count = 0

    async def flaky_send(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("일시적 오류")
        # 3번째 성공
        mock_resp = MagicMock()
        mock_resp.root.result.artifacts = []
        return mock_resp

    from agent import OrchestratorAgent
    orch = OrchestratorAgent.__new__(OrchestratorAgent)
    mock_client = AsyncMock()
    mock_client.send_message.side_effect = flaky_send
    orch.remote_agents = {"web_research": mock_client}

    result = await orch._call_agent("web_research", "테스트", step_index=0)
    assert call_count == 3  # 2회 실패 후 3번째 성공


@pytest.mark.asyncio
async def test_call_agent_fails_after_max_retries():
    """최대 재시도 초과 시 failed AgentResult 반환 확인"""
    from agent import OrchestratorAgent
    orch = OrchestratorAgent.__new__(OrchestratorAgent)
    mock_client = AsyncMock()
    mock_client.send_message.side_effect = Exception("지속적 오류")
    orch.remote_agents = {"web_research": mock_client}

    result = await orch._call_agent("web_research", "테스트", step_index=0)
    assert result.success is False
    assert result.trace.status == "failed"
```

- [ ] **Step 2: 테스트 실행 (FAIL 확인)**

```bash
pytest tests/test_agent.py::test_call_agent_retries_on_failure -v
```

Expected: FAIL

- [ ] **Step 3: tenacity 재시도 로직 추가**

`_call_agent`의 내부 API 호출 부분을 tenacity로 감싼다:

```python
# agent.py 상단 import에 추가
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# _call_agent 내부 — client.send_message 호출 부분을 아래로 교체

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def _send_with_retry(client, request):
    return await client.send_message(request)

# _call_agent 내 try 블록에서 호출 교체
response = await _send_with_retry(client, request)
```

단, `_send_with_retry`는 클래스 외부에 모듈 레벨 함수로 정의한다:

```python
# agent.py — OrchestratorAgent 클래스 밖에 정의

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def _send_with_retry(client, request):
    return await client.send_message(request)
```

그리고 `_call_agent` 내부의 `await client.send_message(request)` 를 `await _send_with_retry(client, request)` 로 교체한다.

- [ ] **Step 4: 테스트 실행 (PASS 확인)**

```bash
pytest tests/test_agent.py::test_call_agent_retries_on_failure tests/test_agent.py::test_call_agent_fails_after_max_retries -v
```

Expected: 2 passed

- [ ] **Step 5: 전체 테스트 실행**

```bash
pytest tests/test_agent.py -v
```

Expected: 전체 PASS

- [ ] **Step 6: 커밋**

```bash
git add ai_llm/orchestrator_agent/agent.py ai_llm/orchestrator_agent/tests/test_agent.py
git commit -m "[F-018][M-002] tenacity 자동 재시도 로직 구현 (최대 3회)"
```

---

## Task 6: 통합 테스트 및 PR

**Files:**
- Test: `ai_llm/orchestrator_agent/tests/test_agent.py`

- [ ] **Step 1: 전체 테스트 실행**

```bash
cd ai_llm/orchestrator_agent
pytest tests/ -v --tb=short
```

Expected: 전체 PASS

- [ ] **Step 2: 서버 실행 확인**

```bash
cd ai_llm/orchestrator_agent
python agent_server.py
```

Expected: `[ORCHESTRATOR AGENT] 서버 주소: http://localhost:10010` 출력

- [ ] **Step 3: PR 생성**

제목: `[F-001][F-002][F-017][F-018][F-020][M-002] Orchestrator Agent 고도화`

base: `dev` → head: `feature/M-002-orchestrator-enhancement`
