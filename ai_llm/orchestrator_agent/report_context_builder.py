"""Orchestrator — upstream 결과 취합 → ReportContext"""

from __future__ import annotations

import json
import re
import sys
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

AI_LLM = Path(__file__).resolve().parents[1]
if str(AI_LLM) not in sys.path:
    sys.path.insert(0, str(AI_LLM))

from shared.report_context import (
    ReportContext,
    SourceReference,
    SourceRole,
    detect_template_id,
    extract_report_topic,
    serialize_report_context,
)

try:
    from .models import AgentResult, PlanStep
except ImportError:
    from models import AgentResult, PlanStep


def _parse_web_sources(artifacts: list) -> list[dict]:
    refs: list[dict] = []
    seen_urls: set[str] = set()

    for artifact in artifacts:
        name = artifact.get("name", "")
        text = artifact.get("text", "")
        if name == "web_search_sources" and text:
            try:
                items = json.loads(text)
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict) and item.get("url"):
                            url = item["url"]
                            if url not in seen_urls:
                                seen_urls.add(url)
                                refs.append({
                                    "title": item.get("title", ""),
                                    "url": url,
                                    "snippet": item.get("snippet") or item.get("content", ""),
                                })
            except json.JSONDecodeError:
                pass
    return refs


def _parse_file_refs(artifacts: list) -> list[dict]:
    files: list[dict] = []
    for artifact in artifacts:
        data = artifact.get("data")
        if artifact.get("name") == "file_list" and isinstance(data, dict):
            for f in data.get("files", []):
                if isinstance(f, dict):
                    files.append({
                        "filename": f.get("filename") or f.get("name", ""),
                        "storage_ref": f.get("storage_ref", ""),
                    })
    return files


def _extract_file_content_payload(artifacts: list, fallback_text: str = "") -> Optional[dict]:
    """file_content artifact 또는 JSON tool 응답에서 파일 원문 추출"""
    for artifact in artifacts:
        if artifact.get("name") != "file_content":
            continue
        data = artifact.get("data")
        if isinstance(data, dict) and data.get("content"):
            return data

    for text in (fallback_text,):
        if not text or not text.strip().startswith("{"):
            continue
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and parsed.get("success") and parsed.get("content"):
                return parsed
        except json.JSONDecodeError:
            continue

    return None


def _enrich_web_summary(summary: str, refs: list[dict]) -> str:
    """웹 검색 요약 + 출처 스니펫을 본문용 풍부한 텍스트로 결합"""
    parts = [summary.strip()] if summary and summary.strip() else []

    snippet_lines: list[str] = []
    for ref in refs:
        snippet = (ref.get("snippet") or "").strip()
        title = (ref.get("title") or "").strip()
        url = (ref.get("url") or "").strip()
        if snippet:
            line = f"- {title}: {snippet[:500]}" if title else f"- {snippet[:500]}"
            if url:
                line += f" ({url})"
            snippet_lines.append(line)

    if snippet_lines:
        parts.append("검색 출처 상세:\n" + "\n".join(snippet_lines))

    return "\n\n".join(p for p in parts if p)


_FORMAT_HINTS = ("양식", "형식", "format", "template", "구조", "참고용", "참고해서", "양식대로")


def _infer_source_role(agent: str, instruction: str, user_query: str) -> SourceRole:
    """양식 참고 파일 vs 본문 조사 자료 구분"""
    hint_text = f"{instruction} {user_query}".lower()
    has_format_hint = any(h in hint_text for h in _FORMAT_HINTS)

    if agent == "web_research":
        return "content"
    if agent == "file_management" and has_format_hint:
        return "format"
    return "content"


def _result_has_usable_data(result: AgentResult) -> bool:
    if result.content and result.content.strip():
        return True
    for artifact in result.artifacts:
        name = artifact.get("name", "")
        if name == "file_content" and artifact.get("data"):
            return True
        if name == "web_search_result" and artifact.get("text"):
            return True
    return False


def extract_source_reference(
    result: AgentResult,
    instruction: str = "",
    user_query: str = "",
) -> SourceReference:
    """AgentResult → SourceReference"""
    summary = result.content or ""
    refs: list[dict] = []
    files: list[dict] = []

    if result.agent == "web_research":
        for artifact in result.artifacts:
            if artifact.get("name") == "web_search_result" and artifact.get("text"):
                summary = artifact["text"]
        refs = _parse_web_sources(result.artifacts)
        summary = _enrich_web_summary(summary, refs)

    elif result.agent == "file_management":
        file_payload = _extract_file_content_payload(result.artifacts, summary)
        if file_payload:
            filename = file_payload.get("filename", "unknown")
            content = file_payload.get("content", "")
            summary = f"[양식 파일: {filename}]\n{content}"
        files = _parse_file_refs(result.artifacts)

    elif result.agent == "internal_rag":
        files = _parse_file_refs(result.artifacts)

    role = _infer_source_role(result.agent, instruction, user_query)

    return SourceReference(
        agent=result.agent,
        role=role,
        summary=summary[:8000],
        references=refs,
        files=files,
    )


def build_report_context(
    step: PlanStep,
    step_index: int,
    results: List[Optional[AgentResult]],
    user_query: str = "",
) -> ReportContext:
    """report_writing step 직전까지의 모든 성공 upstream 결과 취합"""
    sources: List[SourceReference] = []

    for i, result in enumerate(results):
        if i >= step_index or result is None:
            continue
        if result.agent == "report_writing":
            continue
        if not result.success or not _result_has_usable_data(result):
            continue
        sources.append(extract_source_reference(result, step.query, user_query))

    report_topic = extract_report_topic(step.query, user_query)

    format_example = ""
    for src in sources:
        if src.role != "format" or not src.summary:
            continue
        text = src.summary
        if "[양식 파일:" in text:
            _, _, text = text.partition("]\n")
        format_example = text.strip()[:12000]
        break

    logger.info(
        "ReportContext built: topic=%s, sources=%d (content=%d, format=%d), format_example=%s",
        report_topic or "(none)",
        len(sources),
        sum(1 for s in sources if s.role == "content"),
        sum(1 for s in sources if s.role == "format"),
        f"{len(format_example)} chars" if format_example else "no",
    )

    return ReportContext(
        template_id=detect_template_id(step.query),
        language="ko",
        report_topic=report_topic,
        format_example=format_example,
        instruction=step.query,
        sources=sources,
    )


def build_report_query(
    step: PlanStep,
    step_index: int,
    results: List[Optional[AgentResult]],
    user_query: str = "",
) -> str:
    """Report Writing Agent용 A2A 메시지 본문"""
    ctx = build_report_context(step, step_index, results, user_query=user_query)
    return serialize_report_context(ctx)
