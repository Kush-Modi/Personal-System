"""Tests for database migrations and backward compatibility."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.database.migrations import get_applied_versions, run_migrations


class TestDatabaseMigrations(unittest.TestCase):
    """Test migration idempotency and safe upgrade of existing database."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_personal.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_migrations_on_fresh_db(self):
        """Verify migrations create all baseline, Phase 1, and Phase 2 tables on empty DB."""
        applied = run_migrations(self.db_path)
        self.assertGreaterEqual(applied, 3)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}

        self.assertIn("schema_version", tables)
        self.assertIn("weights", tables)
        self.assertIn("food", tables)
        self.assertIn("expenses", tables)
        self.assertIn("pending_items", tables)
        self.assertIn("edit_sessions", tables)

        # Check pending_items columns from migration 003
        cursor.execute("PRAGMA table_info(pending_items);")
        cols = {row[1] for row in cursor.fetchall()}
        self.assertIn("source", cols)
        self.assertIn("confidence", cols)
        self.assertIn("updated_at", cols)
        self.assertIn("expires_at", cols)
        self.assertIn("error_info", cols)

        conn.close()

    def test_migrations_idempotency(self):
        """Running migrations a second time should apply 0 new migrations."""
        first_run = run_migrations(self.db_path)
        self.assertGreater(first_run, 0)

        second_run = run_migrations(self.db_path)
        self.assertEqual(second_run, 0)

    def test_legacy_database_migration_preserves_data(self):
        """Verify that existing legacy tables and data from phone are 100% preserved."""
        # 1. Create legacy DB with existing data
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE weights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                weight REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE food (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                food_name TEXT NOT NULL,
                calories REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Insert legacy records
        cursor.execute("INSERT INTO weights (weight) VALUES (74.2);")
        cursor.execute("INSERT INTO food (food_name, calories) VALUES ('paneer wrap', 450);")
        cursor.execute("INSERT INTO expenses (amount, category, description) VALUES (150, 'Groceries', 'Milk');")
        conn.commit()
        conn.close()

        # 2. Run new migration runner
        applied = run_migrations(self.db_path)
        self.assertGreater(applied, 0)

        # 3. Assert all legacy data is untouched
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT weight FROM weights;")
        weight_row = cursor.fetchone()
        self.assertIsNotNone(weight_row)
        self.assertAlmostEqual(weight_row[0], 74.2)

        cursor.execute("SELECT food_name, calories FROM food;")
        food_row = cursor.fetchone()
        self.assertIsNotNone(food_row)
        self.assertEqual(food_row[0], "paneer wrap")
        self.assertAlmostEqual(food_row[1], 450)

        cursor.execute("SELECT amount, category FROM expenses;")
        expense_row = cursor.fetchone()
        self.assertIsNotNone(expense_row)
        self.assertAlmostEqual(expense_row[0], 150)
        self.assertEqual(expense_row[1], "Groceries")

        # Verify pending_items, edit_sessions, and schema_version now exist alongside legacy tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        self.assertIn("pending_items", tables)
        self.assertIn("edit_sessions", tables)
        self.assertIn("schema_version", tables)
        conn.close()


if __name__ == "__main__":
    unittest.main()
