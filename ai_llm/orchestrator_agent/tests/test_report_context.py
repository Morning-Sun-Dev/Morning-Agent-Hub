"""ReportContext 취합 로직 단위 테스트"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.report_context import (
    ReportContext,
    SourceReference,
    parse_report_context,
    serialize_report_context,
    detect_template_id,
    extract_report_topic,
)
from models import AgentResult, PlanStep, TraceStep


def test_detect_template_id_research():
    assert detect_template_id("조사 보고서로 작성") == "research_report"


def test_report_context_roundtrip():
    ctx = ReportContext(
        template_id="research_report",
        language="ko",
        instruction="research_report 양식으로 작성",
        sources=[
            SourceReference(
                agent="web_research",
                summary="계란요리 레시피 5가지",
                references=[{"title": "레시피", "url": "https://example.com", "snippet": "..."}],
            ),
        ],
    )
    payload = serialize_report_context(ctx)
    parsed = parse_report_context(payload)
    assert parsed is not None
    assert parsed.template_id == "research_report"
    assert len(parsed.sources) == 1
    assert "계란요리" in parsed.to_source_text()


def test_build_report_context_aggregates_all_upstream():
    from report_context_builder import build_report_context, build_report_query

    web = AgentResult(
        agent="web_research",
        success=True,
        content="웹 검색 요약",
        artifacts=[
            {"name": "web_search_sources", "text": json.dumps([
                {"title": "AI News", "url": "https://ai.com", "content": "snippet"},
            ])},
        ],
        trace=TraceStep(step=0, agent="web_research", status="completed", message="ok"),
    )
    rag = AgentResult(
        agent="internal_rag",
        success=True,
        content="사내 문서 검색 결과",
        artifacts=[],
        trace=TraceStep(step=1, agent="internal_rag", status="completed", message="ok"),
    )
    report_step = PlanStep(
        agent="report_writing",
        query="research_report 양식으로 임원 보고서 작성",
        depends_on=1,
    )
    results = [web, rag, None]

    ctx = build_report_context(report_step, 2, results)
    assert len(ctx.sources) == 2
    assert ctx.sources[0].agent == "web_research"
    assert ctx.sources[1].agent == "internal_rag"
    assert len(ctx.sources[0].references) == 1

    query = build_report_query(report_step, 2, results)
    assert "[REPORT_CONTEXT]" in query
    assert parse_report_context(query) is not None


def test_extract_report_topic_from_user_query():
    q = "내 드라이브에 test.txt 참고해서 그 양식대로 SQL에 대한 보고서 작성하고 저장해줘"
    assert extract_report_topic("", q) == "SQL"
    assert extract_report_topic("보고서 주제: SQL. technical_report 형식", q) == "SQL"


def test_format_vs_content_source_roles():
    from report_context_builder import build_report_context, extract_source_reference

    user_q = "test.txt 양식 참고해서 SQL에 대한 보고서 작성"
    rag = AgentResult(
        agent="internal_rag",
        success=True,
        content="LangChain과 RAG 실습 내용...",
        artifacts=[],
        trace=TraceStep(step=0, agent="internal_rag", status="completed", message="ok"),
    )
    web = AgentResult(
        agent="web_research",
        success=True,
        content="SQL은 관계형 DB 질의 언어...",
        artifacts=[],
        trace=TraceStep(step=1, agent="web_research", status="completed", message="ok"),
    )

    rag_ref = extract_source_reference(rag, "test.txt 양식 참고", user_q)
    web_ref = extract_source_reference(web, "보고서 주제: SQL", user_q)
    assert rag_ref.role == "format"
    assert web_ref.role == "content"

    report_step = PlanStep(
        agent="report_writing",
        query="보고서 주제: SQL. test.txt 양식 구조만 참고",
        depends_on=1,
    )
    ctx = build_report_context(report_step, 2, [rag, web], user_query=user_q)
    assert ctx.report_topic == "SQL"
    text = ctx.to_source_text()
    assert "보고서 주제" in text or "SQL" in text
    assert "양식 예시" in text
    assert "본문 참고" in text
    assert "LangChain" in text
    assert "SQL은" in text


def test_file_content_artifact_used_as_format_source():
    from report_context_builder import build_report_context, extract_source_reference

    user_q = "test.txt 양식 참고해서 SQL에 대한 보고서 작성"
    file_result = AgentResult(
        agent="file_management",
        success=True,
        content="test.txt 파일을 확인했습니다.",
        artifacts=[
            {
                "name": "file_content",
                "data": {
                    "filename": "test.txt",
                    "content": "# 개요\n1. LangChain 실습\n2. RAG 개요",
                },
            },
        ],
        trace=TraceStep(step=0, agent="file_management", status="completed", message="ok"),
    )
    web = AgentResult(
        agent="web_research",
        success=True,
        content="SQL 요약",
        artifacts=[
            {"name": "web_search_result", "text": "SQL은 관계형 DB 질의 언어입니다."},
            {"name": "web_search_sources", "text": json.dumps([
                {"title": "SQL Guide", "url": "https://example.com", "content": "SELECT, INSERT 문법"},
            ])},
        ],
        trace=TraceStep(step=1, agent="web_research", status="completed", message="ok"),
    )

    file_ref = extract_source_reference(file_result, "test.txt 양식 참고", user_q)
    assert file_ref.role == "format"
    assert "LangChain 실습" in file_ref.summary

    web_ref = extract_source_reference(web, "보고서 주제: SQL", user_q)
    assert "SELECT" in web_ref.summary or "관계형" in web_ref.summary

    report_step = PlanStep(
        agent="report_writing",
        query="보고서 주제: SQL. test.txt 양식 구조만 참고",
        depends_on=1,
    )
    ctx = build_report_context(report_step, 2, [file_result, web], user_query=user_q)
    assert ctx.format_example
    assert "LangChain 실습" in ctx.format_example
    assert ctx.report_topic == "SQL"
