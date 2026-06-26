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
    assert final["content"] == "**[AI 직접 답변]** 사내 문서를 참조하지 않은 답변입니다.\n\n안녕하세요!"


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
async def test_execute_plan_report_writing_waits_for_upstream():
    """report_writing depends_on=null 이라도 normalize 후 upstream이 채워진 뒤 실행"""
    call_order = []
    report_queries = []

    async def fake_call(agent_name, query, step_index=0):
        call_order.append((step_index, agent_name))
        if agent_name == "report_writing":
            report_queries.append(query)
        if agent_name == "web_research":
            body = "SQL은 관계형 DB 질의 언어입니다."
            artifacts = [{"name": "web_search_result", "text": body}]
        elif agent_name == "file_management" and step_index == 0:
            body = "test.txt 확인"
            artifacts = [{"name": "file_content", "data": {"filename": "test.txt", "content": "# 개요"}}]
        else:
            body = f"{agent_name} ok"
            artifacts = []
        return AgentResult(
            agent=agent_name,
            success=True,
            content=body,
            artifacts=artifacts,
            trace=TraceStep(step=step_index, agent=agent_name, status="completed", message="완료"),
        )

    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from shared.report_context import parse_report_context
    from agent import OrchestratorAgent

    orch = OrchestratorAgent.__new__(OrchestratorAgent)
    orch.remote_agents = {
        "file_management": AsyncMock(),
        "web_research": AsyncMock(),
        "report_writing": AsyncMock(),
    }

    plan = IntentPlan(
        intent="HYBRID",
        plan=[
            PlanStep(agent="file_management", query="test.txt 양식 조회", depends_on=None),
            PlanStep(agent="web_research", query="SQL 조사", depends_on=None),
            PlanStep(agent="report_writing", query="보고서 주제: SQL", depends_on=None),
        ],
    )

    with patch.object(orch, "_call_agent", side_effect=fake_call):
        await orch.execute_plan(plan, user_query="test.txt 양식 참고 SQL 보고서")

    assert call_order.index((2, "report_writing")) > call_order.index((0, "file_management"))
    assert call_order.index((2, "report_writing")) > call_order.index((1, "web_research"))

    ctx = parse_report_context(report_queries[0])
    assert ctx is not None
    assert len(ctx.sources) >= 2
    assert ctx.report_topic == "SQL"


@pytest.mark.asyncio
async def test_call_agent_not_found():
    """존재하지 않는 에이전트 호출 시 failed AgentResult 반환"""
    from agent import OrchestratorAgent
    orch = OrchestratorAgent.__new__(OrchestratorAgent)
    orch.remote_agents = {}

    result = await orch._call_agent("unknown_agent", "쿼리", step_index=0)

    assert result.success is False
    assert result.trace.status == "failed"


@pytest.mark.asyncio
async def test_stream_yields_trace_in_final_response():
    """stream 최종 응답에 trace 목록이 포함되는지 확인"""
    mock_plan = IntentPlan(intent="DIRECT", direct_answer="안녕하세요!")

    from agent import OrchestratorAgent
    orch = OrchestratorAgent.__new__(OrchestratorAgent)
    orch.initialized = True
    orch.llm = MagicMock()
    mock_structured = MagicMock()
    orch.llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = mock_plan

    chunks = []
    async for chunk in orch.stream("안녕"):
        chunks.append(chunk)

    final = chunks[-1]
    assert final["is_task_complete"] is True
    assert "trace" in final
    assert isinstance(final["trace"], list)
    assert len(final["trace"]) == 1
    assert final["trace"][0]["agent"] == "orchestrator"
    assert final["trace"][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_stream_includes_trace_from_agents():
    """에이전트 실행 후 trace에 각 에이전트 단계가 포함되는지 확인"""
    mock_plan = IntentPlan(
        intent="WEB_SEARCH",
        plan=[PlanStep(agent="web_research", query="AI 트렌드")],
    )
    mock_agent_result = AgentResult(
        agent="web_research",
        success=True,
        content="AI 트렌드 결과",
        trace=TraceStep(step=0, agent="web_research", status="completed", message="완료", duration_ms=500),
    )

    from agent import OrchestratorAgent
    orch = OrchestratorAgent.__new__(OrchestratorAgent)
    orch.initialized = True
    orch.llm = MagicMock()
    mock_structured = MagicMock()
    orch.llm.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = mock_plan

    with patch.object(orch, "execute_plan", return_value=[mock_agent_result]):
        chunks = []
        async for chunk in orch.stream("AI 트렌드 알려줘"):
            chunks.append(chunk)

    final = chunks[-1]
    assert final["is_task_complete"] is True
    assert final["content"].startswith("**[웹 검색 기반]**")
    assert "AI 트렌드 결과" in final["content"]
    assert len(final["trace"]) == 1
    assert final["trace"][0]["agent"] == "web_research"
    assert final["trace"][0]["duration_ms"] == 500


@pytest.mark.asyncio
async def test_call_agent_retries_on_transient_failure():
    """_call_agent가 일시적 실패 시 재시도하여 성공하는지 확인"""
    import agent as agent_module
    from tenacity import retry, stop_after_attempt, wait_none, retry_if_exception_type

    call_count = 0

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_none(),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def fast_send_with_retry(client, request):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("일시적 네트워크 오류")
        mock_part = MagicMock()
        mock_part.root.text = "성공 결과"
        mock_artifact = MagicMock()
        mock_artifact.parts = [mock_part]
        mock_resp = MagicMock()
        mock_resp.root.result.artifacts = [mock_artifact]
        return mock_resp

    from agent import OrchestratorAgent
    orch = OrchestratorAgent.__new__(OrchestratorAgent)
    mock_client = AsyncMock()
    orch.remote_agents = {"web_research": mock_client}

    with patch.object(agent_module, "_send_with_retry", new=fast_send_with_retry):
        result = await orch._call_agent("web_research", "테스트", step_index=0)

    assert call_count == 3
    assert result.trace.status == "completed"


@pytest.mark.asyncio
async def test_call_agent_fails_after_max_retries():
    """최대 재시도(3회) 초과 시 failed AgentResult 반환 확인"""
    import agent as agent_module
    from tenacity import retry, stop_after_attempt, wait_none, retry_if_exception_type

    call_count = 0

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_none(),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def always_fail_with_retry(client, request):
        nonlocal call_count
        call_count += 1
        raise Exception("지속적 오류")

    from agent import OrchestratorAgent
    orch = OrchestratorAgent.__new__(OrchestratorAgent)
    mock_client = AsyncMock()
    orch.remote_agents = {"web_research": mock_client}

    with patch.object(agent_module, "_send_with_retry", new=always_fail_with_retry):
        result = await orch._call_agent("web_research", "테스트", step_index=0)

    assert result.success is False
    assert result.trace.status == "failed"
    assert call_count == 3  # 최대 3회 재시도 후 실패


@pytest.mark.asyncio
async def test_generate_final_response_requests_markdown_output():
    """통합 답변 생성은 최종 사용자 응답을 Markdown으로 요구한다"""
    from agent import OrchestratorAgent
    import agent as agent_module

    captured_messages = []

    class FakeFinalLLM:
        async def ainvoke(self, messages):
            captured_messages.extend(messages)
            response = MagicMock()
            response.content = "## 최종 답변\n\n**핵심:** 완료"
            return response

    orch = OrchestratorAgent.__new__(OrchestratorAgent)
    results = [
        AgentResult(
            agent="web_research",
            success=True,
            content="검색 결과",
            trace=TraceStep(step=0, agent="web_research", status="completed", message="완료"),
        )
    ]

    with patch.object(agent_module, "ChatOpenAI", return_value=FakeFinalLLM()):
        content = await orch.generate_final_response("요약해줘", results)

    assert content.startswith("## 최종 답변")
    system_prompt = captured_messages[0]["content"]
    assert "Markdown" in system_prompt
    assert "headings" in system_prompt
    assert "bold" in system_prompt
