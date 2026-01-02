# 001: Initial Implementation

**Date:** January 2025
**Status:** Complete

## Overview

This document describes the initial implementation of MunichGlance, a TRMNL BYOS plugin for displaying Munich public transport departures and weather on an e-ink display.

## Goals

1. Create a full-featured TRMNL BYOS FastAPI server
2. Implement MunichGlance plugin with MVG departures and Open-Meteo weather
3. Generate 800x480 1-bit images optimized for e-ink displays
4. Provide Docker deployment for Raspberry Pi / local hosting

## Architecture Decisions

### BYOS Server Structure

Based on the [TRMNL BYOS FastAPI reference](https://github.com/usetrmnl/byos_fastapi), we implemented:

- **Plugin auto-discovery**: Plugins are automatically discovered by scanning `trmnl_server/plugins/` for classes inheriting from `PluginBase` with `AUTO_REGISTER = True`
- **Background scheduler**: APScheduler runs plugin refresh jobs at configurable intervals
- **SQLite persistence**: Device registration, logs, battery readings, and config are persisted
- **FastAPI async**: All API endpoints and plugin execution use async/await

### Plugin Architecture

```
PluginBase (abstract)
    ├── BASENAME: str           # Plugin identifier
    ├── AUTO_REGISTER: bool     # Enable auto-discovery
    ├── REFRESH_INTERVAL: int   # Seconds between refreshes
    ├── run(**kwargs) -> PluginOutput  # Main execution
    ├── save_assets(image, dir) -> PluginOutput  # Save BMP/PNG
    └── prepare_image(image) -> Image  # E-ink optimization
```

MunichGlancePlugin inherits from PluginBase and:
- Fetches weather and departures concurrently
- Renders a composite image
- Saves 1-bit BMP (for firmware) and grayscale PNG (for preview)

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    MunichGlancePlugin.run()                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐              ┌─────────────────┐          │
│  │  WeatherClient  │              │ DeparturesClient │          │
│  │  (Open-Meteo)   │              │     (MVG)        │          │
│  └────────┬────────┘              └────────┬────────┘          │
│           │ async                          │ async              │
│           ▼                                ▼                    │
│  ┌─────────────────┐              ┌─────────────────┐          │
│  │   WeatherData   │              │ List[Departure] │          │
│  └────────┬────────┘              └────────┬────────┘          │
│           │                                │                    │
│           └────────────┬───────────────────┘                    │
│                        ▼                                        │
│              ┌─────────────────┐                               │
│              │    Renderer     │                               │
│              │  (800x480 PIL)  │                               │
│              └────────┬────────┘                               │
│                       ▼                                        │
│              ┌─────────────────┐                               │
│              │  PluginOutput   │                               │
│              │  (BMP + PNG)    │                               │
│              └─────────────────┘                               │
└─────────────────────────────────────────────────────────────────┘
```

## Implementation Details

### Files Created

#### Core Server (Phase 1-2)

| File | Purpose |
|------|---------|
| `pyproject.toml` | Project dependencies and metadata |
| `trmnl_server/__init__.py` | Package initialization |
| `trmnl_server/__main__.py` | CLI entry point with uvicorn |
| `trmnl_server/main.py` | FastAPI app with lifespan, routes, middleware |
| `trmnl_server/config.py` | Environment variable configuration |
| `trmnl_server/database.py` | SQLAlchemy async session management |
| `trmnl_server/models.py` | ORM models (Device, DeviceLog, BatteryReading, ConfigEntry, PluginState) |
| `trmnl_server/routes/api.py` | TRMNL device endpoints (/api/display, /api/log, /api/battery) |
| `trmnl_server/routes/settings.py` | Settings management endpoints |
| `trmnl_server/plugins/base.py` | PluginBase abstract class and PluginOutput dataclass |
| `trmnl_server/services/scheduler.py` | APScheduler background job management |
| `trmnl_server/services/plugins.py` | Plugin discovery, registry, and caching |

#### MunichGlance Plugin (Phase 3)

| File | Purpose |
|------|---------|
| `plugins/munichglance/__init__.py` | Package exports |
| `plugins/munichglance/config.py` | Plugin configuration from environment |
| `plugins/munichglance/icons.py` | WMO weather codes, transport styling |
| `plugins/munichglance/weather.py` | Open-Meteo API client with caching |
| `plugins/munichglance/departures.py` | MVG API client with caching |
| `plugins/munichglance/renderer.py` | 800x480 Pillow image generation |
| `plugins/munichglance/plugin.py` | Main plugin orchestrating data fetch and render |

#### Deployment (Phase 4)

| File | Purpose |
|------|---------|
| `Dockerfile` | Python 3.12 container with Pillow deps |
| `docker-compose.yml` | Service configuration with all env vars |
| `.env.example` | Documented environment variables |
| `README.md` | Project documentation |
| `web/index.html` | Dashboard with live preview |
| `.gitignore` | Git ignore patterns |

### Key Implementation Choices

#### 1. Async-First Design

All external API calls use async clients:
- `httpx.AsyncClient` for Open-Meteo weather API
- `mvg.MvgApi` sync methods wrapped in executor (library limitation)
- `aiosqlite` for async SQLite operations

#### 2. Multi-Level Caching

```
Level 1: In-Memory (per client)
    WeatherClient._cache: 15 min TTL
    DeparturesClient._cache: 30 sec TTL

Level 2: Plugin Output Cache
    Managed by services/plugins.py
    TTL from plugin.get_content_ttl()

Level 3: File System
    Generated images in var/generated/
```

#### 3. Graceful Degradation

When APIs fail:
- Return cached data if available
- Mark output as `is_cached = True`
- Show error banner on rendered image
- Never crash the plugin - return PluginOutput with error field

#### 4. E-Ink Optimized Rendering

```python
# Render in grayscale for anti-aliased text
img = Image.new("L", (800, 480), 255)

# Use high-contrast fonts
draw.text((x, y), text, font=font, fill=0)  # Pure black

# Convert to 1-bit for BMP output
bmp_image = prepared.convert("1")
bmp_image.save(path, "BMP")
```

#### 5. Transport Badge Styling

- U-Bahn/S-Bahn: Filled black badge with white text
- Bus/Tram: Outlined badge with black text
- Consistent sizing for alignment

### API Endpoints Implemented

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/display` | Returns image URL and refresh metadata for TRMNL |
| POST | `/api/log` | Device event logging |
| POST | `/api/battery` | Battery/RSSI telemetry |
| GET | `/api/setup` | Device initial setup |
| GET | `/api/health` | Health check |
| GET | `/settings` | Current configuration |
| POST | `/settings` | Update configuration |
| GET | `/settings/plugins` | List registered plugins |
| GET | `/image/screen.bmp` | Current display BMP |
| GET | `/image/grayscale.png` | Current display PNG |
| GET | `/` | Dashboard HTML |
| GET | `/docs` | OpenAPI documentation |

### Configuration

All configuration via environment variables:

```bash
# Server
SERVER_PORT=4567
DEBUG=false

# MVG
MVG_STATION_NAME=Marienplatz
MVG_DEPARTURE_LIMIT=10
MVG_OFFSET_MINUTES=0
MVG_TRANSPORT_TYPES=UBAHN,SBAHN,TRAM,BUS

# Weather
WEATHER_LAT=48.1351
WEATHER_LON=11.5820

# Refresh
DEPARTURES_REFRESH_INTERVAL=60
WEATHER_REFRESH_INTERVAL=900
```

## Testing

Syntax validation was performed on all Python files:

```bash
python3 -m py_compile trmnl_server/main.py
python3 -c "import ast; ast.parse(open('file.py').read())"
```

Full test suite to be implemented in future iteration.

## Dependencies

```toml
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "sqlalchemy>=2.0.0",
    "aiosqlite>=0.19.0",
    "aiohttp>=3.9.0",
    "httpx>=0.27.0",
    "pillow>=10.3.0",
    "mvg>=1.2.0",
    "apscheduler>=3.10.0",
    "python-dotenv>=1.0.0",
]
```

## Future Improvements

- [ ] Add unit tests with pytest
- [ ] Implement multiple station rotation
- [ ] Add service disruption alerts
- [ ] Support 2-bit grayscale displays
- [ ] Add weather forecast (hourly)
- [ ] Configurable layout themes
- [ ] Prometheus metrics endpoint

## References

- [TRMNL BYOS FastAPI](https://github.com/usetrmnl/byos_fastapi)
- [MVG Python Library](https://pypi.org/project/mvg/)
- [Open-Meteo API](https://open-meteo.com/en/docs)
- [TRMNL Documentation](https://docs.usetrmnl.com/)
- [WMO Weather Codes](https://www.nodc.noaa.gov/archive/arc0021/0002199/1.1/data/0-data/HTML/WMO-CODE/WMO4677.HTM)
