#!/usr/bin/env python3

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import sys
import argparse
import time
import select
import re


def get_subscription_usage():
    """
    Get Claude Code subscription usage by spawning a claude session.
    Returns usage data dict or None if pexpect is not available or fetch fails.
    """
    try:
        import pexpect
    except ImportError:
        return None

    try:
        # Spawn with dimensions set to ensure proper rendering
        child = pexpect.spawn('claude', encoding='utf-8', timeout=60)
        child.setwinsize(50, 120)  # rows, cols

        # Wait for initialization
        time.sleep(4)

        # Read any initial output
        try:
            while True:
                child.expect(r'.+', timeout=0.5)
        except pexpect.TIMEOUT:
            pass

        # Send the /usage command
        child.send('/usage')
        time.sleep(0.5)
        child.send('\r')

        # Wait for usage display to render
        time.sleep(6)

        # Collect the usage output
        usage_output = ""
        try:
            while True:
                child.expect(r'.+', timeout=1)
                usage_output += child.after
        except pexpect.TIMEOUT:
            pass

        # Exit cleanly
        child.send('/exit\n')
        time.sleep(1)
        try:
            child.expect(pexpect.EOF, timeout=3)
        except:
            child.close(force=True)

        # Strip ANSI codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        clean_output = ansi_escape.sub('', usage_output)

        # Extract data
        percentages = re.findall(r'(\d+)%\s+used', clean_output)
        reset_times = re.findall(r'Resets\s+(.+)', clean_output)

        if not percentages:
            return None

        return {
            'session_pct': int(percentages[0]) if len(percentages) > 0 else 0,
            'week_all_pct': int(percentages[1]) if len(percentages) > 1 else 0,
            'week_opus_pct': int(percentages[2]) if len(percentages) > 2 else 0,
            'session_reset': reset_times[0] if len(reset_times) > 0 else 'Unknown',
            'week_reset': reset_times[1] if len(reset_times) > 1 else 'Unknown'
        }
    except Exception:
        return None


def print_subscription_usage_table(usage_data):
    """
    Print subscription usage information in a 5-line table format, with reset info below.
    """
    TABLE_WIDTH = 90

    if not usage_data:
        # Print error table if no data
        print("="*TABLE_WIDTH)
        print("Current session               :                                              | N/A    |")
        print("Current week (all models)     :                                              | N/A    |")
        print("Current week (Opus)           :                                              | N/A    |")
        print("="*TABLE_WIDTH)
        print("Session resets: N/A")
        print("Weekly resets:  N/A")
        return

    # Create progress bars (47 chars max)
    def make_bar(pct):
        filled = int(pct * 47 / 100)
        return "█" * filled

    session_bar = make_bar(usage_data['session_pct'])
    week_all_bar = make_bar(usage_data['week_all_pct'])
    week_opus_bar = make_bar(usage_data['week_opus_pct'])

    print("="*TABLE_WIDTH)
    print(f"Current session               : {session_bar:<47}| {usage_data['session_pct']:>2}% used|")
    print(f"Current week (all models)     : {week_all_bar:<47}| {usage_data['week_all_pct']:>2}% used|")
    print(f"Current week (Opus)           : {week_opus_bar:<47}| {usage_data['week_opus_pct']:>2}% used|")
    print("="*TABLE_WIDTH)
    print(f"Session resets: {usage_data['session_reset']}")
    print(f"Weekly resets:  {usage_data['week_reset']}")


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


def format_number(num):
    """Format number with thousand separators."""
    return f"{num:,}"


def calculate_overall_stats(usage_data):
    """Calculate overall usage statistics."""
    stats = {
        'total_messages': len(usage_data),
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

    stats['total_tokens'] = stats['input_tokens'] + stats['output_tokens']

    return stats


def calculate_model_breakdown(usage_data):
    """Calculate usage breakdown by model."""
    model_stats = defaultdict(lambda: {
        'count': 0,
        'input': 0,
        'output': 0,
        'cache_creation': 0,
        'cache_read': 0,
    })

    for entry in usage_data:
        model = entry['message'].get('model', 'unknown')
        usage = entry['message']['usage']

        model_stats[model]['count'] += 1
        model_stats[model]['input'] += usage.get('input_tokens', 0)
        model_stats[model]['output'] += usage.get('output_tokens', 0)
        model_stats[model]['cache_creation'] += usage.get('cache_creation_input_tokens', 0)
        model_stats[model]['cache_read'] += usage.get('cache_read_input_tokens', 0)

    # Calculate totals and sort by total tokens
    result = []
    for model, stats in model_stats.items():
        stats['model'] = model
        stats['total'] = stats['input'] + stats['output']
        stats['total_with_cache'] = stats['input'] + stats['output'] + stats['cache_creation'] + stats['cache_read']
        result.append(stats)

    result.sort(key=lambda x: x['total'], reverse=True)
    return result


def calculate_time_series(usage_data, interval_hours=1):
    """Calculate token usage over time in specified hour intervals (local timezone)."""
    # Get local timezone automatically
    local_tz = datetime.now().astimezone().tzinfo

    # Group by time interval and model
    time_series = defaultdict(lambda: defaultdict(int))

    for entry in usage_data:
        timestamp_str = entry.get('timestamp')
        if not timestamp_str:
            continue

        try:
            # Parse ISO timestamp and convert to local timezone
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            timestamp_local = timestamp.astimezone(local_tz)

            # Round down to the nearest interval
            hour = timestamp_local.hour
            interval_hour = (hour // interval_hours) * interval_hours
            interval_time = timestamp_local.replace(hour=interval_hour, minute=0, second=0, microsecond=0)

            model = entry['message'].get('model', 'unknown')
            usage = entry['message']['usage']

            # Total tokens (input + output, in kilo tokens)
            total_tokens = usage.get('input_tokens', 0) + usage.get('output_tokens', 0)

            time_series[interval_time][model] += total_tokens
        except Exception:
            continue

    return time_series


def calculate_all_tokens_time_series(usage_data, interval_hours=1):
    """Calculate ALL token usage (input + output + cache) over time in specified hour intervals (local timezone)."""
    # Get local timezone automatically
    local_tz = datetime.now().astimezone().tzinfo

    # Group by time interval (all models combined)
    time_series = defaultdict(lambda: defaultdict(int))

    for entry in usage_data:
        timestamp_str = entry.get('timestamp')
        if not timestamp_str:
            continue

        try:
            # Parse ISO timestamp and convert to local timezone
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            timestamp_local = timestamp.astimezone(local_tz)

            # Round down to the nearest interval
            hour = timestamp_local.hour
            interval_hour = (hour // interval_hours) * interval_hours
            interval_time = timestamp_local.replace(hour=interval_hour, minute=0, second=0, microsecond=0)

            usage = entry['message']['usage']

            # ALL tokens: input + output + cache_creation + cache_read
            total_tokens = (usage.get('input_tokens', 0) +
                          usage.get('output_tokens', 0) +
                          usage.get('cache_creation_input_tokens', 0) +
                          usage.get('cache_read_input_tokens', 0))

            # Use 'all' as a single model key to combine all models
            time_series[interval_time]['all'] += total_tokens
        except Exception:
            continue

    return time_series


def calculate_token_breakdown_time_series(usage_data, interval_hours=1):
    """Calculate token usage breakdown (input/output/cache_creation/cache_read) over time in specified hour intervals (local timezone)."""
    # Get local timezone automatically
    local_tz = datetime.now().astimezone().tzinfo

    # Group by time interval with breakdown
    time_series = defaultdict(lambda: {
        'input': 0,
        'output': 0,
        'cache_creation': 0,
        'cache_read': 0
    })

    for entry in usage_data:
        timestamp_str = entry.get('timestamp')
        if not timestamp_str:
            continue

        try:
            # Parse ISO timestamp and convert to local timezone
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            timestamp_local = timestamp.astimezone(local_tz)

            # Round down to the nearest interval
            hour = timestamp_local.hour
            interval_hour = (hour // interval_hours) * interval_hours
            interval_time = timestamp_local.replace(hour=interval_hour, minute=0, second=0, microsecond=0)

            usage = entry['message']['usage']

            # Accumulate each token type separately
            time_series[interval_time]['input'] += usage.get('input_tokens', 0)
            time_series[interval_time]['output'] += usage.get('output_tokens', 0)
            time_series[interval_time]['cache_creation'] += usage.get('cache_creation_input_tokens', 0)
            time_series[interval_time]['cache_read'] += usage.get('cache_read_input_tokens', 0)
        except Exception:
            continue

    return time_series


def format_y_axis_value(value):
    """Format Y-axis value to always be 5 characters with K/M units."""
    if value >= 1_000_000:
        # Millions
        val_m = value / 1_000_000
        if val_m >= 100:
            return f"{int(val_m):3d} M"
        elif val_m >= 10:
            return f" {int(val_m):2d} M"
        else:
            return f"{val_m:3.1f} M"
    elif value >= 1000:
        # Thousands
        val_k = value / 1000
        if val_k >= 100:
            return f"{int(val_k):3d} K"
        elif val_k >= 10:
            return f" {int(val_k):2d} K"
        else:
            return f"{val_k:3.1f} K"
    else:
        # Less than 1000, show as integer
        return f"{int(value):5d}"


def format_total_value(value):
    """Format total value with B/M/K units."""
    if value >= 1_000_000_000:
        # Billions
        val_b = value / 1_000_000_000
        if val_b >= 100:
            return f"{int(val_b)}B"
        elif val_b >= 10:
            return f"{val_b:.1f}B"
        else:
            return f"{val_b:.2f}B"
    elif value >= 1_000_000:
        # Millions
        val_m = value / 1_000_000
        if val_m >= 100:
            return f"{int(val_m)}M"
        elif val_m >= 10:
            return f"{val_m:.1f}M"
        else:
            return f"{val_m:.2f}M"
    elif value >= 1_000:
        # Thousands
        val_k = value / 1_000
        if val_k >= 100:
            return f"{int(val_k)}K"
        elif val_k >= 10:
            return f"{val_k:.1f}K"
        else:
            return f"{val_k:.2f}K"
    else:
        # Less than 1000
        return f"{int(value)}"


def print_stacked_bar_chart(time_series, height=80, days_back=7, chart_type='all', show_x_axis=True):
    """Print a text-based stacked bar chart of token usage breakdown over time.

    Args:
        time_series: Time series data with token breakdown
        height: Height of the chart
        days_back: Number of days to show
        chart_type: 'all' (all 4 types), 'io' (input+output), or 'cache' (cache_creation+cache_read)
        show_x_axis: Whether to show X-axis labels
    """
    if not time_series:
        print("No time series data available.")
        return

    # Sort by time
    all_sorted_times = sorted(time_series.keys())

    if not all_sorted_times:
        print("No data available.")
        return

    # Calculate start time based on days_back parameter
    last_time = all_sorted_times[-1]
    start_time = last_time - timedelta(days=days_back)

    # Round start_time down to nearest hour
    start_time_rounded = start_time.replace(minute=0, second=0, microsecond=0)

    # Create a complete continuous time series (every hour)
    # This ensures uniform spacing even when there's no data
    sorted_times = []
    current_time = start_time_rounded
    while current_time <= last_time:
        sorted_times.append(current_time)
        current_time += timedelta(hours=1)

    if len(sorted_times) < 2:
        print("Not enough data points for chart.")
        return

    # Limit chart width to 500 columns
    if len(sorted_times) > 500:
        # Adjust interval to fit in 500 columns
        hours_per_interval = len(sorted_times) / 500
        print(f"Note: Adjusting interval to ~{hours_per_interval:.1f} hours to fit in 500 columns.")

        # Resample to fit in 500 columns
        step = max(1, len(sorted_times) // 500)
        sorted_times = sorted_times[::step]

    # Calculate breakdown per time interval
    breakdown_data = []
    totals = []
    for time in sorted_times:
        if time in time_series:
            input_val = time_series[time].get('input', 0)
            output_val = time_series[time].get('output', 0)
            cache_creation_val = time_series[time].get('cache_creation', 0)
            cache_read_val = time_series[time].get('cache_read', 0)
        else:
            input_val = output_val = cache_creation_val = cache_read_val = 0

        breakdown_data.append({
            'input': input_val,
            'output': output_val,
            'cache_creation': cache_creation_val,
            'cache_read': cache_read_val
        })

        # Calculate total based on chart_type
        if chart_type == 'io':
            total = input_val + output_val
        elif chart_type == 'cache':
            total = cache_creation_val + cache_read_val
        else:  # 'all'
            total = input_val + output_val + cache_creation_val + cache_read_val

        totals.append(total)

    # First pass: calculate Y-axis range from all data
    max_value_raw = max(totals) if totals else 1
    min_value_raw = min(totals) if totals else 0

    # Round min/max to nearest multiple of 5K or 5M
    def round_to_5_multiple(value, round_up=True):
        """Round value to nearest multiple of 5K or 5M."""
        if value >= 1_000_000:
            # Round to nearest 5M
            unit = 5_000_000
        elif value >= 1_000:
            # Round to nearest 5K
            unit = 5_000
        else:
            # Round to nearest 5
            unit = 5

        if round_up:
            return ((int(value) + unit - 1) // unit) * unit
        else:
            return (int(value) // unit) * unit

    min_value = round_to_5_multiple(min_value_raw, round_up=False)
    max_value = round_to_5_multiple(max_value_raw, round_up=True)

    # Ensure max > min
    if max_value == min_value:
        max_value = min_value + 5_000

    num_data_points = len(totals)
    chart_height = height

    # Print chart title based on type
    if chart_type == 'io':
        print("\nInput + Output Tokens Over Time (1-hour intervals, Local Time)")
        print(f"Y-axis: Input and Output token consumption")
    elif chart_type == 'cache':
        print("\nCache Tokens Over Time (1-hour intervals, Local Time)")
        print(f"Y-axis: Cache Output and Cache Input token consumption")
    else:
        print("\nToken Usage Breakdown Over Time (1-hour intervals, Local Time)")
        print(f"Y-axis: Token consumption (all token types)")

    if show_x_axis:
        print(f"X-axis: Time (each day has 24 data points, ticks at 6-hour intervals)\n")
    else:
        print()

    # Scale breakdown values to chart height
    # For each data point, calculate the scaled heights of each segment
    scaled_breakdown = []
    for breakdown in breakdown_data:
        if max_value == min_value:
            scaled_breakdown.append({
                'input': 0,
                'output': 0,
                'cache_creation': 0,
                'cache_read': 0
            })
        else:
            # Scale each component individually
            scaled_breakdown.append({
                'input': int((breakdown['input'] - 0) / (max_value - min_value) * (chart_height - 1)),
                'output': int((breakdown['output'] - 0) / (max_value - min_value) * (chart_height - 1)),
                'cache_creation': int((breakdown['cache_creation'] - 0) / (max_value - min_value) * (chart_height - 1)),
                'cache_read': int((breakdown['cache_read'] - 0) / (max_value - min_value) * (chart_height - 1))
            })

    # Build chart:
    # First day: data points (no separator, Y-axis serves as the boundary)
    # Subsequent days: separator + data points
    chart_columns = []  # List of (type, value)
    data_to_col = {}  # Map data point index to column index

    col_idx = 0
    for i in range(num_data_points):
        time = sorted_times[i]

        # Add separator before 00:00 (except for the very first day)
        if time.hour == 0 and time.minute == 0 and i > 0:
            chart_columns.append(('separator', None))
            col_idx += 1

        # Add data point
        chart_columns.append(('data', i))
        data_to_col[i] = col_idx
        col_idx += 1

    chart_width = len(chart_columns)
    print("=" * (chart_width + 10))

    # Calculate daily totals for display at top of chart
    daily_totals = []
    current_day_start = None
    current_day_total = 0
    current_day_start_col = 0

    for col_idx, (col_type, col_data) in enumerate(chart_columns):
        if col_type == 'separator':
            # End of previous day
            if current_day_start is not None:
                mid_col = (current_day_start_col + col_idx) // 2
                daily_totals.append((mid_col, current_day_total, current_day_start))
            current_day_start = None
            current_day_total = 0
            current_day_start_col = col_idx + 1
        else:
            data_idx = col_data
            if current_day_start is None:
                current_day_start = sorted_times[data_idx]
                current_day_start_col = col_idx
            current_day_total += totals[data_idx]

    # Add last day if exists
    if current_day_start is not None:
        mid_col = (current_day_start_col + len(chart_columns)) // 2
        daily_totals.append((mid_col, current_day_total, current_day_start))

    # Print daily totals at top of chart (weekday + total tokens)
    weekday_line = " " * 7  # Align with Y-axis
    date_line = " " * 7  # Align with Y-axis
    prev_end = 0

    weekday_abbr = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

    for day_idx, (mid_col, total, day_start) in enumerate(daily_totals):
        total_str = format_total_value(total)
        weekday = weekday_abbr[day_start.weekday()]
        weekday_total = f"{weekday} : {total_str}"

        # Format date as " MM / DD"
        date_str = day_start.strftime(' %m / %d')

        # Find positions of : and /
        colon_idx = weekday_total.index(':')
        slash_idx = date_str.index('/')

        # Add padding to align : and / at the same relative position
        if colon_idx > slash_idx:
            # Add spaces before date_str
            date_str = ' ' * (colon_idx - slash_idx) + date_str
            slash_idx = colon_idx
        elif slash_idx > colon_idx:
            # Add spaces before weekday_total
            weekday_total = ' ' * (slash_idx - colon_idx) + weekday_total
            colon_idx = slash_idx

        # Make both strings the same length
        max_len = max(len(weekday_total), len(date_str))
        weekday_total = weekday_total.ljust(max_len)
        date_str = date_str.ljust(max_len)

        # Position them so : and / are at mid_col
        start_pos = mid_col - colon_idx

        # Add padding and content to both lines
        padding = start_pos - prev_end
        if padding > 0:
            weekday_line += " " * padding
            date_line += " " * padding

        weekday_line += weekday_total
        date_line += date_str
        prev_end = start_pos + max_len

    print(weekday_line)
    print(date_line)

    # Draw chart from top to bottom (stacked bar chart style)
    for row in range(chart_height - 1, -1, -1):
        # Y-axis label
        y_val = min_value + (max_value - min_value) * row / (chart_height - 1)
        y_label = f"{format_y_axis_value(y_val)} │"

        # Chart line
        line = ""
        for col_type, col_data in chart_columns:
            if col_type == 'separator':
                line += "│"
            else:
                data_idx = col_data
                breakdown = scaled_breakdown[data_idx]

                # Calculate cumulative heights for stacking (bottom to top)
                # Stack order: input (bottom) -> output -> cache_creation -> cache_read (top)
                input_height = breakdown['input']
                output_height = breakdown['output']
                cache_creation_height = breakdown['cache_creation']
                cache_read_height = breakdown['cache_read']

                cumulative_input = input_height
                cumulative_output = cumulative_input + output_height
                cumulative_cache_creation = cumulative_output + cache_creation_height
                cumulative_cache_read = cumulative_cache_creation + cache_read_height

                # Determine which character to draw based on current row and chart_type
                # ANSI 256-color codes: Cyan for input, Green for output, Orange for cache_output, Pink for cache_input
                if chart_type == 'io':
                    # Only show input and output
                    if row < cumulative_input:
                        line += "\033[38;5;51m█\033[0m"  # Input tokens (Bright Cyan)
                    elif row < cumulative_output:
                        line += "\033[38;5;46m▓\033[0m"  # Output tokens (Bright Green)
                    else:
                        line += " "  # Empty space
                elif chart_type == 'cache':
                    # Only show cache_creation and cache_read, but calculate from 0
                    cache_only_cumulative_creation = cache_creation_height
                    cache_only_cumulative_read = cache_only_cumulative_creation + cache_read_height
                    if row < cache_only_cumulative_creation:
                        line += "\033[38;5;214m▒\033[0m"  # Cache output tokens (Bright Orange)
                    elif row < cache_only_cumulative_read:
                        line += "█"  # Cache input tokens (default color)
                    else:
                        line += " "  # Empty space
                else:
                    # Show all 4 types
                    if row < cumulative_input:
                        line += "\033[38;5;51m█\033[0m"  # Input tokens (Bright Cyan)
                    elif row < cumulative_output:
                        line += "\033[38;5;46m▓\033[0m"  # Output tokens (Bright Green)
                    elif row < cumulative_cache_creation:
                        line += "\033[38;5;214m▒\033[0m"  # Cache output tokens (Bright Orange)
                    elif row < cumulative_cache_read:
                        line += "█░"  # Cache input tokens (default color)
                    else:
                        line += " "  # Empty space

        print(y_label + line)

    # X-axis with day separators
    # Position: 6 spaces to align └ with Y-axis │
    x_axis_line = ""
    for col_type, _ in chart_columns:
        if col_type == 'separator':
            x_axis_line += "┴"
        else:
            x_axis_line += "─"
    print("      └" + x_axis_line)  # 6 spaces + └ aligns with Y-axis position

    # X-axis labels (show only if show_x_axis is True)
    if show_x_axis:
        # X-axis labels (show only 6:00, 12:00, and 18:00) - rotated 90 degrees counter-clockwise
        print()

        # Create label for 6:00, 12:00, and 18:00
        labels = []
        positions = []

        for i, time in enumerate(sorted_times):
            # Only show labels for 6:00, 12:00, and 18:00
            if time.hour in [6, 12, 18]:
                # Position is the column index for this data point
                if i in data_to_col:
                    labels.append(time.strftime('%H'))
                    positions.append(data_to_col[i])

        # Find maximum label length
        max_label_len = max(len(label) for label in labels) if labels else 0

        # Print each character position vertically
        # Position: 6 spaces to align first character with Y-axis │ position
        # Then add one more space so labels start at column 0 of chart content
        for char_idx in range(max_label_len):
            line = "       "  # 7 spaces: aligns with Y-axis format (5 chars + space + │)

            for col_idx, (col_type, col_data) in enumerate(chart_columns):
                if col_type == 'separator':
                    char_to_print = "│"
                else:
                    # Check if this column has a label
                    char_to_print = " "
                    for label_idx, pos in enumerate(positions):
                        if col_idx == pos and char_idx < len(labels[label_idx]):
                            char_to_print = labels[label_idx][char_idx]
                            break

                line += char_to_print

            print(line)

    # Show summary info only for the last chart (when show_x_axis is True)
    if show_x_axis:
        print("\n" + "=" * (chart_width + 10))
        print(f"Total time span: {sorted_times[0].strftime('%Y-%m-%d %H:%M')} to {sorted_times[-1].strftime('%Y-%m-%d %H:%M')} | Data points: {len(sorted_times)}")
        print(f"Legend: \033[38;5;51m█\033[0m Input  \033[38;5;46m▓\033[0m Output  █ Cache Input  \033[38;5;214m▒\033[0m Cache Output")


def print_model_chart(time_series, width=100, height=20):
    """Print a text-based chart showing each model's usage over time."""
    if not time_series:
        print("No time series data available.")
        return

    sorted_times = sorted(time_series.keys())

    if len(sorted_times) < 2:
        print("Not enough data points for chart.")
        return

    # Get all models and their colors
    all_models = set()
    for models in time_series.values():
        all_models.update(models.keys())

    all_models = sorted(all_models)
    model_symbols = {'claude-sonnet-4-5-20250929': '█',
                     'claude-haiku-4-5-20251001': '▓',
                     'claude-opus-4-1-20250805': '▒'}

    print("\n\nToken Usage by Model Over Time")
    print("=" * width)

    for model in all_models:
        if model not in model_symbols:
            model_symbols[model] = '░'

        # Get values for this model
        values = []
        for time in sorted_times:
            val = time_series[time].get(model, 0) / 1000  # KTok
            values.append(val)

        if all(v == 0 for v in values):
            continue

        max_value = max(values)

        # Print model name
        print(f"\n{model}:")
        print(f"Max: {max_value:.1f} KTok")

        # Simple bar chart
        chart_width = width - 25
        for i, val in enumerate(values):
            if i % 4 == 0:  # Show every 4th data point to avoid clutter
                bar_length = int((val / max_value * chart_width)) if max_value > 0 else 0
                time_str = sorted_times[i].strftime('%m/%d %H:%M')
                bar = model_symbols[model] * bar_length
                print(f"  {time_str} │{bar} {val:.1f}")


def filter_usage_data_by_days(usage_data, days_back):
    """Filter usage data to only include entries from the last N days."""
    if not usage_data:
        return []

    # Get local timezone automatically
    local_tz = datetime.now().astimezone().tzinfo

    # Find the latest timestamp in the data
    latest_time = None
    for entry in usage_data:
        timestamp_str = entry.get('timestamp')
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                timestamp_local = timestamp.astimezone(local_tz)
                if latest_time is None or timestamp_local > latest_time:
                    latest_time = timestamp_local
            except Exception:
                continue

    if latest_time is None:
        return usage_data

    # Calculate start time based on days_back
    start_time = latest_time - timedelta(days=days_back)

    # Filter data
    filtered_data = []
    for entry in usage_data:
        timestamp_str = entry.get('timestamp')
        if not timestamp_str:
            continue

        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            timestamp_local = timestamp.astimezone(local_tz)
            if timestamp_local >= start_time:
                filtered_data.append(entry)
        except Exception:
            continue

    return filtered_data


def print_overall_stats(stats):
    """Print overall statistics."""
    print("Overall Usage Statistics")
    print("=" * 50)
    print()
    print(f"Total messages:        {format_number(stats['total_messages'])}")
    print()
    print(f"Input tokens:          {format_number(stats['input_tokens'])}")
    print(f"Output tokens:         {format_number(stats['output_tokens'])}")
    print(f"Cache output tokens:   {format_number(stats['cache_creation_tokens'])}")
    print(f"Cache input tokens:    {format_number(stats['cache_read_tokens'])}")
    print()
    print(f"Total tokens:          {format_number(stats['total_tokens'])}")


def print_model_breakdown(model_stats):
    """Print model breakdown table."""
    print("Usage by Model")
    print("=" * 154)

    # Print header
    header = f"│ {'Model':<35} {'Messages':>10} │ {'Input':>15} {'Output':>15} {'Total Token':>15} │ {'Cache Output':>15} {'Cache Input':>15} {'Total (with cache)':>19} │"
    print(header)
    print("│" + "-" * 152 + "│")

    # Print rows and calculate sums
    sum_messages = 0
    sum_input = 0
    sum_output = 0
    sum_total = 0
    sum_cache_creation = 0
    sum_cache_read = 0
    sum_total_with_cache = 0

    for stats in model_stats:
        row = (f"│ {stats['model']:<35} "
               f"{stats['count']:>10} │ "
               f"{format_number(stats['input']):>15} "
               f"{format_number(stats['output']):>15} "
               f"{format_number(stats['total']):>15} │ "
               f"{format_number(stats['cache_creation']):>15} "
               f"{format_number(stats['cache_read']):>15} "
               f"{format_number(stats['total_with_cache']):>19} │")
        print(row)

        # Accumulate sums
        sum_messages += stats['count']
        sum_input += stats['input']
        sum_output += stats['output']
        sum_total += stats['total']
        sum_cache_creation += stats['cache_creation']
        sum_cache_read += stats['cache_read']
        sum_total_with_cache += stats['total_with_cache']

    # Print separator and sum row
    print("│" + "-" * 152 + "│")
    sum_row = (f"│ {'TOTAL':<35} "
               f"{sum_messages:>10} │ "
               f"{format_number(sum_input):>15} "
               f"{format_number(sum_output):>15} "
               f"{format_number(sum_total):>15} │ "
               f"{format_number(sum_cache_creation):>15} "
               f"{format_number(sum_cache_read):>15} "
               f"{format_number(sum_total_with_cache):>19} │")
    print(sum_row)
    print("=" * 154)


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Analyze Claude Code usage statistics')
    parser.add_argument('--days', type=int, default=7,
                        help='Number of days to look back (default: 7)')
    parser.add_argument('--monitor', type=int, nargs='?', const=3600, metavar='INTERVAL',
                        help='Monitor mode: refresh output every INTERVAL seconds (default: 3600 seconds / 1 hour)')
    args = parser.parse_args()

    claude_dir = get_claude_dir()
    projects_dir = claude_dir / 'projects'

    if not projects_dir.exists():
        print(f"Error: Projects directory not found at {projects_dir}")
        sys.exit(1)

    def print_stats():
        """Print all statistics (for both one-time and monitor mode)."""
        # Clear screen in monitor mode
        if args.monitor:
            os.system('clear' if os.name != 'nt' else 'cls')

        print("Calculating Claude Code usage...")
        print(f"Showing data from last {args.days} days")
        if args.monitor:
            print(f"Monitor mode: Refreshing every {args.monitor} seconds (Press Ctrl+C to exit)")
            print(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # Read data
        usage_data = read_jsonl_files(projects_dir)

        if not usage_data:
            print("No usage data found.")
            return False

        # Filter data based on days parameter
        filtered_usage_data = filter_usage_data_by_days(usage_data, args.days)

        if not filtered_usage_data:
            print(f"No usage data found in the last {args.days} days.")
            return False

        # Calculate and print statistics using filtered data
        model_stats = calculate_model_breakdown(filtered_usage_data)
        print_model_breakdown(model_stats)

        # Calculate and print token breakdown time series (stacked bar charts)
        # Use 1-hour intervals for finer granularity
        breakdown_time_series = calculate_token_breakdown_time_series(filtered_usage_data, interval_hours=1)

        # Print two separate charts: I/O tokens and Cache tokens
        # Each with reduced height (36 instead of 40) to make room for subscription usage table
        print_stacked_bar_chart(breakdown_time_series, height=36, days_back=args.days,
                                chart_type='io', show_x_axis=False)
        print_stacked_bar_chart(breakdown_time_series, height=36, days_back=args.days,
                                chart_type='cache', show_x_axis=True)

        # Print subscription usage information
        print()
        usage_data = get_subscription_usage()
        print_subscription_usage_table(usage_data)

        print()
        return True

    # Monitor mode: interactive continuous refresh
    if args.monitor:
        print("\n" + "=" * 80)
        print("Interactive Monitor Mode")
        print("=" * 80)
        print("Commands:")
        print("  /refresh - Refresh statistics immediately")
        print("  /exit    - Exit monitor mode")
        print("  Ctrl+C   - Exit monitor mode")
        print(f"\nAuto-refresh interval: {args.monitor} seconds")
        print("=" * 80 + "\n")

        # Initial display
        print_stats()

        next_refresh_time = time.time() + args.monitor

        def show_prompt():
            """Display the command prompt."""
            print("\n" + "─" * 80)
            print("> ", end='', flush=True)

        # Show initial prompt
        show_prompt()

        try:
            while True:
                now = time.time()

                # Check if it's time for auto-refresh
                if now >= next_refresh_time:
                    # Clear the current line (prompt)
                    print("\r" + " " * 82 + "\r", end='')
                    print("─" * 80)
                    print("\n" + "━" * 80)
                    print("🔄 AUTO-REFRESH")
                    print("━" * 80 + "\n")
                    print_stats()
                    next_refresh_time = time.time() + args.monitor
                    show_prompt()

                # Wait for input with timeout using select
                time_until_refresh = next_refresh_time - time.time()
                timeout = min(1.0, max(0.1, time_until_refresh))

                ready, _, _ = select.select([sys.stdin], [], [], timeout)

                if ready:
                    command = sys.stdin.readline().strip()

                    if command == "/refresh":
                        print("─" * 80)
                        print("\n" + "━" * 80)
                        print("🔄 MANUAL REFRESH")
                        print("━" * 80 + "\n")
                        print_stats()
                        # Reset auto-refresh timer
                        next_refresh_time = time.time() + args.monitor
                        show_prompt()
                    elif command == "/exit":
                        print("─" * 80)
                        print("\nExiting monitor mode...")
                        break
                    elif command == "":
                        # Empty command, just show prompt again
                        show_prompt()
                    elif command:
                        print(f"Unknown command: '{command}'. Available: /refresh, /exit")
                        show_prompt()

        except KeyboardInterrupt:
            print("\n" + "─" * 80)
            print("\nMonitoring stopped.")

        sys.exit(0)
    else:
        # One-time execution
        if not print_stats():
            sys.exit(0)


if __name__ == '__main__':
    main()
