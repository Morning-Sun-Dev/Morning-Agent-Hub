import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import pytest
from unittest.mock import MagicMock
from models import WebSource, WebSearchResult


def test_extract_sources_from_json_string():
    """JSON 문자열 형태의 Tavily 응답에서 WebSource 추출"""
    from agent import extract_sources

    mock_msg = MagicMock()
    mock_msg.content = json.dumps({
        "results": [
            {"title": "AI 뉴스", "url": "https://ai-news.com", "content": "AI 최신 트렌드", "score": 0.95},
            {"title": "Tech Blog", "url": "https://tech.com", "content": "기술 블로그", "score": 0.80},
        ]
    })

    sources = extract_sources([mock_msg])

    assert len(sources) == 2
    assert sources[0].title == "AI 뉴스"
    assert sources[0].url == "https://ai-news.com"
    assert sources[0].score == 0.95
    assert isinstance(sources[0], WebSource)


def test_extract_sources_invalid_json_returns_empty():
    """잘못된 JSON 응답 시 빈 목록 반환"""
    from agent import extract_sources

    mock_msg = MagicMock()
    mock_msg.content = "not valid json"

    sources = extract_sources([mock_msg])
    assert sources == []


def test_extract_sources_no_url_skips():
    """url 필드 없는 결과는 건너뜀"""
    from agent import extract_sources

    mock_msg = MagicMock()
    mock_msg.content = json.dumps({
        "results": [{"title": "URL 없음", "content": "내용만 있음"}]
    })

    sources = extract_sources([mock_msg])
    assert sources == []


def test_summarize_web_results_with_sources():
    """WebSource 목록을 마크다운 텍스트로 요약"""
    from agent import summarize_web_results

    sources = [
        WebSource(title="출처1", url="https://example1.com", snippet="첫 번째 내용입니다."),
        WebSource(title="출처2", url="https://example2.com"),
    ]

    result = summarize_web_results(sources)

    assert "출처1" in result
    assert "https://example1.com" in result
    assert "출처2" in result


def test_summarize_web_results_empty():
    """빈 목록 시 안내 메시지 반환"""
    from agent import summarize_web_results

    result = summarize_web_results([])
    assert result == "검색 결과가 없습니다."


@pytest.mark.asyncio
async def test_stream_yields_sources_in_final_chunk():
    """stream 최종 청크에 sources 키가 포함되는지 확인"""
    from agent import WebResearchAgent

    agent = WebResearchAgent.__new__(WebResearchAgent)
    agent.initialized = True

    async def fake_astream(input_data):
        yield {"agent": {"messages": [
            MagicMock(content="AI 트렌드 요약입니다.", tool_calls=None, name=None)
        ]}}

    mock_agent = MagicMock()
    mock_agent.astream = fake_astream
    agent.agent = mock_agent

    chunks = []
    async for chunk in agent.stream("AI 트렌드"):
        chunks.append(chunk)

    final = chunks[-1]
    assert final["is_task_complete"] is True
    assert "sources" in final
    assert isinstance(final["sources"], list)
