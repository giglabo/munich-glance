"""SQLAlchemy models for TRMNL BYOS server."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from trmnl_server.database import Base


class Device(Base):
    """TRMNL device registration."""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mac_address: Mapped[str] = mapped_column(String(17), unique=True, nullable=False)
    friendly_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    api_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    firmware_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Display settings
    refresh_rate: Mapped[int] = mapped_column(Integer, default=120)
    current_plugin: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DeviceLog(Base):
    """Device event logs."""

    __tablename__ = "device_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_mac: Mapped[str] = mapped_column(String(17), nullable=False, index=True)

    # Log data
    log_type: Mapped[str] = mapped_column(String(32), nullable=False)  # display, sleep, wake, etc.
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Device state at log time
    firmware_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    wifi_rssi: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    battery_voltage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    free_heap: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class BatteryReading(Base):
    """Battery and signal readings from devices."""

    __tablename__ = "battery_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_mac: Mapped[str] = mapped_column(String(17), nullable=False, index=True)

    # Readings
    voltage: Mapped[float] = mapped_column(Float, nullable=False)
    rssi: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class ConfigEntry(Base):
    """Persisted configuration entries."""

    __tablename__ = "config_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)

    # Metadata
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PluginState(Base):
    """Plugin execution state and cache metadata."""

    __tablename__ = "plugin_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    # State
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_success: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Output info
    current_image: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    image_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
