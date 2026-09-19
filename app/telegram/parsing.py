"""Date parsing and command formatting utilities."""

from datetime import date, datetime, timedelta
from typing import Optional, Tuple


def today_date() -> date:
    """Get current local date."""
    return datetime.now().date()


def parse_date(value: Optional[str]) -> Tuple[Optional[date], Optional[str]]:
    """
    Parse user date string. Supports:
    - empty/None -> today, 'Today'
    - 'today' -> today, 'Today'
    - 'yesterday' -> yesterday, 'Yesterday'
    - 'YYYY-MM-DD' -> date, 'DD Mon YYYY'
    """
    today = today_date()
    if not value:
        return today, "Today"

    val = value.strip().lower()
    if val == "today":
        return today, "Today"
    if val == "yesterday":
        return today - timedelta(days=1), "Yesterday"

    try:
        parsed = datetime.strptime(val, "%Y-%m-%d").date()
        return parsed, parsed.strftime("%d %b %Y")
    except ValueError:
        return None, None


def format_date(d: date) -> str:
    """Format date to ISO format YYYY-MM-DD."""
    return d.isoformat()


def date_error() -> str:
    """Standard error response for invalid dates."""
    return (
        "Invalid date.\n\n"
        "Use:\n"
        "today\n"
        "yesterday\n"
        "YYYY-MM-DD"
    )
