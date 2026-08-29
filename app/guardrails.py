import re
import time
from typing import Dict, Any, Tuple

# Keywords that indicate time-sensitive/volatile data that should bypass semantic caching
VOLATILE_KEYWORDS = {
    "today", "now", "current", "latest", "time", "date",
    "weather", "stock", "price", "news", "ticker", "realtime",
    "real-time", "timestamp", "crypto", "market", "live"
}

VOLATILE_REGEX = re.compile(
    r"\b(" + "|".join(VOLATILE_KEYWORDS) + r")\b", re.IGNORECASE
)


def is_volatile_query(prompt: str) -> bool:
    """Returns True if the prompt contains keywords requiring dynamic, real-time responses."""
    return bool(VOLATILE_REGEX.search(prompt))


class BudgetGuardrailManager:
    """In-memory daily token budget tracker per tenant."""

    def __init__(self, daily_token_limit: int = 100000):
        self.daily_token_limit = daily_token_limit
        # Format: {tenant_id: {"tokens_used": int, "reset_timestamp": float}}
        self._tenant_usage: Dict[str, Dict[str, Any]] = {}

    def _get_current_day_timestamp(self) -> float:
        """Returns midnight timestamp for the current day."""
        now = time.time()
        return now - (now % 86400)

    def check_budget(self, tenant_id: str, estimated_tokens: int = 100) -> Tuple[bool, int, int]:
        """
        Checks if tenant has remaining budget for estimated tokens.
        Returns (is_allowed, current_usage, max_limit).
        """
        current_day = self._get_current_day_timestamp()

        if tenant_id not in self._tenant_usage:
            self._tenant_usage[tenant_id] = {"tokens_used": 0, "reset_timestamp": current_day}

        tenant_data = self._tenant_usage[tenant_id]

        # Reset budget if day boundary has passed
        if tenant_data["reset_timestamp"] < current_day:
            tenant_data["tokens_used"] = 0
            tenant_data["reset_timestamp"] = current_day

        if tenant_data["tokens_used"] + estimated_tokens > self.daily_token_limit:
            return False, tenant_data["tokens_used"], self.daily_token_limit

        return True, tenant_data["tokens_used"], self.daily_token_limit

    def record_usage(self, tenant_id: str, actual_tokens: int):
        """Records token usage after a successful completion."""
        current_day = self._get_current_day_timestamp()

        if tenant_id not in self._tenant_usage:
            self._tenant_usage[tenant_id] = {"tokens_used": 0, "reset_timestamp": current_day}

        self._tenant_usage[tenant_id]["tokens_used"] += actual_tokens