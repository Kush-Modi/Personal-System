"""Telegram photo message handlers (Phase 1 architectural prep)."""

from telegram import Update
from telegram.ext import ContextTypes

from app.core.logging import get_logger

logger = get_logger("telegram.photos")


async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inbound photos."""
    if not update.message or not update.message.photo:
        return

    logger.info("Received photo from user. Photo ingestion pipeline scheduled for Phase 4.")
    await update.message.reply_text(
        "📷 Photo received! AI vision processing is scheduled for an upcoming update."
    )
