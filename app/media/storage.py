"""Secure image storage management."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from app.core.config import settings
from app.core.logging import get_logger
from app.media.optimizer import optimize_image_bytes

logger = get_logger("media.storage")


class MediaStorage:
    """Manages application local image storage and path resolution."""

    def __init__(self, base_dir: Optional[Union[str, Path]] = None):
        self.base_dir = Path(base_dir) if base_dir else settings.image_dir

    def save_image(
        self,
        image_bytes: bytes,
        prefix: str = "photo",
        optimize: bool = True
    ) -> Path:
        """
        Optimize and save image bytes to the managed media directory.
        Generates a non-conflicting, deterministic safe filename.
        """
        self.base_dir.mkdir(parents=True, exist_ok=True)

        processed_bytes = optimize_image_bytes(image_bytes) if optimize else image_bytes

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_token = uuid.uuid4().hex[:8]
        filename = f"{prefix}_{timestamp}_{unique_token}.jpg"

        file_path = (self.base_dir / filename).resolve()
        file_path.write_bytes(processed_bytes)

        logger.info(f"Saved media file: {file_path.name} ({len(processed_bytes)} bytes)")
        return file_path

    def get_image_path(self, filename: str) -> Optional[Path]:
        """Safely resolve an image path without directory traversal vulnerabilities."""
        safe_name = Path(filename).name
        target = (self.base_dir / safe_name).resolve()
        if target.exists() and target.is_relative_to(self.base_dir.resolve()):
            return target
        return None
