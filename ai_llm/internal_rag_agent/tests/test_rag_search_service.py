import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch


def test_rewrite_query_returns_string():
    from rag_search_service import rewrite_query

    with patch("rag_search_service._llm") as mock_llm:
        mock_llm.invoke.return_value = MagicMock(content="휴가 정책 연차 규정")
        result = rewrite_query("우리 회사 휴가 어떻게 돼?")

    assert isinstance(result, str)
    assert len(result) > 0


def test_rewrite_query_fallback_on_error():
    from rag_search_service import rewrite_query

    with patch("rag_search_service._llm") as mock_llm:
        mock_llm.invoke.side_effect = Exception("LLM error")
        result = rewrite_query("원본 질문")

    assert result == "원본 질문"


def test_generate_multi_queries_returns_list():
    from rag_search_service import generate_multi_queries

    with patch("rag_search_service._llm") as mock_llm:
        mock_llm.invoke.return_value = MagicMock(content="쿼리1\n쿼리2\n쿼리3")
        result = generate_multi_queries("휴가 정책 연차 규정")

    assert isinstance(result, list)
    assert len(result) == 3
    assert result[0] == "쿼리1"


def test_generate_multi_queries_fallback_on_error():
    from rag_search_service import generate_multi_queries

    with patch("rag_search_service._llm") as mock_llm:
        mock_llm.invoke.side_effect = Exception("LLM error")
        result = generate_multi_queries("쿼리")

    assert result == []


def test_search_documents_multi_query_dedup():
    from rag_search_service import search_documents

    mock_sb = MagicMock()
    dup_result = {
        "id": "uuid-abc", "content": "내용", "filename": "test.txt",
        "storage_ref": "gdrive://file/abc", "chunk_index": 0,
        "document_type": "text", "created_at": None, "similarity": 0.85,
    }
    mock_sb.rpc.return_value.execute.return_value.data = [dup_result]

    with patch("rag_search_service.rewrite_query", return_value="재작성 쿼리"), \
         patch("rag_search_service.generate_multi_queries", return_value=["변형1", "변형2"]), \
         patch("rag_search_service._embeddings") as mock_emb:

        mock_emb.embed_query.return_value = [0.1] * 1536
        results, sources = search_documents("테스트 질문", mock_sb)

    # 3개 쿼리가 동일 청크 반환해도 중복 제거 후 1개
    assert len(results) == 1
    assert results[0]["storage_ref"] == "gdrive://file/abc"


def test_search_documents_threshold_rpc_param():
    from rag_search_service import search_documents

    mock_sb = MagicMock()
    mock_sb.rpc.return_value.execute.return_value.data = []

    with patch("rag_search_service.rewrite_query", return_value="쿼리"), \
         patch("rag_search_service.generate_multi_queries", return_value=[]), \
         patch("rag_search_service._embeddings") as mock_emb:

        mock_emb.embed_query.return_value = [0.1] * 1536
        search_documents("질문", mock_sb, match_threshold=0.3)

    call_kwargs = mock_sb.rpc.call_args_list[0][0][1]
    assert call_kwargs["match_threshold"] == 0.3
    assert call_kwargs["match_count"] == 10
