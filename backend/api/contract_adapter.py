import json
from typing import Any
from uuid import uuid4

from backend.api.schemas import ChatResponse
from common.contracts import (
    ArtifactEnvelope,
    FileArtifactContract,
    ProgressItemContract,
    SourceContract,
)
from common.schemas import AgentResponse


AGENT_LABELS = {
    "orchestrator": "요청 분석",
    "web_research": "웹 검색",
    "internal_rag": "내부 문서 검색",
    "file_management": "파일 처리",
    "report_writing": "보고서 작성",
}

VALID_AGENTS = set(AGENT_LABELS)

TRACE_STATUS_MAP = {
    "started": "running",
    "completed": "completed",
    "failed": "failed",
    "skipped": "skipped",
}

ANSWER_ARTIFACT_NAMES = (
    "orchestrator_result",
    "report_result",
    "rag_answer",
    "file_operation_result",
    "web_search_result",
    "response",
)


def build_chat_response(
    agent_response: AgentResponse,
    session_id: str,
    run_id: str | None = None,
) -> ChatResponse:
    """Normalize A2A wrapper output into the backend/frontend chat contract."""
    resolved_run_id = run_id or uuid4().hex

    if not agent_response.success:
        return ChatResponse(
            run_id=resolved_run_id,
            session_id=session_id,
            status="failed",
            answer="",
            error=agent_response.error or agent_response.message or "요청 처리에 실패했습니다.",
        )

    artifacts = agent_response.artifacts or []
    answer = _select_answer(artifacts)
    progress = _collect_progress(artifacts, resolved_run_id)
    sources = _collect_sources(artifacts)
    files = _collect_files(artifacts)
    envelopes = _collect_artifact_envelopes(artifacts, sources, files)
    status = "partial_failure" if any(item.status == "failed" for item in progress) else "completed"

    return ChatResponse(
        run_id=resolved_run_id,
        session_id=session_id,
        status=status,
        answer=answer,
        progress=progress,
        sources=sources,
        files=files,
        artifacts=envelopes,
        error="일부 작업이 실패했습니다." if status == "partial_failure" else None,
    )


def _select_answer(artifacts: list[dict[str, Any]]) -> str:
    for name in ANSWER_ARTIFACT_NAMES:
        for artifact in artifacts:
            if artifact.get("name") == name and artifact.get("text"):
                return str(artifact["text"])

    for artifact in artifacts:
        name = artifact.get("name")
        if name in {"execution_trace", "web_search_sources"}:
            continue
        if artifact.get("text"):
            return str(artifact["text"])
    return ""


def _collect_progress(artifacts: list[dict[str, Any]], run_id: str) -> list[ProgressItemContract]:
    progress: list[ProgressItemContract] = []
    for artifact in artifacts:
        if artifact.get("name") != "execution_trace":
            continue
        trace_items = _loads_jsonish(artifact.get("data") or artifact.get("text"))
        if not isinstance(trace_items, list):
            continue
        for item in trace_items:
            if not isinstance(item, dict):
                continue
            agent_id = _coerce_agent_id(item.get("agent"))
            raw_status = str(item.get("status") or "running")
            status = TRACE_STATUS_MAP.get(raw_status, raw_status)
            if status not in {"queued", "running", "completed", "warning", "failed", "skipped"}:
                status = "running"
            step_index = _nonnegative_int_or_none(item.get("step"))
            if item.get("step") is not None and step_index is None:
                continue
            progress.append(
                ProgressItemContract(
                    run_id=run_id,
                    step_index=step_index,
                    agent_id=agent_id,
                    label=AGENT_LABELS[agent_id],
                    message=str(item.get("message") or AGENT_LABELS[agent_id]),
                    status=status,
                    duration_ms=_nonnegative_int_or_none(item.get("duration_ms")),
                )
            )
    return progress


def _collect_sources(artifacts: list[dict[str, Any]]) -> list[SourceContract]:
    sources: list[SourceContract] = []
    for artifact in artifacts:
        if artifact.get("name") != "web_search_sources":
            continue
        raw_sources = _loads_jsonish(artifact.get("data") or artifact.get("text"))
        if not isinstance(raw_sources, list):
            continue
        for source in raw_sources:
            if not isinstance(source, dict):
                continue
            url = source.get("url")
            title = source.get("title") or url or "웹 출처"
            sources.append(
                SourceContract(
                    title=str(title),
                    url=str(url) if url else None,
                    source_type="web",
                    snippet=str(source.get("snippet") or source.get("content") or ""),
                    agent_id="web_research",
                    metadata={k: v for k, v in source.items() if k not in {"title", "url", "snippet", "content"}},
                )
            )
    return sources


def _collect_files(artifacts: list[dict[str, Any]]) -> list[FileArtifactContract]:
    files: list[FileArtifactContract] = []
    for artifact in artifacts:
        name = artifact.get("name")
        data = artifact.get("data")
        if name == "file_list" and isinstance(data, dict):
            for item in data.get("files", []):
                if isinstance(item, dict):
                    files.append(_file_from_drive_item(item))
        elif name == "report_document" and isinstance(data, dict):
            files.append(_file_from_report_document(data))
    return files


def _collect_artifact_envelopes(
    artifacts: list[dict[str, Any]],
    sources: list[SourceContract],
    files: list[FileArtifactContract],
) -> list[ArtifactEnvelope]:
    envelopes: list[ArtifactEnvelope] = []

    for source in sources:
        envelopes.append(
            ArtifactEnvelope(
                id=_stable_id("source", source.url or source.title),
                kind="web_source",
                agent_id="web_research",
                name=source.title,
                source=source,
            )
        )

    for file in files:
        kind = "report_document" if file.kind == "generated" else "file_list"
        agent_id = "report_writing" if file.kind == "generated" else "file_management"
        text = _report_text_for_file(artifacts, file.name) if file.kind == "generated" else None
        data = _report_data_for_file(artifacts, file.name) if file.kind == "generated" else {}
        envelopes.append(
            ArtifactEnvelope(
                id=_stable_id("file", file.id),
                kind=kind,
                agent_id=agent_id,
                name=file.name,
                text=text,
                data=data,
                file=file,
            )
        )

    return envelopes


def _file_from_drive_item(item: dict[str, Any]) -> FileArtifactContract:
    storage_ref = item.get("storage_ref")
    file_id = item.get("file_id") or storage_ref
    open_url = item.get("web_view_link") or item.get("open_url") or item.get("openUrl")
    download_url = item.get("download_url") or item.get("downloadUrl")
    filename = item.get("filename") or item.get("name") or str(file_id or "파일")
    return FileArtifactContract(
        id=str(storage_ref or file_id or filename),
        name=str(filename),
        kind="drive",
        status="downloadable" if open_url or download_url else "pending",
        storage_ref=str(storage_ref) if storage_ref else None,
        mime_type=item.get("mime_type") or item.get("mimeType"),
        size=item.get("size"),
        open_url=str(open_url) if open_url else None,
        download_url=str(download_url) if download_url else None,
    )


def _file_from_report_document(data: dict[str, Any]) -> FileArtifactContract:
    filename = data.get("filename_suggestion") or data.get("filename") or data.get("title") or "report.md"
    storage_ref = data.get("storage_ref")
    open_url = data.get("web_view_link") or data.get("open_url")
    download_url = data.get("download_url")
    return FileArtifactContract(
        id=str(storage_ref or filename),
        name=str(filename),
        kind="generated",
        status="downloadable" if storage_ref or open_url or download_url else "pending",
        storage_ref=str(storage_ref) if storage_ref else None,
        mime_type=data.get("mime_type") or "text/markdown",
        open_url=str(open_url) if open_url else None,
        download_url=str(download_url) if download_url else None,
    )


def _report_text_for_file(artifacts: list[dict[str, Any]], filename: str) -> str | None:
    for artifact in artifacts:
        if artifact.get("name") != "report_document" or not isinstance(artifact.get("data"), dict):
            continue
        data = artifact["data"]
        artifact_filename = data.get("filename_suggestion") or data.get("filename") or data.get("title")
        if artifact_filename == filename and data.get("content"):
            return data["content"]
    for artifact in artifacts:
        if artifact.get("name") == "report_result":
            return artifact.get("text")
    return None


def _report_data_for_file(artifacts: list[dict[str, Any]], filename: str) -> dict[str, Any]:
    for artifact in artifacts:
        if artifact.get("name") != "report_document" or not isinstance(artifact.get("data"), dict):
            continue
        data = artifact["data"]
        artifact_filename = data.get("filename_suggestion") or data.get("filename") or data.get("title")
        if artifact_filename == filename:
            return data
    return {}


def _loads_jsonish(value: Any) -> Any:
    if value is None or isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def _coerce_agent_id(value: Any) -> str:
    agent_id = str(value or "orchestrator")
    return agent_id if agent_id in VALID_AGENTS else "orchestrator"


def _nonnegative_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}:{value}"
