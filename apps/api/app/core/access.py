"""Access control: who gets live LLM calls, and how many per day.

Three layers keep the public demo from generating real spend:
1. Live mode requires the access code (rotate it in the Container App env
   whenever a demo period ends). Everyone else gets canned demo responses.
2. A daily cap on live LLM requests, even with a valid code. In-memory, so it
   resets if the app scales to zero — it is a backstop, not a billing system.
3. Per-IP rate limiting (slowapi, configured in main.py).
"""

import hmac
import threading
from datetime import datetime, timezone

from ..config import get_settings

_lock = threading.Lock()
_budget = {"day": None, "used": 0}


def has_live_access(provided_code: str | None) -> bool:
    """Constant-time comparison; live mode is impossible if no code is configured."""
    expected = get_settings().access_code
    if not expected or not provided_code:
        return False
    return hmac.compare_digest(provided_code, expected)


def is_admin(provided_key: str | None) -> bool:
    expected = get_settings().admin_api_key
    if not expected or not provided_key:
        return False
    return hmac.compare_digest(provided_key, expected)


def try_consume_llm_budget() -> bool:
    """Reserve one live LLM request from today's budget. False when exhausted."""
    today = datetime.now(timezone.utc).date()
    limit = get_settings().llm_daily_request_limit
    with _lock:
        if _budget["day"] != today:
            _budget["day"] = today
            _budget["used"] = 0
        if _budget["used"] >= limit:
            return False
        _budget["used"] += 1
        return True


def llm_budget_remaining() -> int:
    today = datetime.now(timezone.utc).date()
    limit = get_settings().llm_daily_request_limit
    with _lock:
        return limit if _budget["day"] != today else max(0, limit - _budget["used"])
