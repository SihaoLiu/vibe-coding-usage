#!/usr/bin/env python3

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import sys
import argparse
import time
import re
import zoneinfo


def get_gemini_dir():
    """Get Gemini configuration directory."""
    gemini_dir = os.environ.get('GEMINI_CONFIG_DIR', os.path.expanduser('~/.gemini'))
    return Path(gemini_dir)


def read_chat_files(tmp_dir):
    """Read all chat JSON files from tmp directory."""
    usage_data = []

    # Find all session JSON files in chats subdirectories
    for chat_file in tmp_dir.rglob('chats/session-*.json'):
        try:
            with open(chat_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

                # Extract messages with token usage
                if 'messages' in data:
                    for message in data['messages']:
                        # Only include Gemini messages with token data
                        if message.get('type') == 'gemini' and 'tokens' in message:
                            # Create a unified format similar to Claude's
                            usage_entry = {
                                'timestamp': message.get('timestamp'),
                                'session_id': data.get('sessionId'),
                                'project_hash': data.get('projectHash'),
                                'message': {
                                    'id': message.get('id'),
                                    'model': message.get('model', 'unknown'),
                                    'usage': {
                                        'input_tokens': message['tokens'].get('input', 0),
                                        'output_tokens': message['tokens'].get('output', 0),
                                        'cached_tokens': message['tokens'].get('cached', 0),
                                        'thoughts_tokens': message['tokens'].get('thoughts', 0),
                                        'tool_tokens': message['tokens'].get('tool', 0),
                                        'total_tokens': message['tokens'].get('total', 0),
                                    }
                                }
                            }
                            usage_data.append(usage_entry)
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
        'cached_tokens': 0,
        'thoughts_tokens': 0,
        'tool_tokens': 0,
        'total_tokens': 0,
    }

    for entry in usage_data:
        usage = entry['message']['usage']
        stats['input_tokens'] += usage.get('input_tokens', 0)
        stats['output_tokens'] += usage.get('output_tokens', 0)
        stats['cached_tokens'] += usage.get('cached_tokens', 0)
        stats['thoughts_tokens'] += usage.get('thoughts_tokens', 0)
        stats['tool_tokens'] += usage.get('tool_tokens', 0)
        stats['total_tokens'] += usage.get('total_tokens', 0)

    return stats


def calculate_model_breakdown(usage_data):
    """Calculate usage breakdown by model."""
    model_stats = defaultdict(lambda: {
        'count': 0,
        'input': 0,
        'output': 0,
        'cached': 0,
        'thoughts': 0,
        'tool': 0,
        'total': 0,
    })

    for entry in usage_data:
        model = entry['message'].get('model', 'unknown')
        usage = entry['message']['usage']

        model_stats[model]['count'] += 1
        model_stats[model]['input'] += usage.get('input_tokens', 0)
        model_stats[model]['output'] += usage.get('output_tokens', 0)
        model_stats[model]['cached'] += usage.get('cached_tokens', 0)
        model_stats[model]['thoughts'] += usage.get('thoughts_tokens', 0)
        model_stats[model]['tool'] += usage.get('tool_tokens', 0)
        model_stats[model]['total'] += usage.get('total_tokens', 0)

    # Sort by total tokens
    result = []
    for model, stats in model_stats.items():
        stats['model'] = model
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

            # Total tokens
            total_tokens = usage.get('total_tokens', 0)

            time_series[interval_time][model] += total_tokens
        except Exception:
            continue

    return time_series


def calculate_token_breakdown_time_series(usage_data, interval_hours=1):
    """Calculate token usage breakdown over time in specified hour intervals (local timezone)."""
    # Get local timezone automatically
    local_tz = datetime.now().astimezone().tzinfo

    # Group by time interval with breakdown
    time_series = defaultdict(lambda: {
        'input': 0,
        'output': 0,
        'cached': 0,
        'thoughts': 0,
        'tool': 0
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
            time_series[interval_time]['cached'] += usage.get('cached_tokens', 0)
            time_series[interval_time]['thoughts'] += usage.get('thoughts_tokens', 0)
            time_series[interval_time]['tool'] += usage.get('tool_tokens', 0)
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


def print_stacked_bar_chart(time_series, height=75, days_back=7, show_x_axis=True):
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
            cached_val = time_series[time].get('cached', 0)
            thoughts_val = time_series[time].get('thoughts', 0)
            tool_val = time_series[time].get('tool', 0)
        else:
            input_val = output_val = cached_val = thoughts_val = tool_val = 0

        breakdown_data.append({
            'input': input_val,
            'output': output_val,
            'cached': cached_val,
            'thoughts': thoughts_val,
            'tool': tool_val
        })

        total = input_val + output_val + cached_val + thoughts_val + tool_val
        totals.append(total)

    # Calculate Y-axis range
    max_value_raw = max(totals) if totals else 1
    min_value_raw = min(totals) if totals else 0

    # Round min/max to nearest multiple of 5K or 5M or 5B
    def round_to_5_multiple(value, round_up=True):
        """Round value to nearest multiple of 5B/5M/5K."""
        if value >= 5_000_000_000:
            # Round to nearest 5B
            unit = 5_000_000_000
        elif value >= 5_000_000:
            # Round to nearest 5M
            unit = 5_000_000
        elif value >= 5_000:
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

    print("\nToken Usage Breakdown Over Time (1-hour intervals, Local Time)")
    print(f"Y-axis: Token consumption (all token types)")

    if show_x_axis:
        print(f"X-axis: Time (each day has 24 data points, ticks at 6-hour intervals)\n")
    else:
        print()

    # Scale breakdown values to chart height
    scaled_breakdown = []
    for breakdown in breakdown_data:
        if max_value == min_value:
            scaled_breakdown.append({
                'input': 0,
                'output': 0,
                'cached': 0,
                'thoughts': 0,
                'tool': 0
            })
        else:
            # Scale each component individually
            scaled_breakdown.append({
                'input': int((breakdown['input'] - 0) / (max_value - min_value) * (chart_height - 1)),
                'output': int((breakdown['output'] - 0) / (max_value - min_value) * (chart_height - 1)),
                'cached': int((breakdown['cached'] - 0) / (max_value - min_value) * (chart_height - 1)),
                'thoughts': int((breakdown['thoughts'] - 0) / (max_value - min_value) * (chart_height - 1)),
                'tool': int((breakdown['tool'] - 0) / (max_value - min_value) * (chart_height - 1))
            })

    # Build chart columns
    chart_columns = []
    data_to_col = {}

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
    weekday_line = " " * 7
    date_line = " " * 7
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

        # Add padding to align
        if colon_idx > slash_idx:
            date_str = ' ' * (colon_idx - slash_idx) + date_str
            slash_idx = colon_idx
        elif slash_idx > colon_idx:
            weekday_total = ' ' * (slash_idx - colon_idx) + weekday_total
            colon_idx = slash_idx

        # Make both strings the same length
        max_len = max(len(weekday_total), len(date_str))
        weekday_total = weekday_total.ljust(max_len)
        date_str = date_str.ljust(max_len)

        # Position them
        start_pos = mid_col - colon_idx

        # Add padding and content
        padding = start_pos - prev_end
        if padding > 0:
            weekday_line += " " * padding
            date_line += " " * padding

        weekday_line += weekday_total
        date_line += date_str
        prev_end = start_pos + max_len

    print(weekday_line)
    print(date_line)

    # Draw chart from top to bottom (stacked bar chart)
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
                # Stack order: input (bottom) -> output -> cached -> thoughts -> tool (top)
                input_height = breakdown['input']
                output_height = breakdown['output']
                cached_height = breakdown['cached']
                thoughts_height = breakdown['thoughts']
                tool_height = breakdown['tool']

                cumulative_input = input_height
                cumulative_output = cumulative_input + output_height
                cumulative_cached = cumulative_output + cached_height
                cumulative_thoughts = cumulative_cached + thoughts_height
                cumulative_tool = cumulative_thoughts + tool_height

                # Determine which character to draw
                if row < cumulative_input:
                    line += "\033[38;5;51m█\033[0m"  # Input tokens (Bright Cyan)
                elif row < cumulative_output:
                    line += "\033[38;5;46m▓\033[0m"  # Output tokens (Bright Green)
                elif row < cumulative_cached:
                    line += "\033[38;5;214m▒\033[0m"  # Cached tokens (Bright Orange)
                elif row < cumulative_thoughts:
                    line += "\033[38;5;201m░\033[0m"  # Thoughts tokens (Bright Magenta)
                elif row < cumulative_tool:
                    line += "\033[38;5;226m■\033[0m"  # Tool tokens (Bright Yellow)
                else:
                    line += " "  # Empty space

        print(y_label + line)

    # X-axis
    x_axis_line = ""
    for col_type, _ in chart_columns:
        if col_type == 'separator':
            x_axis_line += "┴"
        else:
            x_axis_line += "─"
    print("      └" + x_axis_line)

    # X-axis labels
    if show_x_axis:
        print()

        # Create labels for 6:00, 12:00, and 18:00
        labels = []
        positions = []

        for i, time in enumerate(sorted_times):
            if time.hour in [6, 12, 18]:
                if i in data_to_col:
                    labels.append(time.strftime('%H'))
                    positions.append(data_to_col[i])

        # Find maximum label length
        max_label_len = max(len(label) for label in labels) if labels else 0

        # Print each character position vertically
        for char_idx in range(max_label_len):
            line = "       "  # 7 spaces: aligns with Y-axis

            for col_idx, (col_type, col_data) in enumerate(chart_columns):
                if col_type == 'separator':
                    char_to_print = "│"
                else:
                    char_to_print = " "
                    for label_idx, pos in enumerate(positions):
                        if col_idx == pos and char_idx < len(labels[label_idx]):
                            char_to_print = labels[label_idx][char_idx]
                            break

                line += char_to_print

            print(line)

    # Show summary info
    if show_x_axis:
        print("\n" + "=" * (chart_width + 10))
        print(f"Total time span: {sorted_times[0].strftime('%Y-%m-%d %H:%M')} to {sorted_times[-1].strftime('%Y-%m-%d %H:%M')} | Data points: {len(sorted_times)}")
        print(f"Legend: \033[38;5;51m█\033[0m Input  \033[38;5;46m▓\033[0m Output  \033[38;5;214m▒\033[0m Cached  \033[38;5;201m░\033[0m Thoughts  \033[38;5;226m■\033[0m Tool")


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
    print(f"Cached tokens:         {format_number(stats['cached_tokens'])}")
    print(f"Thoughts tokens:       {format_number(stats['thoughts_tokens'])}")
    print(f"Tool tokens:           {format_number(stats['tool_tokens'])}")
    print()
    print(f"Total tokens:          {format_number(stats['total_tokens'])}")


def print_model_breakdown(model_stats):
    """Print model breakdown table."""
    print("Usage by Model")
    print("=" * 154)

    # Print header
    header = f"│ {'Model':<35} {'Messages':>10} │ {'Input':>15} {'Output':>15} {'Cached':>15} │ {'Thoughts':>15} {'Tool':>15} {'Total':>19} │"
    print(header)
    print("│" + "-" * 152 + "│")

    # Print rows and calculate sums
    sum_messages = 0
    sum_input = 0
    sum_output = 0
    sum_cached = 0
    sum_thoughts = 0
    sum_tool = 0
    sum_total = 0

    for stats in model_stats:
        row = (f"│ {stats['model']:<35} "
               f"{stats['count']:>10} │ "
               f"{format_number(stats['input']):>15} "
               f"{format_number(stats['output']):>15} "
               f"{format_number(stats['cached']):>15} │ "
               f"{format_number(stats['thoughts']):>15} "
               f"{format_number(stats['tool']):>15} "
               f"{format_number(stats['total']):>19} │")
        print(row)

        # Accumulate sums
        sum_messages += stats['count']
        sum_input += stats['input']
        sum_output += stats['output']
        sum_cached += stats['cached']
        sum_thoughts += stats['thoughts']
        sum_tool += stats['tool']
        sum_total += stats['total']

    # Print separator and sum row
    print("│" + "-" * 152 + "│")
    sum_row = (f"│ {'TOTAL':<35} "
               f"{sum_messages:>10} │ "
               f"{format_number(sum_input):>15} "
               f"{format_number(sum_output):>15} "
               f"{format_number(sum_cached):>15} │ "
               f"{format_number(sum_thoughts):>15} "
               f"{format_number(sum_tool):>15} "
               f"{format_number(sum_total):>19} │")
    print(sum_row)
    print("=" * 154)


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Analyze Gemini usage statistics')
    parser.add_argument('--days', type=int, default=7,
                        help='Number of days to look back (default: 7)')
    parser.add_argument('--monitor', type=int, nargs='?', const=3600, metavar='INTERVAL',
                        help='Monitor mode: refresh output every INTERVAL seconds (default: 3600 seconds / 1 hour)')
    args = parser.parse_args()

    gemini_dir = get_gemini_dir()
    tmp_dir = gemini_dir / 'tmp'

    if not tmp_dir.exists():
        print(f"Error: Tmp directory not found at {tmp_dir}")
        sys.exit(1)

    def print_stats():
        """Print all statistics (for both one-time and monitor mode)."""
        # Clear screen in monitor mode
        if args.monitor:
            os.system('clear' if os.name != 'nt' else 'cls')

        print("Calculating Gemini usage...")
        print(f"Showing data from last {args.days} days")
        if args.monitor:
            print(f"Monitor mode: Refreshing every {args.monitor} seconds (Press Ctrl+C to exit)")
            print(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # Read data
        usage_data = read_chat_files(tmp_dir)

        if not usage_data:
            print("No usage data found.")
            return False

        # Filter data based on days parameter
        filtered_usage_data = filter_usage_data_by_days(usage_data, args.days)

        if not filtered_usage_data:
            print(f"No usage data found in the last {args.days} days.")
            return False

        # Calculate and print statistics
        model_stats = calculate_model_breakdown(filtered_usage_data)
        print_model_breakdown(model_stats)

        # Calculate and print token breakdown time series
        breakdown_time_series = calculate_token_breakdown_time_series(filtered_usage_data, interval_hours=1)
        print_stacked_bar_chart(breakdown_time_series, height=75, days_back=args.days, show_x_axis=True)

        print()
        return True

    # Monitor mode
    if args.monitor:
        print("\n" + "=" * 80)
        print("Monitor Mode")
        print("==" * 80)
        print(f"\nAuto-refresh interval: {args.monitor} seconds")
        print("Press Ctrl+C to exit")
        print("=" * 80 + "\n")

        try:
            while True:
                print_stats()
                print(f"\nNext refresh in {args.monitor} seconds...")
                time.sleep(args.monitor)
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped.")

        sys.exit(0)
    else:
        # One-time execution
        if not print_stats():
            sys.exit(0)


if __name__ == '__main__':
    main()
