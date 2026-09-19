"""Telegram callback query handlers."""

from telegram import Update
from telegram.ext import ContextTypes

from app.core.logging import get_logger

logger = get_logger("telegram.callbacks")


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback queries from inline buttons."""
    query = update.callback_query
    if not query:
        return

    await query.answer()
    logger.debug(f"Received callback data: {query.data}")
