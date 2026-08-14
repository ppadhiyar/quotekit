"""Offline eval runner: golden dataset → pipeline → groundedness/precision/recall.

Run locally or in CI:
    python evals/run_evals.py

Exits non-zero if mean groundedness falls below GATE, so a retrieval or prompt
regression fails the build instead of shipping silently.
"""

import json
import sys
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

from app.core.agent import run_quote  # noqa: E402

GATE = 0.6
GOLDEN = Path(__file__).parent / "golden_quotes.jsonl"
RESULTS_DIR = Path(__file__).parent / "results"


def main() -> int:
    cases = [json.loads(line) for line in GOLDEN.read_text().splitlines() if line.strip()]
    scores: list[float] = []
    rows: list[dict] = []

    for case in cases:
        quote = run_quote(case["job_description"])
        item_text = " ".join(li.description.lower() for li in quote.line_items)

        expected_hits = [e for e in case["expected_items"] if e.lower() in item_text]
        forbidden_hits = [f for f in case["must_not_include"] if f.lower() in item_text]
        status_ok = (
            quote.status.value == case["expect_status"]
            if "expect_status" in case
            else True
        )

        recall = (
            len(expected_hits) / len(case["expected_items"]) if case["expected_items"] else 1.0
        )
        scores.append(quote.groundedness_score or 0.0)
        rows.append(
            {
                "job": case["job_description"],
                "groundedness": quote.groundedness_score,
                "item_recall": round(recall, 2),
                "forbidden_items_found": forbidden_hits,
                "status": quote.status.value,
                "status_ok": status_ok,
            }
        )
        print(json.dumps(rows[-1], indent=None))

    avg = mean(scores) if scores else 0.0
    print(f"\nMean groundedness: {avg:.3f} (gate: {GATE})")

    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "latest.json").write_text(json.dumps(rows, indent=2))

    failures = [r for r in rows if r["forbidden_items_found"] or not r["status_ok"]]
    if avg < GATE or failures:
        print(f"FAIL: {len(failures)} case failures, mean groundedness {avg:.3f}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
