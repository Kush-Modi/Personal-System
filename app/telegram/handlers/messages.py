"""Telegram plain text message handlers with edit session management and input routing."""

from telegram import Update
from telegram.ext import ContextTypes

from app.core.exceptions import AlreadyProcessedError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.models import InputSource, ItemType
from app.input.ai_processor import AIInputProcessor
from app.services.pending.service import PendingItemService
from app.telegram.keyboards import build_pending_action_keyboard
from app.telegram.renderers import render_pending_preview
from app.telegram.sessions import TelegramSessionManager

logger = get_logger("telegram.messages")

pending_service = PendingItemService()
session_manager = TelegramSessionManager()
input_processor = AIInputProcessor()


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain text messages from user."""
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id if update.effective_user else 0
    text = update.message.text.strip()
    logger.debug(f"Received text message from user {user_id}: {text[:30]}...")

    # ==================================================
    # 1. CHECK ACTIVE EDIT SESSION
    # ==================================================
    session = session_manager.get_active_session(user_id)
    if session:
        await _handle_edit_reply(update, session, text)
        return

    # ==================================================
    # 2. INPUT PROCESSOR ROUTING (AI / Natural Language / Mock)
    # ==================================================
    result = input_processor.process_text(text)

    if result.success:
        try:
            pending_item = pending_service.create_pending_item(
                item_type=result.item_type,
                structured_payload=result.payload,
                raw_payload=result.raw_text,
                source=result.source or InputSource.TEXT.value,
                confidence=result.confidence
            )

            preview_text = render_pending_preview(pending_item)
            keyboard = build_pending_action_keyboard(pending_item.id)

            await update.message.reply_text(
                preview_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            return

        except ValidationError as e:
            await update.message.reply_text(f"⚠️ Validation error: {e}")
            return
        except Exception as e:
            logger.error(f"Failed to create pending item from text: {e}", exc_info=True)
            await update.message.reply_text("⚠️ An error occurred while processing your message.")
            return

    # Unhandled text: polite guidance
    err_note = f"\n\n{result.error_message}" if result.error_message else ""
    await update.message.reply_text(
        f"💡 You can log food with `/food Name Calories`, weight with `/weight Number`, "
        f"send a meal photo, or describe your food in plain English.{err_note}"
    )


async def _handle_edit_reply(update: Update, session, text: str) -> None:
    """Process user reply when in an interactive edit session."""
    user_id = session.user_id
    item_id = session.pending_item_id
    item_type = session.item_type.upper()

    try:
        new_payload = {}

        if item_type == ItemType.FOOD.value:
            # Expected format: "Name, Calories" or "Name Calories"
            if "," in text:
                parts = text.split(",", 1)
                name = parts[0].strip()
                calories = float(parts[1].strip().split()[0])
            else:
                parts = text.split()
                if len(parts) < 2:
                    raise ValueError("Please provide food name and calories (e.g. 'Paneer tikka, 350')")
                calories = float(parts[-1])
                name = " ".join(parts[:-1])

            new_payload = {"food_name": name, "calories": calories}

        elif item_type == ItemType.EXPENSE.value:
            # Expected format: "Amount, Category, Merchant"
            if "," in text:
                parts = [p.strip() for p in text.split(",")]
                amount = float(parts[0])
                category = parts[1] if len(parts) > 1 else "General"
                merchant = parts[2] if len(parts) > 2 else None
            else:
                parts = text.split()
                if len(parts) < 2:
                    raise ValueError("Please provide amount and category (e.g. '150, Coffee, Starbucks')")
                amount = float(parts[0])
                category = parts[1]
                merchant = " ".join(parts[2:]) if len(parts) > 2 else None

            new_payload = {"amount": amount, "category": category, "merchant": merchant}

        elif item_type == ItemType.TASK.value:
            new_payload = {"title": text.strip()}

        else:
            new_payload = {"text": text.strip()}

        # Update pending item payload (does NOT auto-save)
        updated_item = pending_service.edit_payload(item_id, new_payload)

        # Clear active edit session
        session_manager.end_session(user_id)

        preview_text = render_pending_preview(updated_item)
        keyboard = build_pending_action_keyboard(updated_item.id)

        await update.message.reply_text(
            f"✏️ *Updated Preview:*\n\n{preview_text}",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

    except (ValueError, ValidationError) as e:
        await update.message.reply_text(f"⚠️ Invalid format: {e}\n\nPlease try again.")
    except AlreadyProcessedError:
        session_manager.end_session(user_id)
        await update.message.reply_text("⚠️ This item has already been processed and can no longer be edited.")
    except NotFoundError:
        session_manager.end_session(user_id)
        await update.message.reply_text("❌ Pending item not found.")
    except Exception as e:
        logger.error(f"Error handling edit reply: {e}", exc_info=True)
        session_manager.end_session(user_id)
        await update.message.reply_text("⚠️ Error saving edits.")
