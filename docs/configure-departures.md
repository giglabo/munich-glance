# Configuring Departures with the Interactive CLI

This guide walks you through using the interactive configuration tool to set up multi-station departure tracking for MunichGlance.

## Quick Start

```bash
# Activate your virtual environment
source .venv/bin/activate

# Run the configuration tool
python -m trmnl_server.cli.configure
```

Or if installed via pip:
```bash
munich-glance-configure
```

## What This Tool Does

The interactive CLI helps you:

1. **Search for stations** using fuzzy matching (no need for exact names)
2. **Select transport types** (U-Bahn, S-Bahn, Tram, Bus)
3. **Choose specific lines** from real-time departure data
4. **Configure directions** (all, auto-opposite, or specific destination)
5. **Generate ready-to-use YAML** for your `app-config.yaml`

## Step-by-Step Walkthrough

### Step 1: Station Search

When you start the tool, it loads all MVG stations (this takes a few seconds on first run).

```
============================================================
MunichGlance Departures Configuration
============================================================

Loading MVG stations...
Loaded 1847 stations.
Enter station name (fuzzy search): ridler
```

**Tips for searching:**
- Type partial names: `ridler` finds "Ridlerstrasse"
- Include location: `haupt mun` finds "Hauptbahnhof, München"
- Misspellings work: `schwabing` or `schwabng` both work

### Step 2: Select from Matches

The tool shows the best matches with similarity scores:

```
Select a station:
> Ridlerstrasse, München (92%)
  Ridlerplatz, München (78%)
  Riedlerweg, Wolfratshausen (65%)
  [Search again]
  [Cancel]
```

Use arrow keys to navigate, Enter to select.

### Step 3: Choose Transport Types

After selecting a station, you'll see available transport types:

```
Configuring: Ridlerstrasse, München (de:09162:460)
Fetching available lines...

Available transport types: Bus, Tram
Select transport types to include:
> [x] Bus
  [ ] Tram
```

Use Space to toggle, Enter to confirm.

### Step 4: Select Lines

For each transport type, choose which lines to track:

```
Select Bus lines:
> [x] 53
  [x] 134
  [ ] N40
```

### Step 5: Configure Directions

For each selected line, choose how to filter directions:

```
Direction for Bus line 53:
> All directions
  Auto (opposite of selected)
  Aidenbachstraße
  Münchner Freiheit
```

**Direction Options Explained:**

| Option | What it does | When to use |
|--------|--------------|-------------|
| **All directions** | Shows departures in both directions | You want to see everything |
| **Auto** | Shows the opposite of another direction | Commuting: one direction morning, opposite evening |
| **Specific** | Only shows that exact destination | You only ever go one way |

### Step 6: Using "Auto" Direction

If you select "Auto", you'll be asked which direction to auto-opposite:

```
Direction for Bus line 53:
> Auto (opposite of selected)

Select the direction to auto-opposite (departures NOT going here):
> Aidenbachstraße
  Münchner Freiheit
```

This creates TWO filters:
1. Explicit: `direction: Aidenbachstraße`
2. Auto: `direction: auto` (matches everything NOT going to Aidenbachstraße)

**Use case:** You take Bus 53 toward Aidenbachstraße in the morning, and the opposite direction in the evening. With auto, both directions are tracked, but the system knows they're opposites.

### Step 7: Add More Stations

After configuring one station:

```
Added: Ridlerstrasse with 3 filter(s)
Add another station? (y/N):
```

You can add as many stations as you need. Departures from all stations are merged and sorted by time.

### Step 8: Set Display Name

If you have multiple stations, choose what to show in the header:

```
Select display station name (shown in header):
> Ridlerstrasse
  Heimeranplatz
  [Enter custom name]
```

Or enter a custom name like "Home" or "Work".

### Step 9: Copy the Output

The tool generates YAML configuration:

```
============================================================
Generated Configuration (add to app-config.yaml)
============================================================

mvg:
  display_station: Ridlerstrasse
departures:
  - station: Ridlerstrasse
    filters:
      - type: BUS
        line: '53'
        direction: Aidenbachstraße
      - type: BUS
        line: '53'
        direction: auto
      - type: BUS
        line: '134'
  - station: Heimeranplatz
    filters:
      - type: UBAHN
        line: U4
        direction: Arabellapark

============================================================
```

Copy this output and paste it into your `config/app-config.yaml`.

## Configuration Examples

### Example 1: Simple Single Station

Track all U-Bahn from Marienplatz:

```yaml
mvg:
  display_station: Marienplatz
departures:
  - station: Marienplatz
    filters:
      - type: UBAHN
```

### Example 2: Specific Lines and Directions

Track Bus 53 both ways from Ridlerstrasse:

```yaml
mvg:
  display_station: Ridlerstrasse
departures:
  - station: Ridlerstrasse
    filters:
      - type: BUS
        line: '53'
        direction: Harras
      - type: BUS
        line: '53'
        direction: auto
```

### Example 3: Multiple Stations (Commute)

Track connections from home area to work:

```yaml
mvg:
  display_station: Home
departures:
  - station: Ridlerstrasse
    filters:
      - type: BUS
        line: '53'
        direction: Harras
  - station: Heimeranplatz
    filters:
      - type: UBAHN
        line: U4
        direction: Arabellapark
      - type: UBAHN
        line: U5
        direction: Neuperlach Süd
  - station: Schwanthalerhöhe
    filters:
      - type: UBAHN
        line: U4
```

### Example 4: All Transport from One Station

No filters means accept all departures:

```yaml
mvg:
  display_station: Hauptbahnhof
departures:
  - station: Hauptbahnhof
```

## Troubleshooting

### "No matching stations found"

- Try a shorter search term
- Check spelling (fuzzy matching tolerates errors but not completely wrong names)
- Use German umlauts or their alternatives: `ü` = `ue`, `ö` = `oe`, `ä` = `ae`

### "No departures found"

- The station might have no current service (late night, construction)
- Try a different time of day
- You can still add the station with no filters

### "Failed to load MVG stations"

- Check your internet connection
- The MVG API might be temporarily unavailable
- Try again in a few minutes

### Configuration not taking effect

After updating `app-config.yaml`:

```bash
# Restart the server
docker compose restart

# Or for local development
# Stop with Ctrl+C and restart
python -m trmnl_server
```

## Tips for Best Results

1. **Start broad, then narrow down** - Add fewer filters first, see what appears, then refine

2. **Use auto for commutes** - If you travel the same line both ways at different times, auto direction handles this elegantly

3. **Combine nearby stations** - If you're equidistant from two stations, add both to see all options

4. **Order stations by priority** - Stations appear on the display in the same order as in your config. Put your most important station first!

5. **Test with the preview** - After configuring, check http://localhost:4567 to see how it looks

6. **Adjust walking time** - In `app-config.yaml`, set `offset_minutes` to filter out departures you can't catch:
   ```yaml
   mvg:
     offset_minutes: 3  # Hide departures less than 3 minutes away
   ```

## Full Configuration Reference

After running the CLI, you can fine-tune additional settings in `app-config.yaml`:

```yaml
mvg:
  display_station: My Station    # Header text
  departure_limit: 15            # Max departures to fetch (increase for multiple stations)
  offset_minutes: 2              # Walking time buffer
  max_minutes: 60                # Don't show >60 min away
  show_delays: true              # Show +3 delay indicators
  show_platform: false           # Show platform numbers
  show_cancelled: true           # Show cancelled departures
  show_groups: true              # Group departures by station with headers
  compact_directions: false      # true: 1 row per line, false: max 2 rows per line
  time_format: relative          # "relative" (5 min) or "absolute" (14:32)

departures:
  # Generated by munich-glance-configure
  - station: ...
    filters: ...
```

**Note:** The `departure_limit` is the total number of departures fetched from the API across all stations. When tracking multiple stations, increase this value (e.g., 15-20) to ensure each station gets enough departures. Max 3 departures are shown per line/direction on the display.

### Show Groups Option

When `show_groups: true` (default), departures are grouped by their source station:

- Each station gets a header with its name
- Departure rows are slightly smaller to fit more information
- Useful when tracking multiple stations to see at a glance which departures are from which station
- Lines with exactly 2 directions (bidirectional) are displayed in two columns

When `show_groups: false`, all departures are shown in a flat list sorted by time, without station headers.

### Compact Directions Option

The `compact_directions` setting controls how lines are displayed in grouped mode. **Maximum 3 departures per line/direction** are shown in both modes.

**When `compact_directions: false` (default):**

Each line shows up to **2 rows** with max 3 departures total:
- Row 1: First departure with destination
- Row 2: Next 2 departures combined with " / " separators

```
RIDLERSTRASSE ------------------------------------------------
[134] Fürstenried West                                    now
[134] Fürstenried West                         20 min / 40 min

→ Münchner Freiheit              → Aidenbachstraße
[53]              10 min         [53]                   18 min
[53]              30 min         [53]                   38 min

SCHWANTHALERHÖHE ---------------------------------------------
[U5] Neuperlach Süd                                     5 min
[U5] Neuperlach Süd                            15 min / 25 min
```

**When `compact_directions: true`:**

Each line shows exactly **1 row** with up to 3 departure times combined using " / " separators.

```
RIDLERSTRASSE ------------------------------------------------
[134] Fürstenried West                  4 min / 24 min / 44 min

→ Aidenbachstraße                    → Münchner Freiheit
[53]    2 min / 22 min / 42 min      [53]       14 min / 34 min

SCHWANTHALERHÖHE ---------------------------------------------
[U5] Neuperlach Süd                    now / 9 min / 19 min
```

**Partial Routes:**

When a line has partial routes (e.g., Bus 53 sometimes terminates at Harras instead of going all the way to Aidenbachstraße), the short destination is shown in brackets:

```
→ Aidenbachstraße              → Münchner Freiheit
[53] (Harras) 5 min            [53] 17 min
[53] 12 min / 24 min           [53] 35 min
```

**When to use each mode:**

| Mode | Best for |
|------|----------|
| `compact_directions: false` | Most users - balanced view with clear departure times, 2 rows per line |
| `compact_directions: true` | Maximum density - all times on 1 row per line, fits more stations |

### Station Order Matters

**Important:** The order of stations in the `departures` list determines the display order on screen. Stations are shown top-to-bottom in the same order as they appear in your configuration.

```yaml
departures:
  # This station appears FIRST on the display
  - station: Ridlerstrasse
    filters:
      - type: BUS
        line: '53'

  # This station appears SECOND
  - station: Schwanthalerhöhe
    filters:
      - type: UBAHN
        line: U5

  # This station appears LAST
  - station: Heimeranplatz
    filters:
      - type: BUS
        line: '62'
```

**Tips for ordering:**
- Put your most frequently used station first
- Order by proximity (nearest stations first)
- Order by departure time priority (stations you check first in the morning at top)

Within each station block, departures are sorted by time (soonest first).

## Next Steps

- [Dynamic Refresh Configuration](./implementation/003-dynamic-refresh-multi-station-impl.md) - Set different refresh rates for different times of day
- [Getting Started](./getting-started.md) - Full setup guide

---

<p align="center">
  <a href="https://heretic.giglabo.com">
    <img src="../images/heretic/favicon-128x128.png" alt="VibeCoder Heretic" width="64" height="64">
  </a>
  <br>
  <em>Built with <a href="https://heretic.giglabo.com">VibeCoder Heretic</a></em>
</p>
