import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_executor import build_child_artifact_payloads


def test_build_child_artifact_payloads_preserves_artifact_data():
    payloads = build_child_artifact_payloads([
        {
            "name": "web_search_sources",
            "text": '[{"title":"출처","url":"https://example.com"}]',
        },
        {
            "name": "file_list",
            "data": {"files": [{"filename": "a.pdf", "storage_ref": "gdrive://file/a"}]},
        },
    ])

    assert len(payloads) == 2
    assert payloads[0][0] == "web_search_sources"
    assert payloads[0][1][0].root.text.startswith("[")
    assert payloads[1][0] == "file_list"
    assert payloads[1][1][0].root.data["files"][0]["filename"] == "a.pdf"
