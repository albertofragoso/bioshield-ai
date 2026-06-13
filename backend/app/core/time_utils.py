from datetime import UTC, datetime, time, timedelta


def _seconds_until_midnight_utc() -> int:
    """Seconds from now until 00:00:00 UTC (when daily token budget resets)."""
    now = datetime.now(UTC)
    midnight = datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=UTC)
    return max(1, int((midnight - now).total_seconds()))
