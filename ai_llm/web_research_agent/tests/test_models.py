import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from pydantic import ValidationError
from models import WebSource, WebSearchResult


def test_web_source_valid():
    source = WebSource(title="테스트", url="https://example.com", snippet="내용", score=0.9)
    assert source.title == "테스트"
    assert source.url == "https://example.com"
    assert source.score == 0.9


def test_web_source_optional_fields():
    source = WebSource(title="최소", url="https://example.com")
    assert source.snippet is None
    assert source.score is None


def test_web_source_score_out_of_range_raises():
    with pytest.raises(ValidationError):
        WebSource(title="테스트", url="https://example.com", score=1.5)


def test_web_source_negative_score_raises():
    with pytest.raises(ValidationError):
        WebSource(title="테스트", url="https://example.com", score=-0.1)


def test_web_search_result_valid():
    result = WebSearchResult(
        query="AI 트렌드",
        summary="AI 트렌드 요약",
        sources=[WebSource(title="출처1", url="https://example.com")],
    )
    assert result.query == "AI 트렌드"
    assert len(result.sources) == 1
    assert result.search_successful is True


def test_web_search_result_empty_sources():
    result = WebSearchResult(query="테스트", summary="요약")
    assert result.sources == []
    assert result.search_successful is True


def test_web_search_result_failure():
    result = WebSearchResult(query="실패", summary="검색 실패", search_successful=False)
    assert result.search_successful is False


def test_web_search_result_missing_query_raises():
    with pytest.raises(ValidationError):
        WebSearchResult(summary="요약")


def test_web_search_result_missing_summary_raises():
    with pytest.raises(ValidationError):
        WebSearchResult(query="테스트")
