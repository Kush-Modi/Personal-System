"""Google Gemini AI perception provider using modern google-genai SDK."""

import json
import mimetypes
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.ai.prompts import (
    FOOD_EXTRACTION_JSON_SCHEMA,
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
    parse_extracted_food_item,
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

logger = get_logger("ai.gemini")


class GeminiProvider(AIProvider):
    """Google Gemini AI provider implementation using modern google-genai client."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None
    ):
        self.api_key = api_key if api_key is not None else settings.gemini_api_key
        self.default_model = model_name or settings.ai_default_model
        self._client = None

    @property
    def name(self) -> str:
        return "gemini"

    def is_available(self) -> bool:
        """Check if Gemini API key is configured."""
        return bool(self.api_key and len(self.api_key.strip()) > 0)

    def supports_vision(self) -> bool:
        return True

    def _get_client(self):
        """Lazy initialization of google-genai client."""
        if not self.is_available():
            raise AIAuthenticationError("GEMINI_API_KEY is not configured or is empty.")

        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except ImportError as e:
                raise AIServiceError("google-genai package is not installed.") from e
            except Exception as e:
                raise AIServiceError(f"Failed to initialize Gemini client: {e}") from e

        return self._client

    def generate_structured(self, request: AIRequest) -> AIResponse:
        """Execute structured generation with Gemini."""
        client = self._get_client()
        from google.genai import types

        model_id = request.model or self.default_model
        start_time = time.perf_counter()

        contents = []

        # If an image is provided, load and attach
        if request.image_path:
            img_path = Path(request.image_path)
            if not img_path.exists():
                raise AIServiceError(f"Image not found at path: {img_path}")

            mime_type = mimetypes.guess_type(str(img_path))[0] or "image/jpeg"
            with open(img_path, "rb") as f:
                image_bytes = f.read()

            image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            contents.append(image_part)

        contents.append(request.prompt)

        config_kwargs: Dict[str, Any] = {
            "temperature": request.temperature,
        }
        if request.system_instruction:
            config_kwargs["system_instruction"] = request.system_instruction

        if request.json_mode:
            config_kwargs["response_mime_type"] = "application/json"
            if request.response_schema:
                config_kwargs["response_schema"] = request.response_schema

        config = types.GenerateContentConfig(**config_kwargs)

        try:
            logger.info(f"Calling Gemini model '{model_id}' (task: {request.task_type})...")
            response = client.models.generate_content(
                model=model_id,
                contents=contents,
                config=config,
            )
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Safely extract text without calling response.text directly.
            # When the model returns a blocked/empty candidate, response.text
            # raises "model output must contain either output text or tool calls".
            # Instead we walk candidates/parts manually.
            text_output = ""
            finish_reason = None
            if response.candidates:
                candidate = response.candidates[0]
                finish_reason = getattr(candidate, "finish_reason", None)
                # finish_reason 1 == STOP (normal); anything else may be a block
                if finish_reason and str(finish_reason) not in ("1", "STOP", "FinishReason.STOP"):
                    logger.warning(
                        f"Gemini candidate finish_reason={finish_reason} — "
                        f"model may have been blocked or returned no content."
                    )
                # Walk parts to extract text safely
                if hasattr(candidate, "content") and candidate.content:
                    for part in getattr(candidate.content, "parts", []):
                        part_text = getattr(part, "text", None)
                        if part_text:
                            text_output += part_text

            if not text_output and request.json_mode:
                raise AIServiceError(
                    f"Gemini returned an empty response (finish_reason={finish_reason}). "
                    "The request may have been blocked by safety filters or the model "
                    "produced no output. Try rephrasing the prompt."
                )

            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0

            if hasattr(response, "usage_metadata") and response.usage_metadata:
                prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                completion_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
                total_tokens = getattr(response.usage_metadata, "total_token_count", 0) or (prompt_tokens + completion_tokens)

            structured_data = None
            if request.json_mode and text_output:
                try:
                    structured_data = json.loads(text_output)
                except json.JSONDecodeError as jde:
                    logger.warning(f"Gemini output was not valid JSON: {text_output[:200]}")
                    raise AIParseError(f"Failed to parse Gemini JSON response: {jde}") from jde

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

        except (AIParseError, AIAuthenticationError, AIServiceError):
            raise
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            err_str = str(e).lower()
            logger.error(f"Gemini generation error: {e}", exc_info=True)

            if "429" in err_str or "quota" in err_str or "rate limit" in err_str or "resource_exhausted" in err_str:
                raise AIRateLimitError(f"Gemini rate limit / quota exceeded: {e}") from e
            elif "401" in err_str or "403" in err_str or "api_key_invalid" in err_str or "unauthenticated" in err_str:
                raise AIAuthenticationError(f"Gemini authentication failed: {e}") from e
            elif "503" in err_str or "unavailable" in err_str or "500" in err_str:
                raise AIModelUnavailableError(f"Gemini service temporarily unavailable: {e}") from e
            elif "timeout" in err_str or "timed out" in err_str:
                raise AITimeoutError(f"Gemini request timed out: {e}") from e
            else:
                raise AIServiceError(f"Gemini error: {e}") from e

    def extract_food_from_image(
        self,
        image_path: Union[str, Path],
        context_prompt: str = "",
        memory_context: str = ""
    ) -> FoodExtractionResult:
        """Extract structured food items and estimated calories from an image."""
        if not self.is_available():
            raise AIServiceError("GEMINI_API_KEY is not configured.")

        prompt = build_food_photo_prompt(caption=context_prompt, memory_context=memory_context)
        req = AIRequest(
            task_type=AITaskType.FOOD_PHOTO,
            prompt=prompt,
            system_instruction=FOOD_PHOTO_SYSTEM_PROMPT,
            image_path=image_path,
            model=self.default_model,
            response_schema=FOOD_EXTRACTION_JSON_SCHEMA,
            json_mode=True,
        )

        res = self.generate_structured(req)
        data = res.structured_data or {}
        items_raw = data.get("items", [])
        if not isinstance(items_raw, list):
            items_raw = [items_raw] if isinstance(items_raw, dict) else []

        extracted_items = [
            parse_extracted_food_item(item, default_confidence=0.85)
            for item in items_raw
            if isinstance(item, dict)
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
        """Extract structured food items and estimated calories from natural text."""
        if not self.is_available():
            raise AIServiceError("GEMINI_API_KEY is not configured.")

        prompt = build_food_text_prompt(text=text, memory_context=memory_context)
        req = AIRequest(
            task_type=AITaskType.FOOD_TEXT,
            prompt=prompt,
            system_instruction=FOOD_TEXT_SYSTEM_PROMPT,
            model=self.default_model,
            response_schema=FOOD_EXTRACTION_JSON_SCHEMA,
            json_mode=True,
        )

        res = self.generate_structured(req)
        data = res.structured_data or {}
        items_raw = data.get("items", [])
        if not isinstance(items_raw, list):
            items_raw = [items_raw] if isinstance(items_raw, dict) else []

        extracted_items = [
            parse_extracted_food_item(item, default_confidence=0.9)
            for item in items_raw
            if isinstance(item, dict)
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
        """Extract receipt information from image."""
        if not self.is_available():
            raise AIServiceError("GEMINI_API_KEY is not configured.")

        return ReceiptExtractionResult(
            merchant="Unspecified",
            total_amount=0.0,
            category="General",
            items=[],
            raw_response="Receipt perception not yet activated.",
            provider=self.name,
            model=self.default_model,
        )
