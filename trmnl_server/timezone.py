"""Service timezone helpers.

This is a wall-clock dashboard: refresh schedules, sleep windows and departure
countdowns are all expressed in local time. Containers run with TZ=UTC, so a bare
``datetime.now()`` silently evaluates those rules two hours off in summer. Every
"what time is it" decision must therefore go through here, which resolves the
single configured zone (``server.timezone``, e.g. Europe/Berlin -> CET/CEST with
automatic DST).
"""

from datetime import datetime
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Europe/Berlin"


def get_timezone() -> ZoneInfo:
    """Return the configured service timezone."""
    # Imported lazily: trmnl_server.config imports the config loader at module
    # level, so a top-level import here would be circular.
    from trmnl_server.config import get_config

    try:
        return ZoneInfo(get_config().timezone)
    except Exception:
        return ZoneInfo(DEFAULT_TIMEZONE)


def now() -> datetime:
    """Current time as an aware datetime in the service timezone."""
    return datetime.now(get_timezone())


def to_local(value: datetime) -> datetime:
    """Return ``value`` as an aware datetime in the service timezone.

    Naive values are assumed to already be local wall-clock time, which keeps
    mixed aware/naive arithmetic from raising.
    """
    tz = get_timezone()
    if value.tzinfo is None:
        return value.replace(tzinfo=tz)
    return value.astimezone(tz)
