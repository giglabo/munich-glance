"""Weather codes and transport styling for MunichGlance."""

from typing import NamedTuple


class WeatherInfo(NamedTuple):
    """Weather information for a WMO code."""

    icon: str  # Text icon for e-ink display
    description: str  # Human-readable description
    icon_key: str  # Key for bitmap icons (if used)


# WMO Weather Interpretation Codes (WW)
# https://open-meteo.com/en/docs
WMO_WEATHER_CODES: dict[int, WeatherInfo] = {
    # Clear
    0: WeatherInfo("*", "Clear sky", "clear"),
    1: WeatherInfo("*", "Mainly clear", "mostly_clear"),
    2: WeatherInfo("**", "Partly cloudy", "partly_cloudy"),
    3: WeatherInfo("@", "Overcast", "overcast"),
    # Fog
    45: WeatherInfo("~", "Fog", "fog"),
    48: WeatherInfo("~", "Depositing rime fog", "fog"),
    # Drizzle
    51: WeatherInfo(".", "Light drizzle", "drizzle"),
    53: WeatherInfo("..", "Moderate drizzle", "drizzle"),
    55: WeatherInfo("...", "Dense drizzle", "drizzle"),
    56: WeatherInfo(".,", "Light freezing drizzle", "freezing_drizzle"),
    57: WeatherInfo(".,,", "Dense freezing drizzle", "freezing_drizzle"),
    # Rain
    61: WeatherInfo("/", "Slight rain", "rain_light"),
    63: WeatherInfo("//", "Moderate rain", "rain"),
    65: WeatherInfo("///", "Heavy rain", "rain_heavy"),
    66: WeatherInfo("/,", "Light freezing rain", "freezing_rain"),
    67: WeatherInfo("//,", "Heavy freezing rain", "freezing_rain"),
    # Snow
    71: WeatherInfo("+", "Slight snow", "snow_light"),
    73: WeatherInfo("++", "Moderate snow", "snow"),
    75: WeatherInfo("+++", "Heavy snow", "snow_heavy"),
    77: WeatherInfo("o", "Snow grains", "snow_grains"),
    # Showers
    80: WeatherInfo("/\\", "Slight rain showers", "showers_light"),
    81: WeatherInfo("//\\", "Moderate rain showers", "showers"),
    82: WeatherInfo("///\\", "Violent rain showers", "showers_heavy"),
    85: WeatherInfo("+\\", "Slight snow showers", "snow_showers_light"),
    86: WeatherInfo("++\\", "Heavy snow showers", "snow_showers"),
    # Thunderstorm
    95: WeatherInfo("!", "Thunderstorm", "thunderstorm"),
    96: WeatherInfo("!+", "Thunderstorm with slight hail", "thunderstorm_hail"),
    99: WeatherInfo("!++", "Thunderstorm with heavy hail", "thunderstorm_hail"),
}


def get_weather_info(code: int, is_day: bool = True) -> WeatherInfo:
    """Get weather information for a WMO code.

    Args:
        code: WMO weather code
        is_day: Whether it's daytime (for icon variants)

    Returns:
        WeatherInfo tuple
    """
    info = WMO_WEATHER_CODES.get(code, WeatherInfo("?", "Unknown", "unknown"))

    # Modify icon key for night variants
    if not is_day and info.icon_key in ("clear", "mostly_clear", "partly_cloudy"):
        return WeatherInfo(info.icon, info.description, f"{info.icon_key}_night")

    return info


# Transport type styling for Munich transit
class TransportStyle(NamedTuple):
    """Styling information for transport types."""

    short_name: str  # Short display name (e.g., "U", "S")
    full_name: str  # Full name (e.g., "U-Bahn")
    badge_filled: bool  # Whether badge should be filled (inverted)


TRANSPORT_STYLES: dict[str, TransportStyle] = {
    # MVG transport types (as returned by mvg package)
    "UBAHN": TransportStyle("U", "U-Bahn", True),
    "U-Bahn": TransportStyle("U", "U-Bahn", True),
    "SBAHN": TransportStyle("S", "S-Bahn", True),
    "S-Bahn": TransportStyle("S", "S-Bahn", True),
    "TRAM": TransportStyle("Tram", "Tram", False),
    "Tram": TransportStyle("Tram", "Tram", False),
    "BUS": TransportStyle("Bus", "Bus", False),
    "Bus": TransportStyle("Bus", "Bus", False),
    "REGIONAL_BUS": TransportStyle("RBus", "Regional Bus", False),
    "RegionalBus": TransportStyle("RBus", "Regional Bus", False),
    "BAHN": TransportStyle("RE", "Regional Train", True),
    "Bahn": TransportStyle("RE", "Regional Train", True),
    "SCHIFF": TransportStyle("F", "Ferry", False),
    "Schiff": TransportStyle("F", "Ferry", False),
}


def get_transport_style(transport_type: str) -> TransportStyle:
    """Get styling for a transport type.

    Args:
        transport_type: Transport type string from MVG API

    Returns:
        TransportStyle tuple
    """
    return TRANSPORT_STYLES.get(
        transport_type, TransportStyle(transport_type[:4], transport_type, False)
    )


# Line-specific colors (for reference, e-ink is B&W)
# Could be used for grayscale intensity if 2-bit display is available
LINE_COLORS: dict[str, str] = {
    # U-Bahn lines
    "U1": "#52822F",  # Green
    "U2": "#C4003A",  # Red
    "U3": "#EC6725",  # Orange
    "U4": "#00A984",  # Teal
    "U5": "#BC7A00",  # Brown
    "U6": "#0065AE",  # Blue
    "U7": "#52822F",  # Green (shares with U1)
    "U8": "#C4003A",  # Red (shares with U2)
    # S-Bahn lines
    "S1": "#16BAE7",  # Light blue
    "S2": "#71BF44",  # Green
    "S3": "#7B107D",  # Purple
    "S4": "#C4003A",  # Red
    "S6": "#00975F",  # Dark green
    "S7": "#8B231D",  # Dark red
    "S8": "#F0AA00",  # Yellow/Orange
    "S20": "#F05A73",  # Pink
}


def get_line_color(line: str) -> str:
    """Get color for a transit line.

    Args:
        line: Line name (e.g., "U3", "S8")

    Returns:
        Hex color string
    """
    return LINE_COLORS.get(line, "#333333")
