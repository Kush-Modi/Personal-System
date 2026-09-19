"""Data schemas for AI extraction and perception pipeline."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ExtractedFoodItem:
    food_name: str
    estimated_calories: float
    confidence: float = 1.0
    portion_description: Optional[str] = None


@dataclass
class FoodExtractionResult:
    items: List[ExtractedFoodItem] = field(default_factory=list)
    raw_response: str = ""
    notes: Optional[str] = None


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
