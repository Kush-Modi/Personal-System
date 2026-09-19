"""Telegram inline and reply keyboard markup builders."""

from typing import Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def build_pending_action_keyboard(item_id: int) -> InlineKeyboardMarkup:
    """
    Build standardized [✅ Save] [✏️ Edit] [❌ Reject] inline keyboard for a pending item.
    Callback data is kept compact to stay well within Telegram's 64-byte limit.
    """
    buttons = [
        [
            InlineKeyboardButton("✅ Save", callback_data=f"p:save:{item_id}"),
            InlineKeyboardButton("✏️ Edit", callback_data=f"p:edit:{item_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"p:reject:{item_id}"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def build_confirmation_keyboard(callback_prefix: str, item_id: int) -> InlineKeyboardMarkup:
    """Build Confirm / Reject inline keyboard (backward-compatible helper)."""
    buttons = [
        [
            InlineKeyboardButton("✅ Confirm", callback_data=f"{callback_prefix}:confirm:{item_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"{callback_prefix}:reject:{item_id}"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)
