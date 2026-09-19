"""Centralized configuration management."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Attempt to load dotenv if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Optional fallback parser for .env if python-dotenv is not yet installed in dev env
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent


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

    # Storage
    data_dir: Path = field(
        default_factory=lambda: Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).resolve()
    )
    image_dir: Path = field(
        default_factory=lambda: Path(os.getenv("IMAGE_DIR", str(BASE_DIR / "data" / "images"))).resolve()
    )
    image_retention_days: int = field(
        default_factory=lambda: int(os.getenv("IMAGE_RETENTION_DAYS", "30"))
    )

    # AI Configuration
    gemini_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY")
    )
    daily_ai_request_limit: int = field(
        default_factory=lambda: int(os.getenv("DAILY_AI_REQUEST_LIMIT", "50"))
    )

    def ensure_directories(self) -> None:
        """Create necessary application directories if they don't exist."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.image_dir.mkdir(parents=True, exist_ok=True)

    def safe_dict(self) -> dict:
        """Return configuration dictionary with masked secrets for logging/status."""
        masked_token = (
            f"{self.telegram_bot_token[:4]}...{self.telegram_bot_token[-4:]}"
            if len(self.telegram_bot_token) > 8
            else ("***" if self.telegram_bot_token else "NOT_SET")
        )
        masked_gemini = (
            f"{self.gemini_api_key[:4]}...{self.gemini_api_key[-4:]}"
            if self.gemini_api_key and len(self.gemini_api_key) > 8
            else ("***" if self.gemini_api_key else "NOT_SET")
        )
        return {
            "telegram_bot_token": masked_token,
            "database_path": str(self.database_path),
            "log_level": self.log_level,
            "log_file": str(self.log_file),
            "data_dir": str(self.data_dir),
            "image_dir": str(self.image_dir),
            "image_retention_days": self.image_retention_days,
            "gemini_api_key": masked_gemini,
            "daily_ai_request_limit": self.daily_ai_request_limit,
        }


# Singleton instance
settings = Settings()
