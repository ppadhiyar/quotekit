from enum import Enum

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Pointer back to the exact source chunk a value was retrieved from."""

    document: str
    chunk_id: str
    snippet: str


class LineItem(BaseModel):
    description: str
    quantity: float
    unit: str
    unit_price: float
    total: float
    citation: Citation
    confidence: float = Field(ge=0.0, le=1.0)


class QuoteStatus(str, Enum):
    APPROVED = "approved"          # passed the eval gate
    NEEDS_REVIEW = "needs_review"  # below confidence threshold — human in the loop


class ResponseMode(str, Enum):
    LIVE = "live"  # real retrieval + LLM + eval gate
    DEMO = "demo"  # canned response — no access code, budget exhausted, or DEMO_MODE


class Quote(BaseModel):
    job_description: str
    line_items: list[LineItem]
    subtotal: float
    status: QuoteStatus
    groundedness_score: float | None = None
    review_reasons: list[str] = []
    mode: ResponseMode = ResponseMode.LIVE


class QuoteRequest(BaseModel):
    job_description: str = Field(min_length=10, max_length=2000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    session_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    groundedness_score: float | None = None
    status: QuoteStatus
    mode: ResponseMode = ResponseMode.LIVE


class IngestResult(BaseModel):
    document: str
    chunks_indexed: int
    replaced_chunks: int = 0  # stale chunks deleted before this upload
    warnings: list[str] = []
