import os
import sys
import json
import logging
import asyncio
import re
from typing import AsyncIterator, Dict, Any, Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.tools import tool

from templates import (
    list_templates,
    get_template,
    detect_template_from_query,
    format_template_for_prompt,
)

AI_LLM = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if AI_LLM not in sys.path:
    sys.path.insert(0, AI_LLM)

from shared.report_context import (
    ReportContext,
    parse_report_context,
    detect_template_id,
)

logger = logging.getLogger(__name__)

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

FORMAT_MIMIC_PROMPT = """당신은 **양식 복제** 전문가입니다.

사용자가 [양식 예시] 전체 문서를 제공합니다. 당신의 유일한 임무:
→ 예시와 **거의 동일한 markdown 골격**으로, 주제만 바꿔 새 문서 작성.

반드시 지킬 것:
- 예시의 **섹션 제목 문자열**을 그대로 유지 (예: `- **학습 내용:**`, `- **나의 한 줄 평:**`)
- 예시의 **💡** 구분 위치·개수 유지
- 예시의 bullet 깊이·`- **제목:**` 패턴 유지

절대 금지 (예시에 없는 구조 추가):
- "문서 구조", "서론/본론/결론", "목적/배경/방법론"
- "프롬프트 제공", "질문 예시/답변" 챗봇 형식
- "SQL에 대한 기본 이해", "전달 및 표현" 등 새로운 대분류

본문 내용만 조사 자료 + 보고서 주제로 교체. LangChain/RAG 등 예시 주제 문장 복사 금지.
"""

SYSTEM_PROMPT = """당신은 보고서 작성 에이전트입니다.
양식 예시가 없으면 지정된 내장 템플릿을 따릅니다.
조사·검색을 새로 수행하지 않습니다.
"""


@tool
def list_report_templates() -> str:
    """사용 가능한 보고서 양식(템플릿) 목록을 반환합니다."""
    templates = list_templates()
    return json.dumps(templates, ensure_ascii=False, indent=2)


@tool
def get_report_template(template_id: str) -> str:
    """
    특정 보고서 양식의 상세 구조를 반환합니다.

    Args:
        template_id: 양식 ID (executive_summary, research_report, technical_report, meeting_minutes, general)
    """
    template = get_template(template_id)
    return json.dumps(template, ensure_ascii=False, indent=2)


class ReportWritingAgent:
    """
    보고서 작성 에이전트 — 양식 적용·마크다운 작성 전담

    Orchestrator가 전달한 ReportContext(구조화된 upstream 취합 결과)를
    지정된 템플릿에 맞춰 보고서로 변환합니다.
    """

    def __init__(self):
        self.model = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
        self.model_format = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.initialized = False

    async def initialize(self) -> None:
        if self.initialized:
            return
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY 환경 변수가 필요합니다")
        self.initialized = True
        logger.info("[REPORT AGENT] [INIT] 초기화 완료")

    def _parse_input(self, query: str) -> tuple[str, str, str, str, str, str, str]:
        """
        입력 파싱 → (instruction, content_text, template_id, language,
                      report_topic, format_example, legacy_source_text)
        """
        ctx = parse_report_context(query)
        if ctx:
            format_example = ctx.get_format_example()
            content_text = ctx.get_content_text()
            logger.info(
                f"[REPORT AGENT] ReportContext 수신: template={ctx.template_id}, "
                f"topic={ctx.report_topic or '(없음)'}, "
                f"format_example={'yes (' + str(len(format_example)) + ' chars)' if format_example else 'no'}, "
                f"sources={len(ctx.sources)}"
            )
            return (
                ctx.instruction,
                content_text,
                ctx.template_id,
                ctx.language,
                ctx.report_topic,
                format_example,
                ctx.to_source_text(),
            )

        source_marker = "[이전 에이전트 결과]"
        if source_marker in query:
            parts = query.split(source_marker, 1)
            instruction = parts[0].strip()
            source_data = parts[1].strip().lstrip(":").strip() if len(parts) > 1 else ""
            return instruction, source_data, detect_template_id(query), "ko", "", "", source_data

        return query.strip(), "", detect_template_id(query), "ko", "", "", ""

    async def _write_report_from_format_example(
        self,
        format_example: str,
        content_text: str,
        report_topic: str,
        language: str,
    ) -> str:
        """양식 예시 전문 + 조사 자료 → 동일 형식으로 새 보고서 작성"""
        lang_label = "한국어" if language == "ko" else language
        topic_line = report_topic or "사용자 지정 주제"

        user_content = f"""## 작업
[양식 예시]와 **동일한 markdown 골격**으로, 주제 **{topic_line}** 보고서를 작성하세요.

## 조사 자료 (각 bullet 본문에만 사용)
{content_text if content_text else "제공된 조사 자료 없음 — 해당 bullet에 '제공된 자료 부족' 표기"}

## 작성 언어
{lang_label}

---

## [양식 예시] — 이 문서의 **제목·순서·형식을 그대로 복제** (내용만 SQL로 교체)

{format_example}

---

출력은 [양식 예시]와 같은 섹션 제목(`- **학습 내용:**`, `💡`, `- **나의 한 줄 평:**` 등)을 유지해야 합니다.
서론/본론/결론, 문서 구조, 프롬프트 제공 형식은 **사용 금지**.
"""

        response = await self.model_format.ainvoke([
            {"role": "system", "content": FORMAT_MIMIC_PROMPT},
            {"role": "user", "content": user_content},
        ])
        return response.content

    async def _write_report_from_template(
        self,
        content_text: str,
        template: Dict,
        title: str,
        language: str,
        report_topic: str = "",
    ) -> str:
        """내장 템플릿 기반 작성 (양식 예시 없을 때)"""
        template_spec = format_template_for_prompt(template)
        lang_label = "한국어" if language == "ko" else language
        topic_line = f"\n## 보고서 주제\n{report_topic}\n" if report_topic else ""

        user_content = f"""## 사용할 양식
{template_spec}
{topic_line}
## 보고서 제목
{title}

## 작성 언어
{lang_label}

## 참고 자료
{content_text if content_text else "제공된 자료 없음 — 각 섹션에 '제공된 자료 부족' 표기"}

위 참고 자료만을 기준으로 양식의 모든 섹션을 작성하세요.
보고서 맨 위에 # {title} 형태로 제목을 넣으세요.
"""

        response = await self.model.ainvoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ])
        return response.content

    async def _generate_title(
        self,
        source_data: str,
        template: Dict,
        language: str,
        report_topic: str = "",
    ) -> str:
        """참고 자료 기반 보고서 제목 생성"""
        lang_label = "한국어" if language == "ko" else language
        if report_topic:
            user_content = (
                f"보고서 주제: {report_topic}\n"
                f"양식: {template['name']}\n"
                f"작성 언어: {lang_label}\n\n"
                f"위 주제에 맞는 보고서 제목을 작성하세요."
            )
            system_content = (
                f"보고서 제목만 {lang_label}로 한 줄 작성. 따옴표 없이 제목만 출력. "
                f"주제는 반드시 '{report_topic}'와 일치해야 합니다. 양식 참고 자료의 다른 주제 사용 금지."
            )
        elif source_data:
            user_content = (
                f"양식: {template['name']}\n"
                f"작성 언어: {lang_label}\n\n"
                f"참고 자료:\n{source_data[:4000]}\n\n"
                "위 참고 자료의 주제를 반영한 보고서 제목을 작성하세요."
            )
            system_content = (
                f"보고서 제목만 {lang_label}로 한 줄 작성. 따옴표 없이 제목만 출력. "
                "참고 자료 주제와 반드시 일치. 자료에 없는 새 주제 금지."
            )
        else:
            user_content = f"양식: {template['name']}"
            system_content = f"보고서 제목만 {lang_label}로 한 줄 작성."

        response = await self.model.ainvoke([
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ])
        return response.content.strip().strip('"').strip("'")

    async def _write_report(
        self,
        content_text: str,
        template: Dict,
        title: str,
        language: str,
        report_topic: str = "",
        format_example: str = "",
    ) -> str:
        if format_example:
            return await self._write_report_from_format_example(
                format_example, content_text, report_topic, language
            )
        return await self._write_report_from_template(
            content_text, template, title, language, report_topic
        )

    async def stream(self, query: str) -> AsyncIterator[Dict[str, Any]]:
        if not self.initialized:
            await self.initialize()

        try:
            yield {
                "is_task_complete": False,
                "require_user_input": False,
                "content": "📋 보고서 요청을 분석하고 있습니다...",
            }

            instruction, content_text, template_id, language, report_topic, format_example, _ = (
                self._parse_input(query)
            )
            template = get_template(template_id)

            mode = "양식 예시 따라 작성" if format_example else template["name"]
            yield {
                "is_task_complete": False,
                "require_user_input": False,
                "content": f"📝 {mode} 중..."
                + (f" (주제: {report_topic})" if report_topic else ""),
            }

            if not content_text and not format_example:
                logger.warning("[REPORT AGENT] 참고 자료 없음 — 품질 저하 가능")
            elif format_example and not content_text:
                logger.warning("[REPORT AGENT] 양식은 있으나 조사(content) 자료 없음")
            elif not format_example:
                logger.warning(
                    "[REPORT AGENT] format_example 없음 — test.txt 미전달. "
                    "내장 템플릿으로 작성됩니다 (양식 불일치 가능)"
                )

            if format_example:
                title = report_topic or "보고서"
                report_content = await self._write_report(
                    content_text, template, title, language, report_topic, format_example
                )
            else:
                if not content_text:
                    logger.warning("[REPORT AGENT] 본문(content) 소스 없음")
                title = await self._generate_title(content_text, template, language, report_topic)
                report_content = await self._write_report(
                    content_text, template, title, language, report_topic, ""
                )

            filename_suggestion = re.sub(r'[^\w\s가-힣-]', '', title)
            filename_suggestion = filename_suggestion.replace(" ", "_")[:50] + ".md"

            report_data = {
                "title": title,
                "template_id": template_id,
                "template_name": template["name"],
                "format": "markdown",
                "filename_suggestion": filename_suggestion,
                "sections": [s["title"] for s in template["sections"]],
                "has_source_data": bool(content_text),
                "has_format_example": bool(format_example),
            }

            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": report_content,
                "data": report_data,
            }

        except Exception as e:
            logger.error(f"[REPORT AGENT] [ERROR] {e}")
            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": f"보고서 작성 중 오류 발생: {str(e)}",
            }


if __name__ == "__main__":
    async def test():
        from shared.report_context import ReportContext, SourceReference, serialize_report_context

        print("=" * 60)
        print("Report Writing Agent 테스트 (ReportContext)")
        print("=" * 60)

        ctx = ReportContext(
            template_id="research_report",
            language="ko",
            instruction="조사 결과를 research_report 양식으로 작성해줘",
            sources=[
                SourceReference(
                    agent="web_research",
                    summary="2026년 AI 에이전트 트렌드: 멀티 에이전트, MCP, RAG+Agent 결합",
                    references=[
                        {"title": "AI Trends 2026", "url": "https://example.com", "snippet": "..."},
                    ],
                ),
            ],
        )
        query = serialize_report_context(ctx)

        agent = ReportWritingAgent()
        async for chunk in agent.stream(query):
            if chunk.get("is_task_complete"):
                print(f"\n{chunk['content'][:500]}...")
                if chunk.get("data"):
                    print(f"\nMetadata: {chunk['data']}")

    asyncio.run(test())
