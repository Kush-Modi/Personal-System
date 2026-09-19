"""Telegram bot application entrypoint and lifecycle."""

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


def build_application() -> Application:
    """Construct and configure the Telegram application."""
    token = settings.telegram_bot_token
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN missing from environment or .env")

    app = Application.builder().token(token).build()
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
