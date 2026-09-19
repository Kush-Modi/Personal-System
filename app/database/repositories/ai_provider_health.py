"""Repository for tracking AI provider health, error rates, and circuit breaker cooldowns."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union

from app.database.repositories.base import BaseRepository


@dataclass
class AIProviderHealthRecord:
    provider: str
    consecutive_failures: int = 0
    circuit_open_until: Optional[str] = None
    last_success_at: Optional[str] = None
    last_failure_at: Optional[str] = None
    last_error: Optional[str] = None
    total_requests: int = 0
    total_errors: int = 0
    updated_at: Optional[str] = None


class AIProviderHealthRepository(BaseRepository):
    """Database operations for managing AI provider health and circuit breaking."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        super().__init__(db_path)

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> AIProviderHealthRecord:
        return AIProviderHealthRecord(
            provider=row["provider"],
            consecutive_failures=int(row["consecutive_failures"] or 0),
            circuit_open_until=row["circuit_open_until"],
            last_success_at=row["last_success_at"],
            last_failure_at=row["last_failure_at"],
            last_error=row["last_error"],
            total_requests=int(row["total_requests"] or 0),
            total_errors=int(row["total_errors"] or 0),
            updated_at=row["updated_at"],
        )

    def get_health(self, provider: str) -> Optional[AIProviderHealthRecord]:
        """Fetch health stats for a given provider."""
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ai_provider_health WHERE provider = ?;", (provider.lower(),))
            row = cursor.fetchone()
            return self._row_to_record(row) if row else None

    def record_success(self, provider: str) -> None:
        """Record a successful call to a provider, resetting failure counts and clearing circuit."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        p_name = provider.lower()

        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ai_provider_health (
                    provider, consecutive_failures, circuit_open_until,
                    last_success_at, total_requests, total_errors, updated_at
                ) VALUES (?, 0, NULL, ?, 1, 0, ?)
                ON CONFLICT(provider) DO UPDATE SET
                    consecutive_failures = 0,
                    circuit_open_until = NULL,
                    last_success_at = excluded.last_success_at,
                    total_requests = total_requests + 1,
                    updated_at = excluded.updated_at;
            """, (p_name, now_str, now_str))

    def record_failure(
        self,
        provider: str,
        error_msg: str,
        cooldown_seconds: int = 300,
        consecutive_threshold: int = 3
    ) -> None:
        """Record a failure for a provider. If consecutive failures exceed threshold, open circuit breaker."""
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        p_name = provider.lower()

        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT consecutive_failures, total_requests, total_errors FROM ai_provider_health WHERE provider = ?;", (p_name,))
            row = cursor.fetchone()

            if row:
                failures = (row["consecutive_failures"] or 0) + 1
                circuit_until = None
                if failures >= consecutive_threshold:
                    circuit_until = (now + timedelta(seconds=cooldown_seconds)).strftime("%Y-%m-%d %H:%M:%S")

                cursor.execute("""
                    UPDATE ai_provider_health
                    SET consecutive_failures = ?,
                        circuit_open_until = COALESCE(?, circuit_open_until),
                        last_failure_at = ?,
                        last_error = ?,
                        total_requests = total_requests + 1,
                        total_errors = total_errors + 1,
                        updated_at = ?
                    WHERE provider = ?;
                """, (failures, circuit_until, now_str, str(error_msg)[:255], now_str, p_name))
            else:
                circuit_until = None
                if consecutive_threshold <= 1:
                    circuit_until = (now + timedelta(seconds=cooldown_seconds)).strftime("%Y-%m-%d %H:%M:%S")

                cursor.execute("""
                    INSERT INTO ai_provider_health (
                        provider, consecutive_failures, circuit_open_until,
                        last_failure_at, last_error, total_requests, total_errors, updated_at
                    ) VALUES (?, 1, ?, ?, ?, 1, 1, ?);
                """, (p_name, circuit_until, now_str, str(error_msg)[:255], now_str))

    def is_circuit_open(self, provider: str) -> bool:
        """Check if provider circuit breaker is currently open (in cooldown)."""
        health = self.get_health(provider)
        if not health or not health.circuit_open_until:
            return False

        try:
            open_until = datetime.strptime(health.circuit_open_until, "%Y-%m-%d %H:%M:%S")
            return datetime.now() < open_until
        except Exception:
            return False

    def get_all_health(self) -> Dict[str, AIProviderHealthRecord]:
        """Get health dictionary for all tracked providers."""
        results: Dict[str, AIProviderHealthRecord] = {}
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ai_provider_health;")
            for row in cursor.fetchall():
                rec = self._row_to_record(row)
                results[rec.provider] = rec
        return results
