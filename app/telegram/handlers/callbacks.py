"""Telegram callback query handlers for confirmation and pending item actions."""

from telegram import Update
from telegram.ext import ContextTypes

from app.core.exceptions import AlreadyProcessedError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.services.pending.service import PendingItemService
from app.telegram.renderers import (
    render_edit_prompt,
    render_rejected_confirmation,
    render_saved_confirmation,
)
from app.telegram.sessions import TelegramSessionManager

logger = get_logger("telegram.callbacks")

pending_service = PendingItemService()
session_manager = TelegramSessionManager()


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle inline button callbacks (p:save:<id>, p:edit:<id>, p:reject:<id>).
    Ensures idempotency and security against double-clicks and malformed data.
    """
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data.strip()
    logger.debug(f"Received callback query data: {data}")

    parts = data.split(":")
    if len(parts) != 3 or parts[0] not in ("p", "pending"):
        await query.answer("⚠️ Invalid action.")
        return

    action = parts[1].lower()
    try:
        item_id = int(parts[2])
    except ValueError:
        await query.answer("⚠️ Invalid item ID.")
        return

    user_id = query.from_user.id if query.from_user else 0

    # --------------------------------------------------
    # 1. ACTION: SAVE / CONFIRM
    # --------------------------------------------------
    if action in ("save", "confirm"):
        try:
            item, domain_record = pending_service.confirm(item_id)
            await query.answer("✅ Saved!")
            if query.message:
                await query.edit_message_text(
                    render_saved_confirmation(item, domain_record),
                    parse_mode="Markdown"
                )
        except AlreadyProcessedError:
            await query.answer("⚠️ This item has already been processed.", show_alert=True)
            if query.message:
                try:
                    await query.edit_message_reply_markup(reply_markup=None)
                except Exception:
                    pass
        except NotFoundError:
            await query.answer("❌ Item not found.", show_alert=True)
        except Exception as e:
            logger.error(f"Error confirming pending item #{item_id}: {e}", exc_info=True)
            await query.answer("⚠️ Failed to save item. Please try again.", show_alert=True)

    # --------------------------------------------------
    # 2. ACTION: REJECT
    # --------------------------------------------------
    elif action == "reject":
        try:
            item = pending_service.reject(item_id)
            await query.answer("❌ Rejected.")
            if query.message:
                await query.edit_message_text(
                    render_rejected_confirmation(item),
                    parse_mode="Markdown"
                )
        except AlreadyProcessedError:
            await query.answer("⚠️ This item has already been processed.", show_alert=True)
            if query.message:
                try:
                    await query.edit_message_reply_markup(reply_markup=None)
                except Exception:
                    pass
        except NotFoundError:
            await query.answer("❌ Item not found.", show_alert=True)
        except Exception as e:
            logger.error(f"Error rejecting pending item #{item_id}: {e}", exc_info=True)
            await query.answer("⚠️ Error rejecting item.", show_alert=True)

    # --------------------------------------------------
    # 3. ACTION: EDIT
    # --------------------------------------------------
    elif action == "edit":
        try:
            item = pending_service.get_pending_item(item_id)
            if not item.is_pending:
                await query.answer("⚠️ This item is no longer pending.", show_alert=True)
                return

            # Start interactive edit session
            session_manager.start_edit_session(
                user_id=user_id,
                pending_item_id=item_id,
                item_type=item.item_type
            )
            await query.answer()

            if query.message:
                await query.message.reply_text(
                    render_edit_prompt(item),
                    parse_mode="Markdown"
                )
        except NotFoundError:
            await query.answer("❌ Item not found.", show_alert=True)
        except Exception as e:
            logger.error(f"Error initiating edit for item #{item_id}: {e}", exc_info=True)
            await query.answer("⚠️ Error starting edit mode.", show_alert=True)

    else:
        await query.answer("⚠️ Unknown action.")
