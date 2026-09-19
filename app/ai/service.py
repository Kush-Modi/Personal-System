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

            # 4. Log successful telemetry
            self.ai_request_repo.log_request(
                request_id=req_id,
                task_type=task_type,
                provider=result.provider,
                model=result.model,
                prompt_tokens=1200,  # Estimated or from response
                completion_tokens=250,
                total_tokens=1450,
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

            # 4. Log telemetry
            self.ai_request_repo.log_request(
                request_id=req_id,
                task_type=task_type,
                provider=result.provider,
                model=result.model,
                prompt_tokens=400,
                completion_tokens=150,
                total_tokens=550,
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
