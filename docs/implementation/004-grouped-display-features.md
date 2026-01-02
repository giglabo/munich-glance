# 004: Grouped Display with Bidirectional Columns

**Date:** January 2026
**Status:** Complete

## Overview

This document describes the implementation of grouped departure display with bidirectional two-column layout, configurable font scaling, and timezone support.

## Goals

1. Show departures grouped by station with station headers
2. Display bidirectional departures (same line, 2 directions) in two columns
3. Allow configurable font scaling via `font_scale` setting
4. Display times using configured timezone
5. Fix separator line to not cross date text in weather box

## Features Implemented

### 1. Grouped Display (`show_groups`)

When `show_groups: true` (default), departures are grouped by their source station:

- Each station gets a header with its name in gray uppercase
- A subtle line extends from the station name to the right edge
- Departure rows are slightly smaller to fit more content

### 2. Bidirectional Two-Column Layout

When a station has exactly 2 different destinations (bidirectional), the display splits into two columns:

```
RIDLERSTRASSE
→ Münchner Freiheit          → Aidenbachstraße
[53]           6 min         [53]           6 min
[53]          16 min         [53]          17 min
```

- Each column has a direction header (→ Direction)
- Compact rows show only badge + time (no destination text since it's in header)
- Columns are evenly split across the display width

### 3. Configurable Font Scale

All fonts can be scaled using the `font_scale` setting:

```yaml
mvg:
  font_scale: 1.0  # Default
  # font_scale: 0.8  # Smaller fonts
  # font_scale: 1.2  # Larger fonts
```

The scale factor is applied to all font sizes during initialization.

### 4. Timezone Support

Times are displayed using the configured timezone:

```yaml
server:
  timezone: "Europe/Berlin"  # Default
```

Uses Python's `zoneinfo.ZoneInfo` for timezone conversion.

### 5. Fixed Separator Line

The separator line between header and departures now starts after the weather box, avoiding overlap with the date text.

## Architecture

### New/Modified Methods in Renderer

```
MunichGlanceRenderer
  ├── _get_now() -> datetime              # Get timezone-aware current time
  ├── _load_fonts()                       # Now applies font_scale
  ├── _draw_separator()                   # Starts after weather box
  ├── _draw_departures_grouped()          # Handles bidirectional detection
  ├── _get_bidirectional_groups()         # Detects 2-direction pattern
  ├── _draw_bidirectional_columns()       # Two-column layout
  └── _draw_departure_row_compact()       # Compact row for columns
```

### Data Flow for Grouped Display

```
departures list
      │
      ▼
┌─────────────────────────────────────┐
│  Group by station_name + line       │
│  (allows per-line bidirectional)    │
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│  Sort groups by config order        │
│  (preserves user-defined priority)  │
└─────────────────────────────────────┘
      │
      ▼
For each station+line group:
      │
      ├── Draw station header (if station changed)
      │
      ▼
┌─────────────────────────────────────┐
│  _get_bidirectional_groups()        │
│  Check if exactly 2 destinations    │
└─────────────────────────────────────┘
      │
      ├── Yes (2 directions) ──► _draw_bidirectional_columns()
      │                          Two-column compact layout
      │
      └── No ──► Single column with _draw_departure_row()
```

**Important:** Station order on the display matches the order in `departures` config.
Multiple lines at the same station are grouped together under one header.

## Configuration

### YAML Settings

```yaml
mvg:
  # Group departures by station
  show_groups: true

  # Font scale factor
  font_scale: 1.0

server:
  # Timezone for time display
  timezone: "Europe/Berlin"
```

### Config Class Changes

```python
@dataclass
class MunichGlanceConfig:
    # ...
    show_groups: bool = True
    font_scale: float = 1.0
    timezone: str = "Europe/Berlin"
```

## Files Modified

| File | Changes |
|------|---------|
| `plugins/munichglance/config.py` | Added `font_scale`, `timezone` fields |
| `plugins/munichglance/renderer.py` | Bidirectional columns, font scaling, timezone |
| `plugins/munichglance/departures.py` | Added `station_name` to Departure dataclass |
| `config/app-config.yaml` | Added `font_scale` setting |

## Layout Constants

```python
# Grouped view uses smaller sizes
DEPARTURE_ROW_HEIGHT_GROUPED = 36  # vs 42 for flat
BADGE_WIDTH_GROUPED = 42           # vs 48 for flat
BADGE_HEIGHT_GROUPED = 24          # vs 28 for flat
GROUP_HEADER_HEIGHT = 22
```

## Edge Cases

| Case | Handling |
|------|----------|
| Single direction only | Falls back to single-column layout |
| 3+ directions per line | Falls back to single-column layout |
| Multiple lines same station | Each line gets separate bidirectional check |
| No station_name on departure | Uses "Unknown" as group name |
| Station not in config | Appears last (after configured stations) |
| Invalid timezone | Raises exception on startup |
| font_scale < 0.5 or > 2.0 | No validation, but may cause layout issues |

## Visual Example

**With bidirectional (Bus 53 to 2 directions):**
```
RIDLERSTRASSE ─────────────────────────
→ Münchner Freiheit    → Aidenbachstraße
[53]        6 min      [53]        6 min
[53]       16 min      [53]       17 min
```

**Without bidirectional (U5 to 1 direction):**
```
SCHWANTHALERHÖHE ──────────────────────
[U5] Neuperlach Süd              2 min
[U5] Neuperlach Süd             12 min
```

## Future Improvements

- [ ] Add validation for font_scale range
- [ ] Support more than 2 columns for 3+ directions
- [ ] Allow per-station column configuration
- [ ] Add column width customization
