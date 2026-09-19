"""Input processing schemas and structured results."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ProcessingResult:
    """Standardized output produced by any input processor."""
    success: bool
    item_type: str  # ItemType.value (FOOD, EXPENSE, TASK, etc.)
    payload: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    source: str = "UNKNOWN"  # InputSource.value
    requires_confirmation: bool = True
    raw_text: Optional[str] = None
    error_message: Optional[str] = None
