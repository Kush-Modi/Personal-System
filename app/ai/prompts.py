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
                        "description": "Clean, canonical food item name (e.g. 'Roti', 'Daal', 'Paneer Butter Masala')"
                    },
                    "estimated_calories": {
                        "type": "number",
                        "description": "Estimated total kilocalories (kcal) for this specific portion/quantity. Must be a positive number (> 0)."
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence score between 0.0 and 1.0"
                    },
                    "portion_description": {
                        "type": "string",
                        "description": "Portion description (e.g. '2 pieces', '1 medium bowl', '150g')"
                    },
                    "quantity": {
                        "type": "number",
                        "description": "Numerical quantity or multiplier (e.g. 2, 1, 0.5)"
                    },
                    "unit": {
                        "type": "string",
                        "description": "Unit of measurement (e.g. 'piece', 'bowl', 'plate', 'cup', 'serving')"
                    }
                },
                "required": ["food_name", "estimated_calories"]
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
3. Every identified food item MUST have a realistic positive calorie estimate (estimated_calories > 0). Do NOT return 0 or null for calories.
4. If user context/caption is provided, factor it in heavily (e.g., 'no sugar', 'made with olive oil', '2 chapatis').
5. If local user food memory context is provided in the prompt, prioritize the user's established caloric benchmarks for identical items.
6. Return purely structured JSON conforming to the schema with 'items' containing 'food_name' and 'estimated_calories'.
"""

FOOD_TEXT_SYSTEM_PROMPT = """You are an expert nutrition assistant.
Your goal is to parse natural language food descriptions into structured food items with estimated calories.

Guidelines:
1. Parse every distinct food item mentioned in the text.
2. For each food item, calculate total realistic estimated calories (estimated_calories > 0) based on the specified quantity and standard nutritional values (e.g., 1 whole wheat roti ~90-110 kcal, 1 bowl dal ~150-200 kcal, 1 egg ~75 kcal).
3. Every item MUST have positive estimated calories. Do NOT return 0 or null for calories.
4. If memory benchmarks are provided, prefer the user's established historical caloric benchmarks.
5. Return purely structured JSON conforming to the schema with 'items' containing 'food_name' and 'estimated_calories'.
"""


def build_food_photo_prompt(caption: Optional[str] = None, memory_context: Optional[str] = None) -> str:
    """Construct prompt for multimodal food photo perception."""
    prompt = "Please analyze this meal image and extract all visible food items with portion and positive calorie estimates."
    if caption and caption.strip():
        prompt += f"\n\nUser Notes/Caption: {caption.strip()}"
    if memory_context and memory_context.strip():
        prompt += f"\n\nUser Food Memory Context (known benchmarks):\n{memory_context.strip()}"
    return prompt


def build_food_text_prompt(text: str, memory_context: Optional[str] = None) -> str:
    """Construct prompt for natural language food text extraction."""
    prompt = f"Extract food items and calculate realistic calorie estimates from the following description:\n\"{text.strip()}\""
    if memory_context and memory_context.strip():
        prompt += f"\n\nUser Food Memory Context (known benchmarks):\n{memory_context.strip()}"
    return prompt
