import pytest
import json

from common.schemas import AgentResponse
from backend.api.contract_adapter import build_chat_response


def test_build_chat_response_preserves_trace_sources_and_files():
    agent_response = AgentResponse(
        success=True,
        artifacts=[
            {"name": "orchestrator_result", "text": "최종 답변입니다."},
            {
                "name": "execution_trace",
                "text": (
                    '[{"step":0,"agent":"web_research","status":"completed",'
                    '"message":"검색 완료","duration_ms":1200},'
                    '{"step":1,"agent":"file_management","status":"failed",'
                    '"message":"Drive 저장 실패"}]'
                ),
            },
            {
                "name": "web_search_sources",
                "text": (
                    '[{"title":"OpenAI News","url":"https://openai.com/news/",'
                    '"snippet":"제품 업데이트","score":0.91}]'
                ),
            },
            {
                "name": "file_list",
                "data": {
                    "files": [
                        {
                            "filename": "휴가규정_2026.pdf",
                            "storage_ref": "gdrive://file/abc",
                            "mime_type": "application/pdf",
                            "size": 1234,
                            "web_view_link": "https://drive.google.com/file/d/abc/view",
                        }
                    ]
                },
            },
        ],
    )

    response = build_chat_response(agent_response, session_id="session_1", run_id="run_1")

    assert response.run_id == "run_1"
    assert response.session_id == "session_1"
    assert response.status == "partial_failure"
    assert response.answer == "최종 답변입니다."
    assert response.progress[0].agent_id == "web_research"
    assert response.progress[0].status == "completed"
    assert response.progress[1].agent_id == "file_management"
    assert response.progress[1].status == "failed"
    assert response.sources[0].title == "OpenAI News"
    assert response.sources[0].source_type == "web"
    assert response.files[0].storage_ref == "gdrive://file/abc"
    assert response.files[0].open_url.endswith("/abc/view")


def test_build_chat_response_preserves_markdown_answer_verbatim():
    markdown = "## 요약\n\n**핵심:** [출처](https://example.com)\n\n| 항목 | 값 |\n| --- | --- |\n| 상태 | 완료 |"
    agent_response = AgentResponse(
        success=True,
        artifacts=[
            {"name": "orchestrator_result", "text": markdown},
        ],
    )

    response = build_chat_response(agent_response, session_id="session_md", run_id="run_md")

    assert response.answer == markdown


def test_build_chat_response_skips_invalid_trace_items():
    agent_response = AgentResponse(
        success=True,
        artifacts=[
            {"name": "orchestrator_result", "text": "최종 답변입니다."},
            {
                "name": "execution_trace",
                "text": (
                    '[{"step":-1,"agent":"web_research","status":"completed",'
                    '"message":"잘못된 trace","duration_ms":"bad"},'
                    '{"step":0,"agent":"web_research","status":"completed",'
                    '"message":"정상 trace","duration_ms":10}]'
                ),
            },
        ],
    )

    response = build_chat_response(agent_response, session_id="session_bad_trace", run_id="run_bad_trace")

    assert response.progress[0].message == "정상 trace"
    assert response.progress[0].duration_ms == 10


def test_build_chat_response_maps_report_document_to_generated_file():
    agent_response = AgentResponse(
        success=True,
        artifacts=[
            {"name": "report_result", "text": "# 휴가 규정 요약\n\n본문"},
            {
                "name": "report_document",
                "data": {
                    "title": "휴가 규정 요약",
                    "filename_suggestion": "vacation-summary.md",
                    "template_id": "research_report",
                    "content": "# 휴가 규정 요약\n\n본문",
                },
            },
        ],
    )

    response = build_chat_response(agent_response, session_id="session_2", run_id="run_2")

    assert response.status == "completed"
    assert response.answer.startswith("# 휴가 규정 요약")
    assert response.files[0].name == "vacation-summary.md"
    assert response.files[0].kind == "generated"
    assert response.files[0].status == "pending"
    assert response.artifacts[0].kind == "report_document"
    assert response.artifacts[0].text.startswith("# 휴가 규정 요약")


def test_build_chat_response_preserves_real_report_agent_metadata_and_text():
    agent_response = AgentResponse(
        success=True,
        artifacts=[
            {"name": "report_result", "text": "# 실제 보고서\n\n본문"},
            {
                "name": "report_document",
                "data": {
                    "title": "실제 보고서",
                    "filename_suggestion": "real-report.md",
                    "template_id": "research_report",
                    "sections": ["개요", "결론"],
                },
            },
        ],
    )

    response = build_chat_response(agent_response, session_id="session_4", run_id="run_4")

    assert response.files[0].name == "real-report.md"
    assert response.artifacts[0].kind == "report_document"
    assert response.artifacts[0].text == "# 실제 보고서\n\n본문"
    assert response.artifacts[0].data["template_id"] == "research_report"


def test_chat_route_returns_expanded_contract(monkeypatch):
    from backend.api.routers import chat as chat_router

    class FakeA2AClient:
        async def send_message(self, agent_name, prompt):
            assert agent_name == "orchestrator"
            assert "첨부 파일" in prompt
            assert "gdrive://file/a" in prompt
            assert "web_search" in prompt
            return AgentResponse(
                success=True,
                artifacts=[
                    {"name": "orchestrator_result", "text": "라우터 응답"},
                    {
                        "name": "web_search_sources",
                        "text": '[{"title":"출처","url":"https://example.com","snippet":"요약"}]',
                    },
                ],
            )

    saved_messages = []

    async def fake_ensure_session(session_id, message):
        return session_id or "session_route"

    async def fake_load_history(session_id):
        return ""

    async def fake_save_message(session_id, role, content):
        saved_messages.append((session_id, role, content))

    async def fake_get_a2a_client():
        return FakeA2AClient()

    monkeypatch.setattr(chat_router, "_ensure_session", fake_ensure_session)
    monkeypatch.setattr(chat_router, "_load_history", fake_load_history)
    monkeypatch.setattr(chat_router, "_save_message", fake_save_message)
    monkeypatch.setattr(chat_router, "get_a2a_client", fake_get_a2a_client)

    import asyncio

    response = asyncio.run(chat_router.chat(chat_router.ChatRequest(
        message="안녕",
        attachments=[
            {
                "id": "gdrive://file/a",
                "name": "a.pdf",
                "kind": "uploaded",
                "status": "indexed",
                "storage_ref": "gdrive://file/a",
            }
        ],
        requested_capabilities=["web_search"],
    )))

    assert response.answer == "라우터 응답"
    assert response.session_id == "session_route"
    assert response.sources[0].title == "출처"
    assert saved_messages[-1] == ("session_route", "assistant", "라우터 응답")


def test_chat_route_keeps_http_error_for_agent_failure(monkeypatch):
    from fastapi import HTTPException
    from backend.api.routers import chat as chat_router

    class FakeA2AClient:
        async def send_message(self, agent_name, prompt):
            return AgentResponse(success=False, error="오케스트레이터 연결 실패")

    async def fake_ensure_session(session_id, message):
        return "session_failed"

    async def fake_load_history(session_id):
        return ""

    async def fake_save_message(session_id, role, content):
        return None

    async def fake_get_a2a_client():
        return FakeA2AClient()

    monkeypatch.setattr(chat_router, "_ensure_session", fake_ensure_session)
    monkeypatch.setattr(chat_router, "_load_history", fake_load_history)
    monkeypatch.setattr(chat_router, "_save_message", fake_save_message)
    monkeypatch.setattr(chat_router, "get_a2a_client", fake_get_a2a_client)

    import asyncio

    with pytest.raises(HTTPException) as exc:
        asyncio.run(chat_router.chat(chat_router.ChatRequest(message="안녕")))

    assert exc.value.status_code == 500
    assert "오케스트레이터 연결 실패" in exc.value.detail


def test_sse_answer_event_keeps_legacy_type_and_expanded_payload():
    from backend.api.routers.chat import _answer_event_payload
    from common.contracts import ProgressItemContract, SourceContract
    from backend.api.schemas import ChatResponse

    response = ChatResponse(
        run_id="run_sse",
        session_id="session_sse",
        status="completed",
        answer="스트림 응답",
        error="일부 작업이 실패했습니다.",
        sources=[
            SourceContract(
                title="출처",
                url="https://example.com",
                source_type="web",
                agent_id="web_research",
            )
        ],
        progress=[
            ProgressItemContract(
                run_id="run_sse",
                agent_id="orchestrator",
                capability_id="route_request",
                label="요청 분석",
                message="완료",
                status="completed",
            )
        ],
    )

    payload = _answer_event_payload(response, "session_sse")

    assert payload["type"] == "answer"
    assert payload["content"] == "스트림 응답"
    assert payload["sources"][0]["title"] == "출처"
    assert payload["progress"][0]["label"] == "요청 분석"
    assert payload["artifacts"] == []
    assert payload["error"] == "일부 작업이 실패했습니다."


def test_stream_route_includes_attachments_and_capabilities_in_prompt(monkeypatch):
    from backend.api.routers import chat as chat_router
    import asyncio

    prompts = []

    class FakeA2AClient:
        async def send_message(self, agent_name, prompt):
            assert agent_name == "orchestrator"
            prompts.append(prompt)
            return AgentResponse(
                success=True,
                artifacts=[{"name": "orchestrator_result", "text": "스트림 응답"}],
            )

    async def fake_ensure_session(session_id, message):
        return session_id or "session_stream"

    async def fake_load_history(session_id):
        return ""

    async def fake_save_message(session_id, role, content):
        return None

    async def fake_get_a2a_client():
        return FakeA2AClient()

    monkeypatch.setattr(chat_router, "_ensure_session", fake_ensure_session)
    monkeypatch.setattr(chat_router, "_load_history", fake_load_history)
    monkeypatch.setattr(chat_router, "_save_message", fake_save_message)
    monkeypatch.setattr(chat_router, "get_a2a_client", fake_get_a2a_client)

    async def collect_events():
        response = await chat_router.chat_stream(
            message="첨부 파일 요약",
            attachments=json.dumps([
                {
                    "id": "gdrive://file/a",
                    "name": "a.pdf",
                    "kind": "uploaded",
                    "status": "indexed",
                    "storage_ref": "gdrive://file/a",
                }
            ]),
            requested_capabilities=json.dumps(["web_search", "rag_vector_search"]),
        )
        return [chunk async for chunk in response.body_iterator]

    events = asyncio.run(collect_events())

    assert "[첨부 파일]" in prompts[0]
    assert "gdrive://file/a" in prompts[0]
    assert "[요청 기능]" in prompts[0]
    assert "rag_vector_search" in prompts[0]
    assert any("스트림 응답" in event for event in events)


def test_stream_route_reports_invalid_json_list():
    from backend.api.routers.chat import _json_list_param

    with pytest.raises(ValueError, match="attachments"):
        _json_list_param("{bad", "attachments")


def test_build_chat_response_maps_agent_failure():
    agent_response = AgentResponse(success=False, error="오케스트레이터 연결 실패")

    response = build_chat_response(agent_response, session_id="session_3", run_id="run_3")

    assert response.status == "failed"
    assert response.answer == ""
    assert response.error == "오케스트레이터 연결 실패"
