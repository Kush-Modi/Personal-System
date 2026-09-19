"""Data schemas, types, and robust JSON parsing for AI extraction, perception, and telemetry."""

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class AITaskType(str, Enum):
    FOOD_PHOTO = "food_photo"
    FOOD_TEXT = "food_text"
    RECEIPT_PHOTO = "receipt_photo"
    GENERAL_QUERY = "general_query"


class AIProviderName(str, Enum):
    GEMINI = "gemini"
    GROQ = "groq"
    OPENROUTER = "openrouter"
    MOCK = "mock"


@dataclass
class ExtractedFoodItem:
    food_name: str
    estimated_calories: float
    confidence: float = 1.0
    portion_description: Optional[str] = None
    quantity: float = 1.0
    unit: str = "serving"
    memory_match: bool = False


def parse_calorie_value(val: Any) -> float:
    """Safely parse calorie values from various LLM representation formats (int, float, string, range)."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val_clean = val.replace(",", "").strip()
        # Handle numeric ranges like "150-200" or "300 - 400 kcal"
        range_match = re.search(r"(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)", val_clean)
        if range_match:
            return (float(range_match.group(1)) + float(range_match.group(2))) / 2.0
        # Handle simple numbers with units like "200 kcal", "~180"
        match = re.search(r"(\d+(?:\.\d+)?)", val_clean)
        if match:
            return float(match.group(1))
    return 0.0


def parse_extracted_food_item(item: Dict[str, Any], default_confidence: float = 0.9) -> ExtractedFoodItem:
    """
    Robustly transform an arbitrary LLM food item JSON dictionary into a strongly typed ExtractedFoodItem.
    Handles field name variations (name/food_name/food/dish/title) and calorie fields (estimated_calories/total_calories/calories/kcal/calories_per_unit).
    """
    if not isinstance(item, dict):
        return ExtractedFoodItem(
            food_name="Unknown Food",
            estimated_calories=100.0,
            confidence=0.5
        )

    # 1. Food Name resolution
    name = (
        item.get("food_name")
        or item.get("name")
        or item.get("item")
        or item.get("food")
        or item.get("dish")
        or item.get("title")
        or "Food Item"
    )
    if not isinstance(name, str) or not name.strip():
        name = "Food Item"
    name = name.strip()

    # 2. Quantity & Unit resolution
    qty_raw = item.get("quantity", 1.0)
    try:
        qty = float(qty_raw) if qty_raw is not None else 1.0
    except (ValueError, TypeError):
        qty = 1.0
    if qty <= 0:
        qty = 1.0

    unit = str(item.get("unit") or "serving").strip()

    # 3. Calories resolution across alternate field names
    calories = 0.0
    if "estimated_calories" in item and item["estimated_calories"] is not None:
        calories = parse_calorie_value(item["estimated_calories"])
    elif "total_calories" in item and item["total_calories"] is not None:
        calories = parse_calorie_value(item["total_calories"])
    elif "calories" in item and item["calories"] is not None:
        calories = parse_calorie_value(item["calories"])
    elif "kcal" in item and item["kcal"] is not None:
        calories = parse_calorie_value(item["kcal"])
    elif "total_kcal" in item and item["total_kcal"] is not None:
        calories = parse_calorie_value(item["total_kcal"])
    elif "calories_per_unit" in item and item["calories_per_unit"] is not None:
        cal_unit = parse_calorie_value(item["calories_per_unit"])
        calories = cal_unit * qty
    elif "energy_kcal" in item and item["energy_kcal"] is not None:
        calories = parse_calorie_value(item["energy_kcal"])

    # 4. Confidence resolution
    conf_raw = item.get("confidence", default_confidence)
    try:
        confidence = float(conf_raw) if conf_raw is not None else default_confidence
    except (ValueError, TypeError):
        confidence = default_confidence

    # 5. Portion Description
    portion_desc = item.get("portion_description")
    if not portion_desc:
        portion_desc = f"{qty:.0f} {unit}" if qty.is_integer() else f"{qty:.1f} {unit}"

    return ExtractedFoodItem(
        food_name=name.title(),
        estimated_calories=round(calories, 1),
        confidence=confidence,
        portion_description=portion_desc,
        quantity=qty,
        unit=unit,
    )


@dataclass
class FoodExtractionResult:
    items: List[ExtractedFoodItem] = field(default_factory=list)
    raw_response: str = ""
    notes: Optional[str] = None
    meal_type: Optional[str] = None
    total_estimated_calories: float = 0.0
    provider: str = ""
    model: str = ""

    def __post_init__(self):
        if self.items and self.total_estimated_calories == 0.0:
            self.total_estimated_calories = sum(item.estimated_calories for item in self.items)


@dataclass
class ExtractedReceiptItem:
    name: str
    price: float
    category: Optional[str] = None


@dataclass
class ReceiptExtractionResult:
    merchant: Optional[str] = None
    total_amount: float = 0.0
    category: str = "General"
    date_str: Optional[str] = None
    items: List[ExtractedReceiptItem] = field(default_factory=list)
    raw_response: str = ""
    provider: str = ""
    model: str = ""


@dataclass
class AIRequest:
    task_type: Union[AITaskType, str]
    prompt: str
    system_instruction: Optional[str] = None
    image_path: Optional[Union[str, Path]] = None
    model: Optional[str] = None
    temperature: float = 0.2
    response_schema: Optional[Dict[str, Any]] = None
    json_mode: bool = True


@dataclass
class AIResponse:
    content: str
    structured_data: Optional[Dict[str, Any]] = None
    provider: str = ""
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None
