import logging
import os
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

from a2a.server.apps import A2AFastAPIApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from agent_executor import ReportWritingAgentExecutor


def create_agent_card() -> AgentCard:
    base_url = os.getenv("REPORT_AGENT_URL", "http://localhost:10014")

    write_report_skill = AgentSkill(
        id="write_report",
        name="보고서 작성",
        description="수집된 데이터를 지정된 양식에 맞춰 구조화된 보고서로 작성합니다",
        tags=["report", "writing", "document", "markdown"],
        examples=[
            "조사 결과를 조사 보고서 형식으로 정리해줘",
            "웹 검색 결과를 임원 요약 보고서로 작성해줘",
            "RAG 검색 결과를 기술 보고서로 작성해줘",
        ],
    )

    format_report_skill = AgentSkill(
        id="format_report",
        name="보고서 양식 적용",
        description="executive_summary, research_report, technical_report 등 양식에 맞춰 보고서를 포맷합니다",
        tags=["format", "template", "structure"],
        examples=[
            "research_report 양식으로 보고서 작성해줘",
            "임원 요약 보고서 형식으로 정리해줘",
            "회의록 형식으로 작성해줘",
        ],
    )

    list_templates_skill = AgentSkill(
        id="list_templates",
        name="보고서 양식 조회",
        description="사용 가능한 보고서 양식(템플릿) 목록과 구조를 조회합니다",
        tags=["template", "list", "schema"],
        examples=[
            "사용 가능한 보고서 양식 알려줘",
            "조사 보고서 양식 구조 보여줘",
        ],
    )

    capabilities = AgentCapabilities(
        streaming=True,
        input_modes=["text"],
        output_modes=["text"],
    )

    return AgentCard(
        name="Report Writing Agent",
        description=(
            "다른 에이전트(web_research, internal_rag 등)에서 수집한 데이터를 "
            "지정된 보고서 양식에 맞춰 구조화된 마크다운 보고서로 작성하는 에이전트"
        ),
        url=base_url,
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=capabilities,
        skills=[write_report_skill, format_report_skill, list_templates_skill],
    )


def main():
    agent_card = create_agent_card()
    agent_executor = ReportWritingAgentExecutor()
    task_store = InMemoryTaskStore()

    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=task_store,
    )

    server_app = A2AFastAPIApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    port = int(os.getenv("REPORT_AGENT_PORT", "10014"))

    logger.info("=" * 60)
    logger.info("[REPORT AGENT] FastAPI 서버 시작")
    logger.info("=" * 60)
    logger.info(f"[REPORT AGENT] 서버 주소: http://localhost:{port}")
    logger.info(f"[REPORT AGENT] 에이전트 카드: http://localhost:{port}/.well-known/agent-card.json")
    logger.info(f"[REPORT AGENT] API 문서: http://localhost:{port}/docs")
    logger.info("=" * 60)

    uvicorn.run(
        server_app.build(title="Report Writing Agent", version="1.0.0"),
        host="0.0.0.0",
        port=port,
    )


if __name__ == "__main__":
    main()
