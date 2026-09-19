"""OpenRouter AI provider implementation using httpx for multi-model fallback."""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

import httpx

from app.ai.prompts import (
    FOOD_PHOTO_SYSTEM_PROMPT,
    FOOD_TEXT_SYSTEM_PROMPT,
    build_food_photo_prompt,
    build_food_text_prompt,
)
from app.ai.provider import AIProvider
from app.ai.schemas import (
    AIRequest,
    AIResponse,
    AITaskType,
    ExtractedFoodItem,
    ExtractedReceiptItem,
    FoodExtractionResult,
    ReceiptExtractionResult,
)
from app.core.config import settings
from app.core.exceptions import (
    AIAuthenticationError,
    AIModelUnavailableError,
    AIParseError,
    AIRateLimitError,
    AIServiceError,
    AITimeoutError,
)
from app.core.logging import get_logger

logger = get_logger("ai.openrouter")


class OpenRouterProvider(AIProvider):
    """OpenRouter API provider implementation for external LLM fallback."""

    API_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None
    ):
        self.api_key = api_key if api_key is not None else settings.openrouter_api_key
        self.default_model = default_model or settings.openrouter_default_model

    @property
    def name(self) -> str:
        return "openrouter"

    def is_available(self) -> bool:
        """Check if OpenRouter API key is configured."""
        return bool(self.api_key and len(self.api_key.strip()) > 0)

    def supports_vision(self) -> bool:
        return False

    def generate_structured(self, request: AIRequest) -> AIResponse:
        """Execute structured generation with OpenRouter."""
        if not self.is_available():
            raise AIAuthenticationError("OPENROUTER_API_KEY is not configured or is empty.")

        model_id = request.model or self.default_model
        start_time = time.perf_counter()

        messages = []
        if request.system_instruction:
            sys_content = request.system_instruction
            if request.json_mode:
                sys_content += "\nYou MUST return valid JSON conforming to the requested format."
            messages.append({"role": "system", "content": sys_content})

        messages.append({"role": "user", "content": request.prompt})

        payload: Dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": request.temperature,
        }

        if request.json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key.strip()}",
            "HTTP-Referer": "https://github.com/Kush-Modi/Personal-System",
            "X-Title": "Personal-System",
            "Content-Type": "application/json",
        }

        try:
            logger.info(f"Calling OpenRouter model '{model_id}' (task: {request.task_type})...")
            with httpx.Client(timeout=float(settings.ai_timeout_seconds)) as client:
                response = client.post(self.API_URL, json=payload, headers=headers)

            latency_ms = (time.perf_counter() - start_time) * 1000

            if response.status_code == 401 or response.status_code == 403:
                raise AIAuthenticationError(f"OpenRouter authentication failed (HTTP {response.status_code}): {response.text}")
            elif response.status_code == 429:
                raise AIRateLimitError(f"OpenRouter rate limit / quota exceeded (HTTP 429): {response.text}")
            elif response.status_code >= 500:
                raise AIModelUnavailableError(f"OpenRouter server error (HTTP {response.status_code}): {response.text}")
            elif response.status_code != 200:
                raise AIServiceError(f"OpenRouter request failed (HTTP {response.status_code}): {response.text}")

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise AIServiceError("OpenRouter returned empty choices in response.")

            text_output = choices[0].get("message", {}).get("content", "") or ""
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0) or 0
            completion_tokens = usage.get("completion_tokens", 0) or 0
            total_tokens = usage.get("total_tokens", 0) or (prompt_tokens + completion_tokens)

            structured_data = None
            if request.json_mode and text_output:
                try:
                    structured_data = json.loads(text_output)
                except json.JSONDecodeError as jde:
                    logger.warning(f"OpenRouter output was not valid JSON: {text_output[:200]}")
                    raise AIParseError(f"Failed to parse OpenRouter JSON response: {jde}") from jde

            return AIResponse(
                content=text_output,
                structured_data=structured_data,
                provider=self.name,
                model=model_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                success=True,
            )

        except (AIParseError, AIAuthenticationError, AIRateLimitError, AIModelUnavailableError):
            raise
        except httpx.TimeoutException as te:
            latency_ms = (time.perf_counter() - start_time) * 1000
            raise AITimeoutError(f"OpenRouter request timed out: {te}") from te
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"OpenRouter generation error: {e}", exc_info=True)
            raise AIServiceError(f"OpenRouter error: {e}") from e

    def extract_food_from_image(
        self,
        image_path: Union[str, Path],
        context_prompt: str = "",
        memory_context: str = ""
    ) -> FoodExtractionResult:
        """OpenRouter free tier does not reliably support vision in this profile."""
        raise AIServiceError("OpenRouter provider does not support vision extraction.")

    def extract_food_from_text(
        self,
        text: str,
        memory_context: str = ""
    ) -> FoodExtractionResult:
        """Extract structured food items from natural text via OpenRouter."""
        if not self.is_available():
            raise AIServiceError("OPENROUTER_API_KEY is not configured.")

        prompt = build_food_text_prompt(text=text, memory_context=memory_context)
        req = AIRequest(
            task_type=AITaskType.FOOD_TEXT,
            prompt=prompt,
            system_instruction=FOOD_TEXT_SYSTEM_PROMPT,
            model=self.default_model,
            json_mode=True,
        )

        res = self.generate_structured(req)
        data = res.structured_data or {}
        items_raw = data.get("items", [])

        extracted_items = [
            ExtractedFoodItem(
                food_name=item.get("food_name", "Unknown Food"),
                estimated_calories=float(item.get("estimated_calories", 0.0)),
                confidence=float(item.get("confidence", 0.8)),
                portion_description=item.get("portion_description"),
                quantity=float(item.get("quantity", 1.0)),
                unit=item.get("unit", "serving"),
            )
            for item in items_raw
        ]

        return FoodExtractionResult(
            items=extracted_items,
            raw_response=res.content,
            notes=data.get("notes"),
            meal_type=data.get("meal_type"),
            provider=self.name,
            model=res.model,
        )

    def extract_receipt_from_image(
        self,
        image_path: Union[str, Path]
    ) -> ReceiptExtractionResult:
        raise AIServiceError("OpenRouter provider does not support receipt images.")
