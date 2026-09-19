"""Telegram plain text message handlers."""

from telegram import Update
from telegram.ext import ContextTypes

from app.core.logging import get_logger

logger = get_logger("telegram.messages")


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain text messages."""
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    logger.debug(f"Received text message: {text[:20]}...")
