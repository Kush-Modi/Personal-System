"""Groq AI provider implementation for high-speed inference and fallback perception."""

import base64
import json
import mimetypes
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

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

logger = get_logger("ai.groq")


class GroqProvider(AIProvider):
    """Groq inference provider implementation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        vision_model: Optional[str] = None
    ):
        self.api_key = api_key if api_key is not None else settings.groq_api_key
        self.default_model = default_model or settings.groq_default_model
        self.vision_model = vision_model or settings.groq_vision_model
        self._client = None

    @property
    def name(self) -> str:
        return "groq"

    def is_available(self) -> bool:
        """Check if Groq API key is configured."""
        return bool(self.api_key and len(self.api_key.strip()) > 0)

    def supports_vision(self) -> bool:
        """Groq vision is enabled only if configured in settings."""
        return settings.groq_vision_fallback_enabled

    def _get_client(self):
        """Lazy initialization of Groq client."""
        if not self.is_available():
            raise AIAuthenticationError("GROQ_API_KEY is not configured or is empty.")

        if self._client is None:
            try:
                from groq import Groq
                self._client = Groq(api_key=self.api_key)
            except ImportError as e:
                raise AIServiceError("groq package is not installed.") from e
            except Exception as e:
                raise AIServiceError(f"Failed to initialize Groq client: {e}") from e

        return self._client

    def generate_structured(self, request: AIRequest) -> AIResponse:
        """Execute structured generation with Groq."""
        client = self._get_client()

        model_id = request.model or self.default_model
        if request.image_path:
            model_id = self.vision_model

        start_time = time.perf_counter()
        messages = []

        # System message
        if request.system_instruction:
            system_msg = request.system_instruction
            if request.json_mode:
                system_msg += "\nYou MUST return a valid JSON object matching the requested structure."
            messages.append({"role": "system", "content": system_msg})

        # User content
        if request.image_path:
            img_path = Path(request.image_path)
            if not img_path.exists():
                raise AIServiceError(f"Image not found at path: {img_path}")

            mime_type = mimetypes.guess_type(str(img_path))[0] or "image/jpeg"
            with open(img_path, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("utf-8")

            data_uri = f"data:{mime_type};base64,{b64_data}"
            user_content = [
                {"type": "text", "text": request.prompt},
                {"type": "image_url", "image_url": {"url": data_uri}}
            ]
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": "user", "content": request.prompt})

        kwargs: Dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": request.temperature,
        }

        if request.json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            logger.info(f"Calling Groq model '{model_id}' (task: {request.task_type})...")
            completion = client.chat.completions.create(**kwargs)
            latency_ms = (time.perf_counter() - start_time) * 1000

            text_output = completion.choices[0].message.content or ""
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0

            if hasattr(completion, "usage") and completion.usage:
                prompt_tokens = completion.usage.prompt_tokens or 0
                completion_tokens = completion.usage.completion_tokens or 0
                total_tokens = completion.usage.total_tokens or (prompt_tokens + completion_tokens)

            structured_data = None
            if request.json_mode and text_output:
                try:
                    structured_data = json.loads(text_output)
                except json.JSONDecodeError as jde:
                    logger.warning(f"Groq output was not valid JSON: {text_output[:200]}")
                    raise AIParseError(f"Failed to parse Groq JSON response: {jde}") from jde

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

        except (AIParseError, AIAuthenticationError):
            raise
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            err_str = str(e).lower()
            logger.error(f"Groq generation error: {e}", exc_info=True)

            if "rate_limit" in err_str or "429" in err_str:
                raise AIRateLimitError(f"Groq rate limit exceeded: {e}") from e
            elif "authentication" in err_str or "401" in err_str or "invalid_api_key" in err_str:
                raise AIAuthenticationError(f"Groq authentication failed: {e}") from e
            elif "503" in err_str or "service_unavailable" in err_str or "connection" in err_str:
                raise AIModelUnavailableError(f"Groq service unavailable: {e}") from e
            elif "timeout" in err_str or "timed out" in err_str:
                raise AITimeoutError(f"Groq request timed out: {e}") from e
            else:
                raise AIServiceError(f"Groq error: {e}") from e

    def extract_food_from_image(
        self,
        image_path: Union[str, Path],
        context_prompt: str = "",
        memory_context: str = ""
    ) -> FoodExtractionResult:
        """Extract structured food items from an image via Groq vision."""
        if not self.is_available():
            raise AIServiceError("GROQ_API_KEY is not configured.")
        if not self.supports_vision():
            raise AIServiceError("Groq vision fallback is disabled in settings.")

        prompt = build_food_photo_prompt(caption=context_prompt, memory_context=memory_context)
        req = AIRequest(
            task_type=AITaskType.FOOD_PHOTO,
            prompt=prompt,
            system_instruction=FOOD_PHOTO_SYSTEM_PROMPT,
            image_path=image_path,
            model=self.vision_model,
            json_mode=True,
        )

        res = self.generate_structured(req)
        data = res.structured_data or {}
        items_raw = data.get("items", [])

        extracted_items = [
            ExtractedFoodItem(
                food_name=item.get("food_name", "Unknown Food"),
                estimated_calories=float(item.get("estimated_calories", 0.0)),
                confidence=float(item.get("confidence", 0.75)),
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

    def extract_food_from_text(
        self,
        text: str,
        memory_context: str = ""
    ) -> FoodExtractionResult:
        """Extract structured food items from natural text via Groq."""
        if not self.is_available():
            raise AIServiceError("GROQ_API_KEY is not configured.")

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
                confidence=float(item.get("confidence", 0.85)),
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
        """Placeholder receipt extraction."""
        if not self.is_available():
            raise AIServiceError("GROQ_API_KEY is not configured.")

        return ReceiptExtractionResult(
            merchant="Unspecified",
            total_amount=0.0,
            category="General",
            items=[],
            raw_response="Receipt extraction not active.",
            provider=self.name,
            model=self.default_model,
        )
