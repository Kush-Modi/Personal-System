"""Tests for configuration management."""

import unittest
from app.core.config import Settings


class TestConfig(unittest.TestCase):
    """Test configuration loading, validation, and secret masking."""

    def test_default_settings(self):
        settings = Settings()
        self.assertEqual(settings.image_retention_days, 30)
        self.assertEqual(settings.daily_ai_request_limit, 50)
        self.assertIn("personal.db", str(settings.database_path))

    def test_safe_dict_masks_secrets(self):
        settings = Settings(
            telegram_bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
            gemini_api_key="AIzaSyA1234567890abcdefghijklmnopqrst"
        )
        safe = settings.safe_dict()
        self.assertTrue(safe["telegram_bot_token"].startswith("1234..."))
        self.assertTrue(safe["telegram_bot_token"].endswith("wxyz"))
        self.assertNotIn("ABCdefGHI", safe["telegram_bot_token"])

        self.assertTrue(safe["gemini_api_key"].startswith("AIza..."))
        self.assertTrue(safe["gemini_api_key"].endswith("qrst"))

    def test_safe_dict_with_empty_secrets(self):
        settings = Settings(telegram_bot_token="", gemini_api_key=None)
        safe = settings.safe_dict()
        self.assertEqual(safe["telegram_bot_token"], "NOT_SET")
        self.assertEqual(safe["gemini_api_key"], "NOT_SET")


if __name__ == "__main__":
    unittest.main()
