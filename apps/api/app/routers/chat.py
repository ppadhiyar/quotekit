from fastapi import APIRouter, Header, Request

from ..core import access
from ..core.agent import run_chat
from ..schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: Request,
    body: ChatRequest,
    x_access_code: str | None = Header(default=None),
) -> ChatResponse:
    live = access.has_live_access(x_access_code) and access.try_consume_llm_budget()
    return ChatResponse(**run_chat(body.question, live=live))
