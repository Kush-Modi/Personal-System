"""Custom application exceptions."""


class AppError(Exception):
    """Base exception for all application-level errors."""
    pass


class ConfigError(AppError):
    """Raised when configuration is invalid or missing required values."""
    pass


class ValidationError(AppError):
    """Raised when input validation fails (schema or domain)."""
    pass


class SchemaValidationError(ValidationError):
    """Raised when input structure or types violate expected schema."""
    pass


class DomainValidationError(ValidationError):
    """Raised when business logic rules are violated."""
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


class InvalidStateTransitionError(AppError):
    """Raised when an illegal lifecycle state transition is attempted."""
    pass


class AlreadyProcessedError(AppError):
    """Raised when an item has already been confirmed, rejected, or expired."""
    pass


class SessionExpiredError(AppError):
    """Raised when an interactive session (e.g. edit) has expired."""
    pass


class MediaProcessingError(AppError):
    """Raised when an image or media processing step fails."""
    pass


class AIServiceError(AppError):
    """Raised when an AI provider or operation fails."""
    pass


class AIBudgetExceededError(AIServiceError):
    """Raised when daily AI request or token budget is exhausted."""
    pass


class AIRateLimitError(AIServiceError):
    """Raised when an AI provider rate limits the request (HTTP 429)."""
    pass


class AIAuthenticationError(AIServiceError):
    """Raised when AI provider authentication fails (HTTP 401/403)."""
    pass


class AIModelUnavailableError(AIServiceError):
    """Raised when an AI model or provider endpoint is temporarily unreachable or overloaded."""
    pass


class AIParseError(AIServiceError):
    """Raised when AI output fails schema parsing or JSON validation."""
    pass


class AITimeoutError(AIServiceError):
    """Raised when an AI provider call times out."""
    pass
