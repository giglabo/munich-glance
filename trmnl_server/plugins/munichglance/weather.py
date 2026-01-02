"""Open-Meteo weather API client for MunichGlance."""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import httpx

from trmnl_server.plugins.munichglance.config import MunichGlanceConfig, get_plugin_config
from trmnl_server.plugins.munichglance.icons import WeatherInfo, get_weather_info

logger = logging.getLogger(__name__)


@dataclass
class WeatherData:
    """Current weather data from Open-Meteo."""

    temperature: float  # Temperature in configured units
    weather_code: int  # WMO weather code
    is_day: bool  # True if daytime

    # Optional additional data
    humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    precipitation: Optional[float] = None

    # Metadata
    fetched_at: float = 0.0  # Unix timestamp when fetched

    @property
    def info(self) -> WeatherInfo:
        """Get weather info for current conditions."""
        return get_weather_info(self.weather_code, self.is_day)

    @property
    def description(self) -> str:
        """Human-readable weather description."""
        return self.info.description

    @property
    def icon(self) -> str:
        """Text icon for display."""
        return self.info.icon

    def format_temperature(self, units: str = "celsius") -> str:
        """Format temperature with units.

        Args:
            units: "celsius" or "fahrenheit"

        Returns:
            Formatted temperature string (e.g., "12°C")
        """
        if units == "fahrenheit":
            temp_f = (self.temperature * 9 / 5) + 32
            return f"{temp_f:.0f}°F"
        return f"{self.temperature:.0f}°C"


class WeatherClient:
    """Async client for Open-Meteo weather API."""

    API_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, config: Optional[MunichGlanceConfig] = None):
        """Initialize weather client.

        Args:
            config: Plugin configuration (uses global if not provided)
        """
        self.config = config or get_plugin_config()
        self._cache: Optional[WeatherData] = None
        self._cache_time: float = 0.0

    async def get_weather(self) -> Optional[WeatherData]:
        """Fetch current weather with caching.

        Returns:
            WeatherData or None on failure
        """
        now = time.time()

        # Check cache freshness
        if self._cache and (now - self._cache_time) < self.config.weather_cache_ttl:
            logger.debug("Returning cached weather data")
            return self._cache

        # Fetch fresh data
        try:
            data = await self._fetch_weather()
            if data:
                self._cache = data
                self._cache_time = now
                return data
        except Exception as e:
            logger.error(f"Failed to fetch weather: {e}")

        # Return stale cache if available
        if self._cache:
            logger.warning("Returning stale weather cache")
            return self._cache

        return None

    async def _fetch_weather(self) -> Optional[WeatherData]:
        """Make API request to Open-Meteo.

        Returns:
            WeatherData or None on failure
        """
        params = {
            "latitude": self.config.weather_lat,
            "longitude": self.config.weather_lon,
            "current": "temperature_2m,weather_code,is_day,relative_humidity_2m,wind_speed_10m,precipitation",
            "timezone": "Europe/Berlin",
        }

        # Convert temperature units if needed
        if self.config.weather_units == "fahrenheit":
            params["temperature_unit"] = "fahrenheit"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.API_URL, params=params)
                response.raise_for_status()
                data = response.json()

            current = data.get("current", {})

            weather_data = WeatherData(
                temperature=current.get("temperature_2m", 0.0),
                weather_code=current.get("weather_code", 0),
                is_day=bool(current.get("is_day", 1)),
                humidity=current.get("relative_humidity_2m"),
                wind_speed=current.get("wind_speed_10m"),
                precipitation=current.get("precipitation"),
                fetched_at=time.time(),
            )

            logger.info(
                f"Weather fetched: {weather_data.temperature}°, "
                f"code={weather_data.weather_code} ({weather_data.description})"
            )

            return weather_data

        except httpx.HTTPStatusError as e:
            logger.error(f"Weather API HTTP error: {e.response.status_code}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Weather API request error: {e}")
            raise
        except Exception as e:
            logger.error(f"Weather API error: {e}")
            raise

    def clear_cache(self) -> None:
        """Clear the weather cache."""
        self._cache = None
        self._cache_time = 0.0

    @property
    def cache_age(self) -> Optional[float]:
        """Get age of cache in seconds."""
        if self._cache_time > 0:
            return time.time() - self._cache_time
        return None
