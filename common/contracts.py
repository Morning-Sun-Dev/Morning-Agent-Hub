"""Frontend/backend/orchestrator contract models.

These models are intentionally independent from FastAPI route classes and Vue
state. They define the stable data shape shared across agents, backend, and UI.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


AgentId = Literal[
    "orchestrator",
    "web_research",
    "internal_rag",
    "file_management",
    "report_writing",
]

CapabilityId = Literal[
    "route_request",
    "web_search",
    "news_search",
    "url_fetch",
    "rag_vector_search",
    "rag_sql_search",
    "rag_index",
    "upload_file",
    "download_file",
    "get_file_info",
    "find_folder",
    "list_files",
    "delete_file",
    "update_file",
    "create_folder",
    "write_report",
    "format_report",
    "list_templates",
]

UiSupportStatus = Literal[
    "available",
    "partial",
    "planned",
]

RunStatus = Literal[
    "queued",
    "planning",
    "running",
    "completed",
    "partial_failure",
    "failed",
    "cancelled",
]

StepStatus = Literal[
    "queued",
    "running",
    "completed",
    "warning",
    "failed",
    "skipped",
]

ArtifactKind = Literal[
    "answer",
    "web_source",
    "document_source",
    "uploaded_file",
    "generated_file",
    "file_list",
    "report_document",
    "trace",
    "error",
]


class CapabilityDescriptor(BaseModel):
    agent_id: AgentId
    capability_id: CapabilityId
    label: str
    description: str
    enabled: bool = True
    ui_status: UiSupportStatus = "planned"
    ui_surface: str = ""


class PlanStepContract(BaseModel):
    index: int = Field(ge=0)
    agent_id: AgentId
    query: str
    capability_id: CapabilityId | None = None
    depends_on: int | None = Field(default=None, ge=0)


class ProgressItemContract(BaseModel):
    run_id: str
    agent_id: AgentId
    label: str
    message: str
    status: StepStatus
    step_index: int | None = Field(default=None, ge=0)
    capability_id: CapabilityId | None = None
    duration_ms: int | None = Field(default=None, ge=0)


class SourceContract(BaseModel):
    title: str
    source_type: Literal["web", "internal_document", "uploaded_file"]
    url: str | None = None
    snippet: str = ""
    agent_id: AgentId | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FileArtifactContract(BaseModel):
    id: str
    name: str
    kind: Literal["uploaded", "generated", "drive", "download"]
    status: Literal["uploaded", "indexed", "downloadable", "failed", "pending"]
    storage_ref: str | None = None
    mime_type: str | None = None
    size: int | None = Field(default=None, ge=0)
    open_url: str | None = None
    download_url: str | None = None
    message: str = ""


class ArtifactEnvelope(BaseModel):
    id: str
    kind: ArtifactKind
    agent_id: AgentId
    name: str
    text: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    source: SourceContract | None = None
    file: FileArtifactContract | None = None


class ChatRequestContract(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None
    attachments: list[FileArtifactContract] = Field(default_factory=list)
    requested_capabilities: list[CapabilityId] = Field(default_factory=list)


class ChatResponseContract(BaseModel):
    run_id: str
    session_id: str
    status: RunStatus
    answer: str
    plan: list[PlanStepContract] = Field(default_factory=list)
    progress: list[ProgressItemContract] = Field(default_factory=list)
    sources: list[SourceContract] = Field(default_factory=list)
    files: list[FileArtifactContract] = Field(default_factory=list)
    artifacts: list[ArtifactEnvelope] = Field(default_factory=list)
    error: str | None = None


class RunEventContract(BaseModel):
    type: Literal["run_started", "plan", "progress", "artifact", "answer", "error", "done"]
    run_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
