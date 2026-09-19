"""Telegram handlers package."""

from app.telegram.handlers.commands import (
    start_command,
    status_command,
    food_command,
    weight_command,
    summary_command,
    weekly_command,
    monthly_command,
)
from app.telegram.handlers.messages import handle_text_message
from app.telegram.handlers.photos import handle_photo_message
from app.telegram.handlers.callbacks import handle_callback_query

__all__ = [
    "start_command",
    "status_command",
    "food_command",
    "weight_command",
    "summary_command",
    "weekly_command",
    "monthly_command",
    "handle_text_message",
    "handle_photo_message",
    "handle_callback_query",
]
