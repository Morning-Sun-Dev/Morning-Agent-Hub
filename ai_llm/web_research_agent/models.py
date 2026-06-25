from typing import List, Optional
from pydantic import BaseModel, Field


class WebSource(BaseModel):
    title: str = Field(description="검색 결과 제목")
    url: str = Field(description="출처 URL")
    snippet: Optional[str] = Field(default=None, description="본문 요약 스니펫")
    score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="관련도 점수 (0~1)")


class WebSearchResult(BaseModel):
    query: str = Field(description="실행된 검색 쿼리")
    summary: str = Field(description="검색 결과 종합 요약")
    sources: List[WebSource] = Field(default_factory=list, description="참고 출처 목록")
    search_successful: bool = Field(default=True, description="검색 성공 여부")
