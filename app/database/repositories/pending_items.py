"""Pending items repository for staged items and confirmation lifecycle."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from app.database.repositories.base import BaseRepository
from app.domain.models import PendingItem, PendingStatus


class PendingItemRepository(BaseRepository):
    """Repository handling persistence and queries for pending items."""

    def create(
        self,
        item_type: str,
        structured_payload: Dict[str, Any],
        raw_payload: Optional[str] = None,
        source: str = "UNKNOWN",
        confidence: float = 1.0,
        image_path: Optional[str] = None,
        user_notes: Optional[str] = None,
        expires_at: Optional[str] = None
    ) -> int:
        """Create a new pending item record."""
        payload_json = json.dumps(structured_payload)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO pending_items (
                    item_type, status, raw_payload, structured_payload,
                    source, confidence, image_path, user_notes,
                    created_at, updated_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    item_type.upper(),
                    PendingStatus.PENDING.value,
                    raw_payload,
                    payload_json,
                    source.upper(),
                    confidence,
                    image_path,
                    user_notes,
                    now_str,
                    now_str,
                    expires_at
                )
            )
            return cursor.lastrowid

    def get_by_id(self, item_id: int) -> Optional[PendingItem]:
        """Fetch pending item by primary key."""
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, item_type, status, raw_payload, structured_payload,
                       source, confidence, image_path, user_notes,
                       created_at, updated_at, expires_at, resolved_at, error_info
                FROM pending_items
                WHERE id = ?;
                """,
                (item_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity(row)

    def update_payload(
        self,
        item_id: int,
        structured_payload: Dict[str, Any],
        user_notes: Optional[str] = None
    ) -> bool:
        """Update structured payload and updated_at timestamp for a pending item."""
        payload_json = json.dumps(structured_payload)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.connection() as conn:
            cursor = conn.cursor()
            if user_notes is not None:
                cursor.execute(
                    """
                    UPDATE pending_items
                    SET structured_payload = ?, user_notes = ?, updated_at = ?
                    WHERE id = ? AND status = 'PENDING';
                    """,
                    (payload_json, user_notes, now_str, item_id)
                )
            else:
                cursor.execute(
                    """
                    UPDATE pending_items
                    SET structured_payload = ?, updated_at = ?
                    WHERE id = ? AND status = 'PENDING';
                    """,
                    (payload_json, now_str, item_id)
                )
            return cursor.rowcount > 0

    def update_status(
        self,
        item_id: int,
        status: str,
        error_info: Optional[str] = None
    ) -> bool:
        """Update status and resolved_at timestamp of a pending item."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE pending_items
                SET status = ?, resolved_at = ?, error_info = ?
                WHERE id = ?;
                """,
                (status.upper(), now_str, error_info, item_id)
            )
            return cursor.rowcount > 0

    def list_by_status(self, status: str = "PENDING") -> List[PendingItem]:
        """List all items matching given status, ordered oldest first."""
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, item_type, status, raw_payload, structured_payload,
                       source, confidence, image_path, user_notes,
                       created_at, updated_at, expires_at, resolved_at, error_info
                FROM pending_items
                WHERE status = ?
                ORDER BY id ASC;
                """,
                (status.upper(),)
            )
            return [self._row_to_entity(row) for row in cursor.fetchall()]

    def expire_overdue_items(self, current_time_iso: Optional[str] = None) -> int:
        """Set status to EXPIRED for all PENDING items whose expires_at is in the past."""
        now_str = current_time_iso or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE pending_items
                SET status = 'EXPIRED', resolved_at = ?
                WHERE status = 'PENDING' AND expires_at IS NOT NULL AND expires_at < ?;
                """,
                (now_str, now_str)
            )
            return cursor.rowcount

    def get_active_image_paths(self) -> Set[str]:
        """Get set of all image paths referenced by active PENDING items."""
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT image_path
                FROM pending_items
                WHERE status = 'PENDING' AND image_path IS NOT NULL AND image_path != '';
                """
            )
            return {row["image_path"] for row in cursor.fetchall() if row["image_path"]}

    def _row_to_entity(self, row: Any) -> PendingItem:
        """Helper to map sqlite3.Row to domain PendingItem."""
        return PendingItem(
            id=row["id"],
            item_type=row["item_type"],
            status=row["status"],
            raw_payload=row["raw_payload"],
            structured_payload=json.loads(row["structured_payload"]) if row["structured_payload"] else {},
            source=row["source"] if "source" in row.keys() and row["source"] else "UNKNOWN",
            confidence=float(row["confidence"]) if "confidence" in row.keys() and row["confidence"] is not None else 1.0,
            image_path=row["image_path"],
            user_notes=row["user_notes"],
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] if "updated_at" in row.keys() else None,
            expires_at=row["expires_at"] if "expires_at" in row.keys() else None,
            resolved_at=row["resolved_at"] if "resolved_at" in row.keys() else None,
            error_info=row["error_info"] if "error_info" in row.keys() else None,
        )
