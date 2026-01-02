# Getting Started with MunichGlance

This guide will help you set up and run MunichGlance on your local machine or server.

## Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose (for containerized deployment)
- A TRMNL e-ink display device (optional, for actual display)

## Installation Options

### Option 1: Docker Compose (Recommended)

The easiest way to run MunichGlance is using Docker Compose.

1. **Clone the repository**
   ```bash
   git clone https://github.com/giglabo/munich-glance.git
   cd munich-glance
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` to customize your settings:
   ```bash
   # Set your preferred station
   MVG_STATION_NAME=Marienplatz

   # Adjust walking time to station (minutes)
   MVG_OFFSET_MINUTES=2

   # Choose transport types
   MVG_TRANSPORT_TYPES=UBAHN,SBAHN,TRAM,BUS
   ```

3. **Start the server**
   ```bash
   docker compose up -d
   ```

4. **Verify it's running**
   ```bash
   curl http://localhost:4567/api/health
   ```

   You should see:
   ```json
   {"status":"ok","timestamp":"...","primary_plugin":"munichglance"}
   ```

5. **View the dashboard**

   Open http://localhost:4567 in your browser to see the dashboard and preview the current display.

### Option 2: Local Python Installation

For development or if you prefer not to use Docker.

1. **Clone and enter the directory**
   ```bash
   git clone https://github.com/giglabo/munich-glance.git
   cd munich-glance
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -e .
   ```

4. **Download fonts**
   ```bash
   ./scripts/setup_fonts.sh
   ```

   This downloads DejaVu fonts required for the display renderer.

5. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env as needed
   ```

6. **Run the server**
   ```bash
   python -m trmnl_server
   ```

   Or using the installed command:
   ```bash
   munich-glance
   ```

## Configuring Your TRMNL Device

Once the server is running, configure your TRMNL device:

1. Access your TRMNL device settings
2. Set the BYOS server URL to: `http://YOUR_SERVER_IP:4567`
3. The device will start fetching display images automatically

## Verifying the Setup

### Check the API

```bash
# Health check
curl http://localhost:4567/api/health

# Get current settings
curl http://localhost:4567/settings

# List registered plugins
curl http://localhost:4567/settings/plugins
```

### Preview the Display

1. Open http://localhost:4567 in your browser
2. Click "Refresh Preview" to see the current display
3. The preview updates automatically every 2 minutes

### Download the Image

```bash
# Download BMP (for TRMNL device)
curl -o screen.bmp http://localhost:4567/image/screen.bmp

# Download PNG (for preview)
curl -o screen.png http://localhost:4567/image/grayscale.png
```

## Common Configuration Examples

### Different Stations

```bash
# Hauptbahnhof
MVG_STATION_NAME=Hauptbahnhof

# Münchner Freiheit
MVG_STATION_NAME=Münchner Freiheit

# Using station ID directly
MVG_STATION_ID=de:09162:2
```

### Only Show Subway

```bash
MVG_TRANSPORT_TYPES=UBAHN
```

### Show S-Bahn and Regional Trains

```bash
MVG_TRANSPORT_TYPES=SBAHN,BAHN
```

### Faster Refresh Rate

```bash
DEPARTURES_REFRESH_INTERVAL=30
REFRESH_TIME=60
```

### Different Weather Location

```bash
# Berlin
WEATHER_LAT=52.5200
WEATHER_LON=13.4050

# Vienna
WEATHER_LAT=48.2082
WEATHER_LON=16.3738
```

## Sleep Mode

Sleep mode puts the device into low-power mode during specified hours to save battery. This is especially useful overnight when you're not looking at the display.

### How It Works

1. When the current time falls within the sleep window, the server returns `special_function: "sleep"` in the API response
2. If a custom sleep image is configured, the device downloads and displays it before sleeping
3. The TRMNL device enters deep sleep mode for up to 8 hours
4. The screen retains the displayed content (no additional power used)
5. When the device wakes up and the sleep window has ended, normal operation resumes

### Configuration

Edit `config/app-config.yaml`:

```yaml
device:
  # Enable sleep mode
  sleep_enabled: true

  # Sleep from 11 PM to 6:30 AM
  sleep_start: "23:00"
  sleep_end: "06:30"

  # Optional: Custom image to show during sleep
  # Path relative to web/ directory, leave empty to keep last screen
  sleep_image_path: "sleep-image.bmp"
```

### Custom Sleep Image

You can configure a custom image to display when the device enters sleep mode. This is useful for showing a "goodnight" screen, branding, or any other static content.

**Generate the default sleep image:**
```bash
python scripts/generate_sleep_image.py
```

This creates `web/sleep-image.png` and `web/sleep-image.bmp` with a centered logo and text.

**Configuration options:**

| Value | Behavior |
|-------|----------|
| `sleep_image_path: "sleep-image.bmp"` | Show custom image from `web/sleep-image.bmp` |
| `sleep_image_path: ""` | Keep showing last displayed screen (default) |

**Custom image requirements:**
- Format: BMP (1-bit for TRMNL device)
- Dimensions: 800x480 pixels
- Location: `web/` directory (served from `/static/`)

### Examples

**Standard overnight sleep with custom image (11 PM - 6:30 AM):**
```yaml
device:
  sleep_enabled: true
  sleep_start: "23:00"
  sleep_end: "06:30"
  sleep_image_path: "sleep-image.bmp"
```

**Sleep mode keeping last screen (no custom image):**
```yaml
device:
  sleep_enabled: true
  sleep_start: "01:00"
  sleep_end: "07:00"
  sleep_image_path: ""
```

**Extended sleep for maximum battery (10 PM - 7 AM):**
```yaml
device:
  sleep_enabled: true
  sleep_start: "22:00"
  sleep_end: "07:00"
  sleep_image_path: "sleep-image.bmp"
```

### Battery Savings

With a 15-minute refresh interval:
- Without sleep mode: ~96 refreshes/day
- With 8-hour sleep (e.g., 23:00 - 07:00): ~64 refreshes/day (33% reduction)

This can extend battery life from ~140 days to ~210 days.

### Important Notes

- Sleep window uses the timezone configured in `server.timezone` (default: Europe/Berlin)
- The device may take up to one refresh cycle to enter sleep mode after the window starts
- Overnight windows (e.g., 23:00 - 06:30) are handled correctly
- Sleep mode is disabled by default (`sleep_enabled: false`)

## Troubleshooting

### No departures showing

1. Check if the station name is correct:
   ```bash
   # Test with MVG API directly
   python3 -c "from mvg import MvgApi; print(MvgApi.station('YOUR_STATION'))"
   ```

2. Verify transport types are included in `MVG_TRANSPORT_TYPES`

3. Check server logs:
   ```bash
   docker compose logs -f munich-glance
   ```

### Weather not displaying

1. Verify coordinates are within valid range
2. Check connectivity to api.open-meteo.com
3. Look for errors in the logs

### Image not updating

1. Check the scheduler is running:
   ```bash
   curl http://localhost:4567/settings | jq '.jobs'
   ```

2. Manually trigger a refresh by restarting the container:
   ```bash
   docker compose restart
   ```

### Font rendering issues

If text looks blocky or icons don't render:

1. Run `./scripts/setup_fonts.sh` to download fonts
2. Check that fonts exist in `assets/fonts/`
3. Check the Docker logs for font loading errors
4. The system falls back to a default bitmap font if no TrueType fonts are found

## Next Steps

- **[Configure Departures](./configure-departures.md)** - Use the interactive CLI to set up multi-station tracking
- Read the [API Documentation](/docs) at http://localhost:4567/docs
- Explore the [Implementation Details](./implementation/001-init.md)
- Check the main [README](../README.md) for architecture overview

## Stopping the Server

```bash
# Docker
docker compose down

# Local
# Press Ctrl+C in the terminal running the server
```

## Updating

```bash
# Docker
docker compose pull
docker compose up -d

# Local
git pull
pip install -e .
```

## Development

### Install Development Dependencies

```bash
pip install -e ".[dev]"
```

This installs additional tools for code quality: `ruff`, `black`, `flake8`, `mypy`, `bandit`, and testing dependencies.

### Code Formatting

Auto-format code before committing:

```bash
./scripts/format_code.sh
```

This runs:
1. `ruff check --fix` - Linting fixes and import sorting
2. `ruff format` - Consistent code formatting
3. `black` - Final formatting pass

### Code Quality Checks

Run all code quality checks:

```bash
./scripts/check_code.sh
```

| Tool | Purpose | Blocking |
|------|---------|----------|
| `ruff check` | Linting + import sorting | Yes |
| `ruff format --check` | Format verification | Yes |
| `black --check` | Format verification | Yes |
| `flake8` | Additional linting | Yes |
| `mypy` | Type checking | No |
| `bandit` | Security scanning | No |

### Running Tests

```bash
pytest
```

With coverage:

```bash
pytest --cov=trmnl_server --cov-report=html
```

---

<p align="center">
  <a href="https://heretic.giglabo.com">
    <img src="../images/heretic/favicon-128x128.png" alt="VibeCoder Heretic" width="64" height="64">
  </a>
  <br>
  <em>Built with <a href="https://heretic.giglabo.com">VibeCoder Heretic</a></em>
</p>
