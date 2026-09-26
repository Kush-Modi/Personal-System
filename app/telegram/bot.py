"""Telegram bot application entrypoint and lifecycle."""

import asyncio
import socket

# Force IPv4 because IPv6 connectivity is unreliable on Termux / mobile network
_original_getaddrinfo = socket.getaddrinfo


def getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _original_getaddrinfo(
        host,
        port,
        socket.AF_INET,
        type,
        proto,
        flags
    )


socket.getaddrinfo = getaddrinfo_ipv4


from telegram.ext import Application

from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.database.migrations import run_migrations
from app.telegram.router import register_handlers

logger = get_logger("telegram.bot")

# Module-level reference so we can stop the scheduler cleanly on shutdown
_scheduler_task = None


async def _post_init(application: Application) -> None:
    """
    Called after Application.initialize() but before polling starts.
    Launches the ReminderScheduler as a background asyncio task.
    """
    global _scheduler_task
    try:
        # Import here to avoid circular dependency issues during startup
        from app.services.reminder.scheduler import ReminderScheduler
        from app.database.repositories.reminder import ReminderRepository

        scheduler = ReminderScheduler(
            reminder_repo=ReminderRepository(),
            bot=application.bot,
            poll_interval_seconds=15,
            target_chat_id=settings.telegram_allowed_user_id,
        )
        # Store on application context so handlers can access it if needed
        application.bot_data["reminder_scheduler"] = scheduler

        _scheduler_task = asyncio.create_task(
            scheduler.start_loop(),
            name="reminder_scheduler_loop"
        )
        logger.info("ReminderScheduler background task started.")
    except Exception as e:
        logger.error(f"Failed to start ReminderScheduler: {e}", exc_info=True)


async def _post_shutdown(application: Application) -> None:
    """Gracefully cancel the scheduler task on bot shutdown."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
        logger.info("ReminderScheduler background task stopped.")

    scheduler = application.bot_data.get("reminder_scheduler")
    if scheduler:
        scheduler.stop()


def build_application() -> Application:
    """Construct and configure the Telegram application."""
    token = settings.telegram_bot_token
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN missing from environment or .env")

    app = (
        Application.builder()
        .token(token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    register_handlers(app)
    return app


def main() -> None:
    """Initialize system, execute pending migrations, and start Telegram bot."""
    setup_logging()
    logger.info("Initializing Personal-System...")

    # Ensure directories exist
    settings.ensure_directories()

    # Run database migrations
    try:
        applied = run_migrations()
        logger.info(f"Database migrations complete. {applied} migrations applied.")
    except Exception as e:
        logger.error(f"Fatal error during database migration: {e}", exc_info=True)
        raise

    # Start bot
    app = build_application()
    logger.info("Starting Telegram bot polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
