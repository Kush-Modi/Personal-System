"""System health checking and status diagnostics."""

import os
import shutil
import sqlite3
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("health")

START_TIME = time.time()


@dataclass
class ComponentHealth:
    name: str
    status: str  # "OK", "DEGRADED", "ERROR"
    details: str
    response_time_ms: float = 0.0


@dataclass
class SystemHealthReport:
    overall_status: str  # "HEALTHY", "DEGRADED", "UNHEALTHY"
    timestamp: str
    uptime_seconds: float
    components: Dict[str, ComponentHealth] = field(default_factory=dict)

    def to_formatted_message(self) -> str:
        """Format health report into a concise Telegram Markdown message."""
        uptime_hours = self.uptime_seconds / 3600
        uptime_str = f"{uptime_hours:.1f} hrs" if uptime_hours >= 1 else f"{self.uptime_seconds / 60:.1f} mins"
        
        status_emoji = "🟢" if self.overall_status == "HEALTHY" else ("🟡" if self.overall_status == "DEGRADED" else "🔴")

        message = (
            f"🖥 *System Status:* {status_emoji} *{self.overall_status}*\n"
            f"⏱ *Uptime:* {uptime_str}\n"
            f"📅 *Timestamp:* {self.timestamp}\n\n"
            f"📊 *Components:*\n"
        )

        for name, comp in self.components.items():
            icon = "✅" if comp.status == "OK" else ("⚠️" if comp.status == "DEGRADED" else "❌")
            message += f"• {icon} *{name}*: {comp.details} ({comp.response_time_ms:.0f}ms)\n"

        return message


def check_database() -> ComponentHealth:
    """Check database connection and table integrity."""
    start = time.perf_counter()
    try:
        if not settings.database_path.exists():
            return ComponentHealth(
                name="Database",
                status="DEGRADED",
                details="DB file does not exist yet",
                response_time_ms=(time.perf_counter() - start) * 1000
            )

        conn = sqlite3.connect(settings.database_path, timeout=3.0)
        cursor = conn.cursor()
        cursor.execute("PRAGMA quick_check;")
        result = cursor.fetchone()
        conn.close()

        status = "OK" if result and result[0] == "ok" else "ERROR"
        details = "Connected & integrity OK" if status == "OK" else f"Integrity check: {result}"
        return ComponentHealth(
            name="Database",
            status=status,
            details=details,
            response_time_ms=(time.perf_counter() - start) * 1000
        )
    except Exception as e:
        return ComponentHealth(
            name="Database",
            status="ERROR",
            details=f"Connection failed: {e}",
            response_time_ms=(time.perf_counter() - start) * 1000
        )


def check_disk_storage() -> ComponentHealth:
    """Check available disk space for data and logs."""
    start = time.perf_counter()
    try:
        check_path = settings.data_dir if settings.data_dir.exists() else settings.database_path.parent
        usage = shutil.disk_usage(check_path)
        free_gb = usage.free / (1024 ** 3)
        total_gb = usage.total / (1024 ** 3)
        
        status = "OK" if free_gb > 0.5 else ("DEGRADED" if free_gb > 0.1 else "ERROR")
        return ComponentHealth(
            name="Disk Storage",
            status=status,
            details=f"{free_gb:.1f} GB free of {total_gb:.1f} GB",
            response_time_ms=(time.perf_counter() - start) * 1000
        )
    except Exception as e:
        return ComponentHealth(
            name="Disk Storage",
            status="DEGRADED",
            details=f"Storage check failed: {e}",
            response_time_ms=(time.perf_counter() - start) * 1000
        )


def check_telegram_api() -> ComponentHealth:
    """Check network connectivity to Telegram API."""
    start = time.perf_counter()
    try:
        req = urllib.request.Request(
            "https://api.telegram.org",
            headers={"User-Agent": "Personal-System-Health-Check"}
        )
        with urllib.request.urlopen(req, timeout=4.0) as response:
            code = response.getcode()
            status = "OK" if code in (200, 404, 400) else "DEGRADED"
            return ComponentHealth(
                name="Telegram API",
                status=status,
                details="Network reachable",
                response_time_ms=(time.perf_counter() - start) * 1000
            )
    except Exception as e:
        return ComponentHealth(
            name="Telegram API",
            status="ERROR",
            details="Unreachable / Network issue",
            response_time_ms=(time.perf_counter() - start) * 1000
        )


def get_system_health() -> SystemHealthReport:
    """Run all diagnostics and assemble system health report."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    uptime = time.time() - START_TIME

    components = {
        "Database": check_database(),
        "Disk": check_disk_storage(),
        "Telegram API": check_telegram_api()
    }

    statuses = [comp.status for comp in components.values()]
    if any(s == "ERROR" for s in statuses):
        overall = "UNHEALTHY"
    elif any(s == "DEGRADED" for s in statuses):
        overall = "DEGRADED"
    else:
        overall = "HEALTHY"

    return SystemHealthReport(
        overall_status=overall,
        timestamp=now_str,
        uptime_seconds=uptime,
        components=components
    )
