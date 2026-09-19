"""Benchmark script to measure latency and token throughput across available AI providers."""

import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.ai.gemini_provider import GeminiProvider
from app.ai.groq_provider import GroqProvider
from app.ai.openrouter_provider import OpenRouterProvider
from app.core.config import settings

BENCHMARK_PROMPTS = [
    "2 whole wheat rotis with 1 bowl moong dal",
    "1 scoop whey protein in 250ml milk and 1 medium banana",
    "Paneer butter masala 1 bowl with 2 butter naans and salad",
]


def run_benchmark():
    print("=" * 65)
    print("AI PROVIDER LATENCY & PERFORMANCE BENCHMARK")
    print("=" * 65)

    providers = []
    gemini = GeminiProvider()
    if gemini.is_available():
        providers.append(("Gemini (2.5-flash)", gemini))

    groq = GroqProvider()
    if groq.is_available():
        providers.append((f"Groq ({settings.groq_default_model})", groq))

    openrouter = OpenRouterProvider()
    if openrouter.is_available():
        providers.append((f"OpenRouter ({settings.openrouter_default_model})", openrouter))

    if not providers:
        print("No AI providers configured in .env.")
        return

    for prov_name, provider in providers:
        print(f"\nEvaluating {prov_name}...")
        latencies = []
        for p in BENCHMARK_PROMPTS:
            try:
                t0 = time.perf_counter()
                res = provider.extract_food_from_text(p)
                elapsed = (time.perf_counter() - t0) * 1000
                latencies.append(elapsed)
                print(f"  • \"{p[:35]}...\" -> {elapsed:.1f}ms ({len(res.items)} items, {sum(i.estimated_calories for i in res.items):.0f} kcal)")
            except Exception as e:
                print(f"  • Error: {e}")

        if latencies:
            avg_ms = sum(latencies) / len(latencies)
            min_ms = min(latencies)
            max_ms = max(latencies)
            print(f"  📊 Summary: Avg: {avg_ms:.1f}ms | Min: {min_ms:.1f}ms | Max: {max_ms:.1f}ms")

    print("\n" + "=" * 65)


if __name__ == "__main__":
    run_benchmark()
