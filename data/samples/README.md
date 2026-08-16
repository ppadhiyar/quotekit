# Sample price lists

Three interchangeable versions of the demo price list. **Replacement is keyed by
filename**, so all three are named `sample_price_list.csv` — upload any of them
via the [admin page](https://victorious-cliff-08f5d320f.7.azurestaticapps.net/admin.html)
(or `POST /ingest`) and it replaces whichever version is currently indexed.

| Version | Path | What it demos |
|---|---|---|
| **Standard** (default) | `sample_price_list.csv` | Baseline rates, 20 items |
| **Fall 2026 update** | `variants/fall-2026-price-update/sample_price_list.csv` | Same catalog with ~5–10% price increases plus a seasonal surcharge — run the same quote before and after to show quotes tracking the live price list |
| **Premium contractor** | `variants/premium-contractor/sample_price_list.csv` | High-end positioning: premium rates, upgraded materials (ipe decking, glass railing, solid-core doors), and extra line items — shows the same query producing a very different, still fully cited quote |

All versions cover the items behind the demo suggestion chips (deck, fence,
painting, doors, drywall), so every chip returns a good-looking cited quote no
matter which version is loaded.

**Demo script idea:** quote "rebuild a 200 sq ft deck" on the standard list,
upload the premium list, run the identical query again — the subtotal jumps and
every line item cites the new source rows. That's the grounded-RAG story in one
minute.
