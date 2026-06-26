"""실행 계획 의존성 자동 보정 — report_writing이 upstream 완료 후 실행되도록"""

from __future__ import annotations

import logging
from typing import List

try:
    from .models import PlanStep
except ImportError:
    from models import PlanStep

logger = logging.getLogger(__name__)

_SAVE_KEYWORDS = ("저장", "업로드", "upload", "save", "drive")


def normalize_plan(steps: List[PlanStep]) -> List[PlanStep]:
    """
    LLM이 depends_on을 빠뜨린 경우 보정.

    - report_writing: 이전 모든 step 완료 후 실행 (upstream 취합)
    - file_management(저장): 직전 report_writing 완료 후 실행
    """
    if not steps:
        return steps

    normalized = [step.model_copy() for step in steps]

    for i, step in enumerate(normalized):
        if step.agent != "report_writing" or step.depends_on is not None:
            continue
        upstream = list(range(i))
        if not upstream:
            continue
        step.depends_on = max(upstream)
        logger.info(
            "[ORCHESTRATOR] report_writing step %d → depends_on=%d (자동 보정)",
            i,
            step.depends_on,
        )

    for i, step in enumerate(normalized):
        if step.agent != "file_management" or step.depends_on is not None:
            continue
        query_lower = step.query.lower()
        if not any(kw in query_lower for kw in _SAVE_KEYWORDS):
            continue
        report_indices = [j for j in range(i) if normalized[j].agent == "report_writing"]
        if not report_indices:
            continue
        step.depends_on = max(report_indices)
        logger.info(
            "[ORCHESTRATOR] file_management(save) step %d → depends_on=%d (자동 보정)",
            i,
            step.depends_on,
        )

    return normalized
