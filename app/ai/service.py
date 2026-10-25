"""AI Service orchestrating perception providers, food memory, budget enforcement, and telemetry."""

import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Union

from app.ai.budget import AIBudgetManager
from app.ai.router import AIRouter
from app.ai.schemas import (
    AIRequest,
    AITaskType,
    ExtractedFoodItem,
    FoodExtractionResult,
    IntentResult,
    ReceiptExtractionResult,
)
from app.core.exceptions import (
    AIBudgetExceededError,
    AIServiceError,
)
from app.core.logging import get_logger
from app.database.repositories.ai_request import AIRequestRepository
from app.database.repositories.pending_items import PendingItemRepository
from app.services.food_memory.service import FoodMemoryService

logger = get_logger("ai.service")


class AIService:
    """High-level AI coordinator managing multi-provider execution, memory integration, and telemetry."""

    def __init__(
        self,
        router: Optional[AIRouter] = None,
        budget_manager: Optional[AIBudgetManager] = None,
        food_memory_service: Optional[FoodMemoryService] = None,
        ai_request_repo: Optional[AIRequestRepository] = None,
        pending_repo: Optional[PendingItemRepository] = None,
    ):
        self.router = router or AIRouter()
        self.ai_request_repo = ai_request_repo or AIRequestRepository()
        self.budget_manager = budget_manager or AIBudgetManager(ai_request_repo=self.ai_request_repo)
        self.food_memory = food_memory_service or FoodMemoryService()
        self.pending_repo = pending_repo or PendingItemRepository()

    def is_ai_enabled(self) -> bool:
        """Check if at least one AI provider is configured and available."""
        return any(
            p.is_available()
            for p in self.router.providers.values()
        )

    def process_food_photo(
        self,
        image_path: Union[str, Path],
        caption: str = ""
    ) -> FoodExtractionResult:
        """
        Process food photo:
        1. Query local food memory for context cues.
        2. Verify daily token/request budget.
        3. Dispatch to multimodal router (Gemini / Groq fallback).
        4. Log full telemetry.
        """
        req_id = str(uuid.uuid4())
        task_type = AITaskType.FOOD_PHOTO.value

        # 1. Food memory context
        mem_context = self.food_memory.get_memory_context_prompt(query_hint=caption)

        # 2. Budget verification
        self.budget_manager.check_and_assert_budget(estimated_tokens=1500)

        # 3. Router dispatch
        try:
            result, fallback_used = self.router.route_food_photo(
                image_path=image_path,
                caption=caption,
                memory_context=mem_context
            )

            # 4. Log successful telemetry with authoritative tokens and latency from provider
            p_tokens = result.prompt_tokens or 1200
            c_tokens = result.completion_tokens or 250
            t_tokens = result.total_tokens or (p_tokens + c_tokens)

            self.ai_request_repo.log_request(
                request_id=req_id,
                task_type=task_type,
                provider=result.provider,
                model=result.model,
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
                total_tokens=t_tokens,
                latency_ms=result.latency_ms,
                status="SUCCESS",
                fallback_used=fallback_used
            )
            return result

        except Exception as e:
            # Log failure telemetry
            self.ai_request_repo.log_request(
                request_id=req_id,
                task_type=task_type,
                provider="router",
                model="unknown",
                status="FAILED",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    def process_receipt_photo(
        self,
        image_path: Union[str, Path],
        caption: str = ""
    ) -> ReceiptExtractionResult:
        """
        Process receipt/bill image:
        1. Verify daily token/request budget.
        2. Dispatch to receipt multimodal router.
        3. Independently validate mathematical reconciliation:
           abs(sum(items.total_price) + tax - discount - grand_total) <= tolerance
        4. Log full telemetry.
        """
        req_id = str(uuid.uuid4())
        task_type = AITaskType.RECEIPT_PHOTO.value

        self.budget_manager.check_and_assert_budget(estimated_tokens=1500)

        try:
            result, fallback_used = self.router.route_receipt_photo(
                image_path=image_path,
                caption=caption
            )

            # Mathematical reconciliation check in Python
            items_sum = sum(it.total_price for it in result.items) if result.items else 0.0
            tax_val = result.tax or 0.0
            disc_val = result.discount or 0.0
            grand_total_val = result.grand_total

            # If items are present, check reconciliation
            if result.items and grand_total_val > 0:
                expected_total = items_sum + tax_val - disc_val
                diff = abs(expected_total - grand_total_val)
                tolerance = 2.0  # ₹2 rounding tolerance

                if diff > tolerance:
                    result.is_reconciled = False
                    result.mismatch_warning = (
                        f"⚠️ I found a mismatch in the receipt totals "
                        f"(Items sum: ₹{items_sum:.2f}, Tax: ₹{tax_val:.2f}, Discount: ₹{disc_val:.2f} -> "
                        f"Expected: ₹{expected_total:.2f}, Grand Total: ₹{grand_total_val:.2f}). "
                        f"Please review before saving."
                    )
                    logger.warning(
                        f"Receipt total mismatch: expected {expected_total:.2f} vs grand_total {grand_total_val:.2f}"
                    )
                else:
                    result.is_reconciled = True
                    result.mismatch_warning = None
            else:
                result.is_reconciled = True
                result.mismatch_warning = None

            # Log telemetry with real token counts
            p_tokens = result.prompt_tokens or 1200
            c_tokens = result.completion_tokens or 250
            t_tokens = result.total_tokens or (p_tokens + c_tokens)

            self.ai_request_repo.log_request(
                request_id=req_id,
                task_type=task_type,
                provider=result.provider,
                model=result.model,
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
                total_tokens=t_tokens,
                latency_ms=result.latency_ms,
                status="SUCCESS",
                fallback_used=fallback_used
            )
            return result

        except Exception as e:
            self.ai_request_repo.log_request(
                request_id=req_id,
                task_type=task_type,
                provider="router",
                model="unknown",
                status="FAILED",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    def process_food_text(self, text: str) -> FoodExtractionResult:

        """
        Process natural language food text:
        1. Fast check: exact memory match for single-item query.
        2. Verify budget.
        3. Dispatch to fast text router (Gemini Lite / Groq / OpenRouter).
        4. Log telemetry.
        """
        req_id = str(uuid.uuid4())
        task_type = AITaskType.FOOD_TEXT.value

        # 1. Exact food memory match shortcut (zero AI cost)
        exact_mem = self.food_memory.find_match(text)
        if exact_mem:
            logger.info(f"Zero-AI memory match for '{text}': {exact_mem.default_calories:.0f} kcal")
            return FoodExtractionResult(
                items=[
                    ExtractedFoodItem(
                        food_name=exact_mem.canonical_name.title(),
                        estimated_calories=exact_mem.default_calories,
                        confidence=exact_mem.confidence,
                        portion_description=f"1 {exact_mem.default_unit}",
                        unit=exact_mem.default_unit,
                        memory_match=True,
                    )
                ],
                notes="Matched from local food memory (0 tokens used).",
                provider="food_memory",
                model="local_sqlite",
            )

        # 2. Memory context and budget check
        mem_context = self.food_memory.get_memory_context_prompt(query_hint=text)
        self.budget_manager.check_and_assert_budget(estimated_tokens=500)

        # 3. Router dispatch
        try:
            result, fallback_used = self.router.route_food_text(
                text=text,
                memory_context=mem_context
            )

            # 4. Log telemetry with real token counts
            p_tokens = result.prompt_tokens or 400
            c_tokens = result.completion_tokens or 150
            t_tokens = result.total_tokens or (p_tokens + c_tokens)

            self.ai_request_repo.log_request(
                request_id=req_id,
                task_type=task_type,
                provider=result.provider,
                model=result.model,
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
                total_tokens=t_tokens,
                latency_ms=result.latency_ms,
                status="SUCCESS",
                fallback_used=fallback_used
            )
            return result

        except Exception as e:
            self.ai_request_repo.log_request(
                request_id=req_id,
                task_type=task_type,
                provider="router",
                model="unknown",
                status="FAILED",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    def process_intent_action(
        self,
        text: str,
        current_date: Optional[str] = None
    ) -> IntentResult:
        """
        Process natural language input with unified intent classification and entity extraction:
        1. Query local memory context.
        2. Verify daily token/request budget.
        3. Dispatch to multi-provider router.
        4. Log full telemetry.
        """
        req_id = str(uuid.uuid4())
        task_type = AITaskType.INTENT_ACTION.value

        # 1. Memory context & budget assertion
        mem_context = self.food_memory.get_memory_context_prompt(query_hint=text)
        self.budget_manager.check_and_assert_budget(estimated_tokens=600)

        # 2. Router dispatch
        try:
            result, fallback_used = self.router.route_intent_action(
                text=text,
                current_date=current_date,
                memory_context=mem_context
            )

            # Map telemetry task type if specific
            specific_task_type = task_type
            if result.intent == "FOOD":
                specific_task_type = AITaskType.FOOD_TEXT.value
            elif result.intent == "EXPENSE":
                specific_task_type = AITaskType.EXPENSE.value
            elif result.intent == "WEIGHT":
                specific_task_type = AITaskType.WEIGHT.value
            elif result.intent == "GENERAL_CHAT":
                specific_task_type = AITaskType.GENERAL_CHAT.value
            elif result.intent == "DATA_QUERY":
                specific_task_type = AITaskType.DATA_QUERY.value

            # 3. Log telemetry with real token metrics
            p_tokens = result.prompt_tokens or 450
            c_tokens = result.completion_tokens or 180
            t_tokens = result.total_tokens or (p_tokens + c_tokens)

            self.ai_request_repo.log_request(
                request_id=req_id,
                task_type=specific_task_type,
                provider=result.provider,
                model=result.model,
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
                total_tokens=t_tokens,
                latency_ms=result.latency_ms,
                status="SUCCESS",
                fallback_used=fallback_used
            )
            return result

        except Exception as e:
            self.ai_request_repo.log_request(
                request_id=req_id,
                task_type=task_type,
                provider="router",
                model="unknown",
                status="FAILED",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise


    def get_ai_usage_status(self) -> Dict[str, Any]:
        """Get formatted summary of AI budget and health for /aiusage command."""
        budget_status = self.budget_manager.get_budget_status()
        recent_logs = self.ai_request_repo.get_recent_requests(limit=5)
        provider_health = self.router.health_repo.get_all_health()

        return {
            "budget": budget_status,
            "recent": recent_logs,
            "health": provider_health,
        }
