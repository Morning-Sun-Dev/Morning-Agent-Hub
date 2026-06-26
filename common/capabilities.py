"""Shared agent capability registry for backend and frontend surfaces."""

from common.contracts import CapabilityDescriptor


_CAPABILITIES = [
    CapabilityDescriptor(
        agent_id="orchestrator",
        capability_id="route_request",
        label="요청 라우팅",
        description="사용자 요청을 분석하고 필요한 에이전트 실행 계획을 만듭니다.",
        ui_status="available",
        ui_surface="채팅 입력, 진행 패널",
    ),
    CapabilityDescriptor(
        agent_id="web_research",
        capability_id="web_search",
        label="웹 검색",
        description="외부 웹에서 최신 정보와 출처를 검색합니다.",
        ui_status="available",
        ui_surface="채팅 입력, 출처 패널",
    ),
    CapabilityDescriptor(
        agent_id="web_research",
        capability_id="news_search",
        label="뉴스 검색",
        description="최신 뉴스성 정보를 검색하고 요약합니다.",
        ui_status="planned",
    ),
    CapabilityDescriptor(
        agent_id="web_research",
        capability_id="url_fetch",
        label="URL 내용 분석",
        description="특정 URL의 본문을 가져와 분석합니다.",
        ui_status="planned",
    ),
    CapabilityDescriptor(
        agent_id="internal_rag",
        capability_id="rag_vector_search",
        label="문서 의미 검색",
        description="사내 문서를 의미 기반으로 검색하고 답변 근거를 만듭니다.",
        ui_status="partial",
        ui_surface="채팅 입력, 첨부 파일 요청",
    ),
    CapabilityDescriptor(
        agent_id="internal_rag",
        capability_id="rag_sql_search",
        label="문서 메타데이터 검색",
        description="문서 유형, 날짜 등 메타데이터 조건으로 사내 문서를 검색합니다.",
        ui_status="planned",
    ),
    CapabilityDescriptor(
        agent_id="internal_rag",
        capability_id="rag_index",
        label="문서 인덱싱",
        description="Drive 파일을 텍스트로 추출해 벡터 DB에 인덱싱합니다.",
        ui_status="partial",
        ui_surface="파일 업로드",
    ),
    CapabilityDescriptor(
        agent_id="file_management",
        capability_id="upload_file",
        label="Drive 업로드",
        description="파일이나 생성된 문서를 Google Drive에 저장합니다.",
        ui_status="available",
        ui_surface="파일 첨부, 파일 패널",
    ),
    CapabilityDescriptor(
        agent_id="file_management",
        capability_id="download_file",
        label="Drive 다운로드",
        description="Google Drive 파일을 다운로드하거나 다운로드 링크를 제공합니다.",
        ui_status="partial",
        ui_surface="파일 패널",
    ),
    CapabilityDescriptor(
        agent_id="file_management",
        capability_id="get_file_info",
        label="파일 정보 조회",
        description="Drive 파일의 이름, 크기, MIME 타입, 링크 등 메타데이터를 조회합니다.",
        ui_status="partial",
        ui_surface="파일 패널",
    ),
    CapabilityDescriptor(
        agent_id="file_management",
        capability_id="find_folder",
        label="Drive 폴더 조회",
        description="Google Drive에서 이름 기반으로 폴더를 찾습니다.",
        ui_status="planned",
    ),
    CapabilityDescriptor(
        agent_id="file_management",
        capability_id="list_files",
        label="Drive 파일 목록",
        description="Drive 파일 목록을 조회하고 검색어로 필터링합니다.",
        ui_status="partial",
        ui_surface="파일 API",
    ),
    CapabilityDescriptor(
        agent_id="file_management",
        capability_id="delete_file",
        label="Drive 파일 삭제",
        description="Google Drive 파일을 휴지통으로 이동하거나 삭제합니다.",
        ui_status="planned",
    ),
    CapabilityDescriptor(
        agent_id="file_management",
        capability_id="update_file",
        label="Drive 파일 업데이트",
        description="Drive 파일의 내용이나 이름을 갱신합니다.",
        ui_status="planned",
    ),
    CapabilityDescriptor(
        agent_id="file_management",
        capability_id="create_folder",
        label="Drive 폴더 생성",
        description="Google Drive에 새 폴더를 생성합니다.",
        ui_status="planned",
    ),
    CapabilityDescriptor(
        agent_id="report_writing",
        capability_id="write_report",
        label="보고서 작성",
        description="수집된 정보를 보고서 Markdown으로 구조화합니다.",
        ui_status="partial",
        ui_surface="채팅 입력, 답변 영역",
    ),
    CapabilityDescriptor(
        agent_id="report_writing",
        capability_id="format_report",
        label="보고서 양식 적용",
        description="executive_summary, research_report 등 지정 양식에 맞춰 내용을 정리합니다.",
        ui_status="partial",
        ui_surface="채팅 입력",
    ),
    CapabilityDescriptor(
        agent_id="report_writing",
        capability_id="list_templates",
        label="보고서 양식 조회",
        description="사용 가능한 보고서 템플릿 목록과 구조를 조회합니다.",
        ui_status="partial",
        ui_surface="채팅 입력",
    ),
]


def list_capabilities() -> list[CapabilityDescriptor]:
    return list(_CAPABILITIES)
