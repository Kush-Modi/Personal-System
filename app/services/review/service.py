"""End-of-day pending items review service."""

from typing import List, Optional, Tuple

from app.database.repositories.pending_items import PendingItemRepository
from app.domain.models import PendingItem, PendingStatus


class PendingReviewService:
    """Service to evaluate pending items and generate end-of-day review summaries."""

    def __init__(self, pending_repo: Optional[PendingItemRepository] = None):
        self.repo = pending_repo or PendingItemRepository()

    def check_pending_review(self) -> Tuple[int, Optional[str], List[PendingItem]]:
        """
        Check if any items are waiting for confirmation.
        Returns:
            (count, message_or_none, list_of_pending_items)
        Rule: If count == 0, returns (0, None, []) -> nothing sent to user.
        """
        pending_items = self.repo.list_by_status(PendingStatus.PENDING.value)
        count = len(pending_items)

        if count == 0:
            return 0, None, []

        item_str = "item" if count == 1 else "items"
        message = (
            f"🌙 *Evening Review*\n\n"
            f"You have *{count}* pending {item_str} waiting for your confirmation:\n\n"
        )

        for item in pending_items:
            payload = item.structured_payload
            if item.item_type == "FOOD":
                name = payload.get("food_name", "Food item")
                cals = payload.get("calories", 0)
                message += f"• 🍽 *{name}* ({cals:.0f} kcal)\n"
            elif item.item_type == "EXPENSE":
                amount = payload.get("amount", 0)
                cat = payload.get("category", "Expense")
                message += f"• 💳 *{cat}*: ₹{amount:.2f}\n"
            elif item.item_type == "TASK":
                title = payload.get("title", "Task")
                message += f"• 📋 *{title}*\n"
            else:
                message += f"• 📝 *{item.item_type}* item #{item.id}\n"

        message += "\nUse `/pending` to review or confirm individual items."
        return count, message, pending_items
