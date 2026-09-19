"""System operations and health monitoring service."""

from app.core.health import SystemHealthReport, get_system_health


class SystemService:
    """Service encapsulating system diagnostic checks and status reporting."""

    def get_health_status(self) -> SystemHealthReport:
        """Run system diagnostics and return structured report."""
        return get_system_health()

    def get_formatted_status_message(self) -> str:
        """Return human-readable markdown status message for Telegram /status."""
        report = self.get_health_status()
        return report.to_formatted_message()
