# Dynamic Refresh Intervals & Multi-Station Support

**Status:** Implemented in [003-dynamic-refresh-multi-station-impl.md](003-dynamic-refresh-multi-station-impl.md)

---

## Feature: Time-based Refresh Intervals

Adjust refresh intervals based on day of week and time of day.

### Proposed YAML Configuration

```yaml
refresh_schedule:
  mon:
    default: 5min
    intervals:
      - time: "7:00-8:00"
        freq: 1min
      - time: "15:50-16:30"
        freq: 1min
  tue:
    default: 5min
    intervals:
      - time: "7:00-8:00"
        freq: 1min
      - time: "15:50-16:30"
        freq: 1min
  wed:
    default: 5min
    intervals:
      - time: "7:00-8:00"
        freq: 1min
      - time: "15:50-16:30"
        freq: 1min
  thu:
    default: 5min
    intervals:
      - time: "7:00-8:00"
        freq: 1min
      - time: "15:50-16:30"
        freq: 1min
  fri:
    default: 5min
    intervals:
      - time: "7:00-8:00"
        freq: 1min
      - time: "15:50-16:30"
        freq: 1min
  sat:
    default: 10min
  sun:
    default: 10min
```

### Open Question

Does TRMNL device support dynamic refresh intervals, or is this server-side only?

---

## Feature: Multi-Station Departures

Display departures from multiple stations with specific line/direction filters.

### Proposed YAML Configuration

```yaml
# Station name shown in display header
display_station: "Ridlerstrasse"

departures:
  - station: "Ridlerstrasse"
    filters:
      - type: bus
        line: "53"
        direction: "Harras"
      - type: bus
        line: "53"
        direction: "auto"  # Determine opposite direction from API

  - station: "Heimeranplatz"
    filters:
      - type: bus
        line: "62"
        direction: "Rotkreuzplatz"

  - station: "Schwanthalerhoehe"
    filters:
      - type: ubahn
        line: "U5"
        direction: "Neuperlach Sued"
```

### Implementation Notes

1. Need to query MVG API for available directions per line
2. Support "auto" direction detection (opposite of specified)
3. Aggregate departures from multiple stations
4. Sort by departure time across all stations
