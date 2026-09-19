"""Telegram bot package."""

try:
    from app.telegram.bot import build_application, main
    __all__ = ["build_application", "main"]
except ImportError:
    __all__ = []
