#!/usr/bin/env python3

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import sys
import argparse

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


def calculate_time_series(usage_data, interval_hours=1):
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


def calculate_all_tokens_time_series(usage_data, interval_hours=1):
    """Calculate ALL token usage (input + output + cache) over time in specified hour intervals (LA timezone)."""
    la_tz = pytz.timezone('America/Los_Angeles')

    # Group by time interval (all models combined)
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
    """Calculate token usage breakdown (input/output/cache_creation/cache_read) over time in specified hour intervals (LA timezone)."""
    la_tz = pytz.timezone('America/Los_Angeles')

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
            # Parse ISO timestamp and convert to LA timezone
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            timestamp_la = timestamp.astimezone(la_tz)

            # Round down to the nearest interval
            hour = timestamp_la.hour
            interval_hour = (hour // interval_hours) * interval_hours
            interval_time = timestamp_la.replace(hour=interval_hour, minute=0, second=0, microsecond=0)

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


def print_stacked_bar_chart(time_series, height=50, days_back=7):
    """Print a text-based stacked bar chart of token usage breakdown over time."""
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
        totals.append(input_val + output_val + cache_creation_val + cache_read_val)

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

    print("\nToken Usage Breakdown Over Time (1-hour intervals, LA Time)")
    print(f"Y-axis: Token consumption (all token types)")
    print(f"X-axis: Time (each day has 24 data points, ticks at 6-hour intervals)\n")

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

    # Print daily totals at top of chart
    total_line = " " * 7  # Align with Y-axis
    prev_end = 0
    chinese_chars = "我必须立刻学习"
    for day_idx, (mid_col, total, day_start) in enumerate(daily_totals):
        total_str = format_total_value(total)
        # Add Chinese character cycling through the string
        char_idx = day_idx % len(chinese_chars)
        chinese_char = chinese_chars[char_idx]
        total_with_char = f"{chinese_char} : {total_str}"

        # Center the total string around mid_col
        start_pos = mid_col - len(total_with_char) // 2
        padding = start_pos - prev_end
        if padding > 0:
            total_line += " " * padding
        total_line += total_with_char
        prev_end = start_pos + len(total_with_char)
    print(total_line)

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

                # Determine which character to draw based on current row
                if row < cumulative_input:
                    line += "█"  # Input tokens
                elif row < cumulative_output:
                    line += "▓"  # Output tokens
                elif row < cumulative_cache_creation:
                    line += "▒"  # Cache creation tokens
                elif row < cumulative_cache_read:
                    line += "░"  # Cache read tokens
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

    # Legend - show token types and their symbols
    print("\n" + "=" * (chart_width + 10))
    print("\nLegend (stacked from bottom to top):")
    print(f"  █ Input tokens")
    print(f"  ▓ Output tokens")
    print(f"  ▒ Cache creation tokens")
    print(f"  ░ Cache read tokens")
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
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Analyze Claude Code usage statistics')
    parser.add_argument('--days', type=int, default=7,
                        help='Number of days to look back (default: 7)')
    args = parser.parse_args()

    claude_dir = get_claude_dir()
    projects_dir = claude_dir / 'projects'

    if not projects_dir.exists():
        print(f"Error: Projects directory not found at {projects_dir}")
        sys.exit(1)

    print("Calculating Claude Code usage...")
    print(f"Showing data from last {args.days} days")
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

    # Calculate and print token breakdown time series (stacked bar chart)
    # Use 1-hour intervals for finer granularity
    breakdown_time_series = calculate_token_breakdown_time_series(usage_data, interval_hours=1)
    print_stacked_bar_chart(breakdown_time_series, days_back=args.days)

    print()


if __name__ == '__main__':
    main()
