"""Task repository for persistent task entity operations."""

from dataclasses import dataclass
from typing import List, Optional

from app.database.repositories.base import BaseRepository


@dataclass
class TaskRecord:
    id: int
    user_id: int
    title: str
    description: Optional[str]
    status: str  # PENDING, COMPLETED, CANCELLED
    priority: str  # LOW, MEDIUM, HIGH
    due_at: Optional[str]
    created_at: str
    updated_at: str
    completed_at: Optional[str]
    source: str


class TaskRepository(BaseRepository):
    """Repository handling all task CRUD database operations."""

    def create(
        self,
        title: str,
        user_id: int = 0,
        description: Optional[str] = None,
        priority: str = "MEDIUM",
        due_at: Optional[str] = None,
        source: str = "NATURAL_LANGUAGE"
    ) -> int:
        """Insert a new task."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO tasks (user_id, title, description, status, priority, due_at, source)
                VALUES (?, ?, ?, 'PENDING', ?, ?, ?);
                """,
                (user_id, title, description, priority.upper(), due_at, source)
            )
            return cursor.lastrowid

    def get_by_id(self, task_id: int) -> Optional[TaskRecord]:
        """Fetch single task by ID."""
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, user_id, title, description, status, priority, due_at, created_at, updated_at, completed_at, source
                FROM tasks WHERE id = ?;
                """,
                (task_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return TaskRecord(
                id=row["id"],
                user_id=row["user_id"],
                title=row["title"],
                description=row["description"],
                status=row["status"],
                priority=row["priority"],
                due_at=row["due_at"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                completed_at=row["completed_at"],
                source=row["source"]
            )

    def list_by_status(self, status: str = "PENDING", user_id: int = 0, limit: int = 50) -> List[TaskRecord]:
        """List tasks by status."""
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, user_id, title, description, status, priority, due_at, created_at, updated_at, completed_at, source
                FROM tasks
                WHERE status = ?
                ORDER BY CASE WHEN due_at IS NULL THEN 1 ELSE 0 END, due_at ASC, id DESC
                LIMIT ?;
                """,
                (status.upper(), limit)
            )
            return [
                TaskRecord(
                    id=row["id"],
                    user_id=row["user_id"],
                    title=row["title"],
                    description=row["description"],
                    status=row["status"],
                    priority=row["priority"],
                    due_at=row["due_at"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    completed_at=row["completed_at"],
                    source=row["source"]
                )
                for row in cursor.fetchall()
            ]

    def mark_completed(self, task_id: int) -> bool:
        """Mark task as COMPLETED."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE tasks
                SET status = 'COMPLETED', completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (task_id,)
            )
            return cursor.rowcount > 0

    def mark_cancelled(self, task_id: int) -> bool:
        """Mark task as CANCELLED."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE tasks
                SET status = 'CANCELLED', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (task_id,)
            )
            return cursor.rowcount > 0

    def update_task(self, task_id: int, title: Optional[str] = None, due_at: Optional[str] = None, priority: Optional[str] = None) -> bool:
        """Update fields of a task."""
        updates = []
        params = []
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if due_at is not None:
            updates.append("due_at = ?")
            params.append(due_at)
        if priority is not None:
            updates.append("priority = ?")
            params.append(priority.upper())
        if not updates:
            return False

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(task_id)

        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?;",
                params
            )
            return cursor.rowcount > 0

    def find_by_title_fuzzy(self, query: str, status: str = "PENDING") -> List[TaskRecord]:
        """Search tasks by title keyword match."""
        pattern = f"%{query.strip()}%"
        with self.connection(commit=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, user_id, title, description, status, priority, due_at, created_at, updated_at, completed_at, source
                FROM tasks
                WHERE status = ? AND title LIKE ?
                ORDER BY id DESC LIMIT 10;
                """,
                (status.upper(), pattern)
            )
            return [
                TaskRecord(
                    id=row["id"],
                    user_id=row["user_id"],
                    title=row["title"],
                    description=row["description"],
                    status=row["status"],
                    priority=row["priority"],
                    due_at=row["due_at"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    completed_at=row["completed_at"],
                    source=row["source"]
                )
                for row in cursor.fetchall()
            ]
