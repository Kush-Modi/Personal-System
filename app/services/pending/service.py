"""Pending item domain service managing staging, validation, state transitions, and confirmation."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from app.core.config import settings
from app.core.exceptions import (
    AlreadyProcessedError,
    AppError,
    DomainValidationError,
    InvalidStateTransitionError,
    NotFoundError,
    SchemaValidationError,
)
from app.core.logging import get_logger
from app.database.repositories.pending_items import PendingItemRepository
from app.domain.models import (
    ExpensePayload,
    FoodPayload,
    InputSource,
    ItemType,
    PendingItem,
    PendingStatus,
    TaskPayload,
)
from app.domain.validators import validate_payload
from app.services.finance.service import FinanceService
from app.services.food.service import FoodService

logger = get_logger("services.pending")


class PendingItemService:
    """Service encapsulating the complete lifecycle and state transitions of pending items."""

    def __init__(
        self,
        pending_repo: Optional[PendingItemRepository] = None,
        food_service: Optional[FoodService] = None,
        finance_service: Optional[FinanceService] = None,
        ttl_hours: Optional[int] = None
    ):
        self.repo = pending_repo or PendingItemRepository()
        self.food_service = food_service or FoodService()
        self.finance_service = finance_service or FinanceService()
        self.ttl_hours = ttl_hours if ttl_hours is not None else settings.pending_item_ttl_hours

    def create_pending_item(
        self,
        item_type: Union[ItemType, str],
        structured_payload: Dict[str, Any],
        raw_payload: Optional[str] = None,
        source: Union[InputSource, str] = InputSource.UNKNOWN,
        confidence: float = 1.0,
        image_path: Optional[str] = None,
        user_notes: Optional[str] = None
    ) -> PendingItem:
        """Validate and create a new pending item."""
        type_str = item_type.value if isinstance(item_type, ItemType) else str(item_type).upper()
        source_str = source.value if isinstance(source, InputSource) else str(source).upper()

        # Pre-validate payload
        validate_payload(type_str, structured_payload)

        # Calculate expiration timestamp
        expires_at = (datetime.now() + timedelta(hours=self.ttl_hours)).strftime("%Y-%m-%d %H:%M:%S")

        item_id = self.repo.create(
            item_type=type_str,
            structured_payload=structured_payload,
            raw_payload=raw_payload,
            source=source_str,
            confidence=confidence,
            image_path=image_path,
            user_notes=user_notes,
            expires_at=expires_at
        )

        item = self.repo.get_by_id(item_id)
        if not item:
            raise AppError(f"Failed to retrieve created pending item with ID {item_id}")

        logger.info(f"Created pending item #{item.id} (Type: {item.item_type}, Source: {item.source})")
        return item

    def get_pending_item(self, item_id: int) -> PendingItem:
        """Fetch pending item or raise NotFoundError."""
        item = self.repo.get_by_id(item_id)
        if not item:
            raise NotFoundError(f"Pending item #{item_id} not found.")
        return item

    def confirm(self, item_id: int) -> Tuple[PendingItem, Any]:
        """
        Confirm a pending item:
        1. Check state is PENDING.
        2. Validate payload.
        3. Persist to final domain table via domain service.
        4. Transition state to CONFIRMED.
        Idempotent: double-calls raise AlreadyProcessedError.
        """
        item = self.get_pending_item(item_id)

        # State check
        if item.status == PendingStatus.CONFIRMED.value:
            raise AlreadyProcessedError(f"Pending item #{item_id} has already been confirmed.")
        if item.status == PendingStatus.REJECTED.value:
            raise AlreadyProcessedError(f"Pending item #{item_id} was already rejected.")
        if item.status == PendingStatus.EXPIRED.value:
            raise AlreadyProcessedError(f"Pending item #{item_id} has expired and cannot be confirmed.")
        if item.status != PendingStatus.PENDING.value:
            raise InvalidStateTransitionError(f"Cannot confirm item in state '{item.status}'.")

        # Validate structured payload
        validated_obj = validate_payload(item.item_type, item.structured_payload)
        domain_record = None

        # Execute domain service save
        try:
            if item.item_type == ItemType.FOOD.value or isinstance(validated_obj, FoodPayload):
                food_payload = validated_obj if isinstance(validated_obj, FoodPayload) else FoodPayload(**item.structured_payload)
                domain_record = self.food_service.add_food(
                    name=food_payload.food_name,
                    calories=food_payload.calories
                )

            elif item.item_type == ItemType.EXPENSE.value or isinstance(validated_obj, ExpensePayload):
                exp_payload = validated_obj if isinstance(validated_obj, ExpensePayload) else ExpensePayload(**item.structured_payload)
                desc = exp_payload.description or (f"Merchant: {exp_payload.merchant}" if exp_payload.merchant else None)
                domain_record = self.finance_service.add_expense(
                    amount=exp_payload.amount,
                    category=exp_payload.category,
                    description=desc
                )

            elif item.item_type == ItemType.TASK.value:
                # Task persistence placeholder
                domain_record = {"status": "created", "title": item.structured_payload.get("title")}

            else:
                logger.warning(f"Unrecognized domain item type '{item.item_type}' for item #{item_id}")
                domain_record = {"status": "saved", "type": item.item_type}

            # Update status in database
            self.repo.update_status(item_id, PendingStatus.CONFIRMED.value)
            logger.info(f"Confirmed pending item #{item_id} successfully.")

            updated_item = self.get_pending_item(item_id)
            return updated_item, domain_record

        except Exception as e:
            logger.error(f"Failed to confirm pending item #{item_id}: {e}", exc_info=True)
            self.repo.update_status(item_id, item.status, error_info=str(e))
            raise AppError(f"Could not save pending item: {e}") from e

    def reject(self, item_id: int) -> PendingItem:
        """Reject a pending item."""
        item = self.get_pending_item(item_id)

        if item.status != PendingStatus.PENDING.value:
            raise AlreadyProcessedError(f"Pending item #{item_id} is not in PENDING state (Current: {item.status}).")

        self.repo.update_status(item_id, PendingStatus.REJECTED.value)
        logger.info(f"Rejected pending item #{item_id}.")
        return self.get_pending_item(item_id)

    def edit_payload(
        self,
        item_id: int,
        new_payload: Dict[str, Any],
        user_notes: Optional[str] = None
    ) -> PendingItem:
        """
        Update payload for an item in PENDING state.
        Validates the new payload before updating.
        Does NOT commit to final domain table.
        """
        item = self.get_pending_item(item_id)

        if item.status != PendingStatus.PENDING.value:
            raise AlreadyProcessedError(f"Cannot edit item #{item_id} because it is in '{item.status}' state.")

        # Validate new payload
        validate_payload(item.item_type, new_payload)

        self.repo.update_payload(item_id, new_payload, user_notes=user_notes)
        logger.info(f"Edited payload for pending item #{item_id}.")
        return self.get_pending_item(item_id)

    def expire_overdue(self) -> int:
        """Expire all pending items whose expiration threshold has passed."""
        count = self.repo.expire_overdue_items()
        if count > 0:
            logger.info(f"Expired {count} overdue pending items.")
        return count

    def list_pending(self) -> List[PendingItem]:
        """List all active PENDING items."""
        return self.repo.list_by_status(PendingStatus.PENDING.value)
