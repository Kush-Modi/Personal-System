"""Multi-provider AI router with capability matching, fallback chains, and circuit breaking."""

import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from app.ai.gemini_provider import GeminiProvider
from app.ai.groq_provider import GroqProvider
from app.ai.openrouter_provider import OpenRouterProvider
from app.ai.provider import AIProvider
from app.ai.schemas import (
    AIRequest,
    AIResponse,
    AITaskType,
    FoodExtractionResult,
    IntentResult,
    ReceiptExtractionResult,
)
from app.core.config import settings
from app.core.exceptions import (
    AIAuthenticationError,
    AIModelUnavailableError,
    AIRateLimitError,
    AIServiceError,
    AITimeoutError,
)
from app.core.logging import get_logger
from app.database.repositories.ai_provider_health import (
    AIProviderHealthRepository,
)

logger = get_logger("ai.router")


class AIRouter:
    """Intelligent router dispatching requests across configured AI providers with automatic fallback."""

    def __init__(
        self,
        providers: Optional[Dict[str, AIProvider]] = None,
        health_repo: Optional[AIProviderHealthRepository] = None,
    ):
        self.health_repo = health_repo or AIProviderHealthRepository()
        
        if providers is not None:
            self.providers = providers
        else:
            self.providers = {
                "gemini": GeminiProvider(),
                "groq": GroqProvider(),
                "openrouter": OpenRouterProvider(),
            }

    def get_provider(self, name: str) -> Optional[AIProvider]:
        """Fetch provider instance by name."""
        return self.providers.get(name.lower())

    def is_provider_usable(self, name: str) -> bool:
        """Check if provider is configured and circuit breaker is healthy."""
        p = self.get_provider(name)
        if not p or not p.is_available():
            return False
        if self.health_repo.is_circuit_open(name):
            logger.info(f"Provider '{name}' is currently in cooldown circuit breaker.")
            return False
        return True

    def route_food_photo(
        self,
        image_path: Union[str, Path],
        caption: str = "",
        memory_context: str = ""
    ) -> Tuple[FoodExtractionResult, bool]:
        """
        Route multimodal food photo analysis.
        Chain: Gemini → Groq vision → OpenRouter vision.
        Returns: (FoodExtractionResult, fallback_used).
        """
        # Always build full chain; each provider gates on supports_vision() + is_provider_usable()
        chain: List[str] = ["gemini", "groq", "openrouter"]

        errors = []
        for idx, provider_name in enumerate(chain):
            if not self.is_provider_usable(provider_name):
                logger.info(f"Skipping provider '{provider_name}' for photo (unavailable or circuit open).")
                continue

            provider = self.get_provider(provider_name)
            if not provider or not provider.supports_vision():
                logger.debug(f"Provider '{provider_name}' does not support vision, skipping.")
                continue

            try:
                logger.info(f"Dispatching food photo extraction to provider: {provider_name}")
                result = provider.extract_food_from_image(
                    image_path=image_path,
                    context_prompt=caption,
                    memory_context=memory_context
                )
                self.health_repo.record_success(provider_name)
                fallback_used = (idx > 0)
                return result, fallback_used

            except (AIRateLimitError, AIModelUnavailableError, AITimeoutError) as e:
                logger.warning(f"Provider '{provider_name}' failed with transient error: {e}")
                self.health_repo.record_failure(provider_name, str(e))
                errors.append(f"{provider_name}: {e}")
            except Exception as e:
                logger.error(f"Provider '{provider_name}' failed with unexpected error: {e}", exc_info=True)
                self.health_repo.record_failure(provider_name, str(e))
                errors.append(f"{provider_name}: {e}")

        raise AIServiceError(f"All vision providers failed for food photo: {'; '.join(errors)}")

    def route_food_text(
        self,
        text: str,
        memory_context: str = ""
    ) -> Tuple[FoodExtractionResult, bool]:
        """
        Route natural language food text analysis.
        Chain: Gemini (gemini-2.5-flash-lite) -> Groq (openai/gpt-oss-20b) -> OpenRouter (free).
        Returns: (FoodExtractionResult, fallback_used).
        """
        chain: List[str] = ["gemini", "groq", "openrouter"]
        errors = []

        for idx, provider_name in enumerate(chain):
            if not self.is_provider_usable(provider_name):
                logger.debug(f"Skipping provider '{provider_name}' for text (unavailable or circuit open).")
                continue

            provider = self.get_provider(provider_name)
            if not provider:
                continue

            try:
                logger.info(f"Dispatching food text extraction to provider: {provider_name}")
                result = provider.extract_food_from_text(
                    text=text,
                    memory_context=memory_context
                )
                self.health_repo.record_success(provider_name)
                fallback_used = (idx > 0)
                return result, fallback_used

            except (AIRateLimitError, AIModelUnavailableError, AITimeoutError) as e:
                logger.warning(f"Provider '{provider_name}' failed with transient error: {e}")
                self.health_repo.record_failure(provider_name, str(e))
                errors.append(f"{provider_name}: {e}")
            except Exception as e:
                logger.error(f"Provider '{provider_name}' failed with unexpected error: {e}", exc_info=True)
                self.health_repo.record_failure(provider_name, str(e))
                errors.append(f"{provider_name}: {e}")

        raise AIServiceError(f"All text providers failed for food text: {'; '.join(errors)}")

    def route_intent_action(
        self,
        text: str,
        current_date: Optional[str] = None,
        memory_context: str = ""
    ) -> Tuple[IntentResult, bool]:
        """
        Route natural language understanding and multi-domain extraction.
        Primary: Gemini (gemini-3.8-flash).
        Fallback: Groq (openai/gpt-oss-20b) -> OpenRouter.
        Returns: (IntentResult, fallback_used).
        """
        chain: List[str] = ["gemini", "groq", "openrouter"]
        errors = []

        for idx, provider_name in enumerate(chain):
            if not self.is_provider_usable(provider_name):
                logger.debug(f"Skipping provider '{provider_name}' for intent extraction (unavailable or circuit open).")
                continue

            provider = self.get_provider(provider_name)
            if not provider:
                continue

            try:
                logger.info(f"Dispatching intent extraction to provider: {provider_name}")
                result = provider.extract_intent_action(
                    text=text,
                    current_date=current_date,
                    memory_context=memory_context
                )
                self.health_repo.record_success(provider_name)
                fallback_used = (idx > 0)
                return result, fallback_used

            except (AIRateLimitError, AIModelUnavailableError, AITimeoutError) as e:
                logger.warning(f"Provider '{provider_name}' failed with transient error: {e}")
                self.health_repo.record_failure(provider_name, str(e))
                errors.append(f"{provider_name}: {e}")
            except Exception as e:
                logger.error(f"Provider '{provider_name}' failed with unexpected error: {e}", exc_info=True)
                self.health_repo.record_failure(provider_name, str(e))
                errors.append(f"{provider_name}: {e}")

        raise AIServiceError(f"All text providers failed for intent extraction: {'; '.join(errors)}")

    def route_receipt_photo(
        self,
        image_path: Union[str, Path],
        caption: str = ""
    ) -> Tuple[ReceiptExtractionResult, bool]:
        """
        Route receipt / bill photo analysis.
        Chain: Gemini → Groq vision → OpenRouter vision.
        Returns: (ReceiptExtractionResult, fallback_used).
        """
        chain: List[str] = ["gemini", "groq", "openrouter"]
        errors = []

        for idx, provider_name in enumerate(chain):
            if not self.is_provider_usable(provider_name):
                logger.info(f"Skipping provider '{provider_name}' for receipt (unavailable or circuit open).")
                continue

            provider = self.get_provider(provider_name)
            if not provider or not provider.supports_vision():
                logger.debug(f"Provider '{provider_name}' does not support vision, skipping receipt route.")
                continue

            try:
                logger.info(f"Dispatching receipt extraction to provider: {provider_name}")
                result = provider.extract_receipt_from_image(
                    image_path=image_path,
                    caption=caption
                )
                self.health_repo.record_success(provider_name)
                fallback_used = (idx > 0)
                return result, fallback_used

            except (AIRateLimitError, AIModelUnavailableError, AITimeoutError) as e:
                logger.warning(f"Provider '{provider_name}' failed with transient error: {e}")
                self.health_repo.record_failure(provider_name, str(e))
                errors.append(f"{provider_name}: {e}")
            except Exception as e:
                logger.error(f"Provider '{provider_name}' failed with unexpected error: {e}", exc_info=True)
                self.health_repo.record_failure(provider_name, str(e))
                errors.append(f"{provider_name}: {e}")

        raise AIServiceError(f"All vision providers failed for receipt photo: {'; '.join(errors)}")

