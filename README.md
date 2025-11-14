# Claude Code Usage Monitor

A collection of tools for monitoring and visualizing Claude Code API usage statistics.

## Overview

This repository provides three complementary tools for tracking Claude Code usage:

1. **`claude-usage.py`** - A comprehensive command-line analyzer that generates detailed reports with ASCII charts showing token usage over time (from local JSONL logs)
2. **`claude-subscription-usage.py`** - Get real-time subscription quota usage by programmatically querying the Claude Code CLI
3. **`claude-tray-indicator.py`** - A lightweight GNOME system tray indicator that displays real-time daily token statistics

**Token-based tools** (`claude-usage.py` and `claude-tray-indicator.py`) parse JSONL usage logs from `~/.claude/projects` to provide insights into your historical token consumption patterns.

**Subscription usage tool** (`claude-subscription-usage.py`) queries the live Claude Code CLI to retrieve your current subscription quota usage - the same information you see when running `/usage` in Claude Code.

## Features

### claude-usage.py

- **Detailed Statistics**: View total messages, input/output tokens, cache creation/read tokens
- **Model Breakdown**: Per-model usage statistics with comprehensive tables
- **Time-Series Visualization**: ASCII bar charts showing token consumption patterns over time
  - Separate views for Input/Output tokens and Cache tokens
  - 1-hour interval granularity
  - Color-coded visualization with daily totals
- **Flexible Time Ranges**: Analyze data from the last N days (default: 7 days)
- **Monitor Mode**: Continuous real-time monitoring with auto-refresh
- **Local Timezone Support**: All timestamps displayed in your system's local timezone

**Usage:**
```bash
# Basic usage (last 7 days)
python3 claude-usage.py

# Custom time range
python3 claude-usage.py --days 30

# Monitor mode (auto-refresh every hour)
python3 claude-usage.py --monitor

# Monitor mode with custom interval (in seconds)
python3 claude-usage.py --monitor 1800  # Refresh every 30 minutes
```

### claude-subscription-usage.py

- **Real-time Quota Information**: Get current session and weekly subscription usage percentages
- **Multiple Output Formats**:
  - Human-readable summary with progress bars
  - Compact machine-readable format (key:value)
  - Full raw output option
- **Subscription Limits**: Shows session and weekly usage limits for Claude Max subscribers
- **Reset Times**: Displays when your session and weekly quotas will reset
- **Automated Access**: Programmatically query the same `/usage` data you see in Claude Code

**Usage:**
```bash
# Basic usage (human-readable summary)
python3 claude-subscription-usage.py

# Compact output for scripting/automation
python3 claude-subscription-usage.py --compact

# Verbose mode (show progress)
python3 claude-subscription-usage.py --verbose

# Full output (includes raw data)
python3 claude-subscription-usage.py --full
```

**Example Output:**
```
================================================================================
CLAUDE CODE USAGE SUMMARY
================================================================================
Current session               : ██                                                 4% used
Current week (all models)     : ███                                                7% used
Current week (Opus)           :                                                    0% used

--------------------------------------------------------------------------------
RESET TIMES:
--------------------------------------------------------------------------------
  Session resets: 4pm (America/Los_Angeles)
  Weekly resets:  Nov 18, 3pm (America/Los_Angeles)
================================================================================
```

**Compact Output:**
```
session:4
week_all:7
week_opus:0
```

### claude-tray-indicator.py

- **Real-time Display**: Shows current day's token usage in system tray
- **Compact Format**: `I: 32K  O: 5K  CI: 123M  CO: 5M`
  - **I**: Input tokens
  - **O**: Output tokens
  - **CI**: Cache Input tokens (cache reads)
  - **CO**: Cache Output tokens (cache creation)
- **Daily Reset**: Statistics reset at 3 AM local time each day
- **Auto-refresh**: Updates every 5 minutes automatically
- **Quick Actions**: Right-click menu for manual refresh and quit
- **Lightweight**: Minimal resource usage, only reads data when needed

## Installation

### Prerequisites

**For claude-usage.py:**
- Python 3.6+
- No additional dependencies (uses standard library only)

**For claude-subscription-usage.py:**
- Python 3.6+
- `pexpect` library for terminal automation
- Active Claude Code subscription (Claude Max)

```bash
pip install pexpect
```

**For claude-tray-indicator.py:**
- Python 3.6+
- GNOME desktop environment with GTK3 and AppIndicator3 support
- Required packages:

```bash
# Ubuntu/Debian
sudo apt install python3-gi gir1.2-appindicator3-0.1

# Fedora/RHEL/Rocky Linux
sudo dnf install python3-gobject libappindicator-gtk3
```

### Setting Up the Tray Indicator

#### 1. Make the script executable

```bash
chmod +x ~/playground/claude-experimental/claude-tray-indicator.py
```

#### 2. Test the indicator

```bash
~/playground/claude-experimental/claude-tray-indicator.py
```

You should see the token statistics appear in your system tray (top-right corner).

#### 3. Enable autostart on login

```bash
# Create autostart directory if it doesn't exist
mkdir -p ~/.config/autostart

# Copy the desktop file and update the path for your username
sed "s|/home/USER|$HOME|g" ~/playground/claude-experimental/claude-usage-indicator.desktop > ~/.config/autostart/claude-usage-indicator.desktop
```

**Note:** The desktop file template uses `/home/USER` as a placeholder. The `sed` command above automatically replaces it with your actual home directory path.

#### 4. Start the indicator

**Option 1: Start immediately (no logout required)**
```bash
nohup ~/playground/claude-experimental/claude-tray-indicator.py &
```

**Option 2: Log out and log back in**
- The indicator will start automatically on your next login

## Usage

### Subscription Usage Checker

Get your current Claude Max subscription usage:

```bash
# Quick summary
./claude-subscription-usage.py

# For automation/scripting
./claude-subscription-usage.py --compact
```

The tool spawns a Claude Code session, executes `/usage`, and captures the output. This takes ~10-15 seconds to complete.

**Use Cases:**
- Monitor subscription quota programmatically
- Integration with monitoring systems
- Automated alerts when approaching limits
- Logging usage trends over time

### Tray Indicator

Once running, the indicator displays in your system tray with format:
```
I: 32K  O: 5K  CI: 123M  CO: 5M
```

**Right-click menu options:**
- **Refresh Now**: Manually update statistics immediately
- **Quit**: Stop the indicator

**Daily Reset:** Token counts reset at 3 AM local time each day.

### Command-line Analyzer

**Basic analysis:**
```bash
./claude-usage.py
```

**View last 30 days:**
```bash
./claude-usage.py --days 30
```

**Monitor mode (interactive):**
```bash
./claude-usage.py --monitor
```

In monitor mode, you can use:
- `/refresh` - Manually refresh statistics
- `/exit` - Exit monitor mode
- `Ctrl+C` - Exit monitor mode

## Example Output

### Command-line Analyzer Output

```
user@hostname [~/playground/claude-experimental]
-> % python3 claude-usage.py
Calculating Claude Code usage...
Showing data from last 7 days

Usage by Model
==========================================================================================================================================================
│ Model                                 Messages │           Input          Output     Total Token │    Cache Output     Cache Input  Total (with cache) │
│--------------------------------------------------------------------------------------------------------------------------------------------------------│
│ claude-sonnet-4-5-20250929                5023 │         481,340         141,286         622,626 │      28,335,919     351,980,114         380,938,659 │
│ claude-haiku-4-5-20251001                   54 │          87,529          10,488          98,017 │               0               0              98,017 │
│ <synthetic>                                  2 │               0               0               0 │               0               0                   0 │
│--------------------------------------------------------------------------------------------------------------------------------------------------------│
│ TOTAL                                     5079 │         568,869         151,774         720,643 │      28,335,919     351,980,114         381,036,676 │
==========================================================================================================================================================

Input + Output Tokens Over Time (1-hour intervals, Local Time)
Y-axis: Input and Output token consumption

==========================================================================================================================================================================================
          Wed : 45.9K         Thu : 115K               Fri : 143K               Sat : 26.9K              Sun : 0                  Mon : 231K               Tue : 90.9K       Wed : 65.9K
           10 / 29             10 / 30                  10 / 31                  11 / 01                  11 / 02                  11 / 03                  11 / 04           11 / 05
105 K │              │                        │                        │                        │                        │                        │                        │
102 K │              │                        │                        │                        │                        │                        │                        │
 99 K │              │                        │                        │                        │                        │                        │                        │
 96 K │              │                        │          ▓             │                        │                        │                        │                        │
 94 K │              │                        │          ▓             │                        │                        │                        │                        │
 91 K │              │                        │          ▓             │                        │                        │                        │                        │
 88 K │              │                        │          ▓             │                        │                        │                        │                        │
 86 K │              │                        │          █             │                        │                        │                        │                        │
 83 K │              │                        │          █             │                        │                        │                        │                        │
 80 K │              │                        │          █             │                        │                        │                        │                        │
 78 K │              │                        │          █             │                        │                        │                        │                        │
 75 K │              │                        │          █             │                        │                        │                        │                        │
 72 K │              │                        │          █             │                        │                        │                        │                        │
 70 K │              │                        │          █             │                        │                        │                        │                        │
 67 K │              │                        │          █             │                        │                        │                 ▓      │                        │
 64 K │              │                        │          █             │                        │                        │                 ▓      │                        │
 61 K │              │                        │          █             │                        │                        │                 ▓      │                        │
 59 K │              │                        │          █             │                        │                        │                ▓▓      │                        │         ▓
 56 K │              │                        │          █             │                        │                        │                ▓▓      │                        │         ▓
 53 K │              │                        │          █             │                        │                        │                ▓▓      │                        │         █
 51 K │              │                        │          █             │                        │                        │                ▓▓      │                        │         █
 48 K │              │                        │          █             │                        │                        │                ▓▓      │                        │         █
 45 K │              │                        │          █             │                        │                        │                ▓▓      │                        │         █
 43 K │              │                        │          █             │                        │                        │             █  ▓▓      │                        │         █
 40 K │              │                        │          █             │                        │                        │             █  ▓█      │                        │         █
 37 K │              │                        │          █             │                        │                        │             █  ▓█      │                        │         █
 35 K │              │                        │          █             │                        │                        │             █  ██      │                        │         █
 32 K │              │                   █    │          █             │                        │                        │             █  ██      │                        │         █
 29 K │              │                   █    │          █             │                        │                        │             █  ██      │                        │         █
 26 K │              │            █      █   █│          █             │                        │                        │             █  ██      │               █        │         █
 24 K │              │            █      █   █│          █             │                        │                        │             █  ██      │               █        │         █
 21 K │              │            █      █   █│        █ █             │                        │                        │             █  ██      │               █        │         █
 18 K │              │            █      █   █│        █ █             │                        │                        │             █  ██      │               █        │         █
 16 K │              │            █      █   █│        █ █             │                        │                        │             █  ██      │               ██  █    │         █
 13 K │              │            █      █   █│        █ █             │                        │                        │             █  ██      │        █      ██  █    │         █
 10 K │              │            █      █   █│        █ █             │                        │                        │             █  ██      │        █      ██  █    │         █
8.1 K │▓  ▓          │            █      █   █│        █ █             │               ▓        │                        │             █  ██  ▓   │        █      ██  █    │         █
5.4 K │▓▓ ▓          │            █      █   █│        █ █             │               ▓        │                        │             █  ██  ▓   │        █      ██  █    │         █
2.7 K │▓▓ ▓          │            █ █    █   █│        █ █       █     │             █ █        │                        │          █  █  ██  █   │        █      ██  █    │         █
    0 │▓▓ ██         │            █ █ █  █   █│        █ ██      █     │             ███        │                        │        █ █  █  ██▓▓█▓█ │        █      ██  █    │         █
      └──────────────┴────────────────────────┴────────────────────────┴────────────────────────┴────────────────────────┴────────────────────────┴────────────────────────┴───────────

Cache Tokens Over Time (1-hour intervals, Local Time)
Y-axis: Cache Output and Cache Input token consumption
X-axis: Time (each day has 24 data points, ticks at 6-hour intervals)

==========================================================================================================================================================================================
          Wed : 100M          Thu : 16.8M              Fri : 31.7M              Sat : 26.6M              Sun : 0                  Mon : 150M               Tue : 6.80M       Wed : 47.5M
           10 / 29             10 / 30                  10 / 31                  11 / 01                  11 / 02                  11 / 03                  11 / 04           11 / 05
 45 M │              │                        │                        │                        │                        │                        │                        │
 43 M │              │                        │                        │                        │                        │                        │                        │
 42 M │              │                        │                        │                        │                        │                        │                        │
 41 M │              │                        │                        │                        │                        │                        │                        │         █
 40 M │              │                        │                        │                        │                        │                        │                        │         █
 39 M │              │                        │                        │                        │                        │                        │                        │         █
 38 M │              │                        │                        │                        │                        │                        │                        │         █
 36 M │              │                        │                        │                        │                        │                        │                        │         █
 35 M │   █          │                        │                        │                        │                        │                 █      │                        │         █
 34 M │   █          │                        │                        │                        │                        │                 █      │                        │         █
 33 M │   █          │                        │                        │                        │                        │                 █      │                        │         █
 32 M │   █          │                        │                        │                        │                        │                 █      │                        │         █
 31 M │   █          │                        │                        │                        │                        │                 █      │                        │         █
 30 M │   ██         │                        │                        │                        │                        │                 █      │                        │         █
 28 M │   ██         │                        │                        │                        │                        │                 █      │                        │         █
 27 M │   ██         │                        │                        │                        │                        │                 █      │                        │         █
 26 M │   ██         │                        │                        │                        │                        │                 █      │                        │         █
 25 M │   ██         │                        │                        │                        │                        │                 █      │                        │         █
 24 M │   ██         │                        │                        │                        │                        │                 █      │                        │         █
 23 M │   ██         │                        │                        │                        │                        │                 █      │                        │         █
 21 M │   ██         │                        │                        │                        │                        │                 █  █   │                        │         █
 20 M │   ██         │                        │          █             │                        │                        │                 █  █   │                        │         █
 19 M │   ██         │                        │          █             │                        │                        │                 █  █   │                        │         █
 18 M │   ██         │                        │          █             │                        │                        │                 █  ██  │                        │         █
 17 M │   ██         │                        │          █             │                        │                        │                 █  ██  │                        │         █
 16 M │ █ ██         │                        │          █             │                        │                        │                 █  ██  │                        │         █
 15 M │ █ ██         │                        │          █             │                        │                        │                 █  ██  │                        │         █
 13 M │ █ ██         │                        │          █             │                        │                        │                 █  ██  │                        │         █
 12 M │ █ ██         │                        │          █             │                █       │                        │                 █  ███ │                        │         █
 11 M │ █ ██         │                        │          █             │                █       │                        │                 █  ███ │                        │         █
 10 M │ █ ██         │                        │          █             │                █       │                        │            █    █  ███ │                        │         █
9.2 M │ █ ██         │                        │          █             │                █       │                        │            █    █  ███ │                        │         █
8.1 M │ █ ██         │                        │          █             │                █       │                        │            █    █ ████ │                        │         █
6.9 M │██ ██         │              █         │          █             │                █       │                        │            █    █ ████ │                        │         █
5.8 M │██ ██         │              █         │          █             │                █       │                        │           ██    █ ████ │                        │         █
4.6 M │██ ██         │              █         │          █             │                █       │                        │           ██    ██████ │                        │         █
3.5 M │██ ██         │              █         │          █             │               ██       │                        │           ██    ██████ │                   █    │         █
2.3 M │██ ██         │              █    █    │          █             │               ██       │                        │          ███    ██████ │                   █    │         █
1.2 M │███▒█         │              █    █    │          ██      █     │             █ ██       │                        │          ████  ███████ │                   █    │         ▒
    0 │▒██▒▒         │              █    ██   │          ▒█      █     │             ███▒       │                        │          ████  █▒██▒▒█ │                   █    │         ▒█
      └──────────────┴────────────────────────┴────────────────────────┴────────────────────────┴────────────────────────┴────────────────────────┴────────────────────────┴───────────

         1     1     │      0     1     1     │      0     1     1     │      0     1     1     │      0     1     1     │      0     1     1     │      0     1     1     │      0
         2     8     │      6     2     8     │      6     2     8     │      6     2     8     │      6     2     8     │      6     2     8     │      6     2     8     │      6

==========================================================================================================================================================================================
Total time span: 2025-10-29 10:00 to 2025-11-05 10:00 | Data points: 169
Legend: █ Input  ▓ Output  █ Cache Input  ▒ Cache Output
```

This example shows:
- **Model breakdown table**: Total messages and tokens by model (Sonnet, Haiku, etc.)
- **Input/Output chart**: Hourly visualization of input and output tokens with color coding
- **Cache chart**: Separate visualization for cache creation and read tokens
- **Daily totals**: Aggregated token counts shown at the top of each day column
- **Time indicators**: X-axis labels at 6-hour intervals (06:00, 12:00, 18:00)

The charts clearly show usage patterns - for example, heavy usage on Monday (231K I/O tokens, 150M cache tokens) and quieter days like Sunday with no activity.

## Troubleshooting

### System Tray Icon Not Visible

Some GNOME versions hide the system tray by default. Install the AppIndicator extension:

```bash
# Install the extension
gnome-extensions install appindicatorsupport@rgcjonas.gmail.com
gnome-extensions enable appindicatorsupport@rgcjonas.gmail.com
```

Alternatively, search for "AppIndicator and KStatusNotifierItem Support" in GNOME Extensions.

### "Error: No data" Display

- Verify `~/.claude/projects` directory exists and contains JSONL files
- Check file permissions are readable
- Ensure you have some Claude Code usage history

### Python Import Errors

Verify required packages are installed:
```bash
python3 -c "import gi; gi.require_version('AppIndicator3', '0.1')"
```

If this fails, reinstall the packages listed in Prerequisites.

## Customization

### Change Update Interval (Tray Indicator)

Edit `claude-tray-indicator.py`, find line ~168:
```python
GLib.timeout_add_seconds(300, self.update_label)  # 300 seconds = 5 minutes
```

Change `300` to your desired interval in seconds.

### Change Daily Reset Time

Edit `claude-tray-indicator.py`, find the `filter_usage_data_since_3am` function (~line 62):
```python
today_3am = now_local.replace(hour=3, minute=0, second=0, microsecond=0)
```

Change `hour=3` to any hour (0-23).

### Change System Tray Icon

Edit `claude-tray-indicator.py`, line ~153:
```python
"dialog-information",  # Use system icon
```

Replace with any system icon name:
- `"applications-system"` - System application icon
- `"utilities-system-monitor"` - System monitor icon
- `"appointment-soon"` - Clock icon
- `"emblem-important"` - Important marker
- `"starred"` - Star icon

## Uninstalling

### Remove Tray Indicator

```bash
# Stop running instance
pkill -f claude-tray-indicator.py

# Remove autostart entry
rm ~/.config/autostart/claude-usage-indicator.desktop

# Remove scripts (optional)
rm ~/playground/claude-experimental/claude-tray-indicator.py
rm ~/playground/claude-experimental/claude-usage-indicator.desktop
```

## Technical Details

### Data Sources

**Token-based tools** (`claude-usage.py` and `claude-tray-indicator.py`) read usage data from `~/.claude/projects/**/*.jsonl`, which contains Claude Code API usage logs. Each JSONL entry includes:
- Timestamp (ISO format, UTC)
- Model information
- Token usage (input, output, cache creation, cache read)

**Subscription usage tool** (`claude-subscription-usage.py`) queries the live Claude Code CLI by:
- Spawning an interactive Claude Code session using `pexpect`
- Sending the `/usage` command
- Capturing the subscription quota display
- Parsing percentages and reset times from the output

### Architecture

**claude-usage.py:**
- Single-file utility using Python standard library only
- Time-series data bucketed into 1-hour intervals
- ASCII visualization using ANSI color codes
- Automatic local timezone conversion

**claude-subscription-usage.py:**
- Uses `pexpect` for terminal automation
- Creates a pseudo-terminal (PTY) for Claude Code interaction
- Waits for UI rendering before capturing output
- Strips ANSI codes for clean parsing
- Takes ~10-15 seconds per execution

**claude-tray-indicator.py:**
- GTK3-based system tray application
- Uses AppIndicator3 for cross-desktop compatibility
- Minimal memory footprint
- Non-blocking updates using GLib main loop

### Token Display Format

Token counts are formatted with unit suffixes:
- **K** (Kilo): 1,000 tokens
- **M** (Mega): 1,000,000 tokens
- **B** (Billion): 1,000,000,000 tokens

Decimal places are automatically adjusted based on magnitude.

## Contributing

This is a personal utility repository. Feel free to fork and customize for your needs.

## License

This project is provided as-is for personal use.
