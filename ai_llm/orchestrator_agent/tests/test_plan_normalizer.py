import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from models import PlanStep
from plan_normalizer import normalize_plan


def test_normalize_report_writing_gets_depends_on():
    steps = [
        PlanStep(agent="file_management", query="test.txt 조회", depends_on=None),
        PlanStep(agent="web_research", query="SQL 조사", depends_on=None),
        PlanStep(agent="report_writing", query="보고서 작성", depends_on=None),
        PlanStep(agent="file_management", query="Drive에 저장", depends_on=None),
    ]
    normalized = normalize_plan(steps)
    assert normalized[2].depends_on == 1
    assert normalized[3].depends_on == 2


def test_normalize_preserves_explicit_depends_on():
    steps = [
        PlanStep(agent="web_research", query="조사", depends_on=None),
        PlanStep(agent="report_writing", query="작성", depends_on=0),
    ]
    normalized = normalize_plan(steps)
    assert normalized[1].depends_on == 0


def test_normalize_single_report_no_upstream():
    steps = [PlanStep(agent="report_writing", query="작성", depends_on=None)]
    normalized = normalize_plan(steps)
    assert normalized[0].depends_on is None
