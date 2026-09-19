"""Centralized configuration management."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Attempt to load dotenv if available
try:
    from dotenv import load_dotenv
    # Explicitly load .env from BASE_DIR
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
except ImportError:
    # Optional fallback parser for .env if python-dotenv is not yet installed in dev env
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    """Application configuration container."""

    # Telegram
    telegram_bot_token: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", "")
    )

    # Database
    database_path: Path = field(
        default_factory=lambda: Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "personal.db"))).resolve()
    )

    # Logging
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper()
    )
    log_file: Path = field(
        default_factory=lambda: Path(os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "personal_system.log"))).resolve()
    )

    # Storage & Media
    data_dir: Path = field(
        default_factory=lambda: Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).resolve()
    )
    image_dir: Path = field(
        default_factory=lambda: Path(os.getenv("IMAGE_DIR", str(BASE_DIR / "data" / "images"))).resolve()
    )
    image_retention_days: int = field(
        default_factory=lambda: int(os.getenv("IMAGE_RETENTION_DAYS", "30"))
    )
    image_max_dimension: int = field(
        default_factory=lambda: int(os.getenv("IMAGE_MAX_DIMENSION", "1600"))
    )
    image_quality: int = field(
        default_factory=lambda: int(os.getenv("IMAGE_QUALITY", "80"))
    )

    # Workflow & Pending Items
    pending_item_ttl_hours: int = field(
        default_factory=lambda: int(os.getenv("PENDING_ITEM_TTL_HOURS", "48"))
    )
    edit_session_ttl_minutes: int = field(
        default_factory=lambda: int(os.getenv("EDIT_SESSION_TTL_MINUTES", "10"))
    )
    pending_review_time: str = field(
        default_factory=lambda: os.getenv("PENDING_REVIEW_TIME", "21:00")
    )

    # AI API Keys
    gemini_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY")
    )
    groq_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GROQ_API_KEY")
    )
    openrouter_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("OPENROUTER_API_KEY")
    )

    # AI Model Routing
    ai_fast_model: str = field(
        default_factory=lambda: os.getenv("AI_FAST_MODEL", "gemini-2.5-flash-lite")
    )
    ai_default_model: str = field(
        default_factory=lambda: os.getenv("AI_DEFAULT_MODEL", "gemini-2.5-flash")
    )
    ai_escalation_model: str = field(
        default_factory=lambda: os.getenv("AI_ESCALATION_MODEL", "gemini-3.8-flash")
    )
    ai_escalation_enabled: bool = field(
        default_factory=lambda: os.getenv("AI_ESCALATION_ENABLED", "false").lower() in ("true", "1", "yes")
    )

    groq_default_model: str = field(
        default_factory=lambda: os.getenv("GROQ_DEFAULT_MODEL", "openai/gpt-oss-20b")
    )
    groq_vision_model: str = field(
        default_factory=lambda: os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.6-27b")
    )
    groq_vision_fallback_enabled: bool = field(
        default_factory=lambda: os.getenv("GROQ_VISION_FALLBACK_ENABLED", "false").lower() in ("true", "1", "yes")
    )

    openrouter_default_model: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_DEFAULT_MODEL", "openrouter/free")
    )

    # AI Budgets & Guardrails
    ai_daily_request_limit: int = field(
        default_factory=lambda: int(os.getenv("AI_DAILY_REQUEST_LIMIT", os.getenv("DAILY_AI_REQUEST_LIMIT", "30")))
    )
    ai_daily_token_limit: int = field(
        default_factory=lambda: int(os.getenv("AI_DAILY_TOKEN_LIMIT", os.getenv("DAILY_AI_TOKEN_LIMIT", "50000")))
    )
    timezone: str = field(
        default_factory=lambda: os.getenv("TIMEZONE", "Asia/Kolkata")
    )
    ai_temperature: float = field(
        default_factory=lambda: float(os.getenv("AI_TEMPERATURE", "0.2"))
    )
    ai_timeout_seconds: int = field(
        default_factory=lambda: int(os.getenv("AI_TIMEOUT_SECONDS", "20"))
    )

    @property
    def daily_ai_request_limit(self) -> int:
        return self.ai_daily_request_limit

    @property
    def daily_ai_token_limit(self) -> int:
        return self.ai_daily_token_limit

    def ensure_directories(self) -> None:
        """Create necessary application directories if they don't exist."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.image_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _mask_secret(val: Optional[str]) -> str:
        if not val or not val.strip():
            return "NOT_SET"
        val = val.strip()
        if len(val) <= 8:
            return "***"
        return f"{val[:4]}...{val[-4:]}"

    def safe_dict(self) -> dict:
        """Return configuration dictionary with masked secrets for logging/status."""
        return {
            "telegram_bot_token": self._mask_secret(self.telegram_bot_token),
            "database_path": str(self.database_path),
            "log_level": self.log_level,
            "log_file": str(self.log_file),
            "data_dir": str(self.data_dir),
            "image_dir": str(self.image_dir),
            "image_retention_days": self.image_retention_days,
            "image_max_dimension": self.image_max_dimension,
            "image_quality": self.image_quality,
            "pending_item_ttl_hours": self.pending_item_ttl_hours,
            "edit_session_ttl_minutes": self.edit_session_ttl_minutes,
            "pending_review_time": self.pending_review_time,
            "gemini_api_key": self._mask_secret(self.gemini_api_key),
            "groq_api_key": self._mask_secret(self.groq_api_key),
            "openrouter_api_key": self._mask_secret(self.openrouter_api_key),
            "ai_fast_model": self.ai_fast_model,
            "ai_default_model": self.ai_default_model,
            "ai_escalation_model": self.ai_escalation_model,
            "ai_escalation_enabled": self.ai_escalation_enabled,
            "groq_default_model": self.groq_default_model,
            "groq_vision_model": self.groq_vision_model,
            "groq_vision_fallback_enabled": self.groq_vision_fallback_enabled,
            "openrouter_default_model": self.openrouter_default_model,
            "ai_daily_request_limit": self.ai_daily_request_limit,
            "ai_daily_token_limit": self.ai_daily_token_limit,
            "timezone": self.timezone,
            "ai_temperature": self.ai_temperature,
            "ai_timeout_seconds": self.ai_timeout_seconds,
        }


# Singleton instance
settings = Settings()
