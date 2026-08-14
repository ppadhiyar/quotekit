# QuoteKit Architecture

## Design goals

1. **Grounded by construction** — a price can only appear in output if it was retrieved from the index. The LLM cites `chunk_id`s; the API resolves them against actual retrieval results and silently drops any citation the LLM invented.
2. **Evaluated before delivery** — every response passes a groundedness score (Azure AI Foundry evaluator, LLM-judge, normalized 0–1). Below the confidence threshold (default 0.6), the result is flagged `needs_review` instead of shipping. The gate **fails closed**: if scoring errors, the score is 0.
3. **Near-zero idle cost** — free-tier AI Search, pay-per-token models, scale-to-zero Container App, `DEMO_MODE` for the public site.

## Two products, one core

| | QuoteKit | Website Brain |
|---|---|---|
| Input | Job description | Visitor question |
| Corpus | Price lists, past quotes | Website pages, docs, FAQs |
| Output | Structured `Quote` (line items + citations) | Cited answer in a chat widget |
| Shared | Ingestion → AI Search index → LangGraph retrieve/generate/evaluate → eval gate |

## The LangGraph pipeline

```
retrieve ──► generate ──► evaluate ──┬─► approved (return to user)
                                     └─► needs_review (human-in-the-loop)
```

- **retrieve** — hybrid search (BM25 + vector, `text-embedding-3-small`) against Azure AI Search, top 8.
- **generate** — `gpt-4o-mini`, temperature 0, structured JSON output. The system prompt forbids inventing prices; items without a retrieved source go to `missing_items`.
- **evaluate** — `GroundednessEvaluator` from `azure-ai-evaluation` scores the draft against the retrieved context. Missing items or a low score routes to `needs_review`.

## Ingestion: why tables get special treatment

Contractor price lists are tabular. Naive text chunking splits rows from their prices, which produces confidently wrong quotes — the worst failure mode this system can have. So:

- **CSV** → one chunk per row (`item — price per unit. notes`), price stored as a typed field.
- **PDF with Document Intelligence** → `prebuilt-layout` extracts tables cell-by-cell; each row becomes a chunk with headers re-attached.
- **PDF fallback (pypdf)** → line-based chunking with a warning that structure may be lossy. Zero cost, dev-only.

## Evaluation strategy (offline + online)

- **Online (per request):** groundedness gate described above.
- **Offline (CI):** `evals/run_evals.py` runs a golden dataset through the full pipeline and checks mean groundedness, expected-item recall, forbidden-item leakage, and status routing (e.g. a nonsense job *must* route to `needs_review`). CI fails below the gate — retrieval regressions can't ship silently.

## Cost controls

| Control | Where |
|---|---|
| AI Search free tier (50 MB / 3 indexes) | `infra/main.bicep` |
| Scale-to-zero API (minReplicas: 0) | `infra/main.bicep` |
| IP rate limiting (slowapi) | `apps/api/app/main.py` |
| Upload size cap (5 MB) | `apps/api/app/routers/ingest.py` |
| `DEMO_MODE` canned responses | `apps/api/app/core/demo_cache.py` |

## Multi-tenancy (Website Brain roadmap)

- One AI Search index per tenant (free tier allows 3; Basic tier for growth).
- `X-Tenant` header from the widget maps to index name server-side.
- Per-tenant token metering for usage-based pricing.
