from fastapi import APIRouter, Header, Request

from ..core import access
from ..core.agent import run_quote
from ..schemas import Quote, QuoteRequest

router = APIRouter(tags=["quote"])


@router.post("/quote", response_model=Quote)
async def create_quote(
    request: Request,
    body: QuoteRequest,
    x_access_code: str | None = Header(default=None),
) -> Quote:
    # No valid code (or exhausted daily budget) silently degrades to demo
    # responses — the public site keeps working at zero LLM cost.
    live = access.has_live_access(x_access_code) and access.try_consume_llm_budget()
    return run_quote(body.job_description, live=live)
