import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from unittest.mock import MagicMock, patch
from models import IntentPlan, PlanStep


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
