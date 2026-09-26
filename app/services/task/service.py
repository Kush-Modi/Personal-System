"""Task domain service for managing to-dos, priorities, deadlines, and state transitions."""

from typing import Any, Dict, List, Optional

from app.core.exceptions import DomainValidationError, NotFoundError
from app.core.logging import get_logger
from app.database.repositories.task import TaskRecord, TaskRepository

logger = get_logger("services.task")


class TaskService:
    """Domain service managing task creation, retrieval, updates, and completion."""

    def __init__(self, task_repo: Optional[TaskRepository] = None):
        self.repo = task_repo or TaskRepository()

    def create_task(
        self,
        title: str,
        user_id: int = 0,
        description: Optional[str] = None,
        priority: str = "MEDIUM",
        due_at: Optional[str] = None,
        source: str = "NATURAL_LANGUAGE"
    ) -> TaskRecord:
        """Create and store a new task."""
        clean_title = title.strip()
        if not clean_title:
            raise DomainValidationError("Task title cannot be empty.")
        if len(clean_title) > 255:
            raise DomainValidationError("Task title cannot exceed 255 characters.")

        task_id = self.repo.create(
            title=clean_title,
            user_id=user_id,
            description=description,
            priority=priority,
            due_at=due_at,
            source=source
        )
        task = self.repo.get_by_id(task_id)
        if not task:
            raise NotFoundError(f"Failed to load created task #{task_id}")

        logger.info(f"Created task #{task.id}: '{task.title}' (due: {task.due_at})")
        return task

    def get_task(self, task_id: int) -> TaskRecord:
        """Fetch task or raise NotFoundError."""
        task = self.repo.get_by_id(task_id)
        if not task:
            raise NotFoundError(f"Task #{task_id} not found.")
        return task

    def list_pending_tasks(self, user_id: int = 0, limit: int = 50) -> List[TaskRecord]:
        """List active pending tasks."""
        return self.repo.list_by_status(status="PENDING", user_id=user_id, limit=limit)

    def complete_task(self, task_id: int) -> TaskRecord:
        """Mark task completed."""
        task = self.get_task(task_id)
        self.repo.mark_completed(task_id)
        logger.info(f"Marked task #{task_id} as completed.")
        return self.get_task(task_id)

    def cancel_task(self, task_id: int) -> TaskRecord:
        """Cancel task."""
        task = self.get_task(task_id)
        self.repo.mark_cancelled(task_id)
        logger.info(f"Cancelled task #{task_id}.")
        return self.get_task(task_id)

    def search_tasks(self, query: str, status: str = "PENDING") -> List[TaskRecord]:
        """Fuzzy search tasks by title."""
        return self.repo.find_by_title_fuzzy(query, status=status)
