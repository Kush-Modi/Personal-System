"""Structured application logging setup."""

import logging
import logging.handlers
from typing import Optional
from app.core.config import settings


_INITIALIZED = False


def setup_logging(
    level: Optional[str] = None,
    log_to_file: bool = True
) -> logging.Logger:
    """Initialize structured application logging."""
    global _INITIALIZED

    log_level_name = (level or settings.log_level).upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    root_logger = logging.getLogger()
    
    if _INITIALIZED:
        root_logger.setLevel(log_level)
        return logging.getLogger("personal_system")

    root_logger.setLevel(log_level)

    # Standard format
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    root_logger.addHandler(console_handler)

    # File handler with rotation (up to 5MB x 3 backups)
    if log_to_file:
        try:
            settings.ensure_directories()
            file_handler = logging.handlers.RotatingFileHandler(
                filename=str(settings.log_file),
                maxBytes=5 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(log_level)
            root_logger.addHandler(file_handler)
        except Exception as e:
            console_handler.handle(
                logging.LogRecord(
                    name="logging_setup",
                    level=logging.WARNING,
                    pathname=__file__,
                    lineno=50,
                    msg=f"Could not setup file logging: {e}",
                    args=(),
                    exc_info=None
                )
            )

    # Suppress verbose 3rd party loggers if needed
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)

    _INITIALIZED = True
    return logging.getLogger("personal_system")


def get_logger(name: str) -> logging.Logger:
    """Get a named logger instance under personal_system namespace."""
    if not _INITIALIZED:
        setup_logging()
    return logging.getLogger(f"personal_system.{name}")
