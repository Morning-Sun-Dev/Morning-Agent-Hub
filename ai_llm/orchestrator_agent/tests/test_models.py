import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from pydantic import ValidationError
from models import IntentPlan, PlanStep, TraceStep, AgentResult


def test_intent_plan_direct():
    plan = IntentPlan(intent="DIRECT", direct_answer="안녕하세요!")
    assert plan.intent == "DIRECT"
    assert plan.direct_answer == "안녕하세요!"
    assert plan.plan == []


def test_plan_step_independent():
    step = PlanStep(agent="web_research", query="AI 트렌드 검색", depends_on=None)
    assert step.agent == "web_research"
    assert step.query == "AI 트렌드 검색"
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
    assert result.agent == "web_research"
    assert result.content == "결과"
    assert result.trace.status == "completed"


def test_agent_result_failure_allows_none_content():
    trace = TraceStep(step=0, agent="web_research", status="failed", message="오류")
    result = AgentResult(agent="web_research", success=False, content=None, trace=trace)
    assert result.success is False
    assert result.content is None


def test_plan_step_invalid_agent_raises():
    with pytest.raises(ValidationError):
        PlanStep(agent="unknown_agent", query="x")


def test_intent_plan_invalid_intent_raises():
    with pytest.raises(ValidationError):
        IntentPlan(intent="UNKNOWN_INTENT")


def test_trace_step_invalid_status_raises():
    with pytest.raises(ValidationError):
        TraceStep(step=0, agent="x", status="running", message="x")


def test_plan_step_negative_depends_on_raises():
    with pytest.raises(ValidationError):
        PlanStep(agent="web_research", query="x", depends_on=-1)
