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

        message += f"💳 *Expense:* ₹{amount:.2f}\n"
        message += f"🏷 *Category:* {category}\n"
        if merchant:
            message += f"🏪 *Merchant:* {merchant}\n"
        if desc:
            message += f"📝 *Details:* {desc}\n"
        if date_str:
            message += f"📅 *Date:* {date_str}\n"

    elif type_str == ItemType.TASK.value:
        title = payload.get("title", "Task")
        due_date = payload.get("due_date") or payload.get("date")
        desc = payload.get("description")

        message += f"📋 *Task:* {title}\n"
        if due_date:
            message += f"📅 *Due:* {due_date}\n"
        if desc:
            message += f"📝 *Details:* {desc}\n"

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

    elif type_str == ItemType.TASK.value:
        title = payload.get("title", "Task")
        return f"✅ *Task Created!*\n\n📋 {title}"

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
