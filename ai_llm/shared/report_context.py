"""
오케스트레이터 → Report Writing Agent 구조화 입력 계약

Orchestrator가 upstream 에이전트 결과를 취합해 ReportContext로 전달하고,
Report Agent는 양식 적용·마크다운 작성만 담당합니다.
"""

from __future__ import annotations

import json
import re
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

REPORT_CONTEXT_MARKER = "[REPORT_CONTEXT]"

TemplateId = Literal[
    "executive_summary",
    "research_report",
    "technical_report",
    "meeting_minutes",
    "general",
]

SourceRole = Literal["content", "format"]


class SourceReference(BaseModel):
    """단일 upstream 에이전트 결과"""
    agent: str = Field(description="에이전트 이름 (web_research, internal_rag 등)")
    role: SourceRole = Field(
        default="content",
        description="content=본문 자료, format=양식·구조 참고용(본문 내용으로 사용 금지)",
    )
    summary: str = Field(description="에이전트가 반환한 요약/답변")
    references: List[dict] = Field(
        default_factory=list,
        description="출처 목록 [{title, url, snippet}]",
    )
    files: List[dict] = Field(
        default_factory=list,
        description="파일 참조 [{filename, storage_ref}]",
    )


class ReportContext(BaseModel):
    """보고서 작성용 취합 컨텍스트"""
    template_id: TemplateId = "research_report"
    language: str = "ko"
    report_topic: str = Field(default="", description="보고서 주제 (예: SQL). 양식 파일과 별개")
    format_example: str = Field(
        default="",
        description="Drive 양식 파일 전문 — LLM이 형식·스타일을 그대로 따라 작성",
    )
    instruction: str = Field(default="", description="보고서 작성 지시 (양식·형식)")
    sources: List[SourceReference] = Field(default_factory=list)

    def get_format_example(self) -> str:
        """양식 파일 전문 (format_example 필드 또는 format 소스 summary)"""
        if self.format_example:
            return self.format_example
        for src in self.sources:
            if src.role != "format" or not src.summary:
                continue
            text = src.summary
            if "[양식 파일:" in text:
                _, _, text = text.partition("]\n")
            return text.strip()
        return ""

    def get_content_text(self) -> str:
        """본문 작성용 조사 자료 (content 역할 소스만)"""
        parts: List[str] = []
        if self.report_topic:
            parts.append(f"보고서 주제: {self.report_topic}")

        for i, src in enumerate(
            [s for s in self.sources if s.role == "content"], 1
        ):
            block = [f"### [{i}] {src.agent}", src.summary]
            if src.references:
                block.append("출처:")
                for ref in src.references:
                    title = ref.get("title", "")
                    url = ref.get("url", "")
                    snippet = ref.get("snippet", "")
                    line = f"- {title}"
                    if url:
                        line += f" ({url})"
                    if snippet:
                        line += f": {snippet[:300]}"
                    block.append(line)
            parts.append("\n".join(block))

        return "\n\n".join(parts)

    def to_source_text(self) -> str:
        """레거시 호환용 — format_example 모드에서는 get_content_text() 사용 권장"""
        format_ex = self.get_format_example()
        content = self.get_content_text()

        parts: List[str] = []
        if format_ex:
            parts.append(
                "## 양식 예시 문서 (전문)\n"
                "아래 문서와 동일한 형식·구조·마크다운 스타일로 작성하세요. "
                "예시의 주제/내용은 복사하지 마세요.\n\n"
                f"{format_ex}"
            )
        if content:
            parts.append(f"## 본문 참고 자료\n{content}")
        return "\n\n".join(parts)


def detect_template_id(text: str) -> TemplateId:
    """자연어/지시문에서 template_id 추출"""
    explicit = re.search(
        r"(executive_summary|research_report|technical_report|meeting_minutes|general)",
        text,
        re.IGNORECASE,
    )
    if explicit:
        return explicit.group(1).lower()  # type: ignore[return-value]

    keywords = {
        "임원": "executive_summary",
        "executive": "executive_summary",
        "조사": "research_report",
        "리서치": "research_report",
        "research": "research_report",
        "트렌드": "research_report",
        "기술": "technical_report",
        "technical": "technical_report",
        "회의": "meeting_minutes",
        "회의록": "meeting_minutes",
    }
    lower = text.lower()
    for kw, tid in keywords.items():
        if kw in lower:
            return tid  # type: ignore[return-value]

    return "research_report"


def extract_report_topic(instruction: str, user_query: str = "") -> str:
    """지시문·원본 질문에서 보고서 주제 추출 (양식 파일과 구분)"""
    for text in (instruction, user_query):
        if not text:
            continue
        for pattern in (
            r"보고서\s*주제\s*[:：]\s*([^,.]+)",
            r"주제\s*[:：]\s*([^,.]+)",
        ):
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()

    for text in (user_query, instruction):
        if not text:
            continue
        m = re.search(r"([A-Za-z가-힣0-9]+)에\s*대한\s*(?:보고서|report)", text, re.IGNORECASE)
        if m:
            topic = m.group(1).strip()
            if topic not in ("그", "이", "해당", "위"):
                return topic

    return ""


def serialize_report_context(ctx: ReportContext) -> str:
    """A2A TextPart에 실을 payload"""
    return f"{REPORT_CONTEXT_MARKER}\n{json.dumps(ctx.model_dump(), ensure_ascii=False)}"


def parse_report_context(text: str) -> Optional[ReportContext]:
    """Report Agent 입력에서 ReportContext 파싱"""
    if REPORT_CONTEXT_MARKER not in text:
        return None
    _, _, payload = text.partition(REPORT_CONTEXT_MARKER)
    payload = payload.strip()
    if not payload:
        return None
    try:
        return ReportContext.model_validate_json(payload)
    except Exception:
        return None
