"""Tests for media storage, image optimization, and safe retention cleanup."""

import io
import os
import tempfile
import time
import unittest
from pathlib import Path
from PIL import Image

from app.database.migrations import run_migrations
from app.database.repositories.pending_items import PendingItemRepository
from app.domain.models import ItemType
from app.media.cleanup import MediaCleanupService
from app.media.optimizer import optimize_image_bytes
from app.media.storage import MediaStorage


class TestMediaPipeline(unittest.TestCase):
    """Test image resizing, compression, storage, and retention cleanup."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        self.image_dir = self.base_dir / "images"
        self.db_path = self.base_dir / "test_media.db"
        run_migrations(self.db_path)

        self.pending_repo = PendingItemRepository(self.db_path)
        self.storage = MediaStorage(self.image_dir)
        self.cleanup_service = MediaCleanupService(
            image_dir=self.image_dir,
            pending_repo=self.pending_repo,
            retention_days=30
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_dummy_image_bytes(self, width=2000, height=1500, color="red") -> bytes:
        img = Image.new("RGB", (width, height), color=color)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        return buf.getvalue()

    def test_image_optimization_and_resizing(self):
        raw_bytes = self._create_dummy_image_bytes(width=2400, height=1800)
        optimized = optimize_image_bytes(raw_bytes, max_dimension=1200, quality=75)

        self.assertLess(len(optimized), len(raw_bytes))

        # Check dimensions
        with Image.open(io.BytesIO(optimized)) as img:
            self.assertLessEqual(max(img.size), 1200)

    def test_media_storage_save(self):
        raw_bytes = self._create_dummy_image_bytes(width=500, height=500)
        saved_path = self.storage.save_image(raw_bytes, prefix="test")

        self.assertTrue(saved_path.exists())
        self.assertTrue(saved_path.name.startswith("test_"))
        self.assertEqual(saved_path.suffix, ".jpg")

    def test_media_retention_cleanup_and_active_protection(self):
        raw_bytes = self._create_dummy_image_bytes(width=200, height=200)

        # 1. Save an old unreferenced image
        old_path = self.storage.save_image(raw_bytes, prefix="old_unreferenced")
        # Age the file by 35 days (35 * 86400s)
        old_time = time.time() - (35 * 86400)
        os.utime(old_path, (old_time, old_time))

        # 2. Save an old image that IS referenced by an active PENDING item
        active_old_path = self.storage.save_image(raw_bytes, prefix="active_old")
        os.utime(active_old_path, (old_time, old_time))

        # Create active pending item referencing active_old_path
        self.pending_repo.create(
            item_type=ItemType.FOOD.value,
            structured_payload={"food_name": "Active Meal", "calories": 400},
            image_path=str(active_old_path)
        )

        # 3. Save a fresh image (1 day old)
        fresh_path = self.storage.save_image(raw_bytes, prefix="fresh")

        # Run cleanup
        deleted = self.cleanup_service.cleanup_old_images()

        self.assertEqual(deleted, 1)
        self.assertFalse(old_path.exists())  # Expired & unreferenced -> deleted
        self.assertTrue(active_old_path.exists())  # Expired but active PENDING -> protected!
        self.assertTrue(fresh_path.exists())  # Fresh -> kept!


if __name__ == "__main__":
    unittest.main()
