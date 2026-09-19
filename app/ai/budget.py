"""AI Budget and rate guardrail manager enforcing daily request and token limits."""

from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.exceptions import AIBudgetExceededError
from app.core.logging import get_logger
from app.database.repositories.ai_request import AIRequestRepository

logger = get_logger("ai.budget")


class AIBudgetManager:
    """Enforces daily request and token budgets calculated in user timezone."""

    def __init__(
        self,
        ai_request_repo: Optional[AIRequestRepository] = None,
        daily_request_limit: Optional[int] = None,
        daily_token_limit: Optional[int] = None,
        tz_name: Optional[str] = None
    ):
        self.repo = ai_request_repo or AIRequestRepository()
        self.request_limit = daily_request_limit if daily_request_limit is not None else settings.ai_daily_request_limit
        self.token_limit = daily_token_limit if daily_token_limit is not None else settings.ai_daily_token_limit
        self.tz_name = tz_name or settings.timezone

    def get_current_date_str(self) -> str:
        """Get YYYY-MM-DD for the configured timezone."""
        try:
            tz = ZoneInfo(self.tz_name)
            return datetime.now(tz).strftime("%Y-%m-%d")
        except Exception:
            # Fallback to local system date if timezone string is invalid
            return datetime.now().strftime("%Y-%m-%d")

    def get_budget_status(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """Fetch current budget consumption and remaining limits."""
        target_date = date_str or self.get_current_date_str()
        usage = self.repo.get_daily_usage(target_date)

        requests_used = usage["total_requests"]
        tokens_used = usage["total_tokens"]

        req_pct = round((requests_used / self.request_limit * 100), 1) if self.request_limit > 0 else 0.0
        tok_pct = round((tokens_used / self.token_limit * 100), 1) if self.token_limit > 0 else 0.0

        is_exhausted = (requests_used >= self.request_limit) or (tokens_used >= self.token_limit)

        return {
            "date": target_date,
            "requests_used": requests_used,
            "requests_limit": self.request_limit,
            "tokens_used": tokens_used,
            "tokens_limit": self.token_limit,
            "requests_percent": req_pct,
            "tokens_percent": tok_pct,
            "is_exhausted": is_exhausted,
            "by_provider": usage.get("by_provider", {}),
            "avg_latency_ms": usage.get("avg_latency_ms", 0.0),
        }

    def check_and_assert_budget(self, estimated_tokens: int = 500) -> None:
        """
        Verify budget is not exhausted. Raises AIBudgetExceededError if over limit.
        """
        status = self.get_budget_status()

        if status["requests_used"] >= self.request_limit:
            msg = (
                f"Daily AI request limit reached ({status['requests_used']}/{self.request_limit}). "
                f"Resets at midnight ({self.tz_name})."
            )
            logger.warning(f"AI Budget Exceeded: {msg}")
            raise AIBudgetExceededError(msg)

        if (status["tokens_used"] + estimated_tokens) > self.token_limit:
            msg = (
                f"Daily AI token limit reached ({status['tokens_used']}/{self.token_limit} tokens). "
                f"Resets at midnight ({self.tz_name})."
            )
            logger.warning(f"AI Token Budget Exceeded: {msg}")
            raise AIBudgetExceededError(msg)
