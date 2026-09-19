"""Data schemas and types for AI extraction, perception, and telemetry."""

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
