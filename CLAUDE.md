# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MunichGlance is a self-hosted TRMNL BYOS (Bring Your Own Server) plugin that displays Munich public transport departures and current weather on a 7.5" e-ink display (800x480 1-bit). It uses the MVG API for transit data and Open-Meteo for weather.

## Commands

### Development
```bash
# Install dependencies
pip install -e ".[dev]"

# Run the server
python -m trmnl_server

# Format code (ruff + black)
./scripts/format_code.sh

# Check code quality (ruff, black, flake8, mypy, bandit)
./scripts/check_code.sh
```

### Testing
```bash
# Run all tests
pytest

# Run single test file
pytest tests/test_example.py

# Run with coverage
pytest --cov=trmnl_server
```

### Docker
```bash
# Build locally for current architecture
./scripts/build.sh build

# Build and push multi-arch to registry
./scripts/build.sh push --registry=ghcr.io/myorg
```

## Architecture

### Plugin System

The server uses a plugin architecture where plugins extend `PluginBase` (`trmnl_server/plugins/base.py`):

- Plugins implement an async `run()` method that fetches data and generates images
- `AUTO_REGISTER = True` enables auto-discovery at startup
- `SET_PRIMARY = True` makes this plugin the default for the display endpoint
- `save_assets()` handles image conversion to 1-bit BMP (for TRMNL firmware) and grayscale PNG (for preview)

### MunichGlance Plugin Structure

`trmnl_server/plugins/munichglance/`:
- `plugin.py` - Main plugin orchestrating weather + departures fetch and rendering
- `departures.py` - MVG API client (`MultiStationClient` for multiple stations)
- `weather.py` - Open-Meteo client
- `renderer.py` - PIL-based image generation for e-ink display
- `config.py` - Plugin-specific configuration from YAML/env vars

### Request Flow

1. TRMNL device calls `GET /api/display`
2. Server returns cached image from the primary plugin
3. Background scheduler periodically runs plugins to refresh images
4. Images saved to `var/generated/{plugin_name}/`

### Configuration

Configuration loads from `config/app-config.yaml` with environment variable substitution (`${VAR_NAME}`). The server config (`trmnl_server/config.py`) and plugin config (`trmnl_server/plugins/munichglance/config.py`) are separate.

## Key Patterns

- Async throughout: FastAPI + aiohttp for non-blocking I/O
- SQLAlchemy async for database (device telemetry storage)
- APScheduler for background plugin refresh jobs
- Images are always 800x480; `prepare_image()` handles conversion to grayscale, `save_assets()` handles 1-bit dithering options (none, floyd_steinberg, ordered)
