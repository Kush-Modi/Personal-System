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


# ==================================================
# RECEIPT / BILL PHOTO EXTRACTION SCHEMA & PROMPTS
# ==================================================

RECEIPT_PHOTO_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "is_receipt": {
            "type": "boolean",
            "description": "True if the image is a receipt, invoice, or bill. False if it is a food plate, dish, or non-receipt image."
        },
        "merchant": {
            "type": "string",
            "description": "Store, business, or merchant name (e.g. 'Reliance Fresh', 'Starbucks', 'Swiggy', 'Apollo Pharmacy')"
        },
        "date": {
            "type": "string",
            "description": "Receipt date in YYYY-MM-DD format if visible, else null"
        },
        "currency": {
            "type": "string",
            "description": "Currency code (default 'INR')"
        },
        "items": {
            "type": "array",
            "description": "Line items from the receipt",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Item description/name"},
                    "quantity": {"type": "number", "description": "Quantity multiplier (default 1)"},
                    "unit_price": {"type": "number", "description": "Price per single unit if visible"},
                    "total_price": {"type": "number", "description": "Total price for this line item"}
                },
                "required": ["name", "total_price"]
            }
        },
        "subtotal": {
            "type": "number",
            "description": "Subtotal before taxes/discounts if indicated"
        },
        "tax": {
            "type": "number",
            "description": "Total taxes (GST, CGST, SGST, VAT) if visible, else 0"
        },
        "discount": {
            "type": "number",
            "description": "Discounts applied if visible, else 0"
        },
        "grand_total": {
            "type": "number",
            "description": "Final payable grand total amount. Must be a positive number (> 0)."
        },
        "category": {
            "type": "string",
            "enum": [
                "Food & Dining", "Groceries", "Transport", "Shopping", "Bills",
                "Entertainment", "Health", "Education", "Travel", "Subscriptions", "Other"
            ],
            "description": "Appropriate expense category based on merchant and items."
        },
        "notes": {
            "type": "string",
            "description": "Observation or note on OCR clarity"
        },
        "confidence": {
            "type": "number",
            "description": "Confidence score between 0.0 and 1.0"
        }
    },
    "required": ["is_receipt", "grand_total"]
}

RECEIPT_PHOTO_SYSTEM_PROMPT = """You are an expert financial OCR assistant specialized in inspecting bill, invoice, and receipt images.
Your goal is to inspect the receipt image, extract the merchant name, receipt date, individual line items with prices, tax, discounts, and the grand total.

Guidelines:
1. Determine if this image is indeed a receipt or bill (is_receipt = true). If it is a photo of actual food or a meal on a plate, set is_receipt = false.
2. Extract all readable line items with their item name and line total price.
3. Extract subtotal, taxes (GST, VAT, etc.), and discounts if visible.
4. Extract the final payable grand total. Do NOT guess or hallucinate numbers if unreadable; report best visible figures.
5. Identify the best category: Food & Dining, Groceries, Transport, Shopping, Bills, Entertainment, Health, Education, Travel, Subscriptions, Other.
6. Return purely structured JSON matching the schema.
"""


def build_receipt_photo_prompt(caption: Optional[str] = None) -> str:
    """Construct prompt for receipt/bill image inspection."""
    prompt = "Please analyze this image. If it is a receipt, invoice, or bill, extract all financial fields, merchant, items, and totals."
    if caption and caption.strip():
        prompt += f"\n\nUser Context/Caption: {caption.strip()}"
    return prompt



# ==================================================
# PHASE 4 UNIFIED INTENT & ACTION NLU
# ==================================================

UNIFIED_INTENT_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["FOOD", "EXPENSE", "WEIGHT", "TASK", "REMINDER", "GENERAL_CHAT", "DATA_QUERY", "OTHER"],
            "description": "Primary classified intent of user message."
        },
        "confidence": {
            "type": "number",
            "description": "Confidence score between 0.0 and 1.0."
        },
        "response_mode": {
            "type": "string",
            "enum": ["ACTION", "QUERY", "CHAT", "CLARIFICATION"],
            "description": "ACTION: executable domain log, QUERY: historical data question, CHAT: conversational response, CLARIFICATION: missing info."
        },
        "action": {
            "type": "object",
            "description": "Structured domain parameters for ACTION mode.",
            "properties": {
                "food": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "description": "Food dish name"},
                                    "quantity": {"type": "number", "description": "Quantity multiplier"},
                                    "unit": {"type": "string", "description": "Unit (piece, bowl, plate, cup, etc.)"},
                                    "estimated_calories": {"type": "number", "description": "Realistic positive calories (> 0)"}
                                },
                                "required": ["name", "estimated_calories"]
                            }
                        },
                        "total_calories": {"type": "number", "description": "Sum of item calories"},
                        "meal_type": {"type": "string", "description": "Breakfast, Lunch, Dinner, Snack"},
                        "notes": {"type": "string"}
                    }
                },
                "expense": {
                    "type": "object",
                    "properties": {
                        "amount": {"type": "number", "description": "Monetary amount (> 0)"},
                        "currency": {"type": "string", "description": "Currency code (default 'INR')"},
                        "merchant": {"type": "string", "description": "Merchant/payee name"},
                        "category": {
                            "type": "string",
                            "description": "Category: Food & Dining, Groceries, Transport, Shopping, Bills, Entertainment, Health, Education, Travel, Subscriptions, Other"
                        },
                        "date": {"type": "string", "description": "Date YYYY-MM-DD or 'today'"},
                        "note": {"type": "string", "description": "Optional notes or item description"}
                    }
                },
                "weight": {
                    "type": "object",
                    "properties": {
                        "weight_kg": {"type": "number", "description": "Weight in kilograms (e.g. 76.2)"},
                        "date": {"type": "string", "description": "Date YYYY-MM-DD or 'today'"},
                        "unit_original": {"type": "string", "description": "Original unit ('kg' or 'lbs')"}
                    }
                },
                "task": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Task summary/title"},
                        "due_date": {"type": "string", "description": "Due date if specified"},
                        "priority": {"type": "string", "description": "Low, Medium, High"}
                    }
                },
                "reminder": {
                    "type": "object",
                    "properties": {
                        "reminder_text": {"type": "string", "description": "What to remind"},
                        "remind_at": {"type": "string", "description": "When to remind (ISO datetime or relative)"}
                    }
                }
            }
        },
        "chat_response": {
            "type": "string",
            "description": "Direct response text for CHAT, QUERY, or CLARIFICATION."
        },
        "missing_information": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of missing fields if ambiguous."
        },
        "requires_confirmation": {
            "type": "boolean",
            "description": "Whether user confirmation is required before committing to database."
        }
    },
    "required": ["intent", "confidence", "response_mode"]
}

UNIFIED_NLU_SYSTEM_PROMPT = """You are the intelligent brain of an executive personal assistant.
Your job is to accurately interpret user messages in English, Hindi, and Hinglish, classify the user's intent, and output structured JSON.

### INTENT TAXONOMY & RULES:
1. FOOD: User consumed food/drink or wants to log intake (e.g., 'I had 2 rotis and 1 bowl of dal', 'Had paneer tikka', '3 bananas', 'Aaj do roti khayi').
   - Extract individual items with realistic positive calorie estimates (> 0).
   - Calculate total_calories as sum of items.
   - Set requires_confirmation = true.
   - Default response_mode = 'ACTION'.

2. EXPENSE: User spent money or paid for something (e.g., 'Spent ₹450 at Starbucks', 'Paid 1200 for groceries', '300 on Uber', 'Bought shirt for 1800', '₹80 chai and samosa', 'Aaj ₹500 spend kiya').
   - Extract amount (> 0), currency (default 'INR'), merchant, category (Food & Dining, Groceries, Transport, Shopping, Bills, Entertainment, Health, Education, Travel, Subscriptions, Other).
   - If money spent is on food (e.g. 'Spent ₹60 on chai'), classify as EXPENSE (unless user explicitly asks to log food intake).
   - Set requires_confirmation = true.
   - Default response_mode = 'ACTION'.

3. WEIGHT: User logs body weight (e.g., 'I'm 76.2 kg today', 'My weight is 75.8', 'Weight 75.6', 'Mera weight 76.2 hai').
   - Extract weight_kg (convert lbs to kg if needed: 1 lb = 0.453592 kg).
   - For clear weights, requires_confirmation = false.
   - If ambiguous (e.g. 'I am 76'), response_mode = 'CLARIFICATION' and ask if 76 refers to kg.

4. TASK: User wants to add a task/to-do (e.g., 'Add finish resume to tasks', 'Remember to send email').
   - Extract title, due_date. response_mode = 'ACTION'.

5. REMINDER: User wants a time-based reminder (e.g., 'Remind me tomorrow to call mom').
   - Extract reminder_text, remind_at. response_mode = 'ACTION'.

6. DATA_QUERY: User asks a question about past/historical data (e.g., 'How many calories did I eat yesterday?', 'How much did I spend this month?', 'What was my weight last week?').
   - DO NOT classify as ACTION. Set response_mode = 'QUERY'.
   - Provide a helpful chat_response.

7. GENERAL_CHAT: Conversational questions, advice, greetings (e.g., 'How are you?', 'What should I focus on today?', 'Explain this to me', 'I feel stuck').
   - Set response_mode = 'CHAT'.
   - Provide a thoughtful, warm, and helpful chat_response.

8. OTHER / AMBIGUOUS: Vague statements missing key details (e.g., 'I spent some money', '₹500', 'Had something heavy', 'Remind me about this').
   - Set response_mode = 'CLARIFICATION'.
   - In chat_response, ask a polite, specific clarifying question.

### STRICT CONSTRAINTS:
- Timezone: Asia/Kolkata. Default currency: INR.
- NEVER invent or hallucinate data that wasn't mentioned.
- All food calorie estimates MUST be positive numbers (> 0).
- Return ONLY a valid JSON object matching the requested schema.
"""


def build_unified_nlu_prompt(
    text: str,
    current_date: Optional[str] = None,
    memory_context: Optional[str] = None
) -> str:
    """Construct unified NLU prompt for multi-domain intent and action understanding."""
    date_ctx = current_date or "today"
    prompt = f"Current Date Context: {date_ctx}\n\nUser Message:\n\"{text.strip()}\""
    if memory_context and memory_context.strip():
        prompt += f"\n\nUser Food Memory Context (known benchmarks):\n{memory_context.strip()}"
    return prompt

