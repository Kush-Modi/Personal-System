"""Pending items repository for AI extraction confirmation workflow."""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database.repositories.base import BaseRepository


@dataclass
class PendingItem:
    id: int
    item_type: str
    status: str
    raw_payload: Optional[str]
    structured_payload: Dict[str, Any]
    image_path: Optional[str]
    user_notes: Optional[str]
    created_at: str
    resolved_at: Optional[str]


class PendingItemRepository(BaseRepository):
    """Repository handling staging of unconfirmed items (e.g. from future AI perception)."""

    def create(
        self,
        item_type: str,
        structured_payload: Dict[str, Any],
        raw_payload: Optional[str] = None,
        image_path: Optional[str] = None,
        user_notes: Optional[str] = None
    ) -> int:
        """Create a new pending item record."""
        payload_json = json.dumps(structured_payload)
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO pending_items (
                    item_type, status, raw_payload, structured_payload, image_path, user_notes
                ) VALUES (?, 'PENDING', ?, ?, ?, ?);
                """,
                (item_type, raw_payload, payload_json, image_path, user_notes)
            )
            return cursor.lastrowid

    def get_by_id(self, item_id: int) -> Optional[PendingItem]:
        """Fetch pending item by ID."""
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, item_type, status, raw_payload, structured_payload,
                       image_path, user_notes, created_at, resolved_at
                FROM pending_items
                WHERE id = ?;
                """,
                (item_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return PendingItem(
                id=row["id"],
                item_type=row["item_type"],
                status=row["status"],
                raw_payload=row["raw_payload"],
                structured_payload=json.loads(row["structured_payload"]),
                image_path=row["image_path"],
                user_notes=row["user_notes"],
                created_at=row["created_at"],
                resolved_at=row["resolved_at"]
            )

    def update_status(self, item_id: int, status: str) -> bool:
        """Update status of a pending item (e.g. CONFIRMED, REJECTED, EXPIRED)."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE pending_items
                SET status = ?, resolved_at = ?
                WHERE id = ?;
                """,
                (status, now_str, item_id)
            )
            return cursor.rowcount > 0

    def list_by_status(self, status: str = "PENDING") -> List[PendingItem]:
        """List items matching given status."""
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, item_type, status, raw_payload, structured_payload,
                       image_path, user_notes, created_at, resolved_at
                FROM pending_items
                WHERE status = ?
                ORDER BY id ASC;
                """,
                (status,)
            )
            return [
                PendingItem(
                    id=row["id"],
                    item_type=row["item_type"],
                    status=row["status"],
                    raw_payload=row["raw_payload"],
                    structured_payload=json.loads(row["structured_payload"]),
                    image_path=row["image_path"],
                    user_notes=row["user_notes"],
                    created_at=row["created_at"],
                    resolved_at=row["resolved_at"]
                )
                for row in cursor.fetchall()
            ]
