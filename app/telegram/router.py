"""Telegram handler registration and routing."""

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.core.logging import get_logger
from app.telegram.auth import authorized_only
from app.telegram.handlers.callbacks import handle_callback_query
from app.telegram.handlers.commands import (
    aiusage_command,
    food_command,
    monthly_command,
    pending_command,
    start_command,
    status_command,
    summary_command,
    weekly_command,
    weight_command,
)
from app.telegram.handlers.messages import handle_text_message
from app.telegram.handlers.photos import handle_photo_message

logger = get_logger("telegram.router")


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log unhandled errors cleanly and prevent bot process crash."""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

    # If the update is a message from a user, send a friendly non-fatal notice
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ An unexpected error occurred while processing your request. Please try again."
            )
        except Exception as e:
            logger.error(f"Failed to send error notification message: {e}")


def register_handlers(app: Application) -> None:
    """Register all command and message handlers with the Telegram application, protected by auth guard."""
    # Commands
    app.add_handler(CommandHandler("start", authorized_only(start_command)))
    app.add_handler(CommandHandler("help", authorized_only(start_command)))
    app.add_handler(CommandHandler("status", authorized_only(status_command)))
    app.add_handler(CommandHandler("pending", authorized_only(pending_command)))
    app.add_handler(CommandHandler("food", authorized_only(food_command)))
    app.add_handler(CommandHandler("weight", authorized_only(weight_command)))
    app.add_handler(CommandHandler("summary", authorized_only(summary_command)))
    app.add_handler(CommandHandler("weekly", authorized_only(weekly_command)))
    app.add_handler(CommandHandler("monthly", authorized_only(monthly_command)))
    app.add_handler(CommandHandler("aiusage", authorized_only(aiusage_command)))

    # Media / Messages
    app.add_handler(MessageHandler(filters.PHOTO, authorized_only(handle_photo_message)))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, authorized_only(handle_text_message)))

    # Callbacks
    app.add_handler(CallbackQueryHandler(authorized_only(handle_callback_query)))

    # Global error handler
    app.add_error_handler(global_error_handler)
    logger.info("Telegram handlers registered successfully with authorization guard.")
