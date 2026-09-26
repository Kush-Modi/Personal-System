"""Input processing schemas and structured results."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ProcessingResult:
    """Standardized output produced by any input processor."""
    success: bool
    item_type: str  # ItemType.value (FOOD, EXPENSE, WEIGHT, TASK, REMINDER, GENERAL_CHAT, DATA_QUERY, OTHER)
    payload: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    source: str = "UNKNOWN"  # InputSource.value
    requires_confirmation: bool = True
    response_mode: str = "ACTION"  # ACTION, QUERY, CHAT, CLARIFICATION
    raw_text: Optional[str] = None
    error_message: Optional[str] = None

