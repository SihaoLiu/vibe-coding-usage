# Claude Code Usage Monitor

A collection of tools for monitoring and visualizing Claude Code API usage statistics.

## Overview

This repository provides two complementary tools for tracking Claude Code token consumption:

1. **`claude-usage.py`** - A comprehensive command-line analyzer that generates detailed reports with ASCII charts showing token usage over time
2. **`claude-tray-indicator.py`** - A lightweight GNOME system tray indicator that displays real-time daily token statistics

Both tools parse JSONL usage logs from `~/.claude/projects` to provide insights into your Claude Code consumption patterns.

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

### Data Source

Both tools read usage data from `~/.claude/projects/**/*.jsonl`, which contains Claude Code API usage logs. Each JSONL entry includes:
- Timestamp (ISO format, UTC)
- Model information
- Token usage (input, output, cache creation, cache read)

### Architecture

**claude-usage.py:**
- Single-file utility using Python standard library only
- Time-series data bucketed into 1-hour intervals
- ASCII visualization using ANSI color codes
- Automatic local timezone conversion

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
