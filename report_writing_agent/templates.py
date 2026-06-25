"""
보고서 작성 양식 템플릿 정의

다른 에이전트(web_research, internal_rag 등)에서 수집한 데이터를
아래 양식에 맞춰 구조화된 보고서로 변환합니다.
"""

from typing import Dict, List

REPORT_TEMPLATES: Dict[str, Dict] = {
    "executive_summary": {
        "id": "executive_summary",
        "name": "임원 요약 보고서",
        "description": "핵심 결론과 권고사항 중심의 간결한 임원 보고서",
        "keywords": ["임원", "요약", "executive", "경영", "의사결정"],
        "sections": [
            {"id": "overview", "title": "개요", "description": "보고 목적과 배경 (2~3문장)"},
            {"id": "key_findings", "title": "핵심 발견사항", "description": "3~5개 bullet point"},
            {"id": "analysis", "title": "분석", "description": "주요 데이터 및 근거 요약"},
            {"id": "recommendations", "title": "권고사항", "description": "실행 가능한 권고 3~5개"},
            {"id": "next_steps", "title": "후속 조치", "description": "단기/중기 실행 계획"},
        ],
    },
    "research_report": {
        "id": "research_report",
        "name": "조사 보고서",
        "description": "외부/내부 조사 결과를 체계적으로 정리한 보고서",
        "keywords": ["조사", "리서치", "research", "분석", "트렌드", "동향"],
        "sections": [
            {"id": "title_page", "title": "표지 정보", "description": "제목, 작성일, 작성자(에이전트)"},
            {"id": "abstract", "title": "요약", "description": "200자 내외 핵심 요약"},
            {"id": "background", "title": "배경 및 목적", "description": "조사 배경과 목적"},
            {"id": "methodology", "title": "조사 방법", "description": "정보 출처 및 조사 범위"},
            {"id": "findings", "title": "조사 결과", "description": "상세 조사 내용 (소제목 포함)"},
            {"id": "conclusion", "title": "결론", "description": "종합 결론"},
            {"id": "references", "title": "참고 자료", "description": "출처 및 참고 문헌 목록"},
        ],
    },
    "technical_report": {
        "id": "technical_report",
        "name": "기술 보고서",
        "description": "기술 분석, 아키텍처, 구현 방안 등을 다루는 보고서",
        "keywords": ["기술", "technical", "아키텍처", "구현", "시스템", "개발"],
        "sections": [
            {"id": "overview", "title": "개요", "description": "기술 주제 및 범위"},
            {"id": "current_state", "title": "현황 분석", "description": "현재 기술/시스템 현황"},
            {"id": "technical_details", "title": "기술 상세", "description": "핵심 기술 내용 및 분석"},
            {"id": "comparison", "title": "비교 분석", "description": "대안 비교 (해당 시)"},
            {"id": "recommendations", "title": "기술 권고", "description": "기술적 권고사항"},
            {"id": "appendix", "title": "부록", "description": "추가 기술 자료"},
        ],
    },
    "meeting_minutes": {
        "id": "meeting_minutes",
        "name": "회의록",
        "description": "회의/논의 내용을 기록하는 형식의 보고서",
        "keywords": ["회의", "회의록", "minutes", "논의", "미팅"],
        "sections": [
            {"id": "meeting_info", "title": "회의 정보", "description": "일시, 참석자, 안건"},
            {"id": "agenda", "title": "안건", "description": "논의 안건 목록"},
            {"id": "discussion", "title": "논의 내용", "description": "안건별 논의 요약"},
            {"id": "decisions", "title": "결정 사항", "description": "확정된 결정 목록"},
            {"id": "action_items", "title": "후속 조치", "description": "담당자 및 기한 포함 액션 아이템"},
        ],
    },
    "general": {
        "id": "general",
        "name": "일반 보고서",
        "description": "범용 보고서 양식 (기본)",
        "keywords": ["보고서", "report", "정리", "작성"],
        "sections": [
            {"id": "introduction", "title": "서론", "description": "보고 배경 및 목적"},
            {"id": "main_content", "title": "본론", "description": "주요 내용 (소제목으로 구분)"},
            {"id": "conclusion", "title": "결론", "description": "종합 결론 및 시사점"},
        ],
    },
}


def list_templates() -> List[Dict]:
    """사용 가능한 보고서 양식 목록 반환"""
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "description": t["description"],
            "section_count": len(t["sections"]),
        }
        for t in REPORT_TEMPLATES.values()
    ]


def get_template(template_id: str) -> Dict:
    """특정 보고서 양식 반환"""
    if template_id not in REPORT_TEMPLATES:
        return REPORT_TEMPLATES["general"]
    return REPORT_TEMPLATES[template_id]


def detect_template_from_query(query: str) -> str:
    """쿼리 키워드 기반 양식 자동 감지 (LLM 보조 전 휴리스틱)"""
    query_lower = query.lower()
    scores = {}
    for template_id, template in REPORT_TEMPLATES.items():
        if template_id == "general":
            continue
        score = sum(1 for kw in template["keywords"] if kw in query_lower)
        if score > 0:
            scores[template_id] = score

    if scores:
        return max(scores, key=scores.get)
    return "general"


def format_template_for_prompt(template: Dict) -> str:
    """LLM 프롬프트용 양식 설명 생성"""
    lines = [
        f"양식: {template['name']} ({template['id']})",
        f"설명: {template['description']}",
        "필수 섹션:",
    ]
    for section in template["sections"]:
        lines.append(
            f"  - ## {section['title']}: {section['description']}"
        )
    return "\n".join(lines)
