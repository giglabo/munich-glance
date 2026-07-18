"""MunichGlance plugin for TRMNL BYOS server."""

import asyncio
import logging
from datetime import datetime

from trmnl_server.config import get_config
from trmnl_server.plugins.base import PluginBase, PluginOutput
from trmnl_server.plugins.munichglance.config import get_plugin_config
from trmnl_server.plugins.munichglance.departures import MultiStationClient
from trmnl_server.plugins.munichglance.renderer import MunichGlanceRenderer
from trmnl_server.plugins.munichglance.weather import WeatherClient

logger = logging.getLogger(__name__)


class MunichGlancePlugin(PluginBase):
    """TRMNL plugin displaying Munich transit departures and weather.

    This plugin fetches real-time departure data from the MVG API and
    current weather from Open-Meteo, then renders them on an 800x480
    e-ink display.
    """

    # Plugin identity
    BASENAME = "munichglance"
    DISPLAY_NAME = "Munich Glance"

    # Registration
    AUTO_REGISTER = True
    SET_PRIMARY = True
    REGISTRY_ORDER = 10

    # Output
    OUTPUT_SUBDIR = "munichglance"

    def __init__(self):
        """Initialize MunichGlance plugin."""
        super().__init__()

        self.plugin_config = get_plugin_config()
        self.weather_client = WeatherClient(self.plugin_config)
        self.departures_client = MultiStationClient(self.plugin_config)
        self.renderer = MunichGlanceRenderer(
            config=self.plugin_config,
            fonts_dir=get_config().fonts_dir,
        )

        logger.info(f"MunichGlance plugin initialized for: {self.plugin_config.display_station}")
        logger.info(f"Multi-station config present: {self.plugin_config.multi_station is not None}")
        if self.plugin_config.multi_station:
            logger.info(
                f"Configured stations: {[s.station for s in self.plugin_config.multi_station.stations]}"
            )

    @property
    def REFRESH_INTERVAL(self) -> int:  # noqa: N802  (overrides uppercase base-class constant)
        """Dynamic refresh interval from config."""
        return self.plugin_config.departures_refresh_interval

    def get_content_ttl(self) -> int:
        """Return content TTL based on departures refresh interval."""
        return self.plugin_config.departures_refresh_interval

    def get_dynamic_refresh_rate(self) -> int:
        """Get refresh rate based on current day/time.

        Uses the refresh_schedule if configured, otherwise falls back
        to the static departures_refresh_interval.

        Returns:
            Refresh rate in seconds
        """
        if not self.plugin_config.refresh_schedule:
            return self.plugin_config.departures_refresh_interval

        now = datetime.now()
        return self.plugin_config.refresh_schedule.get_refresh_rate(
            weekday=now.weekday(),  # 0=Monday
            current_time=now.time(),
        )

    async def run(self, **kwargs) -> PluginOutput | None:
        """Execute plugin: fetch data and generate display image.

        Args:
            **kwargs: Additional arguments including:
                - output_dir: Path to save generated images
                - config: Server configuration

        Returns:
            PluginOutput with generated BMP/PNG images
        """
        output_dir = kwargs.get("output_dir")
        if not output_dir:
            server_config = get_config()
            output_dir = self.get_output_dir(server_config.generated_dir)

        errors = []

        # Fetch weather and departures concurrently
        weather_task = self.weather_client.get_weather()
        departures_task = self.departures_client.get_departures()

        try:
            weather, departures = await asyncio.gather(
                weather_task,
                departures_task,
                return_exceptions=True,
            )

            # Handle exceptions from gather
            if isinstance(weather, Exception):
                logger.error(f"Weather fetch failed: {weather}")
                errors.append("Weather unavailable")
                weather = None

            if isinstance(departures, Exception):
                logger.error(f"Departures fetch failed: {departures}")
                errors.append("Departures unavailable")
                departures = []

        except Exception as e:
            logger.exception(f"Error fetching data: {e}")
            weather = None
            departures = []
            errors.append("Data fetch failed")

        logger.info(f"Plugin run(): got {len(departures)} departures to render")
        if not departures:
            logger.warning("Plugin run(): NO departures to render!")

        # Generate image
        try:
            image = self.renderer.render(
                weather=weather,
                departures=departures,
                station_name=self.departures_client.station_name,
                errors=errors if errors else None,
            )
        except Exception as e:
            logger.exception(f"Error rendering image: {e}")
            return PluginOutput(error=str(e), plugin_name=self.BASENAME)

        # Save assets
        try:
            server_config = get_config()
            output = self.save_assets(
                image, output_dir, dithering_mode=server_config.dithering_mode
            )

            if weather:
                logger.info(
                    f"Generated image: {weather.temperature}°C, {len(departures)} departures"
                )
            else:
                logger.info(f"Generated image: no weather, {len(departures)} departures")

            return output

        except Exception as e:
            logger.exception(f"Error saving assets: {e}")
            return PluginOutput(error=str(e), plugin_name=self.BASENAME)

    async def refresh(self) -> PluginOutput | None:
        """Convenience method to refresh plugin output."""
        server_config = get_config()
        output_dir = self.get_output_dir(server_config.generated_dir)
        return await self.run(output_dir=output_dir)
