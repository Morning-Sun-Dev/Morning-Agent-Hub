"""
모든 A2A 에이전트 서버를 한 번에 시작하는 런처

사용법:
    python start_agents.py          # 모든 에이전트 시작
    python start_agents.py --agent report  # 보고서 에이전트만 시작
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
AI_LLM_ROOT = PROJECT_ROOT / "ai_llm"
FRONTEND_ROOT = PROJECT_ROOT / "frontend"

AGENTS = {
    "web": {
        "name": "Web Research Agent",
        "port": 10011,
        "dir": AI_LLM_ROOT / "web_research_agent",
        "script": "agent_server.py",
    },
    "rag": {
        "name": "Internal RAG Agent",
        "port": 10012,
        "dir": AI_LLM_ROOT / "internal_rag_agent",
        "script": "agent_server.py",
    },
    "file": {
        "name": "File Management Agent",
        "port": 10013,
        "dir": AI_LLM_ROOT / "file_management_agent",
        "script": "agent_server.py",
    },
    "report": {
        "name": "Report Writing Agent",
        "port": 10014,
        "dir": AI_LLM_ROOT / "report_writing_agent",
        "script": "agent_server.py",
    },
    "orchestrator": {
        "name": "Orchestrator Agent",
        "port": 10010,
        "dir": AI_LLM_ROOT / "orchestrator_agent",
        "script": "agent_server.py",
    },
}


def start_backend() -> subprocess.Popen:
    print("  Starting FastAPI Backend on port 8000...")
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.api.main:app",
         "--host", "0.0.0.0", "--port", "8000"],
        cwd=str(PROJECT_ROOT),
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
    )


def start_frontend() -> subprocess.Popen:
    print("  Starting Frontend (Vite) on port 5173...")
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    return subprocess.Popen(
        [npm_cmd, "run", "dev"],
        cwd=str(FRONTEND_ROOT),
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
    )


def start_agent(key: str) -> subprocess.Popen:
    agent = AGENTS[key]
    agent_dir = agent["dir"]
    script_path = agent_dir / agent["script"]

    print(f"  Starting {agent['name']} on port {agent['port']}...")

    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
    return subprocess.Popen(
        [sys.executable, str(script_path)],
        cwd=str(agent_dir),
        env=env,
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
    )


def main():
    parser = argparse.ArgumentParser(description="A2A Multi-Agent System Launcher")
    parser.add_argument(
        "--agent",
        choices=list(AGENTS.keys()) + ["all"],
        default="all",
        help="시작할 에이전트 (default: all)",
    )
    parser.add_argument(
        "--no-frontend",
        action="store_true",
        help="프론트엔드 서버 시작 생략",
    )
    args = parser.parse_args()

    keys = list(AGENTS.keys()) if args.agent == "all" else [args.agent]

    print("=" * 60)
    print("A2A Multi-Agent System Launcher")
    print("=" * 60)

    processes = []
    for key in keys:
        if key == "orchestrator" and args.agent == "all":
            continue
        try:
            proc = start_agent(key)
            processes.append((key, proc))
            time.sleep(2)
        except Exception as e:
            print(f"  Failed to start {AGENTS[key]['name']}: {e}")

    if args.agent == "all":
        print("\n  Waiting for remote agents to initialize...")
        time.sleep(5)
        try:
            proc = start_agent("orchestrator")
            processes.append(("orchestrator", proc))
        except Exception as e:
            print(f"  Failed to start Orchestrator: {e}")

    try:
        proc = start_backend()
        processes.append(("backend", proc))
    except Exception as e:
        print(f"  Failed to start Backend: {e}")

    if not args.no_frontend:
        try:
            proc = start_frontend()
            processes.append(("frontend", proc))
        except Exception as e:
            print(f"  Failed to start Frontend: {e}")

    pids_file = PROJECT_ROOT / "running_agents.pids"
    pids_file.write_text("\n".join(str(p.pid) for _, p in processes))

    print("\n" + "=" * 60)
    print(f"Started {len(processes)} process(es)")
    print("Frontend:        http://localhost:5173")
    print("FastAPI Backend: http://localhost:8000")
    print(f"PIDs saved to:   {pids_file.name}  (stop_agents.py로 일괄 종료)")
    print("=" * 60)


if __name__ == "__main__":
    main()
