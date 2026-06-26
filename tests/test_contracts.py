from common.contracts import (
    ArtifactEnvelope,
    CapabilityId,
    ChatResponseContract,
    FileArtifactContract,
    PlanStepContract,
    ProgressItemContract,
    SourceContract,
)
from backend.api.schemas import ChatResponse


def test_chat_response_contract_defaults_to_empty_sections():
    response = ChatResponseContract(
        run_id="run_1",
        session_id="session_1",
        status="completed",
        answer="완료되었습니다.",
    )

    assert response.plan == []
    assert response.progress == []
    assert response.sources == []
    assert response.files == []
    assert response.artifacts == []
    assert response.error is None


def test_chat_response_contract_serializes_partial_failure():
    response = ChatResponseContract(
        run_id="run_2",
        session_id="session_1",
        status="partial_failure",
        answer="웹 검색은 완료됐지만 파일 저장은 실패했습니다.",
        progress=[
            ProgressItemContract(
                run_id="run_2",
                step_index=0,
                agent_id="web_research",
                capability_id="web_search",
                label="웹 검색",
                message="검색 완료",
                status="completed",
                duration_ms=1200,
            ),
            ProgressItemContract(
                run_id="run_2",
                step_index=1,
                agent_id="file_management",
                capability_id="upload_file",
                label="파일 저장",
                message="Drive 업로드 실패",
                status="failed",
            ),
        ],
        sources=[
            SourceContract(
                title="OpenAI News",
                url="https://openai.com/news/",
                source_type="web",
                snippet="제품 업데이트",
                agent_id="web_research",
            )
        ],
        files=[
            FileArtifactContract(
                id="file_1",
                name="report.md",
                kind="generated",
                status="failed",
                message="Drive 업로드 실패",
            )
        ],
        error="일부 작업이 실패했습니다.",
    )

    payload = response.model_dump()

    assert payload["status"] == "partial_failure"
    assert payload["progress"][1]["status"] == "failed"
    assert payload["sources"][0]["source_type"] == "web"
    assert payload["files"][0]["status"] == "failed"
    assert payload["error"] == "일부 작업이 실패했습니다."


def test_chat_response_contract_contains_mixed_artifacts():
    source = SourceContract(
        title="휴가규정_2026.pdf",
        url="https://drive.google.com/file/d/abc/view",
        source_type="internal_document",
        snippet="연차 사용 기준",
        agent_id="internal_rag",
    )
    generated_file = FileArtifactContract(
        id="gdrive://file/report123",
        name="vacation-summary.md",
        kind="generated",
        status="downloadable",
        storage_ref="gdrive://file/report123",
        mime_type="text/markdown",
        open_url="https://drive.google.com/file/d/report123/view",
        download_url="https://drive.google.com/uc?id=report123",
    )
    response = ChatResponseContract(
        run_id="run_3",
        session_id="session_1",
        status="completed",
        answer="휴가 규정 요약입니다.",
        plan=[
            PlanStepContract(
                index=0,
                agent_id="internal_rag",
                capability_id="rag_vector_search",
                query="휴가 규정을 검색해줘",
            ),
            PlanStepContract(
                index=1,
                agent_id="report_writing",
                capability_id="write_report",
                query="검색 결과를 요약 보고서로 작성해줘",
                depends_on=0,
            ),
        ],
        sources=[source],
        files=[generated_file],
        artifacts=[
            ArtifactEnvelope(
                id="artifact_1",
                kind="document_source",
                agent_id="internal_rag",
                name="retrieved_document",
                source=source,
            ),
            ArtifactEnvelope(
                id="artifact_2",
                kind="report_document",
                agent_id="report_writing",
                name="vacation-summary.md",
                file=generated_file,
                text="# 휴가 규정 요약",
            ),
        ],
    )

    payload = response.model_dump()

    assert payload["plan"][1]["depends_on"] == 0
    assert payload["artifacts"][0]["source"]["title"] == "휴가규정_2026.pdf"
    assert payload["artifacts"][1]["file"]["download_url"].endswith("report123")


def test_backend_chat_response_accepts_contract_fields():
    response = ChatResponse(
        run_id="run_4",
        session_id="session_1",
        status="completed",
        answer="백엔드 응답입니다.",
        progress=[
            ProgressItemContract(
                run_id="run_4",
                agent_id="orchestrator",
                capability_id="route_request",
                label="요청 분석",
                message="완료",
                status="completed",
            )
        ],
    )

    payload = response.model_dump()

    assert payload["answer"] == "백엔드 응답입니다."
    assert payload["progress"][0]["agent_id"] == "orchestrator"


def test_contract_aliases_are_exported_from_common_package():
    import common

    assert hasattr(common, "AgentId")
    assert hasattr(common, "RunEventContract")


def test_capability_registry_covers_every_shared_capability():
    from typing import get_args

    from common.capabilities import list_capabilities

    capabilities = list_capabilities()
    capability_ids = {item.capability_id for item in capabilities}

    assert capability_ids == set(get_args(CapabilityId))
    assert {item.agent_id for item in capabilities} == {
        "orchestrator",
        "web_research",
        "internal_rag",
        "file_management",
        "report_writing",
    }
    assert any(
        item.capability_id == "web_search" and item.ui_status == "available"
        for item in capabilities
    )
    assert any(
        item.capability_id == "delete_file" and item.ui_status == "planned"
        for item in capabilities
    )
    assert any(
        item.capability_id == "list_files"
        and item.ui_status == "available"
        and item.ui_surface == "파일 패널"
        for item in capabilities
    )
    assert any(
        item.capability_id == "get_file_info"
        and item.ui_status == "available"
        and item.ui_surface == "파일 패널"
        for item in capabilities
    )
