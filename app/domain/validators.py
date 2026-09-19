"""Two-level validation layer: Level 1 (Schema) and Level 2 (Domain/Business)."""

from datetime import date, datetime
from typing import Any, Dict, Optional, Union

from app.core.exceptions import DomainValidationError, SchemaValidationError, ValidationError
from app.domain.models import ExpensePayload, FoodPayload, ItemType, TaskPayload


def _validate_iso_date(date_str: Optional[str]) -> None:
    """Validate ISO date format YYYY-MM-DD if present."""
    if not date_str:
        return
    try:
        datetime.strptime(date_str.strip(), "%Y-%m-%d")
    except ValueError:
        raise SchemaValidationError(f"Invalid date format '{date_str}'. Expected YYYY-MM-DD.")


# ==================================================
# LEVEL 1: SCHEMA VALIDATION
# ==================================================

def validate_food_schema(payload: Dict[str, Any]) -> FoodPayload:
    """Validate raw payload dictionary into a FoodPayload schema."""
    if not isinstance(payload, dict):
        raise SchemaValidationError("Payload must be a dictionary.")

    food_name = payload.get("food_name") or payload.get("name")
    if food_name is None or not isinstance(food_name, str):
        raise SchemaValidationError("Missing or invalid field 'food_name' (expected string).")

    calories_raw = payload.get("calories")
    if calories_raw is None:
        raise SchemaValidationError("Missing required field 'calories'.")

    try:
        calories = float(calories_raw)
    except (ValueError, TypeError):
        raise SchemaValidationError(f"Invalid calories value '{calories_raw}' (expected numeric).")

    date_val = payload.get("date")
    if date_val is not None and not isinstance(date_val, str):
        raise SchemaValidationError("Field 'date' must be a string in YYYY-MM-DD format.")
    _validate_iso_date(date_val)

    confidence_raw = payload.get("confidence", 1.0)
    try:
        confidence = float(confidence_raw)
    except (ValueError, TypeError):
        confidence = 1.0

    notes = payload.get("notes")
    if notes is not None and not isinstance(notes, str):
        notes = str(notes)

    return FoodPayload(
        food_name=food_name.strip(),
        calories=calories,
        date=date_val.strip() if date_val else None,
        confidence=confidence,
        notes=notes.strip() if notes else None
    )


def validate_expense_schema(payload: Dict[str, Any]) -> ExpensePayload:
    """Validate raw payload dictionary into an ExpensePayload schema."""
    if not isinstance(payload, dict):
        raise SchemaValidationError("Payload must be a dictionary.")

    amount_raw = payload.get("amount")
    if amount_raw is None:
        raise SchemaValidationError("Missing required field 'amount'.")

    try:
        amount = float(amount_raw)
    except (ValueError, TypeError):
        raise SchemaValidationError(f"Invalid amount value '{amount_raw}' (expected numeric).")

    category = payload.get("category", "General")
    if not isinstance(category, str):
        category = str(category)

    merchant = payload.get("merchant")
    if merchant is not None and not isinstance(merchant, str):
        merchant = str(merchant)

    description = payload.get("description")
    if description is not None and not isinstance(description, str):
        description = str(description)

    date_val = payload.get("date")
    if date_val is not None and not isinstance(date_val, str):
        raise SchemaValidationError("Field 'date' must be a string in YYYY-MM-DD format.")
    _validate_iso_date(date_val)

    confidence_raw = payload.get("confidence", 1.0)
    try:
        confidence = float(confidence_raw)
    except (ValueError, TypeError):
        confidence = 1.0

    return ExpensePayload(
        amount=amount,
        category=category.strip(),
        merchant=merchant.strip() if merchant else None,
        description=description.strip() if description else None,
        date=date_val.strip() if date_val else None,
        confidence=confidence
    )


def validate_task_schema(payload: Dict[str, Any]) -> TaskPayload:
    """Validate raw payload dictionary into a TaskPayload schema."""
    if not isinstance(payload, dict):
        raise SchemaValidationError("Payload must be a dictionary.")

    title = payload.get("title")
    if title is None or not isinstance(title, str):
        raise SchemaValidationError("Missing or invalid field 'title' (expected string).")

    due_date = payload.get("due_date") or payload.get("date")
    if due_date is not None and not isinstance(due_date, str):
        raise SchemaValidationError("Field 'due_date' must be a string in YYYY-MM-DD format.")
    _validate_iso_date(due_date)

    description = payload.get("description")
    if description is not None and not isinstance(description, str):
        description = str(description)

    confidence_raw = payload.get("confidence", 1.0)
    try:
        confidence = float(confidence_raw)
    except (ValueError, TypeError):
        confidence = 1.0

    return TaskPayload(
        title=title.strip(),
        due_date=due_date.strip() if due_date else None,
        description=description.strip() if description else None,
        confidence=confidence
    )


# ==================================================
# LEVEL 2: DOMAIN / BUSINESS VALIDATION
# ==================================================

def validate_food_domain(payload: FoodPayload) -> None:
    """Validate business rules for food records."""
    if not payload.food_name:
        raise DomainValidationError("Food name cannot be empty.")
    if len(payload.food_name) > 255:
        raise DomainValidationError("Food name cannot exceed 255 characters.")
    if payload.calories <= 0:
        raise DomainValidationError("Calories must be greater than 0.")
    if payload.calories > 10000:
        raise DomainValidationError("Calories cannot exceed 10,000 kcal.")


def validate_expense_domain(payload: ExpensePayload) -> None:
    """Validate business rules for expense records."""
    if payload.amount <= 0:
        raise DomainValidationError("Expense amount must be greater than 0.")
    if payload.amount > 10000000:
        raise DomainValidationError("Expense amount cannot exceed 10,000,000.")
    if not payload.category:
        raise DomainValidationError("Expense category cannot be empty.")


def validate_task_domain(payload: TaskPayload) -> None:
    """Validate business rules for task records."""
    if not payload.title:
        raise DomainValidationError("Task title cannot be empty.")
    if len(payload.title) > 255:
        raise DomainValidationError("Task title cannot exceed 255 characters.")


# ==================================================
# COMPREHENSIVE VALIDATOR
# ==================================================

def validate_payload(item_type: Union[ItemType, str], payload: Dict[str, Any]) -> Union[FoodPayload, ExpensePayload, TaskPayload, Dict[str, Any]]:
    """
    Execute full Level 1 (Schema) and Level 2 (Domain) validation.
    Returns typed payload dataclass on success.
    """
    item_enum = ItemType.from_str(item_type) if isinstance(item_type, str) else item_type

    if item_enum == ItemType.FOOD:
        food_obj = validate_food_schema(payload)
        validate_food_domain(food_obj)
        return food_obj

    elif item_enum == ItemType.EXPENSE:
        exp_obj = validate_expense_schema(payload)
        validate_expense_domain(exp_obj)
        return exp_obj

    elif item_enum == ItemType.TASK:
        task_obj = validate_task_schema(payload)
        validate_task_domain(task_obj)
        return task_obj

    else:
        # Fallback for OTHER/untyped
        if not isinstance(payload, dict):
            raise SchemaValidationError("Payload must be a dictionary.")
        return payload
