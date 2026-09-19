"""Manual live verification script for testing configured AI providers without consuming test quota."""

import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.ai.budget import AIBudgetManager
from app.ai.gemini_provider import GeminiProvider
from app.ai.groq_provider import GroqProvider
from app.ai.openrouter_provider import OpenRouterProvider
from app.ai.router import AIRouter
from app.ai.schemas import AIRequest, AITaskType
from app.ai.service import AIService
from app.core.config import settings
from app.database.migrations import run_migrations


def test_live_providers():
    print("=" * 60)
    print("PERSONAL-SYSTEM: LIVE AI PROVIDER VERIFICATION")
    print("=" * 60)
    print(f"Timezone: {settings.timezone}")
    print(f"Gemini Key: {'CONFIGURED' if settings.gemini_api_key else 'NOT CONFIGURED'}")
    print(f"Groq Key: {'CONFIGURED' if settings.groq_api_key else 'NOT CONFIGURED'}")
    print(f"OpenRouter Key: {'CONFIGURED' if settings.openrouter_api_key else 'NOT CONFIGURED'}")
    print("-" * 60)

    # 1. Run migrations to ensure telemetry and memory tables exist
    run_migrations()

    # 2. Test Gemini Provider
    gemini = GeminiProvider()
    if gemini.is_available():
        print("\n🔹 Testing Gemini Provider (Text Extraction)...")
        try:
            t0 = time.time()
            res = gemini.extract_food_from_text("2 boiled eggs and 1 slice brown bread")
            elapsed = time.time() - t0
            print(f"  ✅ Success in {elapsed:.2f}s | Provider: {res.provider} | Model: {res.model}")
            for item in res.items:
                print(f"     - {item.food_name}: {item.estimated_calories:.0f} kcal (Confidence: {item.confidence})")
        except Exception as e:
            print(f"  ❌ Gemini Error: {e}")
    else:
        print("\n🔹 Gemini Provider: Skipped (no key)")

    # 3. Test Groq Provider
    groq = GroqProvider()
    if groq.is_available():
        print(f"\n🔹 Testing Groq Provider (Model: {settings.groq_default_model})...")
        try:
            t0 = time.time()
            res = groq.extract_food_from_text("1 bowl dal tadka and 2 rotis")
            elapsed = time.time() - t0
            print(f"  ✅ Success in {elapsed:.2f}s | Provider: {res.provider} | Model: {res.model}")
            for item in res.items:
                print(f"     - {item.food_name}: {item.estimated_calories:.0f} kcal (Confidence: {item.confidence})")
        except Exception as e:
            print(f"  ❌ Groq Error: {e}")
    else:
        print("\n🔹 Groq Provider: Skipped (no key)")

    # 4. Test OpenRouter Provider
    openrouter = OpenRouterProvider()
    if openrouter.is_available():
        print(f"\n🔹 Testing OpenRouter Provider (Model: {settings.openrouter_default_model})...")
        try:
            t0 = time.time()
            res = openrouter.extract_food_from_text("1 cup black coffee with 1 tsp sugar")
            elapsed = time.time() - t0
            print(f"  ✅ Success in {elapsed:.2f}s | Provider: {res.provider} | Model: {res.model}")
            for item in res.items:
                print(f"     - {item.food_name}: {item.estimated_calories:.0f} kcal (Confidence: {item.confidence})")
        except Exception as e:
            print(f"  ❌ OpenRouter Error: {e}")
    else:
        print("\n🔹 OpenRouter Provider: Skipped (no key)")

    # 5. Check AIService and Usage Status
    print("\n" + "=" * 60)
    ai_service = AIService()
    status = ai_service.get_ai_usage_status()
    b = status["budget"]
    print("📊 AI Budget Summary:")
    print(f"  Date: {b['date']}")
    print(f"  Requests Used: {b['requests_used']} / {b['requests_limit']}")
    print(f"  Tokens Used: {b['tokens_used']} / {b['tokens_limit']}")
    print("=" * 60)


if __name__ == "__main__":
    test_live_providers()
