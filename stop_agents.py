"""
실행 중인 모든 에이전트/서버를 한 번에 종료하는 스크립트

사용법:
    python stop_agents.py
"""

import subprocess
import sys
from pathlib import Path

PIDS_FILE = Path(__file__).resolve().parent / "running_agents.pids"


def kill_process(pid: int):
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        subprocess.run(["kill", "-TERM", str(pid)], stderr=subprocess.DEVNULL)


def main():
    if not PIDS_FILE.exists():
        print("running_agents.pids 파일이 없습니다. 실행 중인 프로세스가 없거나 이미 종료됨.")
        return

    pids = [int(line.strip()) for line in PIDS_FILE.read_text().splitlines() if line.strip()]

    if not pids:
        print("종료할 프로세스가 없습니다.")
        PIDS_FILE.unlink()
        return

    print(f"총 {len(pids)}개 프로세스 종료 중...")
    for pid in pids:
        print(f"  PID {pid} 종료 중...")
        kill_process(pid)

    PIDS_FILE.unlink()
    print("\n모든 프로세스가 종료되었습니다.")


if __name__ == "__main__":
    main()
