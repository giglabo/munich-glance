"""TRMNL device API endpoints."""

import logging
import uuid
from datetime import datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, Query, Request
from pydantic import BaseModel

from trmnl_server.config import get_config
from trmnl_server.database import get_session
from trmnl_server.models import BatteryReading, Device, DeviceLog
from trmnl_server.services.plugins import (
    get_cached_output,
    get_plugin,
    get_primary_plugin_name,
    is_cache_valid,
    run_plugin,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["api"])


class DisplayResponse(BaseModel):
    """Response for /api/display endpoint."""

    status: int = 0
    image_url: str
    filename: str
    refresh_rate: int
    update_firmware: bool = False
    firmware_url: Optional[str] = None
    reset_firmware: bool = False
    special_function: Optional[str] = None  # sleep, identify, restart_playlist, etc.


class DeviceStatusStamp(BaseModel):
    """Device status information in log entry."""

    wifi_status: Optional[str] = None
    wakeup_reason: Optional[str] = None
    current_fw_version: Optional[str] = None
    free_heap_size: Optional[int] = None
    special_function: Optional[str] = None
    refresh_rate: Optional[int] = None
    battery_voltage: Optional[float] = None
    time_since_last_sleep_start: Optional[int] = None
    wifi_rssi_level: Optional[int] = None

    model_config = {"extra": "allow"}


class LogEntry(BaseModel):
    """Single log entry from device."""

    log_id: Optional[int] = None
    creation_timestamp: Optional[int] = None
    log_message: Optional[str] = None
    log_codeline: Optional[int] = None
    log_sourcefile: Optional[str] = None
    device_status_stamp: Optional[DeviceStatusStamp] = None
    additional_info: Optional[dict] = None

    model_config = {"extra": "allow"}


class LogArray(BaseModel):
    """Container for log entries array."""

    logs_array: list[LogEntry] = []

    model_config = {"extra": "allow"}


class LogRequest(BaseModel):
    """Request body for /api/log endpoint.

    Accepts the TRMNL firmware log format:
    {"log": {"logs_array": [...]}}
    """

    log: Optional[LogArray] = None

    # Legacy format support
    log_type: Optional[str] = None
    message: Optional[str] = None
    firmware_version: Optional[str] = None
    wifi_rssi: Optional[int] = None
    battery_voltage: Optional[float] = None
    free_heap: Optional[int] = None

    model_config = {"extra": "allow"}


class LogResponse(BaseModel):
    """Response for /api/log endpoint."""

    status: int = 0
    message: str = "ok"


class BatteryRequest(BaseModel):
    """Request body for /api/battery endpoint."""

    voltage: float
    rssi: Optional[int] = None


class BatteryResponse(BaseModel):
    """Response for /api/battery endpoint."""

    status: int = 0
    message: str = "ok"


class SetupResponse(BaseModel):
    """Response for /api/setup endpoint."""

    status: int = 0
    api_key: str
    friendly_id: str
    message: str


def _get_device_mac(request: Request, header_mac: Optional[str] = None) -> str:
    """Extract device MAC address from request."""
    # Try header first
    if header_mac:
        return header_mac.upper().replace(":", "")

    # Try query param
    mac = request.query_params.get("mac", "")
    if mac:
        return mac.upper().replace(":", "")

    # Generate a unique ID for unknown devices
    return f"UNKNOWN-{uuid.uuid4().hex[:8].upper()}"


def _parse_time(time_str: str) -> time:
    """Parse time string (HH:MM) to time object."""
    parts = time_str.strip().split(":")
    return time(int(parts[0]), int(parts[1]))


def _is_in_sleep_window(config) -> bool:
    """Check if current time is within the sleep window.

    Handles overnight windows (e.g., 23:00 - 06:30) correctly.

    Returns:
        True if device should be sleeping, False otherwise.
    """
    if not config.sleep_enabled:
        return False

    try:
        tz = ZoneInfo(config.timezone)
        now = datetime.now(tz).time()
        sleep_start = _parse_time(config.sleep_start)
        sleep_end = _parse_time(config.sleep_end)

        # Handle overnight window (e.g., 23:00 - 06:30)
        if sleep_start > sleep_end:
            # Sleep window crosses midnight
            return now >= sleep_start or now < sleep_end
        else:
            # Normal window (e.g., 02:00 - 06:00)
            return sleep_start <= now < sleep_end

    except Exception as e:
        logger.warning(f"Error checking sleep window: {e}")
        return False


def _seconds_until_sleep_end(config) -> int:
    """Calculate seconds until sleep window ends.

    Returns:
        Seconds until sleep_end time, minimum 60 seconds.
    """
    try:
        tz = ZoneInfo(config.timezone)
        now = datetime.now(tz)
        sleep_end = _parse_time(config.sleep_end)

        # Create datetime for sleep_end today
        end_today = now.replace(
            hour=sleep_end.hour,
            minute=sleep_end.minute,
            second=0,
            microsecond=0,
        )

        # If sleep_end is before current time, it's tomorrow
        if end_today <= now:
            end_today = end_today + timedelta(days=1)

        seconds = int((end_today - now).total_seconds())

        # Minimum 60 seconds, maximum 8 hours
        return max(60, min(seconds, 28800))

    except Exception as e:
        logger.warning(f"Error calculating sleep duration: {e}")
        return 28800  # Fallback to 8 hours


@router.get("/display", response_model=DisplayResponse)
async def get_display(
    request: Request,
    x_device_mac: Optional[str] = Header(None, alias="X-Device-MAC"),
    plugin: Optional[str] = Query(None, description="Specific plugin to display"),
) -> DisplayResponse:
    """Get current display image for TRMNL device.

    This is the main endpoint called by TRMNL firmware.
    Returns the URL to the current BMP image and refresh settings.

    Sleep mode: When sleep is enabled and current time is within the sleep window,
    returns special_function="sleep" to put the device into low-power sleep mode.
    """
    config = get_config()
    mac = _get_device_mac(request, x_device_mac)

    # Check if device should be sleeping
    if _is_in_sleep_window(config):
        base_url = str(request.base_url).rstrip("/")

        # Calculate refresh rate to wake up at sleep_end
        sleep_refresh_rate = _seconds_until_sleep_end(config)
        logger.debug(
            f"Device {mac} entering sleep mode ({config.sleep_start} - {config.sleep_end}), "
            f"wake in {sleep_refresh_rate}s ({sleep_refresh_rate // 60}min)"
        )

        # Use custom sleep image if configured, otherwise use last generated screen
        if config.sleep_image_path:
            # Custom sleep image served from /static/ directory
            image_url = f"{base_url}/static/{config.sleep_image_path}"
            filename = f"sleep_{config.sleep_image_path.replace('/', '_')}"
            logger.debug(f"Using custom sleep image: {image_url}")
        else:
            # Default: keep showing last generated screen
            image_url = f"{base_url}/generated/munichglance/screen.bmp"
            filename = "sleep.bmp"

        return DisplayResponse(
            status=0,
            image_url=image_url,
            filename=filename,
            refresh_rate=sleep_refresh_rate,
            special_function="sleep",
        )

    # Determine which plugin to use
    plugin_name = plugin or get_primary_plugin_name()

    if not plugin_name:
        logger.error("No plugin available")
        base_url = str(request.base_url).rstrip("/")
        return DisplayResponse(
            status=1,
            image_url=f"{base_url}/generated/error.bmp",
            filename="error.bmp",
            refresh_rate=config.refresh_time,
        )

    # Check cache first
    if is_cache_valid(plugin_name):
        output = get_cached_output(plugin_name)
    else:
        # Run plugin to refresh
        output = await run_plugin(plugin_name)

    if not output or not output.has_image():
        logger.error(f"Plugin {plugin_name} produced no output")
        base_url = str(request.base_url).rstrip("/")
        return DisplayResponse(
            status=1,
            image_url=f"{base_url}/generated/error.bmp",
            filename="error.bmp",
            refresh_rate=config.refresh_time,
        )

    # Build image URL - must be a full URL for TRMNL device
    base_url = str(request.base_url).rstrip("/")
    if output.bmp_path:
        # Path relative to generated dir
        relative_path = output.bmp_path.relative_to(config.generated_dir)
        image_url = f"{base_url}/generated/{relative_path}"
        filename = f"{output.content_hash}_{output.bmp_path.name}"
    else:
        image_url = f"{base_url}/generated/screen.bmp"
        filename = f"{output.content_hash}_screen.bmp"

    # Update device last seen
    try:
        async with get_session() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(Device).where(Device.mac_address == mac)
            )
            device = result.scalar_one_or_none()

            if device:
                device.last_seen = datetime.now()
            else:
                # Register new device
                device = Device(
                    mac_address=mac,
                    last_seen=datetime.now(),
                    current_plugin=plugin_name,
                )
                session.add(device)

    except Exception as e:
        logger.warning(f"Could not update device record: {e}")

    logger.debug(f"Display response for {mac}: {image_url}")

    # Get dynamic refresh rate from plugin if available
    refresh_rate = config.refresh_time  # Default from server config
    plugin = get_plugin(plugin_name)
    if plugin and hasattr(plugin, "get_dynamic_refresh_rate"):
        refresh_rate = plugin.get_dynamic_refresh_rate()

    return DisplayResponse(
        status=0,
        image_url=image_url,
        filename=filename,
        refresh_rate=refresh_rate,
    )


@router.post("/log", response_model=LogResponse)
async def post_log(
    request: Request,
    log_data: LogRequest,
    x_device_mac: Optional[str] = Header(None, alias="X-Device-MAC"),
) -> LogResponse:
    """Log device events.

    Called by TRMNL firmware on various events like display update,
    sleep, wake, etc.

    Accepts two formats:
    1. TRMNL firmware format: {"log": {"logs_array": [...]}}
    2. Legacy format: {"log_type": "...", "message": "..."}
    """
    mac = _get_device_mac(request, x_device_mac)

    try:
        async with get_session() as session:
            # Handle TRMNL firmware format
            if log_data.log and log_data.log.logs_array:
                for entry in log_data.log.logs_array:
                    status = entry.device_status_stamp
                    log_entry = DeviceLog(
                        device_mac=mac,
                        log_type=entry.log_sourcefile or "firmware",
                        message=entry.log_message,
                        firmware_version=status.current_fw_version if status else None,
                        wifi_rssi=status.wifi_rssi_level if status else None,
                        battery_voltage=status.battery_voltage if status else None,
                        free_heap=status.free_heap_size if status else None,
                    )
                    session.add(log_entry)
                logger.debug(f"Log from {mac}: {len(log_data.log.logs_array)} entries")
            # Handle legacy format
            elif log_data.log_type:
                log_entry = DeviceLog(
                    device_mac=mac,
                    log_type=log_data.log_type,
                    message=log_data.message,
                    firmware_version=log_data.firmware_version,
                    wifi_rssi=log_data.wifi_rssi,
                    battery_voltage=log_data.battery_voltage,
                    free_heap=log_data.free_heap,
                )
                session.add(log_entry)
                logger.debug(f"Log from {mac}: {log_data.log_type}")
            else:
                # Accept but don't store unknown formats
                logger.debug(f"Log from {mac}: unknown format, accepted")

    except Exception as e:
        logger.error(f"Failed to save log: {e}")
        return LogResponse(status=1, message=str(e))

    return LogResponse(status=0, message="ok")


@router.post("/battery", response_model=BatteryResponse)
async def post_battery(
    request: Request,
    battery_data: BatteryRequest,
    x_device_mac: Optional[str] = Header(None, alias="X-Device-MAC"),
) -> BatteryResponse:
    """Record battery and RSSI readings.

    Called periodically by TRMNL firmware to report battery status.
    """
    mac = _get_device_mac(request, x_device_mac)

    try:
        async with get_session() as session:
            reading = BatteryReading(
                device_mac=mac,
                voltage=battery_data.voltage,
                rssi=battery_data.rssi,
            )
            session.add(reading)

        logger.debug(f"Battery from {mac}: {battery_data.voltage}V")

    except Exception as e:
        logger.error(f"Failed to save battery reading: {e}")
        return BatteryResponse(status=1, message=str(e))

    return BatteryResponse(status=0, message="ok")


@router.get("/setup", response_model=SetupResponse)
async def get_setup(
    request: Request,
    x_device_mac: Optional[str] = Header(None, alias="X-Device-MAC"),
) -> SetupResponse:
    """Get device setup information.

    Called by TRMNL firmware during initial setup.
    """
    config = get_config()
    mac = _get_device_mac(request, x_device_mac)

    # Generate or retrieve API key for device
    api_key = config.setup_api_key or f"mg_{uuid.uuid4().hex[:16]}"

    logger.info(f"Setup request from {mac}")

    return SetupResponse(
        status=0,
        api_key=api_key,
        friendly_id=config.setup_friendly_id,
        message=config.setup_message,
    )


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "primary_plugin": get_primary_plugin_name(),
    }
