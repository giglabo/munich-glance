# 003: Dynamic Refresh & Multi-Station Implementation

**Date:** January 2025
**Status:** Complete
**Implements:** [002-dynamic-refresh-multi-station.md](002-dynamic-refresh-multi-station.md)

## Overview

This document describes the implementation of dynamic refresh intervals based on day/time and multi-station departure aggregation with line/direction filtering for the MunichGlance plugin.

## Goals

1. Adjust TRMNL device refresh rate based on day of week and time of day
2. Fetch departures from multiple MVG stations
3. Filter departures by specific lines and directions
4. Support "auto" direction detection (opposite of specified direction)
5. Aggregate and sort departures across all stations

## Design Decisions

### Dynamic Refresh Strategy

**Decision:** Modify `/api/display` response `refresh_rate` rather than rescheduling background jobs.

**Rationale:**
- TRMNL device controls its own refresh timing based on `refresh_rate` response
- Scheduler's job is to keep cache warm, not drive device refresh
- Simpler implementation with fewer moving parts
- Device respects the returned `refresh_rate` for next wake cycle

### Auto Direction Resolution

**Decision:** Infer from paired filter - "auto" matches anything NOT going to the explicitly specified direction.

**Rationale:**
- MVG API returns `destination` field, not explicit direction IDs
- Simple to implement without additional API calls
- Intuitive for users: specify one direction, auto catches the other

### Backward Compatibility

**Decision:** No backward compatibility - replace old `mvg.station_name` config entirely.

**Rationale:**
- Cleaner configuration structure
- Multi-station is strictly more powerful
- Single-station is just multi-station with one entry

## Architecture

### New Dataclasses

```
┌─────────────────────────────────────────────────────────────────┐
│                     Refresh Schedule                             │
├─────────────────────────────────────────────────────────────────┤
│  RefreshSchedule                                                 │
│    ├── default: int (fallback seconds)                          │
│    ├── mon: DaySchedule                                          │
│    ├── tue: DaySchedule                                          │
│    ├── ... (wed, thu, fri, sat, sun)                            │
│    └── get_refresh_rate(weekday, time) -> int                   │
│                                                                  │
│  DaySchedule                                                     │
│    ├── default: int                                              │
│    ├── intervals: list[TimeInterval]                            │
│    └── get_refresh_rate(time) -> int                            │
│                                                                  │
│  TimeInterval                                                    │
│    ├── start: time                                               │
│    ├── end: time                                                 │
│    ├── refresh: int                                              │
│    └── contains(time) -> bool  # handles midnight crossing       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    Multi-Station Config                          │
├─────────────────────────────────────────────────────────────────┤
│  MultiStationConfig                                              │
│    ├── display_station: str (header name)                       │
│    └── stations: list[StationConfig]                            │
│                                                                  │
│  StationConfig                                                   │
│    ├── station: str (MVG station name)                          │
│    ├── filters: list[DepartureFilter]                           │
│    └── get_opposite_direction(line) -> str                      │
│                                                                  │
│  DepartureFilter                                                 │
│    ├── type: str (UBAHN, BUS, etc.)                             │
│    ├── line: str (optional)                                     │
│    ├── direction: str ("auto" or destination)                   │
│    └── matches(transport_type, line, destination) -> bool       │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                  MultiStationClient.get_departures()             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Station 1    │  │ Station 2    │  │ Station 3    │          │
│  │ Ridlerstr.   │  │ Heimeranpl.  │  │ Schwanth.    │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                  │
│         ▼                  ▼                  ▼                  │
│  ┌─────────────────────────────────────────────────────┐        │
│  │              asyncio.gather() - parallel fetch       │        │
│  └─────────────────────────────────────────────────────┘        │
│         │                  │                  │                  │
│         ▼                  ▼                  ▼                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Apply Filters│  │ Apply Filters│  │ Apply Filters│          │
│  │ Bus 53 → H.  │  │ Bus 62 → R.  │  │ U5 → N.S.    │          │
│  │ Bus 53 ← auto│  │              │  │              │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                  │
│         └──────────────────┼──────────────────┘                  │
│                            ▼                                     │
│                 ┌─────────────────────┐                         │
│                 │   Merge & Sort by   │                         │
│                 │   actual_time       │                         │
│                 └──────────┬──────────┘                         │
│                            ▼                                     │
│                 ┌─────────────────────┐                         │
│                 │  Truncate to limit  │                         │
│                 │  (departure_limit)  │                         │
│                 └─────────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

## Implementation Details

### Files Modified

| File | Changes |
|------|---------|
| `plugins/munichglance/config.py` | +7 new dataclasses, updated `MunichGlanceConfig` |
| `plugins/munichglance/departures.py` | Added `MultiStationClient` class (~180 lines) |
| `plugins/munichglance/plugin.py` | Use `MultiStationClient`, added `get_dynamic_refresh_rate()` |
| `routes/api.py` | Return dynamic `refresh_rate` from plugin |
| `config/app-config.yaml` | New structure with `refresh_schedule` and `departures` |

### Key Code Changes

#### 1. TimeInterval with Midnight Crossing Support

```python
@dataclass
class TimeInterval:
    start: time
    end: time
    refresh: int

    def contains(self, t: time) -> bool:
        if self.start <= self.end:
            # Normal interval (e.g., 07:00-08:00)
            return self.start <= t < self.end
        else:
            # Midnight-crossing interval (e.g., 23:00-01:00)
            return t >= self.start or t < self.end
```

#### 2. Dynamic Refresh Rate Calculation

```python
def get_dynamic_refresh_rate(self) -> int:
    if not self.plugin_config.refresh_schedule:
        return self.plugin_config.departures_refresh_interval

    now = datetime.now()
    return self.plugin_config.refresh_schedule.get_refresh_rate(
        weekday=now.weekday(),  # 0=Monday
        current_time=now.time(),
    )
```

#### 3. API Response with Dynamic Refresh

```python
# In routes/api.py get_display()
refresh_rate = config.refresh_time  # Default
plugin = get_plugin(plugin_name)
if plugin and hasattr(plugin, "get_dynamic_refresh_rate"):
    refresh_rate = plugin.get_dynamic_refresh_rate()

return DisplayResponse(..., refresh_rate=refresh_rate)
```

#### 4. Parallel Station Fetching

```python
async def _fetch_all_stations(self) -> list[Departure]:
    tasks = []
    for station_config in self.config.multi_station.stations:
        tasks.append(self._fetch_station(station_config))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_departures = []
    for result in results:
        if not isinstance(result, Exception):
            all_departures.extend(result)

    all_departures.sort(key=lambda d: d.actual_time)
    return all_departures[:self.config.departure_limit]
```

#### 5. Auto Direction Matching

```python
def get_opposite_direction(self, line: str) -> Optional[str]:
    """Find explicit direction for same line to use as 'NOT' match."""
    for f in self.filters:
        if f.line == line and f.direction and f.direction.lower() != "auto":
            return f.direction
    return None

def matches(self, transport_type, line, destination, opposite_direction=None):
    # ... type and line matching ...

    if self.direction.lower() == "auto":
        # Match anything NOT going to the opposite direction
        if opposite_direction and destination == opposite_direction:
            return False
    else:
        if destination.lower() != self.direction.lower():
            return False
    return True
```

## Configuration

### YAML Structure

```yaml
# Dynamic refresh based on day/time
refresh_schedule:
  default: 300  # 5 min fallback
  mon: &weekday
    default: 300
    intervals:
      - time: "07:00-08:00"
        refresh: 60
      - time: "15:50-16:30"
        refresh: 60
  tue: *weekday
  wed: *weekday
  thu: *weekday
  fri: *weekday
  sat:
    default: 600  # 10 min
  sun:
    default: 600

# Multi-station departures
mvg:
  display_station: "Ridlerstrasse"
  departure_limit: 10
  # ... other shared settings ...

departures:
  - station: "Ridlerstrasse"
    filters:
      - type: BUS
        line: "53"
        direction: "Harras"
      - type: BUS
        line: "53"
        direction: auto  # Opposite of Harras

  - station: "Heimeranplatz"
    filters:
      - type: BUS
        line: "62"
        direction: "Rotkreuzplatz"

  - station: "Schwanthalerhoehe"
    filters:
      - type: UBAHN
        line: "U5"
        direction: "Neuperlach Sued"
```

## Edge Cases Handled

| Case | Handling |
|------|----------|
| Midnight-crossing interval (23:00-01:00) | `TimeInterval.contains()` uses OR logic |
| No refresh_schedule defined | Falls back to `departures_refresh_interval` |
| Missing day in schedule | Uses global `default` |
| Station not found | Logs error, continues with other stations |
| Empty filter list | Accepts all departures from that station |
| "auto" without paired direction | Logs warning, skips that filter |
| Line name variations ("53" vs "Bus 53") | Normalizes by stripping prefixes |

## Testing

### Syntax Validation

```bash
python3 -m py_compile trmnl_server/plugins/munichglance/config.py
python3 -m py_compile trmnl_server/plugins/munichglance/departures.py
python3 -m py_compile trmnl_server/plugins/munichglance/plugin.py
python3 -m py_compile trmnl_server/routes/api.py
# All passed
```

### Manual Testing Checklist

- [ ] TimeInterval parsing with various time ranges
- [ ] Midnight crossing intervals (23:00-01:00)
- [ ] DaySchedule.get_refresh_rate() with overlapping intervals
- [ ] RefreshSchedule weekday selection
- [ ] DepartureFilter.matches() all combinations
- [ ] Auto direction inference
- [ ] MultiStationClient aggregation and sorting
- [ ] API returns dynamic refresh_rate

## Migration Notes

### Breaking Changes

- `mvg.station_name` and `mvg.station_id` are removed
- `mvg.transport_types` is removed (use filters per station)
- New `departures` section required for departure fetching

### Migration Steps

1. Replace `station_name`/`station_id` with `display_station`
2. Add `departures` section with station configurations
3. Optionally add `refresh_schedule` section for dynamic refresh

## Future Improvements

- [ ] Cache station ID resolution to avoid repeated lookups
- [ ] Add per-station offset_minutes for walking time
- [ ] Support regex patterns in direction matching
- [ ] Add departure deduplication for connected stations
- [ ] Implement station ID direct configuration to bypass name resolution
