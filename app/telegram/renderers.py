"""Generic Markdown preview and response renderers for pending items and confirmations."""

from typing import Any, Optional

from app.domain.models import ItemType, PendingItem


def render_pending_preview(item: PendingItem) -> str:
    """Render a human-readable preview of a pending item for Telegram review."""
    payload = item.structured_payload
    type_str = item.item_type.upper()

    message = f"🔎 *Review Item #{item.id}*\n\n"

    if type_str == ItemType.FOOD.value:
        name = payload.get("food_name") or payload.get("name", "Food item")
        calories = payload.get("calories", 0)
        date_str = payload.get("date")
        notes = payload.get("notes") or item.user_notes

        message += f"🍽 *Food:* {name}\n"
        message += f"🔥 *Calories:* {calories:.0f} kcal\n"
        if date_str:
            message += f"📅 *Date:* {date_str}\n"
        if notes:
            message += f"📝 *Notes:* {notes}\n"

    elif type_str == ItemType.EXPENSE.value:
        amount = payload.get("amount", 0)
        category = payload.get("category", "General")
        merchant = payload.get("merchant")
        desc = payload.get("description")
        date_str = payload.get("date")
        mismatch_warning = payload.get("mismatch_warning")
        items = payload.get("items", [])

        if items:
            message = f"🧾 *Receipt Review #{item.id}*\n\n"
        else:
            message += f"💳 *Expense:* ₹{amount:.2f}\n"

        if merchant:
            message += f"🏪 *Merchant:* {merchant}\n"
        if date_str:
            message += f"📅 *Date:* {date_str}\n"

        if items:
            message += "\n*Items:*\n"
            for it in items:
                qty_str = f" × {it['quantity']:.0f}" if it.get("quantity") and it['quantity'] != 1 else ""
                message += f"• {it['name']}{qty_str} — ₹{it['total_price']:.2f}\n"
            if payload.get("subtotal") is not None:
                message += f"Subtotal: ₹{payload['subtotal']:.2f}\n"
            if payload.get("tax"):
                message += f"Tax: ₹{payload['tax']:.2f}\n"
            if payload.get("discount"):
                message += f"Discount: -₹{payload['discount']:.2f}\n"
            message += f"\n💳 *Total:* ₹{amount:.2f}\n"

        message += f"🏷 *Category:* {category}\n"
        if desc and not items:
            message += f"📝 *Details:* {desc}\n"

        if mismatch_warning:
            message += f"\n{mismatch_warning}\n"

    elif type_str == ItemType.WEIGHT.value:
        weight_kg = payload.get("weight_kg", 0.0)
        date_str = payload.get("date")
        unit = payload.get("unit_original", "kg")

        message += f"⚖️ *Weight:* {weight_kg:.1f} kg\n"
        if date_str:
            message += f"📅 *Date:* {date_str}\n"
        if unit != "kg":
            message += f"ℹ️ *Original Unit:* {unit}\n"

    elif type_str == ItemType.TASK.value:
        title = payload.get("title", "Task")
        due_date = payload.get("due_date") or payload.get("date")
        desc = payload.get("description")

        message += f"📋 *Task:* {title}\n"
        if due_date:
            message += f"📅 *Due:* {due_date}\n"
        if desc:
            message += f"📝 *Details:* {desc}\n"

    elif type_str == ItemType.REMINDER.value:
        rem_text = payload.get("reminder_text", "Reminder")
        remind_at = payload.get("remind_at")
        recurrence = payload.get("recurrence_rule")

        message += f"🔔 *Reminder:* {rem_text}\n"
        if remind_at:
            message += f"⏰ *Time:* {remind_at}\n"
        if recurrence:
            message += f"🔁 *Recurrence:* {recurrence}\n"


    else:
        message += f"📝 *Type:* {type_str}\n"
        for k, v in payload.items():
            message += f"• *{k}:* {v}\n"

    # Approximate confidence indicator (only show if < 0.99 and valid)
    if item.confidence and 0.0 < item.confidence < 0.99:
        message += f"\n🎯 *Confidence:* ~{item.confidence * 100:.0f}%\n"

    if item.source and item.source not in ("UNKNOWN", "COMMAND"):
        message += f"📡 *Source:* {item.source}\n"

    return message.strip()


def render_saved_confirmation(item: PendingItem, domain_record: Any) -> str:
    """Render confirmation message when an item is saved."""
    payload = item.structured_payload
    type_str = item.item_type.upper()

    if type_str == ItemType.FOOD.value:
        name = payload.get("food_name", "Food item")
        cals = payload.get("calories", 0)
        return f"✅ *Saved to Food Log!*\n\n🍽 {name} — {cals:.0f} kcal"

    elif type_str == ItemType.EXPENSE.value:
        amount = payload.get("amount", 0)
        cat = payload.get("category", "Expense")
        return f"✅ *Saved to Expenses!*\n\n💳 {cat} — ₹{amount:.2f}"

    elif type_str == ItemType.WEIGHT.value:
        weight_kg = payload.get("weight_kg", 0.0)
        date_str = payload.get("date", "today")
        return f"✅ *Saved to Weight Log!*\n\n⚖️ {weight_kg:.1f} kg ({date_str})"

    elif type_str == ItemType.TASK.value:
        title = payload.get("title", "Task")
        return f"✅ *Task Created!*\n\n📋 {title}"

    elif type_str == ItemType.REMINDER.value:
        text = payload.get("reminder_text", "Reminder")
        rem_at = payload.get("remind_at", "")
        return f"✅ *Reminder Set!*\n\n🔔 {text}\n⏰ {rem_at}"

    return f"✅ *Saved Item #{item.id} successfully.*"



def render_rejected_confirmation(item: PendingItem) -> str:
    """Render message when an item is rejected."""
    return f"❌ *Item #{item.id} rejected and discarded.*"


def render_edit_prompt(item: PendingItem) -> str:
    """Render editing instructions for user."""
    payload = item.structured_payload
    type_str = item.item_type.upper()

    if type_str == ItemType.FOOD.value:
        curr_name = payload.get("food_name", "Food name")
        curr_cals = payload.get("calories", 400)
        return (
            f"✏️ *Editing Food Item #{item.id}*\n\n"
            f"Send the corrected food in this format:\n"
            f"`Food Name, Calories`\n\n"
            f"*Example:*\n"
            f"`{curr_name}, {curr_cals:.0f}`"
        )

    elif type_str == ItemType.EXPENSE.value:
        curr_amt = payload.get("amount", 100)
        curr_cat = payload.get("category", "Groceries")
        return (
            f"✏️ *Editing Expense Item #{item.id}*\n\n"
            f"Send the corrected expense in this format:\n"
            f"`Amount, Category, Merchant`\n\n"
            f"*Example:*\n"
            f"`{curr_amt}, {curr_cat}, Store Name`"
        )

    elif type_str == ItemType.WEIGHT.value:
        curr_weight = payload.get("weight_kg", 75.0)
        return (
            f"✏️ *Editing Weight Item #{item.id}*\n\n"
            f"Send the corrected weight in this format:\n"
            f"`WeightInKg`\n\n"
            f"*Example:*\n"
            f"`{curr_weight:.1f}`"
        )

    elif type_str == ItemType.TASK.value:
        curr_title = payload.get("title", "Task title")
        return (
            f"✏️ *Editing Task Item #{item.id}*\n\n"
            f"Send the corrected title in this format:\n"
            f"`Task Title`\n\n"
            f"*Example:*\n"
            f"`{curr_title}`"
        )

    return f"✏️ Send corrected data for item #{item.id}."
