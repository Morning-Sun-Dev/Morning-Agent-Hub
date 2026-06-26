import json

from fastapi.testclient import TestClient

import backend.main as backend_main
from common.schemas import AgentResponse


def test_backend_main_uses_router_owned_chat_endpoint():
    schema = backend_main.app.openapi()
    chat_operation = schema["paths"]["/api/chat"]["post"]

    assert chat_operation["operationId"] == "chat_api_chat_post"
    assert not hasattr(backend_main, "ChatRequest")
    assert not hasattr(backend_main, "ChatResponse")
    assert not hasattr(backend_main, "get_a2a_client")
    assert not hasattr(backend_main, "extract_response_text")


def test_backend_main_chat_openapi_uses_message_contract():
    schema = backend_main.app.openapi()
    request_ref = schema["paths"]["/api/chat"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]["$ref"]
    component_name = request_ref.rsplit("/", 1)[-1]
    properties = schema["components"]["schemas"][component_name]["properties"]

    assert "message" in properties
    assert "query" not in properties


def test_backend_main_chat_post_dispatches_to_router_without_history(monkeypatch):
    from backend.api.routers import chat as chat_router

    prompts = []

    class FakeA2AClient:
        async def send_message(self, agent_name, prompt):
            assert agent_name == "orchestrator"
            prompts.append(prompt)
            return AgentResponse(
                success=True,
                artifacts=[{"name": "orchestrator_result", "text": "라우터 응답"}],
            )

    async def fake_ensure_session(session_id, message):
        return session_id or "session_main"

    async def fake_load_history(session_id):
        raise AssertionError("history should not be loaded into chat prompts")

    async def fake_save_message(session_id, role, content):
        return None

    async def fake_get_a2a_client():
        return FakeA2AClient()

    monkeypatch.setattr(chat_router, "_ensure_session", fake_ensure_session)
    monkeypatch.setattr(chat_router, "_load_history", fake_load_history)
    monkeypatch.setattr(chat_router, "_save_message", fake_save_message)
    monkeypatch.setattr(chat_router, "get_a2a_client", fake_get_a2a_client)

    response = TestClient(backend_main.app).post(
        "/api/chat",
        json={
            "message": "첨부 파일 요약",
            "attachments": [
                {
                    "id": "gdrive://file/a",
                    "name": "a.pdf",
                    "kind": "uploaded",
                    "status": "indexed",
                    "storage_ref": "gdrive://file/a",
                }
            ],
            "requested_capabilities": ["web_search", "rag_vector_search"],
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "라우터 응답"
    assert "[현재 질문]" in prompts[0]
    assert "[이전 대화]" not in prompts[0]
    assert "gdrive://file/a" in prompts[0]
    assert "rag_vector_search" in prompts[0]


def test_backend_main_chat_stream_dispatches_to_router_without_history(monkeypatch):
    from backend.api.routers import chat as chat_router

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
        raise AssertionError("history should not be loaded into stream prompts")

    async def fake_save_message(session_id, role, content):
        return None

    async def fake_get_a2a_client():
        return FakeA2AClient()

    monkeypatch.setattr(chat_router, "_ensure_session", fake_ensure_session)
    monkeypatch.setattr(chat_router, "_load_history", fake_load_history)
    monkeypatch.setattr(chat_router, "_save_message", fake_save_message)
    monkeypatch.setattr(chat_router, "get_a2a_client", fake_get_a2a_client)

    response = TestClient(backend_main.app).get(
        "/api/chat/stream",
        params={
            "message": "첨부 파일 요약",
            "attachments": json.dumps([
                {
                    "id": "gdrive://file/a",
                    "name": "a.pdf",
                    "kind": "uploaded",
                    "status": "indexed",
                    "storage_ref": "gdrive://file/a",
                }
            ]),
            "requested_capabilities": json.dumps(["web_search", "rag_vector_search"]),
        },
    )

    assert response.status_code == 200
    assert "스트림 응답" in response.text
    assert "[현재 질문]" in prompts[0]
    assert "[이전 대화]" not in prompts[0]
    assert "gdrive://file/a" in prompts[0]
    assert "rag_vector_search" in prompts[0]
