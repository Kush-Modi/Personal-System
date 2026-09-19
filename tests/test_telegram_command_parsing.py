"""Tests for Telegram date parsing and helper logic."""

import unittest
from datetime import date, datetime, timedelta

from app.telegram.parsing import date_error, parse_date, today_date


class TestTelegramCommandHelpers(unittest.TestCase):
    """Test date parsing and validation helper functions."""

    def test_parse_date_keywords(self):
        today = today_date()
        yesterday = today - timedelta(days=1)

        # Empty / None
        d, label = parse_date(None)
        self.assertEqual(d, today)
        self.assertEqual(label, "Today")

        d, label = parse_date("")
        self.assertEqual(d, today)
        self.assertEqual(label, "Today")

        # Today
        d, label = parse_date("today")
        self.assertEqual(d, today)
        self.assertEqual(label, "Today")

        # Yesterday
        d, label = parse_date("yesterday")
        self.assertEqual(d, yesterday)
        self.assertEqual(label, "Yesterday")

    def test_parse_date_iso(self):
        d, label = parse_date("2026-09-01")
        self.assertEqual(d, date(2026, 9, 1))
        self.assertEqual(label, "01 Sep 2026")

    def test_parse_date_invalid(self):
        d, label = parse_date("invalid-date")
        self.assertIsNone(d)
        self.assertIsNone(label)

    def test_date_error_message(self):
        msg = date_error()
        self.assertIn("Invalid date", msg)
        self.assertIn("YYYY-MM-DD", msg)


if __name__ == "__main__":
    unittest.main()
