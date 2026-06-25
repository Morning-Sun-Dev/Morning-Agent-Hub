from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field

AgentName = Literal["internal_rag", "web_research", "file_management", "report_writing"]


class PlanStep(BaseModel):
    """단일 에이전트 실행 단계"""
    agent: AgentName
    query: str = Field(description="에이전트에 전달할 자연어 요청")
    depends_on: Optional[int] = Field(
        default=None,
        ge=0,
        description="의존하는 이전 step 인덱스 (0부터 시작). None이면 독립 실행 가능"
    )


class IntentPlan(BaseModel):
    """Intent 분류 및 실행 계획"""
    intent: Literal["INTERNAL_SEARCH", "WEB_SEARCH", "FILE_OPERATION", "HYBRID", "DIRECT"]
    plan: List[PlanStep] = Field(default_factory=list)
    direct_answer: Optional[str] = Field(
        default=None,
        description="DIRECT intent일 때 직접 답변"
    )


class TraceStep(BaseModel):
    """에이전트 실행 과정 단계 (F-017)"""
    step: int = Field(ge=0)
    agent: str
    status: Literal["started", "completed", "failed", "skipped"]
    message: str
    duration_ms: Optional[int] = None


class AgentResult(BaseModel):
    """단일 에이전트 실행 결과"""
    agent: str
    success: bool
    content: Optional[str] = None
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    trace: TraceStep
