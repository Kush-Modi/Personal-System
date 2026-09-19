"""Media and image optimization pipeline (resizing, JPEG compression, EXIF stripping)."""

import io
from pathlib import Path
from typing import Optional, Tuple, Union

from app.core.config import settings
from app.core.exceptions import MediaProcessingError
from app.core.logging import get_logger

logger = get_logger("media.optimizer")

try:
    from PIL import Image, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def optimize_image_bytes(
    input_bytes: bytes,
    max_dimension: Optional[int] = None,
    quality: Optional[int] = None
) -> bytes:
    """
    Optimize raw image bytes by resizing, converting to RGB, stripping metadata,
    and compressing as JPEG.
    """
    if not input_bytes:
        raise MediaProcessingError("Input image bytes cannot be empty.")

    max_dim = max_dimension or settings.image_max_dimension
    qual = quality or settings.image_quality

    if not PIL_AVAILABLE:
        logger.warning("PIL not installed; returning original uncompressed bytes.")
        return input_bytes

    try:
        with Image.open(io.BytesIO(input_bytes)) as img:
            # Handle orientation from EXIF before stripping
            img = ImageOps.exif_transpose(img)

            # Convert to RGB (in case of PNG/RGBA/P palettes)
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Resize if dimensions exceed max_dimension
            width, height = img.size
            if width > max_dim or height > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                logger.debug(f"Resized image from ({width}, {height}) to {img.size}")

            output_buffer = io.BytesIO()
            img.save(
                output_buffer,
                format="JPEG",
                quality=qual,
                optimize=True
            )
            return output_buffer.getvalue()

    except Exception as e:
        logger.error(f"Image optimization failed: {e}", exc_info=True)
        raise MediaProcessingError(f"Failed to process and optimize image: {e}") from e


def optimize_image_file(
    source_path: Union[str, Path],
    destination_path: Union[str, Path],
    max_dimension: Optional[int] = None,
    quality: Optional[int] = None
) -> Path:
    """Read source image file, optimize, and save to destination path."""
    src = Path(source_path)
    dst = Path(destination_path)

    if not src.exists():
        raise MediaProcessingError(f"Source image does not exist: {src}")

    raw_bytes = src.read_bytes()
    optimized = optimize_image_bytes(raw_bytes, max_dimension, quality)

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(optimized)
    return dst
