import os
import sys
import json
import logging
import asyncio
from typing import AsyncIterator, Dict, Any, List

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

try:
    from .models import WebSource, WebSearchResult
except ImportError:
    from models import WebSource, WebSearchResult

logger = logging.getLogger(__name__)

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

SYSTEM_PROMPT = """당신은 웹 검색 전문가입니다.

필수 규칙:
- 모든 질문에 답하기 전에 반드시 tavily_search 도구를 1회 이상 호출하세요.
- 질문과 동일한 언어로 답변하세요 (한국어 질문 → 한국어 답변).

tavily_search 도구 사용 시:
- topic 파라미터는 'general', 'news', 'finance' 중 하나만 사용
- 기술/AI 질문 → topic='general'
- 최신 뉴스 → topic='news'
- 금융/주식 → topic='finance'

검색 후 반드시 포함:
- 핵심 내용 요약
- 신뢰할 수 있는 출처 링크
"""


def _is_tool_result_message(msg) -> bool:
    """LangGraph/LangChain tool 응답 메시지 판별"""
    msg_type = getattr(msg, "type", None)
    if msg_type == "tool":
        return True
    class_name = type(msg).__name__
    if class_name == "ToolMessage":
        return True
    name = getattr(msg, "name", None)
    if name and not getattr(msg, "tool_calls", None):
        if class_name not in ("AIMessage", "HumanMessage", "SystemMessage"):
            return True
    return False


def extract_sources(tool_messages) -> List[WebSource]:
    """Tavily 도구 응답에서 WebSource 목록 추출"""
    sources = []
    seen_urls: set[str] = set()

    for msg in tool_messages:
        if not hasattr(msg, "content") or not msg.content:
            continue
        try:
            raw = msg.content
            if isinstance(raw, str):
                data = json.loads(raw)
            else:
                data = raw

            results = []
            if isinstance(data, dict):
                results = data.get("results", [])
            elif isinstance(data, list):
                results = data

            for item in results:
                if isinstance(item, dict) and "url" in item:
                    url = item["url"]
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    sources.append(WebSource(
                        title=item.get("title", ""),
                        url=url,
                        snippet=item.get("content", item.get("snippet")),
                        score=item.get("score"),
                    ))
        except (json.JSONDecodeError, TypeError):
            continue
    return sources


def summarize_web_results(results: List[WebSource]) -> str:
    """WebSource 목록을 간결한 텍스트로 요약"""
    if not results:
        return "검색 결과가 없습니다."
    lines = [f"- [{s.title}]({s.url})" + (f": {s.snippet[:100]}..." if s.snippet else "") for s in results[:5]]
    return "\n".join(lines)


class WebResearchAgent:
    """MCP 기반 웹 검색 에이전트 — Tavily MCP 서버 사용"""

    def __init__(self):
        self.model = ChatOpenAI(model="gpt-4o-mini")
        self.mcp_client = None
        self.agent = None
        self.initialized = False

    async def initialize(self) -> None:
        if self.initialized:
            return

        if not TAVILY_API_KEY:
            raise ValueError("TAVILY_API_KEY 환경 변수가 필요합니다")

        self.mcp_client = MultiServerMCPClient({
            "tavily": {
                "url": f"https://mcp.tavily.com/mcp/?tavilyApiKey={TAVILY_API_KEY}",
                "transport": "streamable_http",
            }
        })

        tools = await self.mcp_client.get_tools(server_name="tavily")
        logger.info(f"[WEB AGENT] [INIT] Tavily 도구 로드: {[t.name for t in tools]}")

        self.agent = create_react_agent(self.model, tools, prompt=SYSTEM_PROMPT)
        self.initialized = True
        logger.info("[WEB AGENT] [INIT] 초기화 완료")

    async def stream(self, query: str) -> AsyncIterator[Dict[str, Any]]:
        if not self.initialized:
            await self.initialize()

        try:
            final_message = None
            tool_messages = []
            tool_called = False

            async for chunk in self.agent.astream({
                "messages": [{"role": "user", "content": query}]
            }):
                for node_name, node_output in chunk.items():
                    messages = node_output.get("messages", [])

                    for msg in messages:
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            if not tool_called:
                                tool_called = True
                                tool_names = [
                                    tc.get("name", "unknown") if isinstance(tc, dict) else getattr(tc, "name", "unknown")
                                    for tc in msg.tool_calls
                                ]
                                yield {
                                    "is_task_complete": False,
                                    "require_user_input": False,
                                    "content": f"🔍 웹 검색 중... (도구: {', '.join(tool_names)})",
                                    "sources": [],
                                }

                        if _is_tool_result_message(msg):
                            tool_messages.append(msg)
                            logger.debug(
                                f"[WEB AGENT] tool result: name={getattr(msg, 'name', None)}, "
                                f"type={getattr(msg, 'type', None)}"
                            )

                        if hasattr(msg, "content") and msg.content:
                            if not (hasattr(msg, "tool_calls") and msg.tool_calls):
                                if not _is_tool_result_message(msg):
                                    final_message = msg.content

            sources = extract_sources(tool_messages)
            logger.info(f"[WEB AGENT] sources 추출: {len(sources)}개")

            if final_message:
                yield {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": final_message,
                    "sources": [s.model_dump() for s in sources],
                }
            else:
                yield {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": "응답을 생성하지 못했습니다.",
                    "sources": [],
                }

        except Exception as e:
            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": f"처리 중 오류 발생: {str(e)}",
                "sources": [],
            }


if __name__ == "__main__":
    async def test():
        print("=" * 60)
        print("Web Research Agent 테스트")
        print("=" * 60)
        agent = WebResearchAgent()
        query = "2026년 AI 에이전트 트렌드를 조사해주세요."
        print(f"\n👤 Query: {query}")
        print("-" * 60)
        async for chunk in agent.stream(query):
            content = chunk.get("content", "")
            is_complete = chunk.get("is_task_complete", False)
            sources = chunk.get("sources", [])
            if not is_complete:
                print(f"{content}")
            else:
                print(f"\n💬 {content}")
                if sources:
                    print(f"\n📎 출처 ({len(sources)}개):")
                    for s in sources:
                        print(f"  - {s['title']}: {s['url']}")

    asyncio.run(test())
