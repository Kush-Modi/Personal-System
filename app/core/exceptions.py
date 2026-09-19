"""Custom application exceptions."""


class AppError(Exception):
    """Base exception for all application-level errors."""
    pass


class ConfigError(AppError):
    """Raised when configuration is invalid or missing required values."""
    pass


class ValidationError(AppError):
    """Raised when input validation fails."""
    pass


class NotFoundError(AppError):
    """Raised when a requested resource is not found."""
    pass


class DatabaseError(AppError):
    """Raised when a database operation fails."""
    pass


class MigrationError(DatabaseError):
    """Raised when database migration encounters an issue."""
    pass


class AIServiceError(AppError):
    """Raised when an AI provider or operation fails."""
    pass
