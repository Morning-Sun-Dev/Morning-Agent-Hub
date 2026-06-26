import ast
import sys
from pathlib import Path
from types import SimpleNamespace


def test_start_agents_backend_uses_integrated_backend_entrypoint(monkeypatch):
    import start_agents

    calls = []

    def fake_popen(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(pid=12345)

    monkeypatch.setattr(start_agents.subprocess, "Popen", fake_popen)

    proc = start_agents.start_backend()

    assert proc.pid == 12345
    assert calls[0][0][:4] == [sys.executable, "-m", "uvicorn", "backend.main:app"]
    assert calls[0][1]["cwd"] == str(start_agents.PROJECT_ROOT)


def test_backend_main_runs_integrated_app_entrypoint(monkeypatch):
    import backend.main as backend_main

    run_calls = []

    def fake_run(*args, **kwargs):
        run_calls.append((args, kwargs))

    monkeypatch.setattr("uvicorn.run", fake_run)

    backend_main.main()

    assert run_calls[0][0][0] == "backend.main:app"
    assert run_calls[0][1]["port"] == 8000


def test_file_agent_card_uses_public_download_capability_id():
    source_path = Path("ai_llm/file_management_agent/agent_server.py")
    tree = ast.parse(source_path.read_text())
    skill_ids = {
        keyword.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", "") == "AgentSkill"
        for keyword in node.keywords
        if keyword.arg == "id" and isinstance(keyword.value, ast.Constant)
    }

    assert "download_file" in skill_ids
    assert "download_file_as_base64" not in skill_ids
