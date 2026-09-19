"""Telegram inline and reply keyboard markup builders."""

from typing import List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup


def build_confirmation_keyboard(callback_prefix: str, item_id: int) -> InlineKeyboardMarkup:
    """Build Confirm / Reject inline keyboard for pending items."""
    buttons = [
        [
            InlineKeyboardButton("✅ Confirm", callback_data=f"{callback_prefix}:confirm:{item_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"{callback_prefix}:reject:{item_id}"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)
