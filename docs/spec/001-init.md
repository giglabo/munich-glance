# MunichGlance — E-ink Dashboard for Munich

## Project Goal
Create a self-hosted TRMNL BYOS plugin displaying Munich public transport departures (MVG) and current weather on a 7.5" e-ink display. Weather updates every 15 minutes, departures update every 1-5 minutes (configurable).

## Tech Stack
- **Server**: TRMNL BYOS FastAPI (https://github.com/usetrmnl/byos_fastapi)
- **MVG Library**: `mvg` package (https://pypi.org/project/mvg/) — async-capable
- **Weather API**: Open-Meteo (https://open-meteo.com/) — free, no API key required
- **Image Generation**: Pillow for 800x480 1-bit images

## Architecture
```
┌─────────────────┐     ┌──────────────────────────────────┐
│  TRMNL Device   │────▶│       BYOS FastAPI Server        │
│  (e-ink 800x480)│◀────│  ┌────────────┐  ┌────────────┐  │
└─────────────────┘     │  │ MVG Plugin │  │Weather Plug│  │
                        │  └─────┬──────┘  └─────┬──────┘  │
                        └────────┼───────────────┼─────────┘
                                 ▼               ▼
                           ┌─────────┐    ┌────────────┐
                           │ MVG API │    │ Open-Meteo │
                           └─────────┘    └────────────┘
```

## Screen Layout (800x480)
```
┌──────────────────────────────────────────────────────────────────┐
│ ┌─────────────────────┐                                          │
│ │ ☀️ 12°C             │    MARIENPLATZ              14:32        │
│ │ Partly Cloudy       │                                          │
│ │ Thu, 23 Jan 2025    │─────────────────────────────────────────│
│ └─────────────────────┘                                          │
│                                                                  │
│   U3   Fürstenried West                                  2 min   │
│   U6   Klinikum Großhadern                               4 min   │
│   S1   Flughafen München                                 5 min   │
│   U3   Moosach                                           7 min   │
│   U6   Garching-Forschungszentrum                        9 min   │
│   S8   Herrsching                                       11 min   │
│   Bus 52   Tierpark (Alemannenstraße)                   12 min   │
│   Tram 19   St.-Veit-Straße                             14 min   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Layout Specifications
- **Weather box** (top-left corner): ~200x100 pixels
  - Weather icon (sun, cloud, rain, snow, etc.)
  - Temperature in °C
  - Short condition text
  - Current day and date
- **Station name**: Top center/right, bold
- **Last update time**: Top right corner
- **Departures list**: Main area, 8-10 rows
  - Transport type badge (U, S, Bus, Tram)
  - Line number
  - Destination
  - Minutes until departure (right-aligned)
  - Show delay if present: "+3" in smaller font

## Configuration

### Environment Variables
```bash
# Station
MVG_STATION_NAME="Marienplatz"        # or use MVG_STATION_ID
MVG_DEPARTURE_LIMIT=10                 # number of departures to show
MVG_OFFSET_MINUTES=2                   # walking time to station
MVG_TRANSPORT_TYPES="UBAHN,SBAHN,BUS,TRAM"  # filter (optional)

# Weather
WEATHER_LAT=48.1351                    # Munich latitude
WEATHER_LON=11.5820                    # Munich longitude
WEATHER_UNITS="celsius"                # celsius or fahrenheit

# Refresh intervals (seconds)
DEPARTURES_REFRESH_INTERVAL=60         # minimum 60
WEATHER_REFRESH_INTERVAL=900           # 15 minutes
```

## API Integration

### MVG (Departures)
```python
from mvg import MvgApi, TransportType

# Async usage (preferred for FastAPI)
async with aiohttp.ClientSession() as session:
    station = await MvgApi.station_async('Marienplatz', session=session)
    departures = await MvgApi.departures_async(
        station['id'], 
        session=session
    )

# Departure object fields:
# - line: "U3"
# - destination: "Fürstenried West"  
# - planned_departure_time: timestamp (ms)
# - delay: minutes (int)
# - transport_type: TransportType.UBAHN / SBAHN / BUS / TRAM
```

### Open-Meteo (Weather)
```python
import httpx

async def get_weather(lat: float, lon: float) -> dict:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,weather_code,is_day",
        "timezone": "Europe/Berlin"
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        return resp.json()

# Response includes:
# - current.temperature_2m: 12.5
# - current.weather_code: 3 (WMO code for cloudy)
# - current.is_day: 1 or 0
```

### WMO Weather Codes (for icons)
```python
WEATHER_ICONS = {
    0: "☀️",      # Clear sky
    1: "🌤️",      # Mainly clear
    2: "⛅",      # Partly cloudy
    3: "☁️",      # Overcast
    45: "🌫️",     # Fog
    51: "🌧️",     # Drizzle
    61: "🌧️",     # Rain
    71: "❄️",     # Snow
    95: "⛈️",     # Thunderstorm
}
```

## Image Generation Requirements

- **Output**: 800x480 pixels, 1-bit depth (pure black & white)
- **Format**: PNG
- **Fonts**: 
  - Include DejaVu Sans or similar clear font
  - Weather: 24-32px bold
  - Station name: 28px bold
  - Departures: 20-22px
  - Time badges: 18px
- **Icons**: Use text-based icons or simple geometric shapes for e-ink clarity
- **Dithering**: Only for weather icons if needed

### Transport Type Styling
```
U-Bahn: [U] in box or bold
S-Bahn: [S] in box or bold  
Bus:    "Bus" text
Tram:   "Tram" text
```

## Plugin Structure
```
trmnl_server/
  plugins/
    munichglance/
      __init__.py
      plugin.py          # Main MunichGlancePlugin class
      weather.py         # Open-Meteo API client
      departures.py      # MVG API client
      renderer.py        # Image generation with Pillow
      icons.py           # Weather and transport icons
      config.py          # Configuration from env vars
```

## Caching Strategy

- **Weather**: Cache for 15 minutes (full refresh interval)
- **Departures**: Cache for 30 seconds (in case of API failures)
- **Fallback**: Show cached data with "⚠️ Cached" indicator if API fails

## Deliverables

1. Working BYOS FastAPI server with MunichGlance plugin
2. Docker Compose setup for Raspberry Pi / local deployment
3. Configuration via environment variables
4. README with:
   - Setup instructions
   - Configuration options
   - Screenshot examples
5. Font files included (or instructions to install)

## Error Handling

- MVG API down → Show "No departure data" with last update time
- Weather API down → Show cached weather or hide weather box
- Network issues → Retry with exponential backoff
- Invalid station → Clear error message on screen

## Future Enhancements (optional)

- Multiple stations rotation
- Service alerts / disruptions display
- Dark mode support (for 2-bit grayscale displays)
- Configurable layout themes

## References

- TRMNL BYOS FastAPI: https://github.com/usetrmnl/byos_fastapi
- MVG Python Library: https://pypi.org/project/mvg/
- Open-Meteo API: https://open-meteo.com/en/docs
- TRMNL Image Guide: https://docs.usetrmnl.com/go/imagemagick-guide
- TRMNL Display: 800x480, 1-bit or 2-bit grayscale