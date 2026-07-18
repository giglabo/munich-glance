"""Configuration for MunichGlance plugin."""

import logging
from dataclasses import dataclass, field
from datetime import time

from trmnl_server.config_loader import get_config_loader

logger = logging.getLogger(__name__)


def _parse_bool(value: bool | str, default: bool = False) -> bool:
    """Parse a boolean value from YAML (could be bool or string)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return default


# =============================================================================
# Refresh Schedule Dataclasses
# =============================================================================


@dataclass
class TimeInterval:
    """A time interval with custom refresh rate.

    Supports midnight-crossing intervals like 23:00-01:00.
    """

    start: time  # e.g., time(7, 0) for 07:00
    end: time  # e.g., time(8, 0) for 08:00
    refresh: int  # Refresh rate in seconds

    @classmethod
    def from_string(cls, time_str: str, refresh: int) -> "TimeInterval":
        """Parse '07:00-08:00' format.

        Args:
            time_str: Time range in 'HH:MM-HH:MM' format
            refresh: Refresh rate in seconds

        Returns:
            TimeInterval instance
        """
        parts = time_str.split("-")
        start_h, start_m = map(int, parts[0].strip().split(":"))
        end_h, end_m = map(int, parts[1].strip().split(":"))
        return cls(
            start=time(start_h, start_m),
            end=time(end_h, end_m),
            refresh=refresh,
        )

    def contains(self, t: time) -> bool:
        """Check if time falls within interval.

        Handles midnight-crossing intervals (e.g., 23:00-01:00).

        Args:
            t: Time to check

        Returns:
            True if time is within interval
        """
        if self.start <= self.end:
            # Normal interval (e.g., 07:00-08:00)
            return self.start <= t < self.end
        else:
            # Midnight-crossing interval (e.g., 23:00-01:00)
            return t >= self.start or t < self.end


@dataclass
class DaySchedule:
    """Refresh schedule for a single day."""

    default: int  # Default refresh in seconds
    intervals: list[TimeInterval] = field(default_factory=list)

    def get_refresh_rate(self, current_time: time) -> int:
        """Get refresh rate for given time.

        First matching interval wins.

        Args:
            current_time: Current time

        Returns:
            Refresh rate in seconds
        """
        for interval in self.intervals:
            if interval.contains(current_time):
                return interval.refresh
        return self.default

    @classmethod
    def from_dict(cls, data: dict, global_default: int) -> "DaySchedule":
        """Parse from YAML dictionary.

        Args:
            data: Day schedule data with 'default' and 'intervals'
            global_default: Fallback default if not specified

        Returns:
            DaySchedule instance
        """
        intervals = []
        for interval_data in data.get("intervals", []):
            intervals.append(
                TimeInterval.from_string(
                    interval_data["time"],
                    interval_data["refresh"],
                )
            )
        return cls(
            default=data.get("default", global_default),
            intervals=intervals,
        )


@dataclass
class RefreshSchedule:
    """Complete weekly refresh schedule."""

    default: int = 300  # Global fallback: 5 minutes

    # Day-specific schedules
    mon: DaySchedule | None = None
    tue: DaySchedule | None = None
    wed: DaySchedule | None = None
    thu: DaySchedule | None = None
    fri: DaySchedule | None = None
    sat: DaySchedule | None = None
    sun: DaySchedule | None = None

    def get_refresh_rate(self, weekday: int, current_time: time) -> int:
        """Get refresh rate for given weekday and time.

        Args:
            weekday: Day of week (0=Monday, 6=Sunday)
            current_time: Current time

        Returns:
            Refresh rate in seconds
        """
        day_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        day_schedule: DaySchedule | None = getattr(self, day_names[weekday], None)

        if day_schedule:
            return day_schedule.get_refresh_rate(current_time)
        return self.default

    @classmethod
    def from_dict(cls, data: dict) -> "RefreshSchedule":
        """Parse from YAML dictionary.

        Args:
            data: Schedule data with 'default' and day keys

        Returns:
            RefreshSchedule instance
        """
        global_default = data.get("default", 300)
        schedule = cls(default=global_default)

        day_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        for day in day_names:
            if day in data and data[day]:
                day_data = data[day]
                setattr(
                    schedule,
                    day,
                    DaySchedule.from_dict(day_data, global_default),
                )

        return schedule


# =============================================================================
# Multi-Station Departures Dataclasses
# =============================================================================


@dataclass
class DepartureFilter:
    """Filter for specific line/direction combinations."""

    type: str  # Transport type: UBAHN, SBAHN, TRAM, BUS
    line: str | None = None  # Line name (e.g., "U3", "53") or None for all
    direction: str | None = None  # Destination, "auto", or None

    def matches(
        self,
        transport_type: str,
        line: str,
        destination: str,
        opposite_direction: str | None = None,
    ) -> bool:
        """Check if a departure matches this filter.

        Args:
            transport_type: Departure transport type
            line: Departure line name
            destination: Departure destination
            opposite_direction: For 'auto', the direction to NOT match

        Returns:
            True if departure matches filter
        """
        # Type must match (normalized)
        if transport_type.upper() != self.type.upper():
            return False

        # Line filter (if specified)
        if self.line:
            # Normalize line names: strip "Bus ", "Tram " prefixes
            normalized_line = line.replace("Bus ", "").replace("Tram ", "").strip()
            if normalized_line != self.line:
                return False

        # Direction filter
        if self.direction:
            if self.direction.lower() == "auto":
                # Match anything NOT going to the opposite direction
                if opposite_direction and destination == opposite_direction:
                    return False
            else:
                # Exact match (case-insensitive)
                if destination.lower() != self.direction.lower():
                    return False

        return True


@dataclass
class StationConfig:
    """Configuration for fetching departures from one station."""

    station: str  # Station name
    filters: list[DepartureFilter] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "StationConfig":
        """Parse from YAML dictionary.

        Args:
            data: Station config with 'station' and 'filters'

        Returns:
            StationConfig instance
        """
        filters = []
        for filter_data in data.get("filters", []):
            filters.append(
                DepartureFilter(
                    type=filter_data["type"],
                    line=filter_data.get("line"),
                    direction=filter_data.get("direction"),
                )
            )
        return cls(
            station=data["station"],
            filters=filters,
        )

    def get_opposite_direction(self, line: str) -> str | None:
        """Find the opposite direction for a line with 'auto' filter.

        Looks for an explicit direction filter for the same line.

        Args:
            line: Line name to find opposite direction for

        Returns:
            The explicit direction (what 'auto' should NOT match), or None
        """
        for f in self.filters:
            if f.line == line and f.direction and f.direction.lower() != "auto":
                return f.direction
        return None


@dataclass
class MultiStationConfig:
    """Configuration for multi-station departure aggregation."""

    display_station: str  # Name shown in header
    stations: list[StationConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: list, display_station: str) -> "MultiStationConfig":
        """Parse from YAML list.

        Args:
            data: List of station configurations
            display_station: Name to show in display header

        Returns:
            MultiStationConfig instance
        """
        stations = [StationConfig.from_dict(s) for s in data]
        return cls(
            display_station=display_station,
            stations=stations,
        )


# =============================================================================
# Main Plugin Configuration
# =============================================================================


@dataclass
class MunichGlanceConfig:
    """Configuration for MunichGlance plugin.

    All settings are loaded from config/app-config.yaml.
    Sensitive values can use ${ENV_VAR} syntax for env var substitution.
    """

    # Multi-Station Configuration
    display_station: str = "Munich"  # Name shown in display header
    multi_station: MultiStationConfig | None = None  # Multi-station config

    # MVG Shared Settings
    departure_limit: int = 10
    offset_minutes: int = 0  # Walking time to station
    max_minutes: int = 60  # Don't show departures more than X minutes away

    # Weather Configuration
    weather_lat: float = 48.1351  # Munich latitude
    weather_lon: float = 11.5820  # Munich longitude
    weather_units: str = "celsius"  # celsius or fahrenheit

    # Refresh Schedule
    refresh_schedule: RefreshSchedule | None = None  # Time-based refresh
    departures_refresh_interval: int = 60  # Fallback refresh (seconds)
    weather_refresh_interval: int = 900  # 15 minutes

    # Cache TTLs (seconds)
    departures_cache_ttl: int = 30  # Short cache for API failure fallback
    weather_cache_ttl: int = 900  # Match refresh interval

    # Display Options
    show_delays: bool = True
    show_platform: bool = False
    show_cancelled: bool = True
    show_groups: bool = True  # Show station headers when grouping departures
    compact_directions: bool = (
        False  # Show all times for each direction on one row (e.g., "5 min / 7 min")
    )
    time_format: str = "relative"  # relative (5 min) or absolute (14:32)
    font_scale: float = 1.0  # Scale factor for fonts (0.8 = smaller, 1.2 = larger)
    timezone: str = "Europe/Berlin"  # Timezone for displaying times

    @classmethod
    def from_yaml(cls, config_file: str | None = None) -> "MunichGlanceConfig":
        """Load configuration from YAML file."""
        loader = get_config_loader(config_file=config_file)

        # Parse refresh schedule
        refresh_schedule = None
        schedule_data = loader.get_section("refresh_schedule")
        if schedule_data:
            refresh_schedule = RefreshSchedule.from_dict(schedule_data)

        # Parse multi-station config
        multi_station = None
        display_station = loader.get("mvg", "display_station", "Munich")
        departures_data = loader.get_section("departures")
        if departures_data and isinstance(departures_data, list):
            multi_station = MultiStationConfig.from_dict(departures_data, display_station)

        return cls(
            display_station=display_station,
            multi_station=multi_station,
            departure_limit=int(loader.get("mvg", "departure_limit", 10)),
            offset_minutes=int(loader.get("mvg", "offset_minutes", 0)),
            max_minutes=int(loader.get("mvg", "max_minutes", 60)),
            weather_lat=float(loader.get("weather", "latitude", 48.1351)),
            weather_lon=float(loader.get("weather", "longitude", 11.5820)),
            weather_units=loader.get("weather", "units", "celsius"),
            refresh_schedule=refresh_schedule,
            departures_refresh_interval=int(loader.get("mvg", "refresh_interval", 60)),
            weather_refresh_interval=int(loader.get("weather", "refresh_interval", 900)),
            departures_cache_ttl=int(loader.get("mvg", "cache_ttl", 30)),
            weather_cache_ttl=int(loader.get("weather", "cache_ttl", 900)),
            show_delays=_parse_bool(loader.get("mvg", "show_delays", True), True),
            show_platform=_parse_bool(loader.get("mvg", "show_platform", False), False),
            show_cancelled=_parse_bool(loader.get("mvg", "show_cancelled", True), True),
            show_groups=_parse_bool(loader.get("mvg", "show_groups", True), True),
            compact_directions=_parse_bool(loader.get("mvg", "compact_directions", False), False),
            time_format=loader.get("mvg", "time_format", "relative"),
            font_scale=float(loader.get("mvg", "font_scale", 1.0)),
            timezone=loader.get("server", "timezone", "Europe/Berlin"),
        )


# Global config instance
_config: MunichGlanceConfig | None = None


def get_plugin_config(config_file: str | None = None) -> MunichGlanceConfig:
    """Get or create the plugin config instance."""
    global _config
    if _config is None:
        _config = MunichGlanceConfig.from_yaml(config_file)
    return _config


def reload_plugin_config(config_file: str | None = None) -> MunichGlanceConfig:
    """Reload plugin configuration from YAML."""
    global _config
    _config = MunichGlanceConfig.from_yaml(config_file)
    return _config
