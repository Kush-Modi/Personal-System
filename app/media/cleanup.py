"""Safe media retention cleanup service."""

import time
from pathlib import Path
from typing import Optional, Set, Union

from app.core.config import settings
from app.core.logging import get_logger
from app.database.repositories.pending_items import PendingItemRepository

logger = get_logger("media.cleanup")


class MediaCleanupService:
    """Cleans up old stored images while protecting active pending items."""

    def __init__(
        self,
        image_dir: Optional[Union[str, Path]] = None,
        pending_repo: Optional[PendingItemRepository] = None,
        retention_days: Optional[int] = None
    ):
        self.image_dir = Path(image_dir) if image_dir else settings.image_dir
        self.pending_repo = pending_repo or PendingItemRepository()
        self.retention_days = retention_days if retention_days is not None else settings.image_retention_days

    def cleanup_old_images(self) -> int:
        """
        Delete images older than retention_days, unless referenced by an active PENDING item.
        Returns count of deleted files.
        """
        if not self.image_dir.exists():
            return 0

        # Protected paths from active pending items
        active_paths: Set[str] = set()
        try:
            raw_active = self.pending_repo.get_active_image_paths()
            for p in raw_active:
                if p:
                    active_paths.add(Path(p).resolve().as_posix())
        except Exception as e:
            logger.error(f"Failed to query active pending image paths: {e}", exc_info=True)
            # Fail safely: do not delete anything if we cannot verify active references
            return 0

        now = time.time()
        max_age_seconds = self.retention_days * 86400
        deleted_count = 0

        for file_path in self.image_dir.glob("*.jpg"):
            try:
                resolved_str = file_path.resolve().as_posix()

                # Protect active pending images
                if resolved_str in active_paths:
                    logger.debug(f"Skipping active pending image: {file_path.name}")
                    continue

                # Check file modification time
                stat = file_path.stat()
                file_age = now - stat.st_mtime

                if file_age > max_age_seconds:
                    file_path.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted expired image: {file_path.name} (Age: {file_age/86400:.1f} days)")

            except Exception as e:
                logger.error(f"Error checking/deleting file {file_path}: {e}")

        logger.info(f"Media cleanup completed. {deleted_count} files removed.")
        return deleted_count
