import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch
from models import IntentPlan, PlanStep, AgentResult, TraceStep


@pytest.mark.asyncio
async def test_analyze_intent_returns_intent_plan():
    """analyze_intent가 IntentPlan을 반환하는지 확인"""
    mock_plan = IntentPlan(
        intent="WEB_SEARCH",
        plan=[PlanStep(agent="web_research", query="AI 트렌드")]
    )

    from agent import OrchestratorAgent
    orch = OrchestratorAgent.__new__(OrchestratorAgent)
    mock_llm = MagicMock()
    orch.llm = mock_llm
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = mock_plan

    result = await orch.analyze_intent("최신 AI 트렌드 알려줘")

    assert isinstance(result, IntentPlan)
    assert result.intent == "WEB_SEARCH"
    mock_llm.with_structured_output.assert_called_once_with(IntentPlan)


@pytest.mark.asyncio
async def test_analyze_intent_direct():
    """직접 답변 가능한 경우 DIRECT 반환 확인"""
    mock_plan = IntentPlan(intent="DIRECT", direct_answer="안녕하세요!")

    from agent import OrchestratorAgent
    orch = OrchestratorAgent.__new__(OrchestratorAgent)
    mock_llm = MagicMock()
    orch.llm = mock_llm
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = mock_plan

    result = await orch.analyze_intent("안녕")

    assert result.intent == "DIRECT"
    assert result.direct_answer == "안녕하세요!"


@pytest.mark.asyncio
async def test_stream_direct_response():
    """DIRECT intent는 즉시 응답하는지 확인"""
    mock_plan = IntentPlan(intent="DIRECT", direct_answer="안녕하세요!")

    from agent import OrchestratorAgent
    orch = OrchestratorAgent.__new__(OrchestratorAgent)
    orch.initialized = True
    mock_llm = MagicMock()
    orch.llm = mock_llm
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = mock_plan

    chunks = []
    async for chunk in orch.stream("안녕"):
        chunks.append(chunk)

    final = chunks[-1]
    assert final["is_task_complete"] is True
    assert final["content"] == "안녕하세요!"


@pytest.mark.asyncio
async def test_execute_plan_parallel_independent_steps():
    """독립 단계 2개가 병렬 실행되는지 확인 (순차 0.2s보다 빠른 ~0.1s)"""
    async def fake_call(agent_name, query, step_index=0):
        await asyncio.sleep(0.1)
        return AgentResult(
            agent=agent_name, success=True, content=f"{agent_name} 결과",
            trace=TraceStep(step=step_index, agent=agent_name, status="completed", message="완료")
        )

    from agent import OrchestratorAgent
    orch = OrchestratorAgent.__new__(OrchestratorAgent)
    orch.remote_agents = {"web_research": AsyncMock(), "internal_rag": AsyncMock()}

    plan = IntentPlan(
        intent="HYBRID",
        plan=[
            PlanStep(agent="web_research", query="웹 검색", depends_on=None),
            PlanStep(agent="internal_rag", query="문서 검색", depends_on=None),
        ]
    )

    start = time.time()
    with patch.object(orch, "_call_agent", side_effect=fake_call):
        results = await orch.execute_plan(plan)
    elapsed = time.time() - start

    assert len(results) == 2
    assert all(r.success for r in results)
    assert elapsed < 0.18  # 병렬이면 ~0.1s, 순차면 ~0.2s


@pytest.mark.asyncio
async def test_execute_plan_sequential_dependent_steps():
    """의존성 있는 단계는 순차 실행되고 이전 결과가 쿼리에 포함되는지 확인"""
    received_queries = []

    async def fake_call(agent_name, query, step_index=0):
        received_queries.append((agent_name, query))
        return AgentResult(
            agent=agent_name, success=True, content=f"{agent_name} 결과",
            trace=TraceStep(step=step_index, agent=agent_name, status="completed", message="완료")
        )

    from agent import OrchestratorAgent
    orch = OrchestratorAgent.__new__(OrchestratorAgent)
    orch.remote_agents = {"file_management": AsyncMock(), "internal_rag": AsyncMock()}

    plan = IntentPlan(
        intent="HYBRID",
        plan=[
            PlanStep(agent="file_management", query="파일 목록", depends_on=None),
            PlanStep(agent="internal_rag", query="인덱싱", depends_on=0),
        ]
    )

    with patch.object(orch, "_call_agent", side_effect=fake_call):
        results = await orch.execute_plan(plan)

    assert received_queries[0][0] == "file_management"
    assert received_queries[1][0] == "internal_rag"
    assert "file_management 결과" in received_queries[1][1]


@pytest.mark.asyncio
async def test_call_agent_not_found():
    """존재하지 않는 에이전트 호출 시 failed AgentResult 반환"""
    from agent import OrchestratorAgent
    orch = OrchestratorAgent.__new__(OrchestratorAgent)
    orch.remote_agents = {}

    result = await orch._call_agent("unknown_agent", "쿼리", step_index=0)

    assert result.success is False
    assert result.trace.status == "failed"
