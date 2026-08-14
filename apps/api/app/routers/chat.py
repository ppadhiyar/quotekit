from fastapi import APIRouter, Request

from ..core.agent import run_chat
from ..schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    return ChatResponse(**run_chat(body.question))
