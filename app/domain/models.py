"""Domain models and value objects for Personal-System."""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class ItemType(str, Enum):
    FOOD = "FOOD"
    EXPENSE = "EXPENSE"
    TASK = "TASK"
    REMINDER = "REMINDER"
    OTHER = "OTHER"

    @classmethod
    def from_str(cls, value: str) -> "ItemType":
        try:
            return cls(value.upper().strip())
        except (ValueError, AttributeError):
            return cls.OTHER


class PendingStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

    @classmethod
    def from_str(cls, value: str) -> "PendingStatus":
        try:
            return cls(value.upper().strip())
        except (ValueError, AttributeError):
            return cls.PENDING


class InputSource(str, Enum):
    COMMAND = "COMMAND"
    TEXT = "TEXT"
    PHOTO = "PHOTO"
    AI = "AI"
    MOCK = "MOCK"
    SYSTEM = "SYSTEM"
    UNKNOWN = "UNKNOWN"


@dataclass
class FoodPayload:
    food_name: str
    calories: float
    date: Optional[str] = None  # YYYY-MM-DD
    confidence: float = 1.0
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExpensePayload:
    amount: float
    category: str
    merchant: Optional[str] = None
    description: Optional[str] = None
    date: Optional[str] = None  # YYYY-MM-DD
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TaskPayload:
    title: str
    due_date: Optional[str] = None  # YYYY-MM-DD
    description: Optional[str] = None
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PendingItem:
    """Domain entity representing an unconfirmed or resolved staged item."""
    id: int
    item_type: str
    status: str
    raw_payload: Optional[str]
    structured_payload: Dict[str, Any]
    source: str = "UNKNOWN"
    confidence: float = 1.0
    image_path: Optional[str] = None
    user_notes: Optional[str] = None
    created_at: str = ""
    updated_at: Optional[str] = None
    expires_at: Optional[str] = None
    resolved_at: Optional[str] = None
    error_info: Optional[str] = None

    @property
    def is_pending(self) -> bool:
        return self.status == PendingStatus.PENDING.value

    @property
    def is_confirmed(self) -> bool:
        return self.status == PendingStatus.CONFIRMED.value

    @property
    def is_rejected(self) -> bool:
        return self.status == PendingStatus.REJECTED.value

    @property
    def is_expired(self) -> bool:
        return self.status == PendingStatus.EXPIRED.value


@dataclass
class EditSession:
    """Domain entity representing an active interactive user edit session."""
    user_id: int
    pending_item_id: int
    item_type: str
    created_at: str
    expires_at: str
