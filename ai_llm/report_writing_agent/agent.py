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

logger = logging.getLogger(__name__)

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

SYSTEM_PROMPT = """당신은 전문 보고서 작성 에이전트입니다.

역할:
1. 사용자 요청과 제공된 자료(이전 에이전트 결과 포함)를 분석합니다.
2. 지정된 보고서 양식(템플릿)에 맞춰 구조화된 보고서를 작성합니다.
3. 마크다운 형식으로 작성하며, 각 섹션은 ## 헤더로 구분합니다.

작성 원칙:
- 제공된 자료의 사실만 사용하고, 없는 내용은 추측하지 마세요.
- 자료가 부족하면 해당 섹션에 "제공된 자료 부족"을 명시하세요.
- 한국어로 작성하며, 전문적이고 명확한 문체를 사용하세요.
- 표, bullet point, 번호 목록을 적절히 활용하세요.
- 참고 자료 섹션이 있으면 출처를 명시하세요.
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
    보고서 작성 에이전트

    다른 에이전트(web_research, internal_rag 등)에서 수집한 데이터를
    지정된 양식에 맞춰 구조화된 보고서로 작성합니다.
    """

    def __init__(self):
        self.model = ChatOpenAI(model="gpt-4o", temperature=0.3)
        self.initialized = False

    async def initialize(self) -> None:
        if self.initialized:
            return
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY 환경 변수가 필요합니다")
        self.initialized = True
        logger.info("[REPORT AGENT] [INIT] 초기화 완료")

    def _extract_source_data(self, query: str) -> tuple[str, str]:
        """쿼리에서 원본 요청과 이전 에이전트 결과를 분리"""
        source_marker = "[이전 에이전트 결과]"
        if source_marker in query:
            parts = query.split(source_marker, 1)
            user_request = parts[0].strip()
            source_data = parts[1].strip() if len(parts) > 1 else ""
            return user_request, source_data
        return query.strip(), ""

    def _detect_template_id(self, query: str) -> str:
        """쿼리에서 보고서 양식 ID 추출 또는 자동 감지"""
        explicit_match = re.search(
            r"(executive_summary|research_report|technical_report|meeting_minutes|general)",
            query,
            re.IGNORECASE,
        )
        if explicit_match:
            return explicit_match.group(1).lower()

        template_keywords = {
            "임원": "executive_summary",
            "executive": "executive_summary",
            "조사": "research_report",
            "리서치": "research_report",
            "research": "research_report",
            "트렌드": "research_report",
            "기술": "technical_report",
            "technical": "technical_report",
            "아키텍처": "technical_report",
            "회의": "meeting_minutes",
            "회의록": "meeting_minutes",
            "minutes": "meeting_minutes",
        }
        query_lower = query.lower()
        for keyword, template_id in template_keywords.items():
            if keyword in query_lower:
                return template_id

        return detect_template_from_query(query)

    async def _generate_title(self, user_request: str, template: Dict) -> str:
        """보고서 제목 생성"""
        response = await self.model.ainvoke([
            {"role": "system", "content": "보고서 제목만 한 줄로 생성하세요. 따옴표 없이 제목만 출력하세요."},
            {"role": "user", "content": f"요청: {user_request}\n양식: {template['name']}"},
        ])
        return response.content.strip().strip('"').strip("'")

    async def _write_report(
        self,
        user_request: str,
        source_data: str,
        template: Dict,
        title: str,
    ) -> str:
        """LLM으로 보고서 본문 생성"""
        template_spec = format_template_for_prompt(template)

        user_content = f"""## 보고서 작성 요청
{user_request}

## 사용할 양식
{template_spec}

## 보고서 제목
{title}

## 참고 자료 (이전 에이전트/사용자 제공 데이터)
{source_data if source_data else "별도 자료 없음 - 요청 내용만으로 작성"}

위 양식의 모든 섹션을 포함하여 완성된 마크다운 보고서를 작성하세요.
보고서 맨 위에 # {title} 형태로 제목을 넣으세요.
"""

        response = await self.model.ainvoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ])
        return response.content

    async def stream(self, query: str) -> AsyncIterator[Dict[str, Any]]:
        if not self.initialized:
            await self.initialize()

        try:
            yield {
                "is_task_complete": False,
                "require_user_input": False,
                "content": "📋 보고서 요청을 분석하고 있습니다...",
            }

            user_request, source_data = self._extract_source_data(query)
            template_id = self._detect_template_id(query)
            template = get_template(template_id)

            yield {
                "is_task_complete": False,
                "require_user_input": False,
                "content": f"📝 '{template['name']}' 양식으로 보고서를 작성 중...",
            }

            title = await self._generate_title(user_request, template)
            report_content = await self._write_report(
                user_request, source_data, template, title
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
                "has_source_data": bool(source_data),
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
        print("=" * 60)
        print("Report Writing Agent 테스트")
        print("=" * 60)

        agent = ReportWritingAgent()
        query = """2026년 AI 에이전트 트렌드에 대한 조사 보고서를 작성해줘.

[이전 에이전트 결과]:
2026년 AI 에이전트 주요 트렌드:
1. 멀티 에이전트 오케스트레이션 - A2A 프로토콜 기반 에이전트 간 협업
2. MCP(Model Context Protocol) - 도구 연동 표준화
3. RAG + Agent 결합 - 사내 문서 기반 지능형 에이전트
4. 자율 에이전트(Autonomous Agents) - 장기 작업 자동 수행
출처: Tavily 웹 검색 (2026년 1월)
"""

        print(f"\nQuery: {query[:80]}...")
        print("-" * 60)

        async for chunk in agent.stream(query):
            if chunk.get("is_task_complete"):
                print(f"\n{chunk['content'][:500]}...")
                if chunk.get("data"):
                    print(f"\nMetadata: {chunk['data']}")

    asyncio.run(test())
