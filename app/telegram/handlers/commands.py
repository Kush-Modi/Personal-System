"""Telegram bot command handlers."""

from datetime import date, datetime
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.services.food.service import FoodService
from app.services.system.service import SystemService
from app.services.weight.service import WeightService
from app.telegram.parsing import date_error, format_date, parse_date, today_date

logger = get_logger("telegram.commands")

food_service = FoodService()
weight_service = WeightService()
system_service = SystemService()


# ==================================================
# COMMAND HANDLERS
# ==================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not update.message:
        return

    message = (
        "🤖 Personal Server\n\n"
        "🍽 FOOD\n"
        "/food NAME CALORIES\n"
        "/food\n"
        "/food yesterday\n"
        "/food 2026-09-01\n\n"
        "Edit food:\n"
        "/food edit NUMBER NAME CALORIES\n\n"
        "Delete food:\n"
        "/food delete NUMBER\n\n"
        "⚖️ WEIGHT\n"
        "/weight NUMBER\n"
        "/weight\n"
        "/weight yesterday\n"
        "/weight 2026-09-01\n\n"
        "📊 SUMMARY\n"
        "/summary\n"
        "/summary yesterday\n\n"
        "📈 REPORTS\n"
        "/weekly\n"
        "/weekly 2026-09-01\n\n"
        "/monthly\n"
        "/monthly 2026-09\n\n"
        "🖥 SYSTEM\n"
        "/status"
    )
    await update.message.reply_text(message)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command for system diagnostics."""
    if not update.message:
        return

    status_msg = system_service.get_formatted_status_message()
    await update.message.reply_text(status_msg, parse_mode="Markdown")


async def food_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /food command and its subcommands (add, view, edit, delete)."""
    if not update.message:
        return

    args = context.args or []

    # 1. VIEW FOOD FOR TODAY
    if not args:
        today = today_date()
        await _show_food(update, today, "Today")
        return

    # 2. VIEW FOOD FOR SPECIFIC DATE
    if len(args) == 1:
        target_date, label = parse_date(args[0])
        if target_date:
            await _show_food(update, target_date, label)
            return

    # 3. DELETE FOOD
    if args[0].lower() == "delete":
        await _delete_food(update, args[1:])
        return

    # 4. EDIT FOOD
    if args[0].lower() == "edit":
        await _edit_food(update, args[1:])
        return

    # 5. ADD FOOD
    if len(args) < 2:
        await update.message.reply_text("Usage:\n/food NAME CALORIES")
        return

    try:
        calories = float(args[-1])
        food_name = " ".join(args[:-1])

        record = food_service.add_food(food_name, calories)
        await update.message.reply_text(
            f"🍽 Added: {record.food_name}\n"
            f"🔥 {record.calories:.0f} kcal"
        )
    except (ValueError, ValidationError):
        await update.message.reply_text(
            "Usage:\n"
            "/food NAME CALORIES\n\n"
            "Example:\n"
            "/food veg burrito 650"
        )


async def _show_food(update: Update, target_date: date, label: Optional[str]) -> None:
    """Helper to display formatted food list for a date."""
    records, total_cals = food_service.get_food_for_date(target_date)
    if not records:
        await update.message.reply_text(f"No food recorded for {label}.")
        return

    message = f"🍽 {label}\n\n"
    for number, record in enumerate(records, start=1):
        message += f"{number}. {record.food_name} — {record.calories:.0f} kcal\n"

    message += f"\n━━━━━━━━━━\n🔥 Total: {total_cals:.0f} kcal"
    await update.message.reply_text(message)


async def _delete_food(update: Update, args: list) -> None:
    """Helper to delete a food entry by index."""
    if not args:
        await update.message.reply_text("Usage:\n/food delete NUMBER")
        return

    try:
        number = int(args[0])
        target_date = today_date()

        if len(args) > 1:
            target_date, _ = parse_date(args[1])
            if not target_date:
                await update.message.reply_text(date_error())
                return

        food_service.delete_food_by_index(target_date, number)
        await update.message.reply_text(f"🗑️ Food entry {number} deleted.")
    except NotFoundError:
        await update.message.reply_text("Food entry not found.")
    except ValueError:
        await update.message.reply_text("Please enter a valid number.")


async def _edit_food(update: Update, args: list) -> None:
    """Helper to edit a food entry by index."""
    if len(args) < 3:
        await update.message.reply_text(
            "Usage:\n"
            "/food edit NUMBER NAME CALORIES\n\n"
            "Example:\n"
            "/food edit 2 veg burrito 550"
        )
        return

    try:
        number = int(args[0])
        calories = float(args[-1])
        food_name = " ".join(args[1:-1])

        target_date = today_date()
        record = food_service.edit_food_by_index(target_date, number, food_name, calories)
        await update.message.reply_text(
            f"✏️ Food entry {number} updated.\n\n"
            f"{record.food_name}\n"
            f"🔥 {record.calories:.0f} kcal"
        )
    except NotFoundError:
        await update.message.reply_text("Food entry not found.")
    except (ValueError, ValidationError):
        await update.message.reply_text("Invalid input.")


async def weight_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /weight command and subcommands (history, date view, delete, record)."""
    if not update.message:
        return

    args = context.args or []

    # 1. SHOW HISTORY
    if not args:
        history = weight_service.get_recent_history(30)
        if not history:
            await update.message.reply_text("No weight records yet.")
            return

        message = "⚖️ Weight History\n\n"
        for val, created_at in history:
            d_str = created_at[:10]
            message += f"{d_str} — {val:.1f} kg\n"
        await update.message.reply_text(message)
        return

    # 2. DELETE WEIGHT
    if args[0].lower() == "delete":
        target_date = today_date()
        if len(args) > 1:
            target_date, _ = parse_date(args[1])
            if not target_date:
                await update.message.reply_text(date_error())
                return

        deleted = weight_service.delete_weight_for_date(target_date)
        if deleted:
            await update.message.reply_text("🗑️ Weight deleted.")
        else:
            await update.message.reply_text("No weight found for that date.")
        return

    # 3. VIEW SPECIFIC DATE
    target_date, label = parse_date(args[0])
    if target_date:
        w = weight_service.get_weight_for_date(target_date)
        if w is None:
            await update.message.reply_text(f"No weight recorded for {label}.")
        else:
            await update.message.reply_text(f"⚖️ {label}\n\n{w:.1f} kg")
        return

    # 4. SAVE / UPDATE WEIGHT
    try:
        weight_val = float(args[0])
        today = today_date()
        is_updated, val = weight_service.record_weight(today, weight_val)
        if is_updated:
            await update.message.reply_text(f"⚖️ Today's weight updated: {val:.1f} kg")
        else:
            await update.message.reply_text(f"⚖️ Weight saved: {val:.1f} kg")
    except (ValueError, ValidationError):
        await update.message.reply_text("Usage:\n/weight 75.5")


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /summary command."""
    if not update.message:
        return

    target_date = today_date()
    label = "Today"

    if context.args:
        target_date, label = parse_date(context.args[0])
        if not target_date:
            await update.message.reply_text(date_error())
            return

    food_count, calories = food_service.get_date_stats(target_date)
    weight_val = weight_service.get_weight_for_date(target_date)

    message = (
        f"📊 {label}\n\n"
        f"🍽 Food entries: {food_count}\n"
        f"🔥 Calories: {calories:.0f} kcal\n"
    )

    if weight_val is not None:
        message += f"⚖️ Weight: {weight_val:.1f} kg"
    else:
        message += "⚖️ Weight: Not recorded"

    await update.message.reply_text(message)


async def weekly_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /weekly report command."""
    if not update.message:
        return

    reference_date = today_date()
    if context.args:
        reference_date, _ = parse_date(context.args[0])
        if not reference_date:
            await update.message.reply_text(date_error())
            return

    data = weight_service.get_weekly_report(reference_date)

    message = (
        "📈 Weekly Report\n"
        f"{data.start_date.strftime('%d %b')} – "
        f"{data.end_date.strftime('%d %b %Y')}\n\n"
        "⚖️ Weight\n\n"
    )

    for day, w in data.daily_weights:
        if w is not None:
            message += f"{day.strftime('%a')} {w:.1f} kg\n"
        else:
            message += f"{day.strftime('%a')} —\n"

    message += "\n━━━━━━━━━━\n\n"

    if data.weight_stats:
        stats = data.weight_stats
        message += (
            f"Start: {stats['start']:.1f} kg\n"
            f"Latest: {stats['latest']:.1f} kg\n"
            f"Change: {stats['change']:+.1f} kg\n"
            f"Average: {stats['average']:.1f} kg\n"
            f"Lowest: {stats['lowest']:.1f} kg\n"
            f"Highest: {stats['highest']:.1f} kg\n"
        )
    else:
        message += "No weight data this week.\n"

    message += "\n━━━━━━━━━━\n\n🔥 Calories\n\n"

    for day, _, cals in data.daily_calories:
        message += f"{day.strftime('%a')} {cals:.0f} kcal\n"

    message += (
        f"\n━━━━━━━━━━\n"
        f"Total calories: {data.total_calories:.0f} kcal\n"
        f"Daily average: {data.daily_average_calories:.0f} kcal\n"
        f"Food entries: {data.total_food_entries}"
    )

    await update.message.reply_text(message)


async def monthly_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /monthly report command."""
    if not update.message:
        return

    reference_date = today_date()
    if context.args:
        try:
            reference_date = datetime.strptime(context.args[0], "%Y-%m").date()
        except ValueError:
            await update.message.reply_text(
                "Usage:\n"
                "/monthly\n"
                "/monthly 2026-09"
            )
            return

    data = weight_service.get_monthly_report(reference_date)

    message = (
        "📅 Monthly Report\n"
        f"{data.start_date.strftime('%B %Y')}\n\n"
        "⚖️ Weight\n\n"
    )

    has_weight = False
    for day, w in data.daily_weights:
        if w is not None:
            has_weight = True
            message += f"{day.strftime('%d %b')} {w:.1f} kg\n"

    if not has_weight:
        message += "No weight data.\n"

    message += "\n━━━━━━━━━━\n\n"

    if data.weight_stats:
        stats = data.weight_stats
        message += (
            f"Start: {stats['start']:.1f} kg\n"
            f"Latest: {stats['latest']:.1f} kg\n"
            f"Change: {stats['change']:+.1f} kg\n"
            f"Average: {stats['average']:.1f} kg\n"
            f"Lowest: {stats['lowest']:.1f} kg\n"
            f"Highest: {stats['highest']:.1f} kg\n"
        )

    message += "\n━━━━━━━━━━\n\n🔥 Calories\n\n"

    for day, _, cals in data.daily_calories:
        message += f"{day.strftime('%d %b')} {cals:.0f} kcal\n"

    message += (
        f"\n━━━━━━━━━━\n"
        f"Total calories: {data.total_calories:.0f} kcal\n"
        f"Average per logged day: {data.average_per_logged_day:.0f} kcal\n"
        f"Food entries: {data.total_food_entries}"
    )

    await update.message.reply_text(message)
