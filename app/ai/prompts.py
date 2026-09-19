"""Centralized AI prompt templates and structured JSON schema definitions."""

from typing import Any, Dict, List, Optional

FOOD_EXTRACTION_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "description": "List of distinct identified food items in the meal or description",
            "items": {
                "type": "object",
                "properties": {
                    "food_name": {
                        "type": "string",
                        "description": "Clean, canonical food item name (e.g. 'Paneer Butter Masala', 'Steamed White Rice')"
                    },
                    "estimated_calories": {
                        "type": "number",
                        "description": "Estimated total kilocalories (kcal) for this specific portion"
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence score between 0.0 and 1.0"
                    },
                    "portion_description": {
                        "type": "string",
                        "description": "Visual or textual portion estimate (e.g. '1 medium bowl', '2 pieces', '150g')"
                    },
                    "quantity": {
                        "type": "number",
                        "description": "Numerical count or multiplier of servings"
                    },
                    "unit": {
                        "type": "string",
                        "description": "Unit of measurement (e.g. 'serving', 'piece', 'bowl', 'plate', 'cup')"
                    }
                },
                "required": ["food_name", "estimated_calories", "confidence"]
            }
        },
        "meal_type": {
            "type": "string",
            "description": "Estimated meal category (Breakfast, Lunch, Dinner, Snack, Beverage)"
        },
        "notes": {
            "type": "string",
            "description": "Brief nutritional observation or portion reasoning"
        }
    },
    "required": ["items"]
}

FOOD_PHOTO_SYSTEM_PROMPT = """You are an expert nutrition and visual food estimation assistant.
Your goal is to inspect the provided food image, accurately identify all distinct food components, estimate reasonable portion sizes based on visual cues, and calculate realistic caloric values (in kcal).

Guidelines:
1. Break mixed meals down into realistic components (e.g., rice, dal, sabzi, salad, chapati).
2. For Indian / home-cooked dishes, use standard realistic nutritional values (accounting for moderate cooking oil/ghee).
3. If user context/caption is provided, factor it in heavily (e.g., 'no sugar', 'made with olive oil', '2 chapatis').
4. Be objective and avoid extreme over/under estimation.
5. If local user food memory context is provided in the prompt, prioritize the user's established caloric benchmarks for identical items.
6. Return purely structured JSON conforming to the schema.
"""

FOOD_TEXT_SYSTEM_PROMPT = """You are an expert nutrition assistant.
Your goal is to parse natural language food descriptions into structured food items with estimated calories.

Guidelines:
1. Parse every distinct food item mentioned.
2. If quantities are mentioned (e.g., '2 eggs', '1 cup curd'), calculate total calories for that quantity.
3. If memory benchmarks are provided, prefer the user's established historical caloric benchmarks.
4. Return purely structured JSON conforming to the schema.
"""


def build_food_photo_prompt(caption: Optional[str] = None, memory_context: Optional[str] = None) -> str:
    """Construct prompt for multimodal food photo perception."""
    prompt = "Please analyze this meal image and extract all visible food items with portion and calorie estimates."
    if caption and caption.strip():
        prompt += f"\n\nUser Notes/Caption: {caption.strip()}"
    if memory_context and memory_context.strip():
        prompt += f"\n\nUser Food Memory Context (known benchmarks):\n{memory_context.strip()}"
    return prompt


def build_food_text_prompt(text: str, memory_context: Optional[str] = None) -> str:
    """Construct prompt for natural language food text extraction."""
    prompt = f"Extract food items and estimate calories from the following description:\n\"{text.strip()}\""
    if memory_context and memory_context.strip():
        prompt += f"\n\nUser Food Memory Context (known benchmarks):\n{memory_context.strip()}"
    return prompt
