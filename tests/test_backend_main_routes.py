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


def test_backend_main_exposes_capability_registry():
    response = TestClient(backend_main.app).get("/api/capabilities")

    assert response.status_code == 200
    payload = response.json()
    capability_ids = {item["capability_id"] for item in payload}

    assert "web_search" in capability_ids
    assert "delete_file" in capability_ids
    assert any(
        item["agent_id"] == "web_research"
        and item["capability_id"] == "web_search"
        and item["ui_status"] == "available"
        for item in payload
    )
    assert any(
        item["agent_id"] == "web_research"
        and item["capability_id"] == "news_search"
        and item["ui_status"] == "available"
        and "빠른 실행" in item["ui_surface"]
        for item in payload
    )
    assert any(
        item["agent_id"] == "web_research"
        and item["capability_id"] == "url_fetch"
        and item["ui_status"] == "available"
        and "빠른 실행" in item["ui_surface"]
        for item in payload
    )
    assert any(
        item["agent_id"] == "file_management"
        and item["capability_id"] == "delete_file"
        and item["ui_status"] == "available"
        and item["ui_surface"] == "파일 패널"
        for item in payload
    )
    assert any(
        item["agent_id"] == "file_management"
        and item["capability_id"] == "list_files"
        and item["ui_status"] == "available"
        and item["ui_surface"] == "파일 패널"
        for item in payload
    )
    assert any(
        item["agent_id"] == "file_management"
        and item["capability_id"] == "get_file_info"
        and item["ui_status"] == "available"
        and item["ui_surface"] == "파일 패널"
        for item in payload
    )
    assert any(
        item["agent_id"] == "file_management"
        and item["capability_id"] == "download_file"
        and item["ui_status"] == "partial"
        and item["ui_surface"] == "파일 패널"
        for item in payload
    )
    assert any(
        item["agent_id"] == "file_management"
        and item["capability_id"] == "find_folder"
        and item["ui_status"] == "available"
        and item["ui_surface"] == "파일 패널"
        for item in payload
    )
    assert any(
        item["agent_id"] == "file_management"
        and item["capability_id"] == "create_folder"
        and item["ui_status"] == "available"
        and item["ui_surface"] == "파일 패널"
        for item in payload
    )
    assert any(
        item["agent_id"] == "file_management"
        and item["capability_id"] == "update_file"
        and item["ui_status"] == "partial"
        and "이름 변경" in item["ui_surface"]
        for item in payload
    )
    assert any(
        item["agent_id"] == "report_writing"
        and item["capability_id"] == "list_templates"
        and item["ui_status"] == "partial"
        and item["ui_surface"] == "채팅 입력"
        for item in payload
    )


def test_backend_main_file_list_route_preserves_and_normalizes_drive_items(monkeypatch):
    from backend.api.routers import files as files_router

    class FakeDriveClient:
        def list_files(self):
            return [
                {
                    "file_id": "drive-file-1",
                    "storage_ref": "gdrive://file/drive-file-1",
                    "filename": "brief.md",
                    "mime_type": "text/markdown",
                    "size": 42,
                    "web_view_link": "https://drive.example/open/drive-file-1",
                    "web_content_link": "https://drive.example/download/drive-file-1",
                }
            ]

    monkeypatch.setattr(files_router, "get_gdrive_client", lambda: FakeDriveClient())

    response = TestClient(backend_main.app).get("/api/files")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    file_item = payload["files"][0]
    assert file_item["file_id"] == "drive-file-1"
    assert file_item["filename"] == "brief.md"
    assert file_item["id"] == "gdrive://file/drive-file-1"
    assert file_item["name"] == "brief.md"
    assert file_item["kind"] == "drive"
    assert file_item["status"] == "downloadable"
    assert file_item["open_url"] == "https://drive.example/open/drive-file-1"
    assert file_item["download_url"] == "https://drive.example/download/drive-file-1"


def test_backend_main_file_info_route_returns_normalized_metadata(monkeypatch):
    from backend.api.routers import files as files_router

    class FakeDriveClient:
        def get_file_info(self, file_id):
            assert file_id == "drive-file-1"
            return {
                "file_id": "drive-file-1",
                "storage_ref": "gdrive://file/drive-file-1",
                "filename": "brief.md",
                "mime_type": "text/markdown",
                "size": 42,
                "web_view_link": "https://drive.example/open/drive-file-1",
                "web_content_link": "https://drive.example/download/drive-file-1",
                "is_trashed": False,
            }

    monkeypatch.setattr(files_router, "get_gdrive_client", lambda: FakeDriveClient())

    response = TestClient(backend_main.app).get("/api/files/drive-file-1")

    assert response.status_code == 200
    payload = response.json()
    file_item = payload["file"]
    assert file_item["file_id"] == "drive-file-1"
    assert file_item["id"] == "gdrive://file/drive-file-1"
    assert file_item["name"] == "brief.md"
    assert file_item["kind"] == "drive"
    assert file_item["status"] == "downloadable"
    assert file_item["open_url"] == "https://drive.example/open/drive-file-1"
    assert file_item["download_url"] == "https://drive.example/download/drive-file-1"


def test_backend_main_file_info_route_returns_404_for_missing_file(monkeypatch):
    from backend.api.routers import files as files_router

    class FakeDriveClient:
        def get_file_info(self, file_id):
            assert file_id == "missing-file"
            return None

    monkeypatch.setattr(files_router, "get_gdrive_client", lambda: FakeDriveClient())

    response = TestClient(backend_main.app).get("/api/files/missing-file")

    assert response.status_code == 404
    assert response.json()["detail"] == "파일을 찾을 수 없습니다"


def test_backend_main_file_download_route_returns_ui_action_links(monkeypatch):
    from backend.api.routers import files as files_router

    class FakeDriveClient:
        def get_file_info(self, file_id):
            assert file_id == "drive-file-1"
            return {
                "file_id": "drive-file-1",
                "storage_ref": "gdrive://file/drive-file-1",
                "filename": "brief.md",
                "mime_type": "text/markdown",
                "web_view_link": "https://drive.example/open/drive-file-1",
                "web_content_link": "https://drive.example/download/drive-file-1",
            }

    monkeypatch.setattr(files_router, "get_gdrive_client", lambda: FakeDriveClient())

    response = TestClient(backend_main.app).get("/api/files/drive-file-1/download")

    assert response.status_code == 200
    payload = response.json()
    assert payload["file"]["id"] == "gdrive://file/drive-file-1"
    assert payload["download"]["available"] is True
    assert payload["download"]["url"] == "https://drive.example/download/drive-file-1"
    assert payload["download"]["fallback_open_url"] == "https://drive.example/open/drive-file-1"
    assert payload["download"]["method"] == "open_url"


def test_backend_main_folder_routes_return_normalized_folders(monkeypatch):
    from backend.api.routers import files as files_router

    class FakeDriveClient:
        def find_folder_by_name(self, name):
            assert name == "reports"
            return [
                {
                    "folder_id": "folder-1",
                    "storage_ref": "gdrive://file/folder-1",
                    "folder_name": "reports",
                    "web_view_link": "https://drive.example/folders/folder-1",
                }
            ]

        def create_folder(self, name, parent_folder_id=None):
            assert name == "reports"
            assert parent_folder_id == "parent-1"
            return {
                "file_id": "folder-2",
                "storage_ref": "gdrive://file/folder-2",
                "folder_name": "reports",
                "web_view_link": "https://drive.example/folders/folder-2",
            }

    monkeypatch.setattr(files_router, "get_gdrive_client", lambda: FakeDriveClient())
    client = TestClient(backend_main.app)

    search_response = client.get("/api/folders", params={"name": "reports"})
    create_response = client.post(
        "/api/folders",
        json={"name": "reports", "parent_folder_id": "parent-1"},
    )

    assert search_response.status_code == 200
    folder = search_response.json()["folders"][0]
    assert folder["id"] == "gdrive://file/folder-1"
    assert folder["folder_id"] == "folder-1"
    assert folder["name"] == "reports"
    assert folder["kind"] == "folder"
    assert folder["open_url"] == "https://drive.example/folders/folder-1"

    assert create_response.status_code == 200
    created = create_response.json()["folder"]
    assert created["id"] == "gdrive://file/folder-2"
    assert created["folder_id"] == "folder-2"


def test_backend_main_file_update_route_renames_drive_file(monkeypatch):
    from backend.api.routers import files as files_router

    class FakeDriveClient:
        def update_file(self, file_id, new_name=None):
            assert file_id == "drive-file-1"
            assert new_name == "renamed.md"
            return {
                "file_id": "drive-file-1",
                "storage_ref": "gdrive://file/drive-file-1",
                "filename": "renamed.md",
                "mime_type": "text/markdown",
                "web_view_link": "https://drive.example/open/drive-file-1",
            }

    monkeypatch.setattr(files_router, "get_gdrive_client", lambda: FakeDriveClient())

    response = TestClient(backend_main.app).patch(
        "/api/files/drive-file-1",
        json={"name": "renamed.md"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "파일 이름 변경 완료"
    assert payload["file"]["name"] == "renamed.md"
    assert payload["file"]["id"] == "gdrive://file/drive-file-1"


def test_backend_main_file_delete_route_trashes_drive_file(monkeypatch):
    from backend.api.routers import files as files_router

    deleted_ids = []

    class FakeDriveClient:
        def delete_file(self, file_id):
            deleted_ids.append(file_id)
            return True

    monkeypatch.setattr(files_router, "get_gdrive_client", lambda: FakeDriveClient())

    response = TestClient(backend_main.app).delete("/api/files/drive-file-1")

    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert deleted_ids == ["drive-file-1"]


def test_backend_main_file_delete_route_returns_404_for_missing_file(monkeypatch):
    from backend.api.routers import files as files_router

    class FakeDriveClient:
        def delete_file(self, file_id):
            assert file_id == "missing-file"
            return False

    monkeypatch.setattr(files_router, "get_gdrive_client", lambda: FakeDriveClient())

    response = TestClient(backend_main.app).delete("/api/files/missing-file")

    assert response.status_code == 404
    assert response.json()["detail"] == "파일을 찾을 수 없습니다"


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
