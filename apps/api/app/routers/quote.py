from fastapi import APIRouter, Request

from ..core.agent import run_quote
from ..schemas import Quote, QuoteRequest

router = APIRouter(tags=["quote"])


@router.post("/quote", response_model=Quote)
async def create_quote(request: Request, body: QuoteRequest) -> Quote:
    return run_quote(body.job_description)
