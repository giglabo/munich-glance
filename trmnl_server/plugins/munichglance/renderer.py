"""Image renderer for MunichGlance e-ink display."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

from trmnl_server.plugins.munichglance.config import MunichGlanceConfig, get_plugin_config
from trmnl_server.plugins.munichglance.departures import Departure
from trmnl_server.plugins.munichglance.weather import WeatherData

logger = logging.getLogger(__name__)


class MunichGlanceRenderer:
    """Renders 800x480 e-ink image for MunichGlance display."""

    # Display dimensions
    WIDTH = 800
    HEIGHT = 480

    # Colors (grayscale values)
    # Note: For 1-bit BMP conversion, values < 128 become black, >= 128 become white
    BLACK = 0
    WHITE = 255
    GRAY = 64  # Dark gray - renders as black in 1-bit conversion
    LIGHT_GRAY = 96  # For separators - still renders as black in 1-bit

    # Layout constants
    HEADER_HEIGHT = 70
    WEATHER_BOX_WIDTH = 180
    WEATHER_BOX_HEIGHT = 65
    WEATHER_MARGIN = 8

    DEPARTURE_START_Y = 85  # Slightly lower to give more space after header
    DEPARTURE_ROW_HEIGHT = 42
    DEPARTURE_ROW_HEIGHT_GROUPED = 32  # Smaller rows when showing groups
    DEPARTURE_PADDING = 8

    BADGE_WIDTH = 48
    BADGE_HEIGHT = 28
    BADGE_WIDTH_GROUPED = 42  # Smaller badge when grouped
    BADGE_HEIGHT_GROUPED = 24
    BADGE_RADIUS = 4

    # Group header settings
    GROUP_HEADER_HEIGHT = 22
    FONT_GROUP_HEADER = 14

    # Font sizes
    FONT_TEMP = 36
    FONT_WEATHER_DESC = 14
    FONT_DATE = 14  # Increased from 12
    FONT_STATION = 24
    FONT_TIME = 20
    FONT_LINE = 18
    FONT_DESTINATION = 18
    FONT_MINUTES = 20
    FONT_DELAY = 16  # Increased from 14

    def __init__(
        self,
        config: Optional[MunichGlanceConfig] = None,
        fonts_dir: Optional[Path] = None,
    ):
        """Initialize renderer.

        Args:
            config: Plugin configuration
            fonts_dir: Directory containing font files
        """
        self.config = config or get_plugin_config()
        self.fonts_dir = fonts_dir or Path(__file__).parent.parent.parent.parent / "assets" / "fonts"
        self._fonts: dict[str, ImageFont.FreeTypeFont] = {}
        self._tz = ZoneInfo(self.config.timezone)
        self._load_fonts()

    def _get_now(self) -> datetime:
        """Get current time in configured timezone."""
        return datetime.now(self._tz)

    def _load_fonts(self) -> None:
        """Load fonts for rendering."""
        # Try to find regular and bold fonts
        regular_font_path = None
        bold_font_path = None

        for name in ["DejaVuSans.ttf"]:
            path = self.fonts_dir / name
            if path.exists():
                regular_font_path = path
                break

        for name in ["DejaVuSans-Bold.ttf"]:
            path = self.fonts_dir / name
            if path.exists():
                bold_font_path = path
                break

        # Fall back to bold for regular if regular not found
        if not regular_font_path:
            regular_font_path = bold_font_path

        # Apply font scale from config
        scale = self.config.font_scale

        # Load fonts at different sizes (scaled)
        # Format: (name, size, use_bold)
        font_specs = [
            ("temp", int(self.FONT_TEMP * scale), False),
            ("weather_desc", int(self.FONT_WEATHER_DESC * scale), False),
            ("date", int(self.FONT_DATE * scale), False),
            ("station", int(self.FONT_STATION * scale), False),
            ("time", int(self.FONT_TIME * scale), False),
            ("line", int(self.FONT_LINE * scale), False),
            ("line_small", int((self.FONT_LINE - 2) * scale), False),
            ("destination", int(self.FONT_DESTINATION * scale), False),
            ("destination_small", int((self.FONT_DESTINATION - 2) * scale), False),
            ("minutes", int(self.FONT_MINUTES * scale), False),
            ("minutes_small", int((self.FONT_MINUTES - 2) * scale), False),
            ("delay", int(self.FONT_DELAY * scale), False),
            ("group_header", int(self.FONT_GROUP_HEADER * scale), False),
            ("direction_header", int(self.FONT_GROUP_HEADER * scale), True),  # Bold for direction headers
        ]

        for name, size, use_bold in font_specs:
            font_path = bold_font_path if use_bold and bold_font_path else regular_font_path
            try:
                if font_path:
                    self._fonts[name] = ImageFont.truetype(str(font_path), size)
                else:
                    # Try system font
                    self._fonts[name] = ImageFont.truetype("DejaVuSans.ttf", size)
            except Exception:
                try:
                    self._fonts[name] = ImageFont.truetype("arial.ttf", size)
                except Exception:
                    # Use default font as last resort
                    self._fonts[name] = ImageFont.load_default()
                    logger.warning(f"Using default font for {name}")

    def render(
        self,
        weather: Optional[WeatherData],
        departures: list[Departure],
        station_name: str = "",
        errors: Optional[list[str]] = None,
    ) -> Image.Image:
        """Generate complete display image.

        Args:
            weather: Current weather data (or None if unavailable)
            departures: List of departures to display
            station_name: Station name for header
            errors: List of error messages to display

        Returns:
            PIL Image in grayscale mode
        """
        logger.info(f"render() called with {len(departures)} departures, station={station_name}")
        if departures:
            logger.info(f"First departure: {departures[0].line} -> {departures[0].destination}")
        else:
            logger.warning("render() received EMPTY departures list!")

        # Create image with white background
        img = Image.new("L", (self.WIDTH, self.HEIGHT), self.WHITE)
        draw = ImageDraw.Draw(img)

        # Draw components
        self._draw_weather_box(draw, weather)
        self._draw_header(draw, station_name)
        self._draw_separator(draw, self.HEADER_HEIGHT)  # Line slightly lower
        self._draw_departures(draw, departures)

        # Draw error banner if needed
        if errors:
            self._draw_error_banner(draw, errors)

        return img

    def _draw_weather_box(self, draw: ImageDraw.Draw, weather: Optional[WeatherData]) -> None:
        """Draw weather section in top-left corner."""
        x = self.WEATHER_MARGIN
        y = self.WEATHER_MARGIN

        if not weather:
            # Draw placeholder
            draw.text(
                (x + 10, y + 20),
                "Weather",
                font=self._fonts["weather_desc"],
                fill=self.GRAY,
            )
            draw.text(
                (x + 10, y + 36),
                "unavailable",
                font=self._fonts["weather_desc"],
                fill=self.GRAY,
            )
            return

        # Temperature
        temp_str = weather.format_temperature(self.config.weather_units)
        draw.text(
            (x + 5, y),
            temp_str,
            font=self._fonts["temp"],
            fill=self.BLACK,
        )

        # Weather description
        draw.text(
            (x + 5, y + 40),
            weather.description,
            font=self._fonts["weather_desc"],
            fill=self.BLACK,
        )

        # Date
        date_str = self._get_now().strftime("%a, %d %b")
        draw.text(
            (x + 5, y + 56),
            date_str,
            font=self._fonts["date"],
            fill=self.GRAY,
        )

    def _draw_header(self, draw: ImageDraw.Draw, station_name: str) -> None:
        """Draw station name and current time in header."""
        # Station name - centered in remaining header space
        station_x = self.WEATHER_BOX_WIDTH + 20
        station_y = 20

        # Truncate station name if too long
        max_width = self.WIDTH - station_x - 100
        display_name = station_name.upper()

        # Measure text width
        bbox = draw.textbbox((0, 0), display_name, font=self._fonts["station"])
        text_width = bbox[2] - bbox[0]

        # Truncate if needed
        while text_width > max_width and len(display_name) > 10:
            display_name = display_name[:-4] + "..."
            bbox = draw.textbbox((0, 0), display_name, font=self._fonts["station"])
            text_width = bbox[2] - bbox[0]

        draw.text(
            (station_x, station_y),
            display_name,
            font=self._fonts["station"],
            fill=self.BLACK,
        )

        # Current time - right aligned
        time_str = self._get_now().strftime("%H:%M")
        bbox = draw.textbbox((0, 0), time_str, font=self._fonts["time"])
        time_width = bbox[2] - bbox[0]
        time_x = self.WIDTH - time_width - 15
        time_y = 25

        draw.text(
            (time_x, time_y),
            time_str,
            font=self._fonts["time"],
            fill=self.BLACK,
        )

    def _draw_separator(self, draw: ImageDraw.Draw, y: int) -> None:
        """Draw a horizontal separator line starting after weather box."""
        # Start separator after weather box to avoid crossing date text
        start_x = self.WEATHER_BOX_WIDTH + 10
        draw.line([(start_x, y), (self.WIDTH - 10, y)], fill=self.BLACK, width=1)

    def _draw_departures(self, draw: ImageDraw.Draw, departures: list[Departure]) -> None:
        """Draw the departures list."""
        y = self.DEPARTURE_START_Y

        if not departures:
            # No departures message
            draw.text(
                (self.WIDTH // 2 - 100, self.HEIGHT // 2 - 20),
                "No departures available",
                font=self._fonts["destination"],
                fill=self.GRAY,
            )
            return

        # Check if we should show groups
        if self.config.show_groups:
            self._draw_departures_grouped(draw, departures)
        else:
            self._draw_departures_flat(draw, departures)

    def _draw_departures_flat(self, draw: ImageDraw.Draw, departures: list[Departure]) -> None:
        """Draw departures without grouping."""
        y = self.DEPARTURE_START_Y

        # Calculate how many departures we can show
        available_height = self.HEIGHT - self.DEPARTURE_START_Y - 10
        max_rows = available_height // self.DEPARTURE_ROW_HEIGHT

        for i, dep in enumerate(departures[:max_rows]):
            self._draw_departure_row(draw, dep, y, grouped=False)
            y += self.DEPARTURE_ROW_HEIGHT

            # Draw subtle separator between rows
            if i < len(departures) - 1 and i < max_rows - 1:
                draw.line(
                    [(20, y - 5), (self.WIDTH - 20, y - 5)],
                    fill=self.LIGHT_GRAY,
                    width=1,
                )

    def _draw_departures_grouped(self, draw: ImageDraw.Draw, departures: list[Departure]) -> None:
        """Draw departures grouped by station + line, with bidirectional split into columns."""
        y = self.DEPARTURE_START_Y

        # Group departures by station name + line for proper bidirectional detection
        # This allows Bus 53 (bidirectional) and Bus 134 (unidirectional) at same station
        # to be displayed correctly
        from collections import OrderedDict
        groups: OrderedDict[str, list[Departure]] = OrderedDict()
        for dep in departures:
            station = dep.station_name or "Unknown"
            # Group by station + line so bidirectional detection works per line
            group_key = f"{station}||{dep.line}"
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(dep)

        # Sort groups by station order from config (not alphabetically)
        # This preserves the user-defined station priority in the display
        station_order: dict[str, int] = {}
        if self.config.multi_station:
            for i, station_cfg in enumerate(self.config.multi_station.stations):
                station_order[station_cfg.station] = i

        def get_sort_key(group_key: str) -> tuple[int, str]:
            station = group_key.split("||")[0]
            # Use config order if available, otherwise put at end (999)
            order = station_order.get(station, 999)
            return (order, group_key)

        sorted_keys = sorted(groups.keys(), key=get_sort_key)

        # Calculate available space
        row_height = self.DEPARTURE_ROW_HEIGHT_GROUPED

        # Track current station to avoid duplicate headers
        current_station: str | None = None

        for group_key in sorted_keys:
            line_deps = groups[group_key]
            station_name = group_key.split("||")[0]

            # Check if we have space for header + at least one departure
            if y + self.GROUP_HEADER_HEIGHT + row_height > self.HEIGHT - 10:
                break

            # Draw station header only if station changed
            if station_name != current_station:
                self._draw_group_header(draw, station_name, y)
                y += self.GROUP_HEADER_HEIGHT
                current_station = station_name

            # Check if this line has bidirectional departures (same line, different directions)
            directions = self._get_bidirectional_groups(line_deps)

            if directions and len(directions) == 2:
                # Two-column layout for bidirectional
                y = self._draw_bidirectional_columns(draw, directions, y, row_height)
            else:
                # Single column layout - max 2 rows per line group
                # If compact_directions: all times on one row
                # Otherwise: row 1 = first, row 2 = rest combined with "/"
                if self.config.compact_directions:
                    # All departures on one row (max 3)
                    if line_deps and y + row_height <= self.HEIGHT - 10:
                        limited_deps = line_deps[:3]  # Max 3 per line
                        time_parts = [d.format_time(self.config.time_format) for d in limited_deps]
                        combined_time = " / ".join(time_parts)
                        self._draw_departure_row_compact(
                            draw, line_deps[0], self.DEPARTURE_PADDING + 10, y,
                            self.WIDTH - 40, None, combined_time, show_destination=True
                        )
                        y += row_height
                elif len(line_deps) <= 2:
                    # 1-2 departures: each gets its own row
                    for dep in line_deps:
                        if y + row_height > self.HEIGHT - 10:
                            break
                        self._draw_departure_row(draw, dep, y, grouped=True)
                        y += row_height
                else:
                    # 3+ departures: row 1 = first, row 2 = next 2 combined (max 3 total)
                    if y + row_height <= self.HEIGHT - 10:
                        self._draw_departure_row(draw, line_deps[0], y, grouped=True)
                        y += row_height
                    if y + row_height <= self.HEIGHT - 10:
                        # Limit to 2 more departures on combined row (3 total per line)
                        rest_deps = line_deps[1:3]
                        rest_times = [d.format_time(self.config.time_format) for d in rest_deps]
                        combined_time = " / ".join(rest_times)
                        self._draw_departure_row_compact(
                            draw, line_deps[1], self.DEPARTURE_PADDING + 10, y,
                            self.WIDTH - 40, None, combined_time, show_destination=True
                        )
                        y += row_height

            # Add small gap between groups
            y += 3

    def _get_bidirectional_groups(
        self, departures: list[Departure]
    ) -> Optional[dict[str, list[tuple[Departure, Optional[str]]]]]:
        """Check if departures have bidirectional pattern and group them.

        Returns dict with direction as key if bidirectional (2+ destinations), None otherwise.
        Each departure is paired with an optional "partial route" label (shown in brackets).

        For 3+ destinations, the 2 most frequent become main directions,
        and others are grouped under them with their original destination shown in brackets.
        """
        # Group by destination
        by_destination: dict[str, list[Departure]] = {}
        for dep in departures:
            dest = dep.destination
            if dest not in by_destination:
                by_destination[dest] = []
            by_destination[dest].append(dep)

        # Need at least 2 destinations for bidirectional
        if len(by_destination) < 2:
            return None

        # If exactly 2 destinations, simple case - no partial routes
        if len(by_destination) == 2:
            result: dict[str, list[tuple[Departure, Optional[str]]]] = {}
            for dest, deps in by_destination.items():
                result[dest] = [(d, None) for d in deps]
            return result

        # 3+ destinations: find the 2 most frequent as main directions
        # Tie-breaker: prefer longer destination names (terminus stations usually have longer names)
        sorted_dests = sorted(
            by_destination.keys(),
            key=lambda d: (len(by_destination[d]), len(d)),  # frequency, then name length
            reverse=True
        )
        main_dir_1 = sorted_dests[0]
        main_dir_2 = sorted_dests[1]
        partial_dests = sorted_dests[2:]

        # Build result with main directions
        result: dict[str, list[tuple[Departure, Optional[str]]]] = {
            main_dir_1: [(d, None) for d in by_destination[main_dir_1]],
            main_dir_2: [(d, None) for d in by_destination[main_dir_2]],
        }

        # Assign partial routes to one of the main directions
        # Strategy: alternate between main directions to balance columns
        for i, partial_dest in enumerate(partial_dests):
            target_dir = main_dir_1 if i % 2 == 0 else main_dir_2
            for dep in by_destination[partial_dest]:
                # Store with the partial route name to show in brackets
                result[target_dir].append((dep, partial_dest))

        # Sort each group by departure time
        for dest in result:
            result[dest].sort(key=lambda x: x[0].actual_time)

        return result

    def _draw_bidirectional_columns(
        self,
        draw: ImageDraw.Draw,
        directions: dict[str, list[tuple[Departure, Optional[str]]]],
        start_y: int,
        row_height: int,
    ) -> int:
        """Draw two columns for bidirectional departures.

        Args:
            directions: Dict mapping direction name to list of (Departure, partial_label) tuples.
                       partial_label is shown in brackets for partial routes.

        Returns the Y position after drawing.

        Row limits (per direction):
        - compact_directions: true  → 1 row (all times combined with " / ")
        - compact_directions: false → max 2 rows (3+ departures combined on row 2)
        """
        col_width = (self.WIDTH - 30) // 2  # Two columns with padding
        left_x = self.DEPARTURE_PADDING + 10
        right_x = left_x + col_width + 10

        # Get the two direction groups
        dir_names = list(directions.keys())
        left_deps = directions[dir_names[0]]
        right_deps = directions[dir_names[1]]

        # Draw column headers (direction names) in bold
        header_font = self._fonts["direction_header"]
        draw.text(
            (left_x, start_y),
            f"→ {dir_names[0][:20]}",
            font=header_font,
            fill=self.BLACK,
        )
        draw.text(
            (right_x, start_y),
            f"→ {dir_names[1][:20]}",
            font=header_font,
            fill=self.BLACK,
        )

        y = start_y + 18  # After direction headers

        # Prepare rows (max 2 per column, combine extras with " / ")
        left_rows = self._prepare_column_rows(left_deps)
        right_rows = self._prepare_column_rows(right_deps)

        # Draw up to 2 rows
        max_row_count = max(len(left_rows), len(right_rows))
        for i in range(max_row_count):
            if y + row_height > self.HEIGHT - 10:
                break

            # Left column
            if i < len(left_rows):
                dep, time_str, partial_label = left_rows[i]
                self._draw_departure_row_compact(
                    draw, dep, left_x, y, col_width, partial_label, time_str
                )

            # Right column
            if i < len(right_rows):
                dep, time_str, partial_label = right_rows[i]
                self._draw_departure_row_compact(
                    draw, dep, right_x, y, col_width, partial_label, time_str
                )

            y += row_height

        return y

    def _prepare_column_rows(
        self, deps: list[tuple[Departure, Optional[str]]], max_rows: int = 2
    ) -> list[tuple[Departure, str, Optional[str]]]:
        """Prepare column rows for bidirectional display.

        Returns list of (departure, time_string, partial_label) tuples.

        Args:
            deps: List of (Departure, partial_label) tuples
            max_rows: Maximum rows to use (default 2, can be 3 for balancing)

        If compact_directions is enabled: all times on one row (e.g., "5 min / 7 min / 12 min")
        Otherwise: up to max_rows, with additional departures combined on last row
        """
        if not deps:
            return []

        # Compact mode: all times on single row (max 3), with partial labels in brackets
        if self.config.compact_directions:
            limited_deps = deps[:3]  # Max 3 per direction
            time_parts = []
            for dep, label in limited_deps:
                time_str = dep.format_time(self.config.time_format)
                if label:
                    time_str = f"{time_str} ({label[:8]})"  # Shorter label for compact
                time_parts.append(time_str)
            combined_time = " / ".join(time_parts)
            return [(deps[0][0], combined_time, None)]

        # Standard mode: up to max_rows
        if len(deps) <= max_rows:
            # Each departure gets its own row
            return [
                (dep, dep.format_time(self.config.time_format), label)
                for dep, label in deps
            ]

        # More departures than max_rows: first (max_rows-1) get own rows, rest combined
        # Limit to 3 total departures per direction
        result = []

        # First (max_rows - 1) departures get their own rows
        for i in range(max_rows - 1):
            dep, label = deps[i]
            result.append((dep, dep.format_time(self.config.time_format), label))

        # Rest are combined on the last row (max 2 more for 3 total)
        rest_deps = deps[max_rows - 1:max_rows + 1]  # Limit to 2 more
        rest_parts = []
        for dep, label in rest_deps:
            time_str = dep.format_time(self.config.time_format)
            if label:
                time_str = f"{time_str} ({label[:8]})"
            rest_parts.append(time_str)
        combined_time = " / ".join(rest_parts)

        result.append((deps[max_rows - 1][0], combined_time, None))

        return result

    def _draw_departure_row_compact(
        self,
        draw: ImageDraw.Draw,
        dep: Departure,
        x: int,
        y: int,
        max_width: int,
        partial_label: Optional[str] = None,
        time_override: Optional[str] = None,
        show_destination: bool = False,
    ) -> None:
        """Draw a compact departure row for column layout (badge + time, optional partial label).

        Args:
            partial_label: If set, shows this destination in brackets (for partial routes).
            time_override: If set, use this string instead of departure's formatted time.
            show_destination: If True, show destination after badge (for single-column layout).
        """
        badge_width = self.BADGE_WIDTH_GROUPED
        badge_height = self.BADGE_HEIGHT_GROUPED
        line_font = self._fonts["line_small"]
        time_font = self._fonts["minutes_small"]
        dest_font = self._fonts["destination_small"]

        # Draw transport badge
        self._draw_transport_badge(draw, x, y + 3, dep, badge_width, badge_height, line_font)

        # Time - right aligned within column
        time_str = time_override if time_override else dep.format_time(self.config.time_format)
        bbox = draw.textbbox((0, 0), time_str, font=time_font)
        time_width = bbox[2] - bbox[0]
        time_x = x + max_width - time_width - 10

        draw.text(
            (time_x, y + 5),
            time_str,
            font=time_font,
            fill=self.BLACK,
        )

        # Show destination if requested (for single-column combined rows)
        if show_destination:
            dest_x = x + badge_width + 10
            dest_max_width = time_x - dest_x - 10
            dest_text = dep.destination

            # Truncate if needed
            bbox = draw.textbbox((0, 0), dest_text, font=dest_font)
            text_width = bbox[2] - bbox[0]
            while text_width > dest_max_width and len(dest_text) > 10:
                dest_text = dest_text[:-4] + "..."
                bbox = draw.textbbox((0, 0), dest_text, font=dest_font)
                text_width = bbox[2] - bbox[0]

            draw.text(
                (dest_x, y + 6),
                dest_text,
                font=dest_font,
                fill=self.BLACK,
            )
        # Show partial route label in brackets if present (for bidirectional columns)
        elif partial_label:
            label_text = f"({partial_label[:12]})"
            label_font = self._fonts["group_header"]
            # Position after badge, before time
            label_x = x + badge_width + 8
            draw.text(
                (label_x, y + 6),
                label_text,
                font=label_font,
                fill=self.GRAY,
            )

    def _draw_group_header(self, draw: ImageDraw.Draw, station_name: str, y: int) -> None:
        """Draw a station group header."""
        x = self.DEPARTURE_PADDING + 10

        # Draw station name in smaller font
        draw.text(
            (x, y + 2),
            station_name.upper(),
            font=self._fonts["group_header"],
            fill=self.GRAY,
        )

        # Draw subtle line under the header
        bbox = draw.textbbox((0, 0), station_name.upper(), font=self._fonts["group_header"])
        text_width = bbox[2] - bbox[0]
        draw.line(
            [(x + text_width + 10, y + 10), (self.WIDTH - 20, y + 10)],
            fill=self.LIGHT_GRAY,
            width=1,
        )

    def _draw_departure_row(
        self, draw: ImageDraw.Draw, dep: Departure, y: int, grouped: bool = False
    ) -> None:
        """Draw a single departure row.

        Args:
            draw: ImageDraw instance
            dep: Departure to draw
            y: Y position
            grouped: Whether this is in grouped view (smaller sizing)
        """
        x = self.DEPARTURE_PADDING + 10

        # Use smaller sizes when grouped
        badge_width = self.BADGE_WIDTH_GROUPED if grouped else self.BADGE_WIDTH
        badge_height = self.BADGE_HEIGHT_GROUPED if grouped else self.BADGE_HEIGHT
        dest_font = self._fonts["destination_small"] if grouped else self._fonts["destination"]
        time_font = self._fonts["minutes_small"] if grouped else self._fonts["minutes"]
        line_font = self._fonts["line_small"] if grouped else self._fonts["line"]

        # Draw transport badge
        self._draw_transport_badge(draw, x, y + 3, dep, badge_width, badge_height, line_font)
        x += badge_width + 12

        # Destination
        dest_max_width = self.WIDTH - x - 100  # Leave space for time
        dest_text = dep.destination

        # Measure and truncate if needed
        bbox = draw.textbbox((0, 0), dest_text, font=dest_font)
        text_width = bbox[2] - bbox[0]

        while text_width > dest_max_width and len(dest_text) > 10:
            dest_text = dest_text[:-4] + "..."
            bbox = draw.textbbox((0, 0), dest_text, font=dest_font)
            text_width = bbox[2] - bbox[0]

        text_y_offset = 6 if grouped else 8
        draw.text(
            (x, y + text_y_offset),
            dest_text,
            font=dest_font,
            fill=self.BLACK,
        )

        # Time - right aligned
        time_str = dep.format_time(self.config.time_format)
        bbox = draw.textbbox((0, 0), time_str, font=time_font)
        time_width = bbox[2] - bbox[0]
        time_x = self.WIDTH - time_width - 15

        draw.text(
            (time_x, y + text_y_offset - 1),
            time_str,
            font=time_font,
            fill=self.BLACK,
        )

        # Delay indicator (if showing delays and there is a delay)
        if self.config.show_delays and dep.delay > 0:
            delay_str = dep.format_delay()
            delay_x = time_x - 35
            draw.text(
                (delay_x, y + text_y_offset + 4),
                delay_str,
                font=self._fonts["delay"],
                fill=self.GRAY,
            )

        # Cancelled indicator
        if dep.cancelled:
            # Draw strikethrough
            strike_y = y + text_y_offset + 8
            draw.line(
                [(x, strike_y), (x + text_width, strike_y)],
                fill=self.BLACK,
                width=2,
            )

    def _draw_transport_badge(
        self,
        draw: ImageDraw.Draw,
        x: int,
        y: int,
        dep: Departure,
        badge_width: int = None,
        badge_height: int = None,
        font: ImageFont.FreeTypeFont = None,
    ) -> None:
        """Draw transport type badge with line number.

        Args:
            draw: ImageDraw instance
            x: X position
            y: Y position
            dep: Departure to draw badge for
            badge_width: Badge width (defaults to BADGE_WIDTH)
            badge_height: Badge height (defaults to BADGE_HEIGHT)
            font: Font for line text (defaults to "line" font)
        """
        style = dep.style
        badge_width = badge_width or self.BADGE_WIDTH
        badge_height = badge_height or self.BADGE_HEIGHT
        font = font or self._fonts["line"]

        # Badge dimensions
        badge_x = x
        badge_y = y
        badge_x2 = x + badge_width
        badge_y2 = y + badge_height

        if style.badge_filled:
            # Filled badge (U-Bahn, S-Bahn)
            draw.rounded_rectangle(
                [(badge_x, badge_y), (badge_x2, badge_y2)],
                radius=self.BADGE_RADIUS,
                fill=self.BLACK,
            )
            text_color = self.WHITE
        else:
            # Outlined badge (Bus, Tram)
            draw.rounded_rectangle(
                [(badge_x, badge_y), (badge_x2, badge_y2)],
                radius=self.BADGE_RADIUS,
                outline=self.BLACK,
                width=2,
            )
            text_color = self.BLACK

        # Draw line text centered in badge
        line_text = dep.line
        bbox = draw.textbbox((0, 0), line_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        text_x = badge_x + (badge_width - text_width) // 2
        text_y = badge_y + (badge_height - text_height) // 2 - 2

        draw.text(
            (text_x, text_y),
            line_text,
            font=font,
            fill=text_color,
        )

    def _draw_error_banner(self, draw: ImageDraw.Draw, errors: list[str]) -> None:
        """Draw error banner at bottom of screen."""
        banner_height = 30
        banner_y = self.HEIGHT - banner_height

        # Banner background with border
        draw.rectangle(
            [(0, banner_y), (self.WIDTH, self.HEIGHT)],
            fill=self.WHITE,
            outline=self.BLACK,
            width=1,
        )

        # Error icon and text
        error_text = "! " + " | ".join(errors[:2])  # Show max 2 errors
        if len(error_text) > 80:
            error_text = error_text[:77] + "..."

        draw.text(
            (10, banner_y + 8),
            error_text,
            font=self._fonts["delay"],
            fill=self.BLACK,
        )

    def _draw_no_departures(self, draw: ImageDraw.Draw) -> None:
        """Draw message when no departures are available."""
        message = "No departures available"
        bbox = draw.textbbox((0, 0), message, font=self._fonts["destination"])
        text_width = bbox[2] - bbox[0]

        x = (self.WIDTH - text_width) // 2
        y = self.HEIGHT // 2 - 10

        draw.text(
            (x, y),
            message,
            font=self._fonts["destination"],
            fill=self.GRAY,
        )

    def _draw_weather_placeholder(self, draw: ImageDraw.Draw) -> None:
        """Draw placeholder when weather is unavailable."""
        x = self.WEATHER_MARGIN + 10
        y = self.WEATHER_MARGIN + 20

        draw.text(
            (x, y),
            "Weather",
            font=self._fonts["weather_desc"],
            fill=self.GRAY,
        )
        draw.text(
            (x, y + 16),
            "unavailable",
            font=self._fonts["weather_desc"],
            fill=self.GRAY,
        )
