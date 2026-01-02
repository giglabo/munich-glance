"""Interactive CLI for configuring MunichGlance departures."""

import asyncio
import sys
from dataclasses import dataclass, field
from typing import Optional

import questionary
import yaml
from rapidfuzz import fuzz, process


@dataclass
class FilterConfig:
    """A single departure filter configuration."""

    transport_type: str
    line: Optional[str] = None
    direction: Optional[str] = None


@dataclass
class StationFilterConfig:
    """Configuration for one station with its filters."""

    station_name: str
    station_id: str
    filters: list[FilterConfig] = field(default_factory=list)


@dataclass
class ConfigSession:
    """Holds the current configuration session state."""

    stations: list[StationFilterConfig] = field(default_factory=list)
    display_station: Optional[str] = None
    all_mvg_stations: list[dict] = field(default_factory=list)


# Transport type display names
TRANSPORT_TYPES = {
    "UBAHN": "U-Bahn",
    "SBAHN": "S-Bahn",
    "TRAM": "Tram",
    "BUS": "Bus",
    "REGIONAL_BUS": "Regional Bus",
}


async def load_all_stations() -> list[dict]:
    """Load all MVG stations for fuzzy search."""
    from mvg import MvgApi

    print("Loading MVG stations...")
    stations = await MvgApi.stations_async()
    print(f"Loaded {len(stations)} stations.")
    return stations


def fuzzy_search_stations(
    query: str, stations: list[dict], limit: int = 10
) -> list[tuple[dict, float]]:
    """Fuzzy search stations by name.

    Args:
        query: Search query
        stations: List of station dicts with 'name' and 'place'
        limit: Max results to return

    Returns:
        List of (station_dict, score) tuples sorted by score descending
    """
    if not query.strip():
        return []

    # Create searchable strings combining name and place
    choices = []
    for station in stations:
        name = station.get("name", "")
        place = station.get("place", "")
        # Combine for better matching
        full_name = f"{name}, {place}" if place else name
        choices.append((full_name, station))

    # Use rapidfuzz to find best matches
    results = process.extract(
        query,
        [c[0] for c in choices],
        scorer=fuzz.WRatio,
        limit=limit,
    )

    # Map back to station dicts
    matched = []
    for match_name, score, _idx in results:
        for full_name, station in choices:
            if full_name == match_name:
                matched.append((station, score))
                break

    return matched


async def fetch_departures_for_station(station_id: str) -> list[dict]:
    """Fetch current departures to discover available lines."""
    from mvg import MvgApi

    try:
        departures = await MvgApi.departures_async(station_id, limit=50)
        return departures
    except Exception as e:
        print(f"Error fetching departures: {e}")
        return []


def group_departures_by_type_and_line(
    departures: list[dict],
) -> dict[str, dict[str, set[str]]]:
    """Group departures by transport type, then line, then collect destinations.

    Returns:
        {transport_type: {line: {destination1, destination2, ...}}}
    """
    grouped: dict[str, dict[str, set[str]]] = {}

    for dep in departures:
        raw_type = dep.get("type", dep.get("transportType", ""))
        transport_type = raw_type.upper().replace("-", "").replace(" ", "")

        line = dep.get("line", dep.get("label", ""))
        destination = dep.get("destination", "")

        if transport_type not in grouped:
            grouped[transport_type] = {}
        if line not in grouped[transport_type]:
            grouped[transport_type][line] = set()
        if destination:
            grouped[transport_type][line].add(destination)

    return grouped


async def select_station(session: ConfigSession) -> Optional[dict]:
    """Interactive station selection with fuzzy search."""
    while True:
        query = await questionary.text(
            "Enter station name (fuzzy search):",
            validate=lambda x: len(x.strip()) >= 2 or "Enter at least 2 characters",
        ).ask_async()

        if query is None:  # User cancelled
            return None

        matches = fuzzy_search_stations(query, session.all_mvg_stations)

        if not matches:
            print("No matching stations found. Try again.")
            continue

        # Build choices for selection
        choices = []
        for station, score in matches:
            name = station.get("name", "")
            place = station.get("place", "")
            display = f"{name}, {place}" if place else name
            choices.append(questionary.Choice(title=f"{display} ({score:.0f}%)", value=station))

        choices.append(questionary.Choice(title="[Search again]", value="search_again"))
        choices.append(questionary.Choice(title="[Cancel]", value=None))

        selected = await questionary.select(
            "Select a station:",
            choices=choices,
        ).ask_async()

        if selected == "search_again":
            continue
        # Return None for cancel or if not a valid station dict
        if selected is None or not isinstance(selected, dict):
            return None
        return selected


async def select_transport_types(available_types: list[str]) -> list[str]:
    """Let user select which transport types to include."""
    choices = []
    for t in available_types:
        display_name = TRANSPORT_TYPES.get(t, t)
        choices.append(questionary.Choice(title=display_name, value=t))

    selected = await questionary.checkbox(
        "Select transport types to include:",
        choices=choices,
        validate=lambda x: len(x) > 0 or "Select at least one transport type",
    ).ask_async()

    return selected or []


async def select_lines_for_type(
    transport_type: str, lines_with_destinations: dict[str, set[str]]
) -> list[tuple[str, Optional[str]]]:
    """Let user select lines and directions for a transport type.

    Returns:
        List of (line, direction) tuples. direction is None for "all", "auto", or specific.
    """
    display_type = TRANSPORT_TYPES.get(transport_type, transport_type)
    result = []

    # First, select which lines
    line_choices = [questionary.Choice(title=f"{line}", value=line) for line in sorted(lines_with_destinations.keys())]

    if not line_choices:
        print(f"No {display_type} lines available at this station.")
        return []

    selected_lines = await questionary.checkbox(
        f"Select {display_type} lines:",
        choices=line_choices,
        validate=lambda x: len(x) > 0 or "Select at least one line",
    ).ask_async()

    if not selected_lines:
        return []

    # For each selected line, ask about direction
    for line in selected_lines:
        destinations = sorted(lines_with_destinations.get(line, set()))

        if len(destinations) <= 1:
            # Only one direction or none, just include all
            result.append((line, None))
            continue

        # Multiple destinations - ask user
        direction_choices = [
            questionary.Choice(title="All directions", value="all"),
            questionary.Choice(title="Auto (opposite of selected)", value="auto"),
        ]
        for dest in destinations:
            direction_choices.append(questionary.Choice(title=dest, value=dest))

        selected_direction = await questionary.select(
            f"Direction for {display_type} line {line}:",
            choices=direction_choices,
        ).ask_async()

        if selected_direction == "all":
            result.append((line, None))
        elif selected_direction == "auto":
            # For auto, we need a paired direction. Ask which one to auto-opposite.
            paired = await questionary.select(
                f"Select the direction to auto-opposite (departures NOT going here):",
                choices=[questionary.Choice(title=d, value=d) for d in destinations],
            ).ask_async()
            # Add both: the explicit direction and the auto
            result.append((line, paired))
            result.append((line, "auto"))
        else:
            result.append((line, selected_direction))

    return result


async def configure_station(session: ConfigSession) -> Optional[StationFilterConfig]:
    """Configure filters for a single station."""
    # Select station
    station = await select_station(session)
    if station is None or not isinstance(station, dict):
        return None

    station_name = station.get("name", "")
    station_id = station.get("id", "")
    place = station.get("place", "")

    display_name = f"{station_name}, {place}" if place else station_name
    print(f"\nConfiguring: {display_name} ({station_id})")

    # Fetch departures to see available lines
    print("Fetching available lines...")
    departures = await fetch_departures_for_station(station_id)

    if not departures:
        print("No departures found. Station might have no current service.")
        add_anyway = await questionary.confirm(
            "Add station anyway with no filters (accepts all departures)?",
            default=False,
        ).ask_async()
        if add_anyway:
            return StationFilterConfig(station_name=station_name, station_id=station_id)
        return None

    # Group by transport type and line
    grouped = group_departures_by_type_and_line(departures)

    # Show available types
    available_types = list(grouped.keys())
    print(f"\nAvailable transport types: {', '.join(TRANSPORT_TYPES.get(t, t) for t in available_types)}")

    # Select transport types
    selected_types = await select_transport_types(available_types)
    if not selected_types:
        return None

    # For each type, select lines and directions
    filters = []
    for transport_type in selected_types:
        lines_data = grouped.get(transport_type, {})
        line_directions = await select_lines_for_type(transport_type, lines_data)

        for line, direction in line_directions:
            filters.append(
                FilterConfig(
                    transport_type=transport_type,
                    line=line,
                    direction=direction,
                )
            )

    if not filters:
        # No specific filters - add type-only filters
        for transport_type in selected_types:
            filters.append(FilterConfig(transport_type=transport_type))

    return StationFilterConfig(
        station_name=station_name,
        station_id=station_id,
        filters=filters,
    )


def generate_yaml_output(session: ConfigSession) -> str:
    """Generate YAML configuration output."""
    # Build departures list
    departures = []
    for station_config in session.stations:
        station_entry = {"station": station_config.station_name}

        if station_config.filters:
            filters_list = []
            for f in station_config.filters:
                filter_entry = {"type": f.transport_type}
                if f.line:
                    filter_entry["line"] = f.line
                if f.direction:
                    filter_entry["direction"] = f.direction
                filters_list.append(filter_entry)
            station_entry["filters"] = filters_list

        departures.append(station_entry)

    # Build MVG section
    mvg_section = {
        "display_station": session.display_station or session.stations[0].station_name,
    }

    output = {
        "mvg": mvg_section,
        "departures": departures,
    }

    return yaml.dump(output, default_flow_style=False, sort_keys=False, allow_unicode=True)


async def run_interactive() -> None:
    """Run the interactive configuration session."""
    print("=" * 60)
    print("MunichGlance Departures Configuration")
    print("=" * 60)
    print()

    session = ConfigSession()

    # Load all stations for fuzzy search
    try:
        session.all_mvg_stations = await load_all_stations()
    except Exception as e:
        print(f"Failed to load MVG stations: {e}")
        print("Please check your internet connection and try again.")
        sys.exit(1)

    # Configure stations
    while True:
        station_config = await configure_station(session)

        if station_config:
            session.stations.append(station_config)
            print(f"\nAdded: {station_config.station_name} with {len(station_config.filters)} filter(s)")

        if session.stations:
            add_more = await questionary.confirm(
                "Add another station?",
                default=False,
            ).ask_async()

            if not add_more:
                break
        else:
            retry = await questionary.confirm(
                "No stations configured. Try again?",
                default=True,
            ).ask_async()
            if not retry:
                print("No configuration generated.")
                sys.exit(0)

    # Set display station name
    if len(session.stations) == 1:
        session.display_station = session.stations[0].station_name
    else:
        choices = [
            questionary.Choice(title=s.station_name, value=s.station_name)
            for s in session.stations
        ]
        choices.append(questionary.Choice(title="[Enter custom name]", value="_custom_"))

        selected = await questionary.select(
            "Select display station name (shown in header):",
            choices=choices,
        ).ask_async()

        if selected == "_custom_":
            session.display_station = await questionary.text(
                "Enter custom display name:"
            ).ask_async()
        else:
            session.display_station = selected

    # Generate and output YAML
    print()
    print("=" * 60)
    print("Generated Configuration (add to app-config.yaml)")
    print("=" * 60)
    print()
    yaml_output = generate_yaml_output(session)
    print(yaml_output)
    print("=" * 60)


def main() -> None:
    """Entry point for the CLI."""
    try:
        asyncio.run(run_interactive())
    except KeyboardInterrupt:
        print("\nConfiguration cancelled.")
        sys.exit(0)


if __name__ == "__main__":
    main()
