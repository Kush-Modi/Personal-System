"""OpenRouter AI provider implementation using httpx for multi-model fallback."""

import base64
import json
import mimetypes
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

import httpx

from app.ai.prompts import (
    FOOD_PHOTO_SYSTEM_PROMPT,
    FOOD_TEXT_SYSTEM_PROMPT,
    UNIFIED_NLU_SYSTEM_PROMPT,
    build_food_photo_prompt,
    build_food_text_prompt,
    build_unified_nlu_prompt,
)
from app.ai.provider import AIProvider
from app.ai.schemas import (
    AIRequest,
    AIResponse,
    AITaskType,
    ExtractedFoodItem,
    ExtractedReceiptItem,
    FoodExtractionResult,
    IntentResult,
    ReceiptExtractionResult,
    parse_intent_result,
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
        default_model: Optional[str] = None,
        vision_model: Optional[str] = None
    ):
        self.api_key = api_key if api_key is not None else settings.openrouter_api_key
        self.default_model = default_model or settings.openrouter_default_model
        self.vision_model = vision_model or settings.openrouter_vision_model

    @property
    def name(self) -> str:
        return "openrouter"

    def is_available(self) -> bool:
        """Check if OpenRouter API key is configured."""
        return bool(self.api_key and len(self.api_key.strip()) > 0)

    def supports_vision(self) -> bool:
        """OpenRouter supports vision via multimodal models when API key is configured."""
        return self.is_available()

    def _encode_image_to_data_uri(self, image_path: Union[str, Path]) -> str:
        """Encode an image file to a base64 data URI."""
        img_path = Path(image_path)
        if not img_path.exists():
            raise AIServiceError(f"Image not found at path: {img_path}")
        mime_type = mimetypes.guess_type(str(img_path))[0] or "image/jpeg"
        with open(img_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime_type};base64,{b64_data}"

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

    def extract_intent_action(
        self,
        text: str,
        current_date: Optional[str] = None,
        memory_context: str = ""
    ) -> IntentResult:
        """Extract multi-domain intent and structured action from natural text via OpenRouter fallback."""
        if not self.is_available():
            raise AIServiceError("OPENROUTER_API_KEY is not configured.")

        prompt = build_unified_nlu_prompt(text, current_date=current_date, memory_context=memory_context)
        req = AIRequest(
            task_type=AITaskType.INTENT_ACTION,
            prompt=prompt,
            system_instruction=UNIFIED_NLU_SYSTEM_PROMPT,
            model=self.default_model,
            json_mode=True,
        )

        res = self.generate_structured(req)
        data = res.structured_data or {}
        intent_res = parse_intent_result(data, default_confidence=0.80)
        intent_res.provider = self.name
        intent_res.model = res.model
        intent_res.raw_response = res.content
        intent_res.prompt_tokens = res.prompt_tokens
        intent_res.completion_tokens = res.completion_tokens
        intent_res.total_tokens = res.total_tokens
        intent_res.latency_ms = res.latency_ms
        return intent_res

    def extract_food_from_image(
        self,
        image_path: Union[str, Path],
        context_prompt: str = "",
        memory_context: str = ""
    ) -> FoodExtractionResult:
        """Extract structured food items from an image via OpenRouter vision model."""
        if not self.is_available():
            raise AIServiceError("OPENROUTER_API_KEY is not configured.")

        data_uri = self._encode_image_to_data_uri(image_path)
        prompt_text = build_food_photo_prompt(caption=context_prompt, memory_context=memory_context)

        messages = [
            {"role": "system", "content": FOOD_PHOTO_SYSTEM_PROMPT + "\nReturn ONLY valid JSON."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": data_uri}}
                ]
            }
        ]

        payload: Dict[str, Any] = {
            "model": self.vision_model,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"}
        }
        headers = {
            "Authorization": f"Bearer {self.api_key.strip()}",
            "HTTP-Referer": "https://github.com/Kush-Modi/Personal-System",
            "X-Title": "Personal-System",
            "Content-Type": "application/json",
        }

        start_time = time.perf_counter()
        logger.info(f"Dispatching food photo to OpenRouter vision model '{self.vision_model}'...")
        try:
            with httpx.Client(timeout=float(settings.ai_timeout_seconds)) as client:
                response = client.post(self.API_URL, json=payload, headers=headers)

            if response.status_code == 401 or response.status_code == 403:
                raise AIAuthenticationError(f"OpenRouter vision auth failed (HTTP {response.status_code})")
            elif response.status_code == 429:
                raise AIRateLimitError(f"OpenRouter vision rate limit (HTTP 429): {response.text}")
            elif response.status_code >= 500:
                raise AIModelUnavailableError(f"OpenRouter vision server error (HTTP {response.status_code})")
            elif response.status_code != 200:
                raise AIServiceError(f"OpenRouter vision request failed (HTTP {response.status_code}): {response.text}")

            resp_data = response.json()
            choices = resp_data.get("choices", [])
            if not choices:
                raise AIServiceError("OpenRouter vision returned empty choices.")

            text_output = choices[0].get("message", {}).get("content", "") or ""
            data = json.loads(text_output) if text_output else {}
            items_raw = data.get("items", [])

            extracted_items = [
                ExtractedFoodItem(
                    food_name=item.get("food_name", "Unknown Food"),
                    estimated_calories=float(item.get("estimated_calories", 0.0)),
                    confidence=float(item.get("confidence", 0.70)),
                    portion_description=item.get("portion_description"),
                    quantity=float(item.get("quantity", 1.0)),
                    unit=item.get("unit", "serving"),
                )
                for item in items_raw
            ]
            prompt_tokens = usage.get("prompt_tokens", 0) or 0
            completion_tokens = usage.get("completion_tokens", 0) or 0
            total_tokens = usage.get("total_tokens", 0) or (prompt_tokens + completion_tokens)
            latency_ms = (time.perf_counter() - start_time) * 1000

            return FoodExtractionResult(
                items=extracted_items,
                raw_response=text_output,
                notes=data.get("notes"),
                meal_type=data.get("meal_type"),
                provider=self.name,
                model=self.vision_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
            )

        except (AIAuthenticationError, AIRateLimitError, AIModelUnavailableError):
            raise
        except httpx.TimeoutException as te:
            raise AITimeoutError(f"OpenRouter vision request timed out: {te}") from te
        except json.JSONDecodeError as jde:
            raise AIParseError(f"Failed to parse OpenRouter vision JSON: {jde}") from jde
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"OpenRouter vision error: {e}", exc_info=True)
            raise AIServiceError(f"OpenRouter vision error: {e}") from e

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
            prompt_tokens=res.prompt_tokens,
            completion_tokens=res.completion_tokens,
            total_tokens=res.total_tokens,
            latency_ms=res.latency_ms,
        )

    def extract_receipt_from_image(
        self,
        image_path: Union[str, Path],
        caption: str = ""
    ) -> ReceiptExtractionResult:
        """Extract receipt from image via OpenRouter vision model (fallback)."""
        if not self.is_available():
            raise AIServiceError("OPENROUTER_API_KEY is not configured.")

        data_uri = self._encode_image_to_data_uri(image_path)
        from app.ai.prompts import RECEIPT_PHOTO_SYSTEM_PROMPT, build_receipt_photo_prompt
        prompt_text = build_receipt_photo_prompt(caption=caption)

        messages = [
            {"role": "system", "content": RECEIPT_PHOTO_SYSTEM_PROMPT + "\nReturn ONLY valid JSON."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": data_uri}}
                ]
            }
        ]

        payload: Dict[str, Any] = {
            "model": self.vision_model,
            "messages": messages,
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }
        headers = {
            "Authorization": f"Bearer {self.api_key.strip()}",
            "HTTP-Referer": "https://github.com/Kush-Modi/Personal-System",
            "X-Title": "Personal-System",
            "Content-Type": "application/json",
        }

        logger.info(f"Dispatching receipt to OpenRouter vision model '{self.vision_model}'...")
        start_time = time.perf_counter()
        try:
            with httpx.Client(timeout=float(settings.ai_timeout_seconds)) as client:
                response = client.post(self.API_URL, json=payload, headers=headers)

            latency_ms = (time.perf_counter() - start_time) * 1000

            if response.status_code >= 400:
                raise AIModelUnavailableError(f"OpenRouter receipt vision failed (HTTP {response.status_code})")

            resp_data = response.json()
            choices = resp_data.get("choices", [])
            if not choices:
                raise AIServiceError("OpenRouter receipt vision returned empty choices.")

            text_output = choices[0].get("message", {}).get("content", "") or ""
            data = json.loads(text_output) if text_output else {}

            usage = resp_data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0) or 0
            completion_tokens = usage.get("completion_tokens", 0) or 0
            total_tokens = usage.get("total_tokens", 0) or (prompt_tokens + completion_tokens)

            items_raw = data.get("items", [])
            receipt_items = [
                ExtractedReceiptItem(
                    name=it.get("name", "Item"),
                    quantity=float(it.get("quantity", 1.0)),
                    unit_price=float(it["unit_price"]) if it.get("unit_price") else None,
                    total_price=float(it.get("total_price", 0.0)),
                )
                for it in items_raw
            ]

            return ReceiptExtractionResult(
                merchant=data.get("merchant"),
                date_str=data.get("date"),
                currency=data.get("currency", "INR"),
                items=receipt_items,
                subtotal=float(data["subtotal"]) if data.get("subtotal") else None,
                tax=float(data.get("tax", 0.0)),
                discount=float(data.get("discount", 0.0)),
                grand_total=float(data.get("grand_total", 0.0)),
                category=data.get("category", "Other"),
                notes=data.get("notes"),
                confidence=float(data.get("confidence", 0.70)),
                raw_response=text_output,
                provider=self.name,
                model=self.vision_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
            )

        except (AIAuthenticationError, AIRateLimitError, AIModelUnavailableError):
            raise
        except httpx.TimeoutException as te:
            raise AITimeoutError(f"OpenRouter receipt vision timed out: {te}") from te
        except Exception as e:
            logger.error(f"OpenRouter receipt vision error: {e}", exc_info=True)
            raise AIServiceError(f"OpenRouter receipt vision error: {e}") from e

