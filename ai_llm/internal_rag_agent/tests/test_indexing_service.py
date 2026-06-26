import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch, call
from indexing_service import chunk_documents, index_document, IndexJobStatus


def test_chunk_documents_default_size():
    text = "a" * 1000
    chunks = chunk_documents(text)
    # 기본 청크 크기 800 적용 확인 — 1000자 텍스트는 2청크 이하로 분할
    assert len(chunks) <= 2


def test_chunk_documents_custom_size():
    text = "a" * 1000
    chunks = chunk_documents(text, chunk_size=200, chunk_overlap=20)
    assert len(chunks) > 2


def test_index_document_batch_insert():
    """배치 INSERT: sb.table().insert()가 1번만 호출되어야 한다"""
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []

    dummy_bytes = b"hello world " * 100
    with patch("indexing_service.parse_document") as mock_parse, \
         patch("indexing_service.embed_chunks") as mock_embed:

        mock_parse.return_value = MagicMock(
            text="hello world " * 100,
            filename="test.txt",
            document_type="text",
        )
        mock_embed.return_value = [[0.1] * 1536, [0.2] * 1536]

        with patch("indexing_service.chunk_documents") as mock_chunk:
            mock_chunk.return_value = ["chunk1", "chunk2"]
            job = index_document(mock_sb, "gdrive://file/abc", "test.txt", dummy_bytes, "text/plain")

    assert job.status == IndexJobStatus.SUCCESS
    assert job.chunk_count == 2
    # insert가 정확히 1번 호출되어야 함 (배치)
    insert_calls = mock_sb.table.return_value.insert.call_args_list
    assert len(insert_calls) == 1
    # insert에 전달된 rows가 리스트여야 함
    rows_arg = insert_calls[0][0][0]
    assert isinstance(rows_arg, list)
    assert len(rows_arg) == 2
