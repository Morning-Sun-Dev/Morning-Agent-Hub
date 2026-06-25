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

AGENTS = {
    "web": {
        "name": "Web Research Agent",
        "port": 10011,
        "dir": "web_research_agent",
        "script": "agent_server.py",
    },
    "rag": {
        "name": "Internal RAG Agent",
        "port": 10012,
        "dir": "internal_rag_agent",
        "script": "agent_server.py",
    },
    "file": {
        "name": "File Management Agent",
        "port": 10013,
        "dir": "file_management_agent",
        "script": "agent_server.py",
    },
    "report": {
        "name": "Report Writing Agent",
        "port": 10014,
        "dir": "report_writing_agent",
        "script": "agent_server.py",
    },
    "orchestrator": {
        "name": "Orchestrator Agent",
        "port": 10010,
        "dir": "orchestrator_agent",
        "script": "agent_server.py",
    },
}


def start_agent(key: str) -> subprocess.Popen:
    agent = AGENTS[key]
    agent_dir = PROJECT_ROOT / agent["dir"]
    script_path = agent_dir / agent["script"]

    print(f"  Starting {agent['name']} on port {agent['port']}...")

    return subprocess.Popen(
        [sys.executable, str(script_path)],
        cwd=str(agent_dir),
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

    print("\n" + "=" * 60)
    print(f"Started {len(processes)} agent(s)")
    print("FastAPI Backend: python backend/main.py  (port 8000)")
    print("Test Client:     python test_client.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
