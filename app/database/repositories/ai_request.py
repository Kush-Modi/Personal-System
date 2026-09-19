"""Repository for logging and aggregating AI telemetry and token usage."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.database.repositories.base import BaseRepository


@dataclass
class AIRequestRecord:
    id: int
    request_id: str
    task_type: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    status: str
    error_type: Optional[str]
    error_message: Optional[str]
    fallback_used: bool
    created_at: str


class AIRequestRepository(BaseRepository):
    """Database operations for AI request logs and usage accounting."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        super().__init__(db_path)

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> AIRequestRecord:
        return AIRequestRecord(
            id=row["id"],
            request_id=row["request_id"],
            task_type=row["task_type"],
            provider=row["provider"],
            model=row["model"],
            prompt_tokens=int(row["prompt_tokens"] or 0),
            completion_tokens=int(row["completion_tokens"] or 0),
            total_tokens=int(row["total_tokens"] or 0),
            latency_ms=float(row["latency_ms"] or 0.0),
            status=row["status"],
            error_type=row["error_type"],
            error_message=row["error_message"],
            fallback_used=bool(row["fallback_used"]),
            created_at=row["created_at"],
        )

    def log_request(
        self,
        request_id: str,
        task_type: str,
        provider: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        latency_ms: float = 0.0,
        status: str = "SUCCESS",
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        fallback_used: bool = False,
    ) -> int:
        """Record an AI invocation to the telemetry log."""
        if total_tokens == 0 and (prompt_tokens > 0 or completion_tokens > 0):
            total_tokens = prompt_tokens + completion_tokens

        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ai_requests (
                    request_id, task_type, provider, model,
                    prompt_tokens, completion_tokens, total_tokens,
                    latency_ms, status, error_type, error_message,
                    fallback_used, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                request_id,
                task_type,
                provider,
                model,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                latency_ms,
                status,
                error_type,
                error_message,
                1 if fallback_used else 0,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
            return cursor.lastrowid

    def get_daily_usage(self, date_str: str) -> Dict[str, Any]:
        """
        Aggregate usage telemetry for a specific date (YYYY-MM-DD).
        Counts total requests, successful requests, failed requests, and tokens.
        """
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    COUNT(*) as total_requests,
                    SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as success_requests,
                    SUM(CASE WHEN status != 'SUCCESS' THEN 1 ELSE 0 END) as failed_requests,
                    COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) as total_completion_tokens,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(AVG(latency_ms), 0.0) as avg_latency_ms
                FROM ai_requests
                WHERE created_at LIKE ?;
            """, (f"{date_str}%",))
            row = cursor.fetchone()

            # Provider breakdown
            cursor.execute("""
                SELECT
                    provider,
                    COUNT(*) as requests,
                    COALESCE(SUM(total_tokens), 0) as tokens
                FROM ai_requests
                WHERE created_at LIKE ?
                GROUP BY provider;
            """, (f"{date_str}%",))
            provider_breakdown = {
                r["provider"]: {"requests": r["requests"], "tokens": r["tokens"]}
                for r in cursor.fetchall()
            }

            return {
                "date": date_str,
                "total_requests": int(row["total_requests"] or 0),
                "success_requests": int(row["success_requests"] or 0),
                "failed_requests": int(row["failed_requests"] or 0),
                "total_prompt_tokens": int(row["total_prompt_tokens"] or 0),
                "total_completion_tokens": int(row["total_completion_tokens"] or 0),
                "total_tokens": int(row["total_tokens"] or 0),
                "avg_latency_ms": round(float(row["avg_latency_ms"] or 0.0), 1),
                "by_provider": provider_breakdown,
            }

    def get_recent_requests(self, limit: int = 15) -> List[AIRequestRecord]:
        """Fetch the most recent AI requests."""
        results: List[AIRequestRecord] = []
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM ai_requests ORDER BY id DESC LIMIT ?;",
                (limit,)
            )
            for row in cursor.fetchall():
                results.append(self._row_to_record(row))
        return results
