"""End-to-end smoke runner for the local Morning Agent Hub stack."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib import parse, request
from urllib.error import HTTPError, URLError


REQUIRED_CAPABILITY_IDS = {
    "route_request",
    "web_search",
    "news_search",
    "url_fetch",
    "rag_vector_search",
    "upload_file",
    "list_files",
    "download_file",
    "write_report",
}


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str

    @property
    def passed(self) -> bool:
        return self.status in {"pass", "warn"}


class SmokeHttpClient:
    def __init__(self, base_url: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_json(self, path: str) -> Any:
        return json.loads(self.get_text(path))

    def get_text(self, path: str, query: dict[str, str] | None = None) -> str:
        url = self._url(path, query)
        with request.urlopen(url, timeout=self.timeout) as response:
            return response.read().decode("utf-8")

    def post_file(self, path: str, file_path: Path) -> Any:
        boundary = "----morning-agent-hub-smoke"
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        body = b"".join(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                (
                    'Content-Disposition: form-data; name="file"; '
                    f'filename="{file_path.name}"\r\n'
                ).encode("utf-8"),
                f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
                file_path.read_bytes(),
                f"\r\n--{boundary}--\r\n".encode("utf-8"),
            ]
        )
        req = request.Request(
            self._url(path),
            data=body,
            method="POST",
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
            },
        )
        with request.urlopen(req, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _url(self, path: str, query: dict[str, str] | None = None) -> str:
        normalized = path if path.startswith("/") else f"/{path}"
        url = f"{self.base_url}{normalized}"
        if query:
            url = f"{url}?{parse.urlencode(query)}"
        return url


def parse_sse_events(raw: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line.removeprefix("data:").strip()
        if not payload or payload == "[DONE]":
            continue
        events.append(json.loads(payload))
    return events


def validate_capability_payload(payload: Any) -> CheckResult:
    if not isinstance(payload, list):
        return CheckResult("capabilities", "fail", "capability payload is not a list")

    capability_ids = {
        item.get("capability_id")
        for item in payload
        if isinstance(item, dict)
    }
    missing = sorted(REQUIRED_CAPABILITY_IDS - capability_ids)
    if missing:
        return CheckResult(
            "capabilities",
            "fail",
            f"missing core capability ids: {', '.join(missing)}",
        )

    return CheckResult(
        "capabilities",
        "pass",
        f"{len(payload)} capabilities exposed",
    )


def validate_stream_events(events: list[dict[str, Any]]) -> CheckResult:
    answers = [
        event
        for event in events
        if event.get("type") == "answer" and str(event.get("content") or "").strip()
    ]
    if not answers:
        return CheckResult("chat_stream", "fail", "missing non-empty answer event")

    answer = answers[-1]
    required_fields = {
        "session_id",
        "run_id",
        "status",
        "sources",
        "files",
        "progress",
        "artifacts",
        "error",
    }
    missing = sorted(required_fields - answer.keys())
    if missing:
        return CheckResult(
            "chat_stream",
            "fail",
            f"answer event missing structured fields: {', '.join(missing)}",
        )

    list_fields = ("sources", "files", "progress", "artifacts")
    invalid_lists = [
        field
        for field in list_fields
        if not isinstance(answer.get(field), list)
    ]
    if invalid_lists:
        return CheckResult(
            "chat_stream",
            "fail",
            f"answer event fields are not lists: {', '.join(invalid_lists)}",
        )

    status = answer.get("status") or "completed"
    run_id = answer.get("run_id") or "(missing)"
    return CheckResult("chat_stream", "pass", f"answer event received with status={status}, run_id={run_id}")


def validate_health_payload(payload: Any) -> CheckResult:
    if not isinstance(payload, dict):
        return CheckResult("health", "fail", "health payload is not an object")
    status = payload.get("status")
    agents = payload.get("agents") or []
    if status == "healthy":
        return CheckResult("health", "pass", f"{len(agents)} agents online")
    if status == "degraded":
        offline = [
            agent.get("name")
            for agent in agents
            if isinstance(agent, dict) and not agent.get("online")
        ]
        return CheckResult("health", "fail", f"degraded, offline={offline}")
    return CheckResult("health", "fail", f"unexpected health status={status}")


def validate_templates_payload(payload: Any) -> CheckResult:
    if isinstance(payload, list) and payload:
        return CheckResult("report_templates", "pass", f"{len(payload)} templates exposed")
    return CheckResult("report_templates", "warn", "no report templates returned")


def validate_upload_payload(payload: Any) -> CheckResult:
    if not isinstance(payload, dict):
        return CheckResult("file_upload", "fail", "upload payload is not an object")
    filename = payload.get("filename") or payload.get("name")
    storage_ref = payload.get("storage_ref") or payload.get("id")
    if filename and storage_ref:
        return CheckResult("file_upload", "pass", f"uploaded {filename}")
    return CheckResult("file_upload", "fail", "upload response lacks filename or storage_ref")


def run_smoke(
    client: SmokeHttpClient,
    message: str,
    file_path: Path | None = None,
    skip_chat: bool = False,
    requested_capabilities: list[str] | None = None,
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    checks.append(_capture("health", lambda: validate_health_payload(client.get_json("/api/health"))))
    checks.append(
        _capture(
            "capabilities",
            lambda: validate_capability_payload(client.get_json("/api/capabilities")),
        )
    )
    checks.append(
        _capture(
            "report_templates",
            lambda: validate_templates_payload(client.get_json("/api/report-templates")),
        )
    )

    if file_path:
        checks.append(
            _capture(
                "file_upload",
                lambda: validate_upload_payload(client.post_file("/api/files/upload", file_path)),
            )
        )

    if not skip_chat:
        query = {"message": message}
        if requested_capabilities:
            query["requested_capabilities"] = json.dumps(requested_capabilities, ensure_ascii=False)
        checks.append(
            _capture(
                "chat_stream",
                lambda: validate_stream_events(
                    parse_sse_events(
                        client.get_text("/api/chat/stream", query)
                    )
                ),
            )
        )

    return checks


def _capture(name: str, action) -> CheckResult:
    try:
        return action()
    except HTTPError as exc:
        return CheckResult(name, "fail", f"HTTP {exc.code}: {exc.reason}")
    except (TimeoutError, URLError) as exc:
        return CheckResult(name, "fail", f"connection failed: {exc}")
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        return CheckResult(name, "fail", f"{type(exc).__name__}: {exc}")


def format_results(results: list[CheckResult]) -> str:
    lines = ["# Morning Agent Hub Smoke"]
    for result in results:
        marker = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}.get(result.status, result.status)
        lines.append(f"- {marker} `{result.name}`: {result.detail}")
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local Morning Agent Hub smoke checks.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--message", default="안녕하세요. 현재 시스템 상태를 짧게 알려줘.")
    parser.add_argument("--file", type=Path, default=None)
    parser.add_argument("--skip-chat", action="store_true")
    parser.add_argument(
        "--capability",
        action="append",
        default=[],
        help="Capability id to include in the chat stream smoke request. Repeatable.",
    )
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--timeout", type=float, default=120.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    client = SmokeHttpClient(args.base_url, timeout=args.timeout)
    results = run_smoke(
        client,
        message=args.message,
        file_path=args.file,
        skip_chat=args.skip_chat,
        requested_capabilities=args.capability,
    )

    if args.json_output:
        print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))
    else:
        print(format_results(results))

    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
