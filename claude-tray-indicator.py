#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, AppIndicator3, GLib

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
import signal

def get_claude_dir():
    """Get Claude configuration directory."""
    claude_dir = os.environ.get('CLAUDE_CONFIG_DIR', os.path.expanduser('~/.claude'))
    return Path(claude_dir)


def read_jsonl_files(projects_dir):
    """Read all JSONL files from projects directory."""
    usage_data = []

    for jsonl_file in projects_dir.rglob('*.jsonl'):
        try:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        # Only include entries with usage data
                        if data.get('message') and data['message'].get('usage'):
                            usage_data.append(data)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            continue

    return usage_data


def filter_usage_data_since_3am(usage_data):
    """Filter usage data to only include entries since 3 AM today (local time)."""
    if not usage_data:
        return []

    # Get local timezone automatically
    local_tz = datetime.now().astimezone().tzinfo

    # Get current time in local timezone
    now_local = datetime.now(local_tz)

    # Calculate 3 AM today
    today_3am = now_local.replace(hour=3, minute=0, second=0, microsecond=0)

    # If current time is before 3 AM, use yesterday's 3 AM
    if now_local.hour < 3:
        today_3am = today_3am - timedelta(days=1)

    # Filter data
    filtered_data = []
    for entry in usage_data:
        timestamp_str = entry.get('timestamp')
        if not timestamp_str:
            continue

        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            timestamp_local = timestamp.astimezone(local_tz)
            if timestamp_local >= today_3am:
                filtered_data.append(entry)
        except Exception:
            continue

    return filtered_data


def calculate_daily_stats(usage_data):
    """Calculate daily usage statistics since 3 AM."""
    stats = {
        'input_tokens': 0,
        'output_tokens': 0,
        'cache_creation_tokens': 0,
        'cache_read_tokens': 0,
    }

    for entry in usage_data:
        usage = entry['message']['usage']
        stats['input_tokens'] += usage.get('input_tokens', 0)
        stats['output_tokens'] += usage.get('output_tokens', 0)
        stats['cache_creation_tokens'] += usage.get('cache_creation_input_tokens', 0)
        stats['cache_read_tokens'] += usage.get('cache_read_input_tokens', 0)

    return stats


def format_token_count(count):
    """Format token count with K/M/B units."""
    if count >= 1_000_000_000:
        return f"{count / 1_000_000_000:.1f}B".rstrip('0').rstrip('.')
    elif count >= 1_000_000:
        val = f"{count / 1_000_000:.1f}M"
        # Remove unnecessary decimals
        if val.endswith('.0M'):
            return val[:-3] + 'M'
        return val
    elif count >= 1_000:
        val = f"{count / 1_000:.1f}K"
        # Remove unnecessary decimals
        if val.endswith('.0K'):
            return val[:-3] + 'K'
        return val
    else:
        return str(int(count))


def get_token_stats_label():
    """Get formatted token statistics label for display."""
    try:
        claude_dir = get_claude_dir()
        projects_dir = claude_dir / 'projects'

        if not projects_dir.exists():
            return "Error: No data"

        # Read and filter data
        usage_data = read_jsonl_files(projects_dir)
        filtered_data = filter_usage_data_since_3am(usage_data)

        if not filtered_data:
            return "I: 0  O: 0  CI: 0  CO: 0"

        # Calculate stats
        stats = calculate_daily_stats(filtered_data)

        # Format label with wider spacing
        label = (f"I: {format_token_count(stats['input_tokens'])}  "
                f"O: {format_token_count(stats['output_tokens'])}  "
                f"CI: {format_token_count(stats['cache_read_tokens'])}  "
                f"CO: {format_token_count(stats['cache_creation_tokens'])}")

        return label
    except Exception as e:
        return f"Error: {str(e)[:20]}"


class ClaudeUsageIndicator:
    def __init__(self):
        self.indicator = AppIndicator3.Indicator.new(
            "claude-usage-indicator",
            "dialog-information",  # Use system icon to avoid three dots
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        # Create menu
        self.menu = Gtk.Menu()

        # Refresh item
        item_refresh = Gtk.MenuItem(label='Refresh Now')
        item_refresh.connect('activate', self.refresh)
        self.menu.append(item_refresh)

        # Separator
        self.menu.append(Gtk.SeparatorMenuItem())

        # Quit item
        item_quit = Gtk.MenuItem(label='Quit')
        item_quit.connect('activate', self.quit)
        self.menu.append(item_quit)

        self.menu.show_all()
        self.indicator.set_menu(self.menu)

        # Initial update
        self.update_label()

        # Update every 5 minutes (300 seconds = 300000 milliseconds)
        GLib.timeout_add_seconds(300, self.update_label)

    def update_label(self):
        """Update the indicator label with current stats."""
        label = get_token_stats_label()
        self.indicator.set_label(label, "")
        return True  # Keep timeout active

    def refresh(self, source):
        """Manual refresh triggered by menu."""
        self.update_label()

    def quit(self, source):
        """Quit the application."""
        Gtk.main_quit()


def main():
    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Create indicator
    ClaudeUsageIndicator()

    # Start GTK main loop
    Gtk.main()


if __name__ == '__main__':
    main()
