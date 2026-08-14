"""LangGraph pipeline: retrieve → generate → eval gate → approve / flag.

The graph is deliberately linear with one conditional edge — the eval gate.
That gate is the point of the whole system: nothing reaches the user without
being scored against the retrieved sources first.
"""

import json
import logging
from typing import Literal, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI
from langgraph.graph import END, StateGraph

from ..config import get_settings
from ..schemas import Citation, LineItem, Quote, QuoteStatus
from . import demo_cache, search
from .eval_gate import score_groundedness

logger = logging.getLogger(__name__)

QUOTE_SYSTEM_PROMPT = """You are a quoting assistant for a contracting business.
Given a job description and a set of retrieved price-list entries, produce a quote.

Rules — these are hard constraints:
- Only use prices that appear in the retrieved entries. Never invent a price.
- Every line item MUST reference the chunk_id of the entry its price came from.
- If the job needs an item that has no matching retrieved entry, do NOT guess:
  list it in "missing_items" instead.
- Estimate quantities from the job description; state your unit assumptions.

Respond with JSON only:
{
  "line_items": [
    {"description": str, "quantity": number, "unit": str, "unit_price": number,
     "chunk_id": str, "confidence": number between 0 and 1}
  ],
  "missing_items": [str]
}"""

CHAT_SYSTEM_PROMPT = """You answer questions about a business using ONLY the
retrieved context below. If the context does not contain the answer, say so —
never fill gaps from general knowledge. Cite chunk_ids inline like [chunk_id]."""


class AgentState(TypedDict, total=False):
    query: str
    mode: Literal["quote", "chat"]
    hits: list[dict]
    draft: dict          # raw LLM JSON (quote) or {"answer": str} (chat)
    groundedness: float
    status: QuoteStatus
    review_reasons: list[str]


def _llm() -> AzureChatOpenAI:
    s = get_settings()
    return AzureChatOpenAI(
        azure_endpoint=s.azure_openai_endpoint,
        api_key=s.azure_openai_api_key,
        api_version=s.azure_openai_api_version,
        azure_deployment=s.azure_openai_chat_deployment,
        temperature=0,
    )


# --- Graph nodes -----------------------------------------------------------


def retrieve(state: AgentState) -> AgentState:
    hits = search.hybrid_search(state["query"], top=8)
    return {"hits": hits}


def generate(state: AgentState) -> AgentState:
    context = "\n".join(
        f"[{h['chunk_id']}] ({h['document']}) {h['content']}" for h in state["hits"]
    )
    system = QUOTE_SYSTEM_PROMPT if state["mode"] == "quote" else CHAT_SYSTEM_PROMPT
    response = _llm().invoke(
        [
            SystemMessage(content=system),
            HumanMessage(content=f"Retrieved entries:\n{context}\n\nRequest: {state['query']}"),
        ]
    )
    text = response.content
    if state["mode"] == "quote":
        draft = json.loads(text.strip().removeprefix("```json").removesuffix("```").strip())
    else:
        draft = {"answer": text}
    return {"draft": draft}


def evaluate(state: AgentState) -> AgentState:
    """The eval gate: score the draft against the retrieved sources."""
    context = "\n".join(h["content"] for h in state["hits"])
    answer_text = json.dumps(state["draft"])
    score = score_groundedness(query=state["query"], context=context, answer=answer_text)

    reasons: list[str] = []
    threshold = get_settings().confidence_threshold
    if score < threshold:
        reasons.append(f"groundedness {score:.2f} below threshold {threshold}")
    if state["mode"] == "quote" and state["draft"].get("missing_items"):
        reasons.append(f"no price source for: {', '.join(state['draft']['missing_items'])}")

    status = QuoteStatus.APPROVED if not reasons else QuoteStatus.NEEDS_REVIEW
    return {"groundedness": score, "status": status, "review_reasons": reasons}


def route_after_eval(state: AgentState) -> str:
    # Both branches currently end the graph; the split is kept explicit so a
    # human-review queue (ticket, email, dashboard) can hook in per branch.
    return "approved" if state["status"] == QuoteStatus.APPROVED else "needs_review"


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("retrieve", retrieve)
    g.add_node("generate", generate)
    g.add_node("evaluate", evaluate)
    g.set_entry_point("retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", "evaluate")
    g.add_conditional_edges("evaluate", route_after_eval, {"approved": END, "needs_review": END})
    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


# --- Public entry points ---------------------------------------------------


def run_quote(job_description: str, live: bool = True) -> Quote:
    if get_settings().demo_mode or not live:
        return demo_cache.demo_quote(job_description)

    state = get_graph().invoke({"query": job_description, "mode": "quote"})
    hits_by_id = {h["chunk_id"]: h for h in state["hits"]}

    line_items = []
    for item in state["draft"].get("line_items", []):
        hit = hits_by_id.get(item.get("chunk_id"))
        if hit is None:
            continue  # LLM cited a chunk that wasn't retrieved — drop, never trust
        line_items.append(
            LineItem(
                description=item["description"],
                quantity=item["quantity"],
                unit=item["unit"],
                unit_price=item["unit_price"],
                total=round(item["quantity"] * item["unit_price"], 2),
                citation=Citation(
                    document=hit["document"], chunk_id=hit["chunk_id"], snippet=hit["content"]
                ),
                confidence=item.get("confidence", 0.5),
            )
        )

    return Quote(
        job_description=job_description,
        line_items=line_items,
        subtotal=round(sum(li.total for li in line_items), 2),
        status=state["status"],
        groundedness_score=state["groundedness"],
        review_reasons=state["review_reasons"],
    )


def run_chat(question: str, live: bool = True) -> dict:
    if get_settings().demo_mode or not live:
        return demo_cache.demo_chat(question)

    state = get_graph().invoke({"query": question, "mode": "chat"})
    citations = [
        Citation(document=h["document"], chunk_id=h["chunk_id"], snippet=h["content"])
        for h in state["hits"]
        if h["chunk_id"] in state["draft"]["answer"]
    ]
    return {
        "answer": state["draft"]["answer"],
        "citations": citations,
        "groundedness_score": state["groundedness"],
        "status": state["status"],
    }
