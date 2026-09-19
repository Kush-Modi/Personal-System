"""Telegram photo message handlers for image ingestion and confirmation staging."""

from telegram import Update
from telegram.ext import ContextTypes

from app.core.exceptions import MediaProcessingError, ValidationError
from app.core.logging import get_logger
from app.domain.models import InputSource
from app.input.mock_processor import MockInputProcessor
from app.media.storage import MediaStorage
from app.services.pending.service import PendingItemService
from app.telegram.keyboards import build_pending_action_keyboard
from app.telegram.renderers import render_pending_preview

logger = get_logger("telegram.photos")

media_storage = MediaStorage()
mock_processor = MockInputProcessor()
pending_service = PendingItemService()


async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download inbound photo, optimize and store locally, parse via processor, stage as pending item."""
    if not update.message or not update.message.photo:
        return

    try:
        # Get highest resolution photo object
        photo = update.message.photo[-1]
        caption = update.message.caption or ""

        logger.info(f"Received photo (file_id: {photo.file_id}, size: {photo.file_size} bytes)")

        # Download photo bytes
        telegram_file = await context.bot.get_file(photo.file_id)
        photo_bytes = await telegram_file.download_as_bytearray()

        # Optimize and save locally
        saved_path = media_storage.save_image(bytes(photo_bytes), prefix="inbound", optimize=True)

        # Process photo with mock/deterministic processor (Phase 2 foundation)
        result = mock_processor.process_photo(image_path=saved_path, caption=caption)

        if result.success:
            pending_item = pending_service.create_pending_item(
                item_type=result.item_type,
                structured_payload=result.payload,
                raw_payload=caption,
                source=InputSource.PHOTO.value,
                confidence=result.confidence,
                image_path=str(saved_path)
            )

            preview_text = render_pending_preview(pending_item)
            keyboard = build_pending_action_keyboard(pending_item.id)

            await update.message.reply_text(
                f"📷 *Photo Processed*\n\n{preview_text}",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "📷 Photo received, but could not identify structured items from it."
            )

    except MediaProcessingError as e:
        logger.error(f"Media processing error: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Could not process the received image.")
    except Exception as e:
        logger.error(f"Unexpected error handling photo: {e}", exc_info=True)
        await update.message.reply_text("⚠️ An error occurred while saving the photo.")
