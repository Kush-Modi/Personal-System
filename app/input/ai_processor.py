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

        # 2. If AI is enabled, execute unified intent and entity extraction
        if self.ai_service.is_ai_enabled():
            try:
                result = self.ai_service.process_intent_action(cleaned)
                action = result.action or {}

                if result.intent == ItemType.FOOD.value:
                    items = action.get("items", [])
                    if items and isinstance(items, list):
                        name = ", ".join(str(i.get("name") or i.get("food_name", "Food")).strip() for i in items)
                        cals = action.get("total_calories")
                        if cals is None:
                            cals = sum(float(i.get("estimated_calories", 0.0)) for i in items)
                        else:
                            cals = float(cals)
                    else:
                        name = str(action.get("food_name") or action.get("name") or cleaned)
                        cals = float(action.get("calories") or action.get("total_calories") or 100.0)

                    return ProcessingResult(
                        success=True,
                        item_type=ItemType.FOOD.value,
                        payload={
                            "food_name": name.title() if name else "Food Item",
                            "calories": round(cals, 1),
                            "notes": action.get("notes") or (f"Identified {len(items)} items" if items else None),
                            "meal_type": action.get("meal_type")
                        },
                        confidence=result.confidence,
                        source=InputSource.TEXT.value,
                        requires_confirmation=True,
                        response_mode=result.response_mode,
                        raw_text=cleaned,
                    )

                elif result.intent == ItemType.EXPENSE.value:
                    # Robust amount extraction: try multiple keys, then regex on raw text
                    import re as _re

                    def _extract_amount(action_dict: dict, raw_input: str) -> float:
                        """Try multiple keys; last resort: regex on raw user text."""
                        for key in ("amount", "total", "price", "cost", "grand_total", "value"):
                            raw = action_dict.get(key)
                            if raw is not None:
                                s = str(raw).strip()
                                # Strip currency prefixes: ₹, Rs., INR, $
                                s = _re.sub(r"(?i)^(₹|rs\.?|inr|\$)\s*", "", s)
                                try:
                                    v = float(s)
                                    if v > 0:
                                        return v
                                except (ValueError, TypeError):
                                    pass
                        # Fallback: regex on raw text for patterns like "₹290", "Rs 290", "290 rupees"
                        m = _re.search(
                            r"(?:₹|rs\.?|inr)?\s*(\d+(?:[.,]\d+)?)",
                            raw_input,
                            _re.IGNORECASE
                        )
                        if m:
                            try:
                                return float(m.group(1).replace(",", ""))
                            except ValueError:
                                pass
                        return 0.0

                    amt = _extract_amount(action, cleaned)

                    date_val = action.get("date")
                    if date_val == "today":
                        date_val = None

                    return ProcessingResult(
                        success=True,
                        item_type=ItemType.EXPENSE.value,
                        payload={
                            "amount": amt,
                            "currency": action.get("currency", "INR"),
                            "category": action.get("category", "Other"),
                            "merchant": action.get("merchant"),
                            "date": date_val,
                            "description": action.get("note") or action.get("description"),
                        },
                        confidence=result.confidence,
                        source=InputSource.TEXT.value,
                        requires_confirmation=True,
                        response_mode=result.response_mode,
                        raw_text=cleaned,
                    )


                elif result.intent == ItemType.WEIGHT.value:
                    w_raw = action.get("weight_kg") or action.get("weight", 0.0)
                    try:
                        weight_kg = float(w_raw)
                    except (ValueError, TypeError):
                        weight_kg = 0.0

                    date_val = action.get("date")
                    if date_val == "today":
                        date_val = None

                    return ProcessingResult(
                        success=True,
                        item_type=ItemType.WEIGHT.value,
                        payload={
                            "weight_kg": weight_kg,
                            "date": date_val,
                            "unit_original": action.get("unit_original", "kg"),
                        },
                        confidence=result.confidence,
                        source=InputSource.TEXT.value,
                        requires_confirmation=result.requires_confirmation,
                        response_mode=result.response_mode,
                        raw_text=cleaned,
                    )

                elif result.intent == ItemType.TASK.value:
                    return ProcessingResult(
                        success=True,
                        item_type=ItemType.TASK.value,
                        payload={
                            "title": action.get("title") or cleaned,
                            "due_date": action.get("due_date"),
                            "priority": action.get("priority", "Medium"),
                        },
                        confidence=result.confidence,
                        source=InputSource.TEXT.value,
                        requires_confirmation=False,
                        response_mode=result.response_mode,
                        raw_text=cleaned,
                    )

                elif result.intent == ItemType.REMINDER.value:
                    return ProcessingResult(
                        success=True,
                        item_type=ItemType.REMINDER.value,
                        payload={
                            "reminder_text": action.get("reminder_text") or cleaned,
                            "remind_at": action.get("remind_at"),
                        },
                        confidence=result.confidence,
                        source=InputSource.TEXT.value,
                        requires_confirmation=False,
                        response_mode=result.response_mode,
                        raw_text=cleaned,
                    )

                elif result.intent == ItemType.GENERAL_CHAT.value or result.response_mode == "CHAT":
                    return ProcessingResult(
                        success=True,
                        item_type=ItemType.GENERAL_CHAT.value,
                        payload={
                            "reply": result.chat_response or "I'm here! How can I help you today?"
                        },
                        confidence=result.confidence,
                        source=InputSource.TEXT.value,
                        requires_confirmation=False,
                        response_mode="CHAT",
                        raw_text=cleaned,
                    )

                elif result.intent == ItemType.DATA_QUERY.value or result.response_mode == "QUERY":
                    return ProcessingResult(
                        success=True,
                        item_type=ItemType.DATA_QUERY.value,
                        payload={
                            "reply": result.chat_response or "Historical query support is arriving in the next phase."
                        },
                        confidence=result.confidence,
                        source=InputSource.TEXT.value,
                        requires_confirmation=False,
                        response_mode="QUERY",
                        raw_text=cleaned,
                    )

                else:
                    # CLARIFICATION or OTHER
                    return ProcessingResult(
                        success=True,
                        item_type=ItemType.OTHER.value,
                        payload={
                            "reply": result.chat_response or "I didn't quite catch all details. Could you please clarify?"
                        },
                        confidence=result.confidence,
                        source=InputSource.TEXT.value,
                        requires_confirmation=False,
                        response_mode="CLARIFICATION",
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
                    response_mode="CLARIFICATION",
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
                # Check if caption explicitly or strongly suggests a receipt, bill, or invoice
                cap_lower = cap.lower()
                is_receipt_hint = any(k in cap_lower for k in ("receipt", "bill", "invoice", "slip", "expense", "spent", "paid"))

                if is_receipt_hint:
                    receipt_res = self.ai_service.process_receipt_photo(image_path, caption=cap)
                    amt = receipt_res.grand_total
                    merchant = receipt_res.merchant
                    cat = receipt_res.category or "Other"
                    desc_parts = []
                    if merchant:
                        desc_parts.append(f"Merchant: {merchant}")
                    if receipt_res.items:
                        items_str = ", ".join(f"{it.name} (₹{it.total_price:.0f})" for it in receipt_res.items[:5])
                        desc_parts.append(f"Items: {items_str}")
                    desc = " | ".join(desc_parts) if desc_parts else (cap or "Receipt expense")

                    payload = {
                        "amount": amt,
                        "currency": receipt_res.currency,
                        "category": cat,
                        "merchant": merchant,
                        "date": receipt_res.date_str,
                        "description": desc,
                        "items": [
                            {"name": it.name, "quantity": it.quantity, "unit_price": it.unit_price, "total_price": it.total_price}
                            for it in receipt_res.items
                        ],
                        "subtotal": receipt_res.subtotal,
                        "tax": receipt_res.tax,
                        "discount": receipt_res.discount,
                        "is_reconciled": receipt_res.is_reconciled,
                        "mismatch_warning": receipt_res.mismatch_warning,
                    }

                    return ProcessingResult(
                        success=True,
                        item_type=ItemType.EXPENSE.value,
                        payload=payload,
                        confidence=receipt_res.confidence,
                        source=InputSource.PHOTO.value,
                        requires_confirmation=True,
                        raw_text=cap,
                    )

                # Default multimodal inspection: Food photo
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

