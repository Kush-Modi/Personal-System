"""AI-powered Input Processor mediating between Telegram inputs and AIService."""

from pathlib import Path
from typing import Optional, Union

from app.ai.schemas import FoodExtractionResult
from app.ai.service import AIService
from app.core.exceptions import (
    AIBudgetExceededError,
    AIRateLimitError,
    AIServiceError,
)
from app.core.logging import get_logger
from app.domain.models import InputSource, ItemType
from app.input.mock_processor import MockInputProcessor
from app.input.processor import InputProcessor
from app.input.schemas import ProcessingResult

logger = get_logger("input.ai_processor")


class AIInputProcessor(InputProcessor):
    """Input processor delegating extraction to real AI providers with deterministic fallback."""

    def __init__(
        self,
        ai_service: Optional[AIService] = None,
        mock_processor: Optional[MockInputProcessor] = None
    ):
        self.ai_service = ai_service or AIService()
        self.mock_processor = mock_processor or MockInputProcessor()

    def process_text(self, text: str, context: Optional[dict] = None) -> ProcessingResult:
        cleaned = text.strip()

        # 1. Deterministic Mock commands always bypass AI
        if cleaned.lower().startswith("mock "):
            return self.mock_processor.process_text(cleaned, context)

        # 2. If AI is enabled, attempt AI extraction
        if self.ai_service.is_ai_enabled():
            try:
                result = self.ai_service.process_food_text(cleaned)
                if result.items:
                    # Construct aggregated name if multiple items
                    if len(result.items) == 1:
                        name = result.items[0].food_name
                        cals = result.items[0].estimated_calories
                        conf = result.items[0].confidence
                    else:
                        name = ", ".join(item.food_name for item in result.items)
                        cals = sum(item.estimated_calories for item in result.items)
                        conf = min(item.confidence for item in result.items)

                    return ProcessingResult(
                        success=True,
                        item_type=ItemType.FOOD.value,
                        payload={
                            "food_name": name,
                            "calories": round(cals, 1),
                            "notes": result.notes or f"Identified {len(result.items)} items",
                            "meal_type": result.meal_type
                        },
                        confidence=conf,
                        source=InputSource.TEXT.value,
                        requires_confirmation=True,
                        raw_text=cleaned,
                    )

            except AIBudgetExceededError as e:
                logger.warning(f"AI text extraction budget exceeded: {e}")
                return ProcessingResult(
                    success=False,
                    item_type=ItemType.OTHER.value,
                    payload={},
                    confidence=0.0,
                    source=InputSource.TEXT.value,
                    requires_confirmation=False,
                    raw_text=cleaned,
                    error_message=f"⏳ Daily AI Budget Limit Reached: {e}"
                )
            except Exception as e:
                logger.warning(f"AI text processing failed: {e}. Falling back to deterministic rules.")

        # 3. Fallback to deterministic parser
        return self.mock_processor.process_text(cleaned, context)

    def process_photo(
        self,
        image_path: Union[str, Path],
        caption: Optional[str] = None
    ) -> ProcessingResult:
        cap = (caption or "").strip()

        # 1. Mock prefix bypass
        if cap.lower().startswith("mock "):
            return self.mock_processor.process_photo(image_path, cap)

        # 2. AI Multimodal Perception
        if self.ai_service.is_ai_enabled():
            try:
                result = self.ai_service.process_food_photo(image_path, caption=cap)
                if result.items:
                    if len(result.items) == 1:
                        name = result.items[0].food_name
                        cals = result.items[0].estimated_calories
                        conf = result.items[0].confidence
                    else:
                        name = ", ".join(item.food_name for item in result.items)
                        cals = sum(item.estimated_calories for item in result.items)
                        conf = min(item.confidence for item in result.items)

                    return ProcessingResult(
                        success=True,
                        item_type=ItemType.FOOD.value,
                        payload={
                            "food_name": name,
                            "calories": round(cals, 1),
                            "notes": result.notes or f"Identified {len(result.items)} items from photo",
                            "meal_type": result.meal_type
                        },
                        confidence=conf,
                        source=InputSource.PHOTO.value,
                        requires_confirmation=True,
                        raw_text=cap,
                    )

            except AIBudgetExceededError as e:
                logger.warning(f"AI photo extraction budget exceeded: {e}")
                return ProcessingResult(
                    success=False,
                    item_type=ItemType.OTHER.value,
                    payload={},
                    confidence=0.0,
                    source=InputSource.PHOTO.value,
                    requires_confirmation=False,
                    raw_text=cap,
                    error_message=f"⏳ Daily AI Budget Limit Reached: {e}"
                )
            except Exception as e:
                logger.warning(f"AI photo perception failed: {e}. Falling back to mock/heuristics.")

        # 3. Fallback
        return self.mock_processor.process_photo(image_path, cap)
