import json

from scripts.smoke_system import (
    parse_sse_events,
    validate_health_payload,
    validate_capability_payload,
    validate_stream_events,
)


def test_parse_sse_events_keeps_json_payloads_and_ignores_done():
    raw = "\n".join(
        [
            'data: {"type": "status", "state": "working"}',
            "",
            'data: {"type": "answer", "content": "완료"}',
            "",
            "data: [DONE]",
            "",
        ]
    )

    assert parse_sse_events(raw) == [
        {"type": "status", "state": "working"},
        {"type": "answer", "content": "완료"},
    ]


def test_validate_capability_payload_requires_core_capabilities():
    payload = [
        {"agent_id": "orchestrator", "capability_id": "route_request"},
        {"agent_id": "web_research", "capability_id": "web_search"},
        {"agent_id": "internal_rag", "capability_id": "rag_vector_search"},
        {"agent_id": "file_management", "capability_id": "upload_file"},
        {"agent_id": "report_writing", "capability_id": "write_report"},
    ]

    result = validate_capability_payload(payload)

    assert result.passed is True
    assert result.status == "pass"


def test_validate_capability_payload_reports_missing_ids():
    result = validate_capability_payload([
        {"agent_id": "orchestrator", "capability_id": "route_request"},
    ])

    assert result.passed is False
    assert result.status == "fail"
    assert "web_search" in result.detail


def test_validate_health_payload_requires_healthy_stack():
    result = validate_health_payload({
        "status": "degraded",
        "agents": [{"name": "web_research", "online": False}],
    })

    assert result.passed is False
    assert result.status == "fail"
    assert "web_research" in result.detail


def test_validate_stream_events_requires_answer_content():
    result = validate_stream_events([
        {"type": "status", "state": "working"},
        {"type": "answer", "content": "## 답변\n\n완료"},
    ])

    assert result.passed is True
    assert result.status == "pass"


def test_validate_stream_events_rejects_missing_answer():
    result = validate_stream_events([
        {"type": "status", "state": "working"},
        json.loads('{"type": "answer", "content": ""}'),
    ])

    assert result.passed is False
    assert result.status == "fail"
    assert "answer" in result.detail
