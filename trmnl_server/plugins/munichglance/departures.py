"""MVG departures API client for MunichGlance."""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime

from trmnl_server.plugins.munichglance.config import (
    MunichGlanceConfig,
    StationConfig,
    get_plugin_config,
)
from trmnl_server.plugins.munichglance.icons import TransportStyle, get_transport_style
from trmnl_server.timezone import get_timezone
from trmnl_server.timezone import now as local_now

logger = logging.getLogger(__name__)


@dataclass
class Departure:
    """Single departure from MVG API."""

    line: str  # Line name (e.g., "U3", "S8", "Bus 52")
    destination: str  # Final destination
    planned_time: datetime  # Planned departure time
    delay: int  # Delay in minutes (0 if on time)
    transport_type: str  # Transport type (e.g., "UBAHN", "SBAHN")
    cancelled: bool  # True if cancelled
    platform: str | None = None  # Platform/track if available
    messages: list[str] | None = None  # Service messages
    station_name: str | None = None  # Source station name (for grouping)

    def __post_init__(self):
        if self.messages is None:
            self.messages = []

    @property
    def actual_time(self) -> datetime:
        """Actual departure time including delay."""
        from datetime import timedelta

        return self.planned_time + timedelta(minutes=self.delay)

    @property
    def minutes_until(self) -> int:
        """Minutes until departure (including delay)."""
        from trmnl_server.timezone import now as local_now
        from trmnl_server.timezone import to_local

        delta = to_local(self.actual_time) - local_now()
        return max(0, int(delta.total_seconds() / 60))

    @property
    def style(self) -> TransportStyle:
        """Get transport styling."""
        return get_transport_style(self.transport_type)

    def format_time(self, style: str = "relative") -> str:
        """Format departure time for display.

        Args:
            style: "relative" (5 min) or "absolute" (14:32)

        Returns:
            Formatted time string
        """
        if style == "absolute":
            return self.actual_time.strftime("%H:%M")

        minutes = self.minutes_until
        if minutes == 0:
            return "now"
        elif minutes == 1:
            return "1 min"
        else:
            return f"{minutes} min"

    def format_delay(self) -> str:
        """Format delay for display.

        Returns:
            Delay string (e.g., "+3") or empty string if on time
        """
        if self.delay > 0:
            return f"+{self.delay}"
        return ""


class MultiStationClient:
    """Client for fetching departures from multiple stations with filtering."""

    def __init__(self, config: MunichGlanceConfig | None = None):
        """Initialize multi-station client.

        Args:
            config: Plugin configuration (uses global if not provided)
        """
        self.config = config or get_plugin_config()
        self._cache: list[Departure] | None = None
        self._cache_time: float = 0.0
        # Cache for station name -> (station_id, resolved_name)
        # Station IDs don't change, so we resolve once and reuse
        self._station_cache: dict[str, tuple[str, str]] = {}

    async def get_departures(self) -> list[Departure]:
        """Fetch and aggregate departures from all stations.

        Returns:
            Merged and sorted list of departures
        """
        logger.info("get_departures() called")
        now = time.time()

        # Check cache freshness
        if self._cache and (now - self._cache_time) < self.config.departures_cache_ttl:
            logger.info(f"Returning cached multi-station departures ({len(self._cache)} items)")
            return self._cache

        try:
            logger.info("Fetching fresh departures from all stations...")
            departures = await self._fetch_all_stations()
            logger.info(f"Fetched {len(departures)} departures total")
            self._cache = departures
            self._cache_time = now
            return departures
        except Exception as e:
            logger.error(f"Failed to fetch multi-station departures: {e}")
            if self._cache:
                logger.warning("Returning stale multi-station cache")
                return self._cache
            return []

    async def _resolve_stations(self) -> None:
        """Resolve all station names to IDs once and cache them."""
        if not self.config.multi_station:
            return

        from mvg import MvgApi

        for station_config in self.config.multi_station.stations:
            if station_config.station in self._station_cache:
                continue  # Already resolved

            try:
                station = await MvgApi.station_async(station_config.station)
                if station:
                    self._station_cache[station_config.station] = (
                        station["id"],
                        station["name"],
                    )
                    logger.info(f"Resolved station: {station['name']} ({station['id']})")
                else:
                    logger.error(f"Station not found: {station_config.station}")
            except Exception as e:
                logger.error(f"Failed to resolve station {station_config.station}: {e}")

    async def _fetch_all_stations(self) -> list[Departure]:
        """Fetch from all configured stations in parallel."""
        if not self.config.multi_station:
            logger.warning("No multi-station config, returning empty")
            return []

        # Resolve stations once (cached)
        if not self._station_cache:
            logger.info("Resolving station IDs (first time)...")
            await self._resolve_stations()

        logger.debug(f"Fetching departures from {len(self._station_cache)} stations")

        # Create fetch tasks for each station
        tasks = []
        for station_config in self.config.multi_station.stations:
            tasks.append(self._fetch_station(station_config))

        # Fetch all in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge all departures
        all_departures: list[Departure] = []
        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                station_name = self.config.multi_station.stations[i].station
                logger.error(f"Station {station_name} fetch failed: {result}")
                continue
            all_departures.extend(result)

        # Sort by actual departure time
        all_departures.sort(key=lambda d: d.actual_time)

        # Truncate to limit
        return all_departures[: self.config.departure_limit]

    async def _fetch_station(self, station_config: StationConfig) -> list[Departure]:
        """Fetch and filter departures for one station.

        Args:
            station_config: Configuration for this station

        Returns:
            Filtered list of departures
        """
        from mvg import MvgApi

        # Use cached station ID
        cached = self._station_cache.get(station_config.station)
        if not cached:
            logger.error(f"Station not in cache: {station_config.station}")
            return []

        station_id, station_name = cached

        # Fetch departures
        try:
            raw_departures = await MvgApi.departures_async(
                station_id,
                limit=50,  # Fetch more since we filter
                offset=self.config.offset_minutes,
            )
        except Exception as e:
            logger.error(f"Failed to fetch departures from {station_name}: {e}")
            return []

        # Process and filter departures
        departures = []
        for dep in raw_departures:
            # Parse transport type
            raw_type = dep.get("type", dep.get("transportType", ""))
            transport_type = raw_type.upper().replace("-", "").replace(" ", "")

            # Parse line name
            line = dep.get("line", dep.get("label", ""))

            # Parse destination
            destination = dep.get("destination", "")

            # Parse planned time
            planned_ts = dep.get("planned", dep.get("time", 0))
            if planned_ts > 1e12:
                planned_ts = planned_ts / 1000
            planned_time = datetime.fromtimestamp(planned_ts, tz=get_timezone())

            # Skip if too far in the future
            minutes_away = (planned_time - local_now()).total_seconds() / 60
            if minutes_away > self.config.max_minutes:
                continue

            # Apply filters if defined
            if station_config.filters:
                matched = False
                for filter_rule in station_config.filters:
                    # Get opposite direction for 'auto' handling
                    opposite_dir = None
                    if filter_rule.direction and filter_rule.direction.lower() == "auto":
                        opposite_dir = station_config.get_opposite_direction(
                            filter_rule.line or line
                        )
                        if not opposite_dir:
                            logger.warning(
                                f"No paired direction for 'auto' filter on line {filter_rule.line}"
                            )

                    if filter_rule.matches(transport_type, line, destination, opposite_dir):
                        matched = True
                        break

                if not matched:
                    continue

            # Create departure object
            departure = Departure(
                line=line,
                destination=destination,
                planned_time=planned_time,
                delay=dep.get("delay", 0) or 0,
                transport_type=transport_type,
                cancelled=dep.get("cancelled", False),
                platform=str(dep.get("platform", "")) if dep.get("platform") else None,
                messages=dep.get("messages", []),
                station_name=station_name,
            )

            # Skip cancelled if configured
            if departure.cancelled and not self.config.show_cancelled:
                continue

            departures.append(departure)

        logger.info(f"Fetched {len(departures)} departures from {station_name}")
        return departures

    @property
    def station_name(self) -> str:
        """Get display station name for header."""
        return self.config.display_station

    def clear_cache(self) -> None:
        """Clear the departures cache."""
        self._cache = None
        self._cache_time = 0.0

    @property
    def cache_age(self) -> float | None:
        """Get age of cache in seconds."""
        if self._cache_time > 0:
            return time.time() - self._cache_time
        return None
