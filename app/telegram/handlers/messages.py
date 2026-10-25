"""Telegram plain text message handlers with edit session management and input routing."""

import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from app.core.exceptions import AlreadyProcessedError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.models import InputSource, ItemType
from app.input.ai_processor import AIInputProcessor
from app.services.analytics.service import AnalyticsQueryService
from app.services.conversation.service import ConversationContextService
from app.services.pending.service import PendingItemService
from app.services.reminder.service import ReminderService
from app.services.task.service import TaskService
from app.services.weight.service import WeightService
from app.telegram.keyboards import build_pending_action_keyboard
from app.telegram.renderers import render_pending_preview
from app.telegram.sessions import TelegramSessionManager

logger = get_logger("telegram.messages")

pending_service = PendingItemService()
weight_service = WeightService()
task_service = TaskService()
reminder_service = ReminderService()
conversation_service = ConversationContextService()
analytics_service = AnalyticsQueryService()
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
    # 2. CHECK MULTI-TURN CONVERSATION FOLLOW-UP CORRECTION
    # ==================================================
    # If the user says e.g. "Actually make it 350", "Make the dal 1 bowl", "Change to ₹450"
    # and has an active unconfirmed pending item in short-term context:
    user_context = conversation_service.get_context(user_id)
    if user_context and user_context.active_pending_id:
        try:
            active_item = pending_service.get_pending_item(user_context.active_pending_id)
            if active_item.is_pending:
                # Check for correction trigger keywords
                text_lower = text.lower()
                is_correction = any(w in text_lower for w in ("actually", "change", "make it", "make the", "correct to", "instead", "no it was", "nah"))
                if is_correction:
                    # Let's adjust the pending item based on the intent
                    if active_item.item_type == ItemType.FOOD.value:
                        # Extract calories or name
                        import re
                        num_match = re.search(r"(\d+(?:\.\d+)?)", text)
                        if num_match:
                            new_cals = float(num_match.group(1))
                            active_item.structured_payload["calories"] = new_cals
                            updated = pending_service.edit_payload(active_item.id, active_item.structured_payload, user_notes=text)
                            preview_text = render_pending_preview(updated)
                            keyboard = build_pending_action_keyboard(updated.id)
                            reply_msg = f"✏️ *Updated pending food item:*\n\n{preview_text}"
                            conversation_service.record_turn(user_id, text, reply_msg, intent="FOOD", active_pending_id=updated.id)
                            await update.message.reply_text(reply_msg, reply_markup=keyboard, parse_mode="Markdown")
                            return
                    elif active_item.item_type == ItemType.EXPENSE.value:
                        import re
                        num_match = re.search(r"(\d+(?:\.\d+)?)", text)
                        if num_match:
                            new_amt = float(num_match.group(1))
                            active_item.structured_payload["amount"] = new_amt
                            updated = pending_service.edit_payload(active_item.id, active_item.structured_payload, user_notes=text)
                            preview_text = render_pending_preview(updated)
                            keyboard = build_pending_action_keyboard(updated.id)
                            reply_msg = f"✏️ *Updated pending expense:*\n\n{preview_text}"
                            conversation_service.record_turn(user_id, text, reply_msg, intent="EXPENSE", active_pending_id=updated.id)
                            await update.message.reply_text(reply_msg, reply_markup=keyboard, parse_mode="Markdown")
                            return
        except Exception as e:
            logger.debug(f"Context correction check passed through: {e}")

    # ==================================================
    # 3. REMINDER MANAGEMENT SHORTCUT (list / cancel)
    # ==================================================
    text_lower = text.lower()
    _reminder_list_triggers = (
        "my reminders", "show reminders", "list reminders", "reminders i have",
        "what reminders", "upcoming reminders", "pending reminders", "active reminders"
    )
    _reminder_cancel_triggers = ("cancel reminder", "delete reminder", "remove reminder", "stop reminder")

    if any(t in text_lower for t in _reminder_list_triggers):
        try:
            reminders = reminder_service.list_upcoming(user_id=user_id, limit=15)
            if not reminders:
                reply_text = "📭 You have no upcoming reminders."
            else:
                lines = ["🔔 *Your Upcoming Reminders:*\n"]
                for r in reminders:
                    rec_label = f" 🔁 {r.recurrence}" if r.recurrence else ""
                    lines.append(f"• `#{r.id}` {r.reminder_text} — _{r.remind_at}{rec_label}_")
                reply_text = "\n".join(lines)
            conversation_service.record_turn(user_id, text, reply_text, intent="REMINDER")
            await update.message.reply_text(reply_text, parse_mode="Markdown")
            return
        except Exception as e:
            logger.error(f"Failed to list reminders: {e}", exc_info=True)

    if any(t in text_lower for t in _reminder_cancel_triggers):
        import re as _re
        id_match = _re.search(r"#?(\d+)", text)
        if id_match:
            rid = int(id_match.group(1))
            try:
                reminder_service.cancel_reminder(rid)
                reply_text = f"✅ Reminder #{rid} cancelled."
                conversation_service.record_turn(user_id, text, reply_text, intent="REMINDER")
                await update.message.reply_text(reply_text)
                return
            except Exception as e:
                await update.message.reply_text(f"❌ Could not cancel reminder #{rid}: {e}")
                return

    # ==================================================
    # 4. INPUT PROCESSOR ROUTING (AI / Natural Language / Mock)
    # ==================================================
    # Offload blocking network AI inference to worker thread to prevent event-loop freezing
    result = await asyncio.to_thread(input_processor.process_text, text)

    if result.success:

        # A. DATA_QUERY Execution via Analytics Planner
        if result.item_type == ItemType.DATA_QUERY.value or result.response_mode == "QUERY":
            # Formulate query plan or execute
            query_plan = {
                "domain": "FOOD" if "calorie" in text.lower() or "eat" in text.lower() or "ate" in text.lower()
                else ("EXPENSE" if "spend" in text.lower() or "spent" in text.lower() or "expense" in text.lower() or "money" in text.lower() or "cost" in text.lower()
                else ("WEIGHT" if "weight" in text.lower() or "kg" in text.lower() or "gain" in text.lower() or "lost" in text.lower()
                else ("TASK" if "task" in text.lower() or "todo" in text.lower()
                else ("REMINDER" if "reminder" in text.lower() else "OTHER")))),
                "operation": "AVERAGE" if "average" in text.lower() or "avg" in text.lower()
                else ("HIGHEST" if "highest" in text.lower() or "max" in text.lower() or "biggest" in text.lower()
                else ("TREND" if "trend" in text.lower() or "progress" in text.lower() else "TOTAL")),
                "date_range": {
                    "range": "yesterday" if "yesterday" in text.lower()
                    else ("this_week" if "this week" in text.lower() or "week" in text.lower()
                    else ("last_week" if "last week" in text.lower()
                    else ("this_month" if "this month" in text.lower() or "month" in text.lower()
                    else ("last_month" if "last month" in text.lower() else "today"))))
                },
                "filters": {}
            }
            # Check category filter in expenses
            for cat in ("Food & Dining", "Groceries", "Transport", "Shopping", "Bills", "Health"):
                if cat.lower() in text.lower():
                    query_plan["filters"]["category"] = cat
                    query_plan["domain"] = "EXPENSE"
                    break

            reply_text = analytics_service.execute_query(query_plan)
            conversation_service.record_turn(user_id, text, reply_text, intent="DATA_QUERY")
            await update.message.reply_text(reply_text, parse_mode="Markdown")
            return

        # B. Conversational / Direct response modes (CHAT, CLARIFICATION)
        if result.response_mode in ("CHAT", "CLARIFICATION") or result.item_type in (
            ItemType.GENERAL_CHAT.value,
            ItemType.OTHER.value,
        ):
            reply_text = result.payload.get("reply") or "I'm here to help!"
            conversation_service.record_turn(user_id, text, reply_text, intent="CHAT")
            await update.message.reply_text(reply_text)
            return

        # C. Deterministic Weight Direct Save (if no confirmation requested)
        if result.item_type == ItemType.WEIGHT.value and not result.requires_confirmation:
            try:
                w_kg = float(result.payload.get("weight_kg", 0.0))
                w_date = result.payload.get("date")
                rec = weight_service.record_weight(weight_kg=w_kg, date=w_date)
                date_label = w_date or "today"
                reply_msg = f"⚖️ *Weight logged successfully!*\n\n{w_kg:.1f} kg ({date_label})"
                conversation_service.record_turn(user_id, text, reply_msg, intent="WEIGHT")
                await update.message.reply_text(reply_msg, parse_mode="Markdown")
                return
            except ValidationError as e:
                await update.message.reply_text(f"⚠️ Validation error: {e}")
                return
            except Exception as e:
                logger.error(f"Failed to directly log weight: {e}", exc_info=True)
                await update.message.reply_text("⚠️ An error occurred while saving your weight.")
                return

        # D. Staged Pending Action (FOOD, EXPENSE, TASK, REMINDER, or Ambiguous WEIGHT)
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

            conversation_service.record_turn(
                user_id=user_id,
                user_message=text,
                bot_response=preview_text,
                intent=result.item_type,
                active_pending_id=pending_item.id
            )

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
        f"💡 You can log food (e.g. 'I had 2 rotis and dal'), expenses (e.g. 'Spent 450 at Starbucks'), "
        f"weight (e.g. '76.2 kg'), add tasks ('Add finish resume to tasks'), reminders ('Remind me tomorrow at 8 AM to call mom'), "
        f"send receipt/meal photos, or ask questions.{err_note}"
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

        elif item_type == ItemType.WEIGHT.value:
            try:
                weight_val = float(text.strip().split()[0])
                new_payload = {"weight_kg": weight_val}
            except (ValueError, IndexError):
                raise ValueError("Please provide a valid weight in kg (e.g. '76.2')")

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
