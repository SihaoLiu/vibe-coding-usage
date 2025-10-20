#!/usr/bin/env python3

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import sys

try:
    import pytz
except ImportError:
    print("Error: pytz is required. Install with: pip install pytz")
    sys.exit(1)


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
        result.append(stats)

    result.sort(key=lambda x: x['total'], reverse=True)
    return result


def calculate_time_series(usage_data, interval_hours=3):
    """Calculate token usage over time in specified hour intervals (LA timezone)."""
    la_tz = pytz.timezone('America/Los_Angeles')

    # Group by time interval and model
    time_series = defaultdict(lambda: defaultdict(int))

    for entry in usage_data:
        timestamp_str = entry.get('timestamp')
        if not timestamp_str:
            continue

        try:
            # Parse ISO timestamp and convert to LA timezone
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            timestamp_la = timestamp.astimezone(la_tz)

            # Round down to the nearest interval
            hour = timestamp_la.hour
            interval_hour = (hour // interval_hours) * interval_hours
            interval_time = timestamp_la.replace(hour=interval_hour, minute=0, second=0, microsecond=0)

            model = entry['message'].get('model', 'unknown')
            usage = entry['message']['usage']

            # Total tokens (input + output, in kilo tokens)
            total_tokens = usage.get('input_tokens', 0) + usage.get('output_tokens', 0)

            time_series[interval_time][model] += total_tokens
        except Exception:
            continue

    return time_series


def print_line_chart(time_series, height=20):
    """Print a text-based line chart of token usage over time."""
    if not time_series:
        print("No time series data available.")
        return

    # Sort by time
    all_sorted_times = sorted(time_series.keys())

    if not all_sorted_times:
        print("No data available.")
        return

    # Use all data (don't discard incomplete first day)
    first_time = all_sorted_times[0]
    last_time = all_sorted_times[-1]

    # Round first_time down to nearest 3-hour interval
    first_hour = (first_time.hour // 3) * 3
    first_time_rounded = first_time.replace(hour=first_hour, minute=0, second=0, microsecond=0)

    # Create a complete continuous time series (every 3 hours)
    # This ensures uniform spacing even when there's no data
    sorted_times = []
    current_time = first_time_rounded
    while current_time <= last_time:
        sorted_times.append(current_time)
        current_time += timedelta(hours=3)

    if len(sorted_times) < 2:
        print("Not enough data points for chart.")
        return

    # Check if chart would be too wide (max 500 columns)
    if len(sorted_times) > 500:
        print(f"Warning: Too many data points ({len(sorted_times)}). Maximum is 500.")
        print("Consider using a longer time interval or limiting the time range.")
        return

    # Get all models
    all_models = set()
    for models in time_series.values():
        all_models.update(models.keys())

    # Calculate totals per time interval (use 0 for missing data)
    totals = []
    for time in sorted_times:
        if time in time_series:
            total = sum(time_series[time].values()) / 1000  # Convert to KTok
        else:
            total = 0.0  # No data for this interval
        totals.append(total)

    max_value = max(totals) if totals else 1
    min_value = min(totals) if totals else 0

    num_data_points = len(totals)
    chart_height = height

    print("\nToken Usage Over Time (3-hour intervals, LA Time)")
    print(f"Y-axis: Token consumption (KTok)")
    print(f"X-axis: Time (each day has 8 data points, ticks at 6-hour intervals)\n")

    # Scale values to chart height
    if max_value == min_value:
        scaled_values = [chart_height // 2] * num_data_points
    else:
        scaled_values = [
            int((val - min_value) / (max_value - min_value) * (chart_height - 1))
            for val in totals
        ]

    # Build chart:
    # First day: 8 data points (no separator, Y-axis serves as the boundary)
    # Subsequent days: separator + 8 data points
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

    # Draw chart from top to bottom
    for row in range(chart_height - 1, -1, -1):
        # Y-axis label
        y_val = min_value + (max_value - min_value) * row / (chart_height - 1)
        y_label = f"{y_val:6.1f} │"

        # Chart line
        line = ""
        prev_val = None
        for col_type, col_data in chart_columns:
            if col_type == 'separator':
                line += "│"
            else:
                data_idx = col_data
                val = scaled_values[data_idx]

                if val == row:
                    line += "●"
                elif prev_val is not None and min(prev_val, val) <= row <= max(prev_val, val):
                    line += "│"
                else:
                    line += " "

                prev_val = val

        print(y_label + line)

    # X-axis with day separators
    x_axis_line = ""
    for col_type, _ in chart_columns:
        if col_type == 'separator':
            x_axis_line += "┴"
        else:
            x_axis_line += "─"
    print("       └" + x_axis_line)

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
                labels.append(time.strftime('%m/%d %H:%M'))
                positions.append(data_to_col[i])

    # Find maximum label length
    max_label_len = max(len(label) for label in labels) if labels else 0

    # Print each character position vertically
    for char_idx in range(max_label_len):
        line = "        "  # Indent to align with chart (one extra space for first day alignment)

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

    # Legend - show models and their totals
    print(f"\nTotal time span: {sorted_times[0].strftime('%Y-%m-%d %H:%M')} to {sorted_times[-1].strftime('%Y-%m-%d %H:%M')}")
    print(f"Data points: {len(sorted_times)}")


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


def print_overall_stats(stats):
    """Print overall statistics."""
    print("Overall Usage Statistics")
    print("=" * 50)
    print()
    print(f"Total messages:        {format_number(stats['total_messages'])}")
    print()
    print(f"Input tokens:          {format_number(stats['input_tokens'])}")
    print(f"Output tokens:         {format_number(stats['output_tokens'])}")
    print(f"Cache creation tokens: {format_number(stats['cache_creation_tokens'])}")
    print(f"Cache read tokens:     {format_number(stats['cache_read_tokens'])}")
    print()
    print(f"Total tokens:          {format_number(stats['total_tokens'])}")


def print_model_breakdown(model_stats):
    """Print model breakdown table."""
    print("\n\n")
    print("Usage by Model")
    print("=" * 120)

    # Print header
    header = f"{'Model':<35} {'Messages':>10} {'Input':>15} {'Output':>15} {'Cache Create':>15} {'Cache Read':>15} {'Total':>15}"
    print(header)
    print("-" * 120)

    # Print rows
    for stats in model_stats:
        row = (f"{stats['model']:<35} "
               f"{stats['count']:>10} "
               f"{format_number(stats['input']):>15} "
               f"{format_number(stats['output']):>15} "
               f"{format_number(stats['cache_creation']):>15} "
               f"{format_number(stats['cache_read']):>15} "
               f"{format_number(stats['total']):>15}")
        print(row)


def main():
    claude_dir = get_claude_dir()
    projects_dir = claude_dir / 'projects'

    if not projects_dir.exists():
        print(f"Error: Projects directory not found at {projects_dir}")
        sys.exit(1)

    print("Calculating Claude Code usage...")
    print()

    # Read data
    usage_data = read_jsonl_files(projects_dir)

    if not usage_data:
        print("No usage data found.")
        sys.exit(0)

    # Calculate and print statistics
    overall_stats = calculate_overall_stats(usage_data)
    print_overall_stats(overall_stats)

    model_stats = calculate_model_breakdown(usage_data)
    print_model_breakdown(model_stats)

    # Calculate and print time series
    time_series = calculate_time_series(usage_data, interval_hours=3)
    print_line_chart(time_series)
    print_model_chart(time_series)

    print()


if __name__ == '__main__':
    main()
