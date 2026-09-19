"""Deterministic mock input processor for Phase 2 testing and verification."""

import re
from pathlib import Path
from typing import Optional, Union

from app.domain.models import InputSource, ItemType
from app.input.processor import InputProcessor
from app.input.schemas import ProcessingResult


class MockInputProcessor(InputProcessor):
    """
    Deterministic input processor for testing the complete end-to-end
    confirmation and pending item pipeline without calling external AI APIs.
    """

    def process_text(self, text: str, context: Optional[dict] = None) -> ProcessingResult:
        cleaned = text.strip()

        # 1. Explicit Mock Food: "mock food <name> <calories>"
        if cleaned.lower().startswith("mock food "):
            parts = cleaned[10:].strip().split()
            if len(parts) >= 2:
                try:
                    calories = float(parts[-1])
                    name = " ".join(parts[:-1])
                    return ProcessingResult(
                        success=True,
                        item_type=ItemType.FOOD.value,
                        payload={"food_name": name, "calories": calories},
                        confidence=1.0,
                        source=InputSource.MOCK.value,
                        requires_confirmation=True,
                        raw_text=cleaned
                    )
                except ValueError:
                    pass

        # 2. Explicit Mock Expense: "mock expense <amount> <category> [merchant]"
        if cleaned.lower().startswith("mock expense "):
            parts = cleaned[13:].strip().split()
            if len(parts) >= 2:
                try:
                    amount = float(parts[0])
                    category = parts[1]
                    merchant = " ".join(parts[2:]) if len(parts) > 2 else "Mock Store"
                    return ProcessingResult(
                        success=True,
                        item_type=ItemType.EXPENSE.value,
                        payload={"amount": amount, "category": category, "merchant": merchant},
                        confidence=1.0,
                        source=InputSource.MOCK.value,
                        requires_confirmation=True,
                        raw_text=cleaned
                    )
                except ValueError:
                    pass

        # 3. Explicit Mock Task: "mock task <title>"
        if cleaned.lower().startswith("mock task "):
            title = cleaned[10:].strip()
            if title:
                return ProcessingResult(
                    success=True,
                    item_type=ItemType.TASK.value,
                    payload={"title": title},
                    confidence=1.0,
                    source=InputSource.MOCK.value,
                    requires_confirmation=True,
                    raw_text=cleaned
                )

        # 4. Simple Natural Language Heuristic (e.g. "had 2 rotis 240 kcal")
        food_match = re.search(r"had\s+(.+?)\s+(\d+)\s*(?:kcal|calories)?$", cleaned, re.IGNORECASE)
        if food_match:
            name = food_match.group(1).strip()
            calories = float(food_match.group(2))
            return ProcessingResult(
                success=True,
                item_type=ItemType.FOOD.value,
                payload={"food_name": name, "calories": calories},
                confidence=0.85,
                source=InputSource.TEXT.value,
                requires_confirmation=True,
                raw_text=cleaned
            )

        # 5. Simple Natural Language Expense (e.g. "spent 150 on coffee at starbucks")
        expense_match = re.search(r"spent\s+(\d+(?:\.\d+)?)\s+on\s+([a-zA-Z]+)(?:\s+at\s+(.+))?", cleaned, re.IGNORECASE)
        if expense_match:
            amount = float(expense_match.group(1))
            category = expense_match.group(2).capitalize()
            merchant = expense_match.group(3).strip() if expense_match.group(3) else None
            return ProcessingResult(
                success=True,
                item_type=ItemType.EXPENSE.value,
                payload={"amount": amount, "category": category, "merchant": merchant},
                confidence=0.85,
                source=InputSource.TEXT.value,
                requires_confirmation=True,
                raw_text=cleaned
            )

        return ProcessingResult(
            success=False,
            item_type=ItemType.OTHER.value,
            payload={},
            confidence=0.0,
            source=InputSource.UNKNOWN.value,
            requires_confirmation=False,
            raw_text=cleaned,
            error_message="Could not parse input into a structured action."
        )

    def process_photo(
        self,
        image_path: Union[str, Path],
        caption: Optional[str] = None
    ) -> ProcessingResult:
        """Deterministic mock image perception."""
        cap = (caption or "").lower()

        if "receipt" in cap or "expense" in cap or "bill" in cap:
            return ProcessingResult(
                success=True,
                item_type=ItemType.EXPENSE.value,
                payload={
                    "amount": 450.0,
                    "category": "Groceries",
                    "merchant": "Supermarket (Mock OCR)",
                    "description": "Receipt extraction mock"
                },
                confidence=0.92,
                source=InputSource.MOCK.value,
                requires_confirmation=True,
                raw_text=caption
            )
        else:
            return ProcessingResult(
                success=True,
                item_type=ItemType.FOOD.value,
                payload={
                    "food_name": "Paneer Tikka (Mock Vision)",
                    "calories": 420.0,
                    "notes": "Estimated from photo"
                },
                confidence=0.87,
                source=InputSource.MOCK.value,
                requires_confirmation=True,
                raw_text=caption
            )
