"""Settings management endpoints."""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from trmnl_server.config import get_config, reload_config
from trmnl_server.database import get_session
from trmnl_server.models import ConfigEntry
from trmnl_server.services.plugins import (
    get_primary_plugin_name,
    list_plugins,
    set_primary_plugin,
)
from trmnl_server.services.scheduler import list_jobs

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsResponse(BaseModel):
    """Current server settings."""

    # Server
    host: str
    port: int
    debug: bool

    # TRMNL
    refresh_time: int
    setup_friendly_id: str
    setup_message: str

    # Display
    dithering_mode: str
    timezone: str

    # Plugin info
    primary_plugin: str | None
    plugins: list[dict]
    jobs: list[dict]


class SettingsUpdateRequest(BaseModel):
    """Settings update request."""

    refresh_time: int | None = None
    setup_friendly_id: str | None = None
    setup_message: str | None = None
    dithering_mode: str | None = None
    timezone: str | None = None
    primary_plugin: str | None = None


class SettingsUpdateResponse(BaseModel):
    """Settings update response."""

    status: str = "ok"
    message: str = "Settings updated"
    updated: dict = {}


class PluginListResponse(BaseModel):
    """List of registered plugins."""

    plugins: list[dict]
    primary: str | None


@router.get("", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    """Get current server settings."""
    config = get_config()

    return SettingsResponse(
        host=config.host,
        port=config.port,
        debug=config.debug,
        refresh_time=config.refresh_time,
        setup_friendly_id=config.setup_friendly_id,
        setup_message=config.setup_message,
        dithering_mode=config.dithering_mode,
        timezone=config.timezone,
        primary_plugin=get_primary_plugin_name(),
        plugins=list_plugins(),
        jobs=list_jobs(),
    )


@router.post("", response_model=SettingsUpdateResponse)
async def update_settings(updates: SettingsUpdateRequest) -> SettingsUpdateResponse:
    """Update server settings.

    Settings are persisted to the database and take effect immediately.
    """
    updated = {}

    try:
        async with get_session() as session:
            from sqlalchemy import select

            for field, value in updates.model_dump(exclude_none=True).items():
                if field == "primary_plugin":
                    # Handle plugin change
                    if set_primary_plugin(value):
                        updated[field] = value
                    else:
                        logger.warning(f"Plugin not found: {value}")
                    continue

                # Persist to database
                result = await session.execute(select(ConfigEntry).where(ConfigEntry.key == field))
                entry = result.scalar_one_or_none()

                if entry:
                    entry.value = str(value)
                else:
                    entry = ConfigEntry(key=field, value=str(value))
                    session.add(entry)

                updated[field] = value
                logger.info(f"Updated setting: {field} = {value}")

    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        return SettingsUpdateResponse(
            status="error",
            message=str(e),
            updated={},
        )

    # Reload config to pick up changes
    reload_config()

    return SettingsUpdateResponse(
        status="ok",
        message=f"Updated {len(updated)} settings",
        updated=updated,
    )


@router.get("/plugins", response_model=PluginListResponse)
async def get_plugins() -> PluginListResponse:
    """List all registered plugins."""
    return PluginListResponse(
        plugins=list_plugins(),
        primary=get_primary_plugin_name(),
    )


@router.post("/plugins/{plugin_name}/primary")
async def set_plugin_primary(plugin_name: str) -> dict:
    """Set a plugin as the primary display plugin."""
    if set_primary_plugin(plugin_name):
        return {"status": "ok", "primary": plugin_name}
    else:
        return {"status": "error", "message": f"Plugin not found: {plugin_name}"}


@router.get("/config/{key}")
async def get_config_entry(key: str) -> dict:
    """Get a specific config entry from the database."""
    try:
        async with get_session() as session:
            from sqlalchemy import select

            result = await session.execute(select(ConfigEntry).where(ConfigEntry.key == key))
            entry = result.scalar_one_or_none()

            if entry:
                return {
                    "key": entry.key,
                    "value": entry.value,
                    "description": entry.description,
                    "updated_at": entry.updated_at.isoformat(),
                }
            else:
                return {"error": "not_found", "key": key}

    except Exception as e:
        return {"error": str(e)}


@router.put("/config/{key}")
async def set_config_entry(key: str, value: str, description: str | None = None) -> dict:
    """Set a config entry in the database."""
    try:
        async with get_session() as session:
            from sqlalchemy import select

            result = await session.execute(select(ConfigEntry).where(ConfigEntry.key == key))
            entry = result.scalar_one_or_none()

            if entry:
                entry.value = value
                if description:
                    entry.description = description
            else:
                entry = ConfigEntry(key=key, value=value, description=description)
                session.add(entry)

        return {"status": "ok", "key": key, "value": value}

    except Exception as e:
        return {"error": str(e)}
