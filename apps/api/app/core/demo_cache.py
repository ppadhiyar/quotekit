"""Canned responses for DEMO_MODE.

Lets the public demo (and local UI work) run with zero Azure spend: no search
index, no LLM calls. The shapes are identical to live responses, so the
frontend can't tell the difference.
"""

from ..schemas import Citation, LineItem, Quote, QuoteStatus

_DEMO_DOC = "acme_contracting_price_list_2026.csv"


def demo_quote(job_description: str) -> Quote:
    items = [
        LineItem(
            description="Pressure-treated decking 5/4x6",
            quantity=220,
            unit="sq ft",
            unit_price=4.85,
            total=1067.00,
            citation=Citation(
                document=_DEMO_DOC,
                chunk_id="demo-001",
                snippet="Pressure-treated decking 5/4x6 — 4.85 per sq ft",
            ),
            confidence=0.92,
        ),
        LineItem(
            description="Deck framing labour",
            quantity=16,
            unit="hour",
            unit_price=68.00,
            total=1088.00,
            citation=Citation(
                document=_DEMO_DOC,
                chunk_id="demo-014",
                snippet="Deck framing labour — 68.00 per hour",
            ),
            confidence=0.81,
        ),
        LineItem(
            description="Stair stringer set (3-step)",
            quantity=2,
            unit="each",
            unit_price=145.00,
            total=290.00,
            citation=Citation(
                document=_DEMO_DOC,
                chunk_id="demo-022",
                snippet="Stair stringer set (3-step) — 145.00 each",
            ),
            confidence=0.77,
        ),
    ]
    return Quote(
        job_description=job_description,
        line_items=items,
        subtotal=round(sum(i.total for i in items), 2),
        status=QuoteStatus.APPROVED,
        groundedness_score=0.88,
        review_reasons=[],
    )


def demo_chat(question: str) -> dict:
    return {
        "answer": (
            "Based on the indexed price list, pressure-treated decking runs "
            "$4.85/sq ft and framing labour is $68/hour [demo-001] [demo-014]. "
            "(Demo mode — responses are canned.)"
        ),
        "citations": [
            Citation(
                document=_DEMO_DOC,
                chunk_id="demo-001",
                snippet="Pressure-treated decking 5/4x6 — 4.85 per sq ft",
            )
        ],
        "groundedness_score": 0.9,
        "status": QuoteStatus.APPROVED,
    }
