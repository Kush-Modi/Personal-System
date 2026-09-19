"""Tests for AI budget manager, daily limits, and guardrails."""

import tempfile
import unittest
from pathlib import Path

from app.ai.budget import AIBudgetManager
from app.core.exceptions import AIBudgetExceededError
from app.database.migrations import run_migrations
from app.database.repositories.ai_request import AIRequestRepository


class TestAIBudget(unittest.TestCase):
    """Test suite for AI daily budget accounting and limits."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_budget.db"
        run_migrations(self.db_path)
        self.repo = AIRequestRepository(self.db_path)
        self.budget_manager = AIBudgetManager(
            ai_request_repo=self.repo,
            daily_request_limit=3,
            daily_token_limit=1000,
            tz_name="Asia/Kolkata"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_budget_consumption_and_guardrails(self):
        # 0 requests initially
        status = self.budget_manager.get_budget_status()
        self.assertEqual(status["requests_used"], 0)
        self.assertEqual(status["tokens_used"], 0)
        self.assertFalse(status["is_exhausted"])

        # Check passes with no requests
        self.budget_manager.check_and_assert_budget(estimated_tokens=200)

        # Log 2 requests
        self.repo.log_request(
            request_id="req-1",
            task_type="food_text",
            provider="gemini",
            model="gemini-2.5-flash-lite",
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
            status="SUCCESS"
        )
        self.repo.log_request(
            request_id="req-2",
            task_type="food_text",
            provider="groq",
            model="openai/gpt-oss-20b",
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
            status="SUCCESS"
        )

        status = self.budget_manager.get_budget_status()
        self.assertEqual(status["requests_used"], 2)
        self.assertEqual(status["tokens_used"], 600)
        self.assertFalse(status["is_exhausted"])

        # 3rd request reaches limit of 3
        self.repo.log_request(
            request_id="req-3",
            task_type="food_text",
            provider="gemini",
            model="gemini-2.5-flash-lite",
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
            status="SUCCESS"
        )

        status = self.budget_manager.get_budget_status()
        self.assertEqual(status["requests_used"], 3)
        self.assertTrue(status["is_exhausted"])

        # Next check raises AIBudgetExceededError
        with self.assertRaises(AIBudgetExceededError):
            self.budget_manager.check_and_assert_budget()


if __name__ == "__main__":
    unittest.main()
