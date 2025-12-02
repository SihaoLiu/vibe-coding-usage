"""Subscription usage functions for Claude Code usage analysis."""

import re
from datetime import datetime, timedelta
import zoneinfo

from constants import SESSION_DURATION_MINUTES, WEEKLY_DURATION_MINUTES
from get_usage import get_usage, UsageReport


def get_subscription_usage():
    """
    Get Claude Code subscription usage by spawning a claude session.
    Returns usage data dict or None if fetch fails.

    Uses get_usage.py to spawn an interactive session and parse /usage output.
    """
    try:
        report = get_usage()

        if not report.entries:
            return {'error': 'parse', 'message': 'No usage entries found in /usage output'}

        # Map entries to the expected format
        # Expected entries: "Current session", "Current week (all models)", "Current week (Sonnet only)"
        result = {
            'session_pct': 0,
            'week_all_pct': 0,
            'week_sonnet_pct': 0,
            'session_reset': 'Unknown',
            'week_reset': 'Unknown'
        }

        for entry in report.entries:
            name_lower = entry.name.lower()
            reset_str = f"{entry.reset_time} ({entry.reset_timezone})" if entry.reset_time else 'Unknown'

            if 'session' in name_lower:
                result['session_pct'] = entry.percentage
                result['session_reset'] = reset_str
            elif 'week' in name_lower and 'all' in name_lower:
                result['week_all_pct'] = entry.percentage
                result['week_reset'] = reset_str
            elif 'week' in name_lower and 'sonnet' in name_lower:
                result['week_sonnet_pct'] = entry.percentage
                # Week reset time is the same for both weekly entries

        return result

    except Exception as e:
        return {'error': 'exception', 'message': f'Failed to fetch subscription usage: {str(e)}'}


def parse_reset_time_and_calculate_remaining(reset_str, period_duration_minutes):
    """
    Parse reset time string and calculate time remaining until reset.

    Args:
        reset_str: String like "4pm (America/Los_Angeles)" or "Nov 18, 3pm (America/Los_Angeles)"
        period_duration_minutes: Total duration of the period in minutes (e.g., 300 for 5 hours, 10080 for 7 days)

    Returns:
        Tuple of (formatted_string, time_elapsed_pct) or (None, None) if parsing fails
        formatted_string: like "XX day(s) XX hr(s) XX min(s)"
        time_elapsed_pct: percentage of time elapsed (0-100)
    """
    if not reset_str or reset_str == 'Unknown' or reset_str == 'N/A':
        return None, None

    try:
        # Extract timezone from parentheses
        tz_match = re.search(r'\(([^)]+)\)', reset_str)
        if not tz_match:
            return None, None

        tz_name = tz_match.group(1)
        try:
            tz = zoneinfo.ZoneInfo(tz_name)
        except:
            return None, None

        # Get current time in that timezone
        now = datetime.now(tz)

        # Remove timezone part to parse the time
        time_part = reset_str[:tz_match.start()].strip().rstrip(',')

        # Check if it has a date (like "Nov 18, 3pm") or just time (like "4pm")
        if ',' in time_part:
            # Has date - parse as "Nov 18, 3pm"
            # Need to add current year
            date_with_year = f"{time_part}, {now.year}"
            try:
                reset_time = datetime.strptime(date_with_year, "%b %d, %I%p, %Y")
            except:
                # Try with different format
                reset_time = datetime.strptime(date_with_year, "%b %d, %I:%M%p, %Y")

            # Add timezone info
            reset_time = reset_time.replace(tzinfo=tz)

            # If the reset time is in the past, assume it's next year
            if reset_time < now:
                reset_time = reset_time.replace(year=now.year + 1)
        else:
            # Just time - assume today or tomorrow
            try:
                time_obj = datetime.strptime(time_part, "%I%p")
            except:
                time_obj = datetime.strptime(time_part, "%I:%M%p")

            # Combine with today's date
            reset_time = now.replace(
                hour=time_obj.hour,
                minute=time_obj.minute,
                second=0,
                microsecond=0
            )

            # If it's in the past today, it must be tomorrow
            if reset_time < now:
                reset_time += timedelta(days=1)

        # Calculate time difference
        time_diff = reset_time - now

        # Convert to days, hours, minutes
        total_seconds = int(time_diff.total_seconds())
        days = total_seconds // 86400
        remaining_seconds = total_seconds % 86400
        hours = remaining_seconds // 3600
        minutes = (remaining_seconds % 3600) // 60

        # Format output
        parts = []
        if days > 0:
            parts.append(f"{days} day(s)")
        if hours > 0 or days > 0:  # Show hours if there are days
            parts.append(f"{hours} hr(s)")
        parts.append(f"{minutes} min(s)")

        # Calculate time elapsed percentage within the current period
        time_remaining_minutes = total_seconds / 60
        # Find how much time remains in the current period (using modulo)
        time_remaining_in_period = time_remaining_minutes % period_duration_minutes
        time_elapsed_in_period = period_duration_minutes - time_remaining_in_period
        time_elapsed_pct = (time_elapsed_in_period / period_duration_minutes) * 100

        # Ensure percentage is between 0 and 100
        time_elapsed_pct = max(0, min(100, time_elapsed_pct))

        return " ".join(parts), time_elapsed_pct

    except Exception:
        return None, None


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
        print("Current week (Sonnet)         :                                              | N/A    |")
        print("="*TABLE_WIDTH)
        print("Session resets: N/A")
        print("Weekly resets:  N/A")
        return

    # Check if usage_data contains an error
    if isinstance(usage_data, dict) and 'error' in usage_data:
        print("="*TABLE_WIDTH)
        print("Current session               :                                              | ERROR  |")
        print("Current week (all models)     :                                              | ERROR  |")
        print("Current week (Sonnet)         :                                              | ERROR  |")
        print("="*TABLE_WIDTH)
        print(f"\nError: {usage_data['message']}")
        print()
        return

    # Create progress bars (47 chars max)
    def make_bar(pct):
        filled = int(pct * 47 / 100)
        return "\u2588" * filled

    session_bar = make_bar(usage_data['session_pct'])
    week_all_bar = make_bar(usage_data['week_all_pct'])
    week_sonnet_bar = make_bar(usage_data['week_sonnet_pct'])

    print("="*TABLE_WIDTH)
    print(f"Current session               : {session_bar:<47}| {usage_data['session_pct']:>2}% used|")
    print(f"Current week (all models)     : {week_all_bar:<47}| {usage_data['week_all_pct']:>2}% used|")
    print(f"Current week (Sonnet)         : {week_sonnet_bar:<47}| {usage_data['week_sonnet_pct']:>2}% used|")
    print("="*TABLE_WIDTH)
    print()

    # Print session reset with time remaining and predictions
    session_reset_str = usage_data['session_reset']
    time_remaining, time_elapsed_pct = parse_reset_time_and_calculate_remaining(session_reset_str, SESSION_DURATION_MINUTES)
    print(f"Session resets at: {session_reset_str}")
    if time_remaining:
        # Calculate predicted token consumption
        session_usage_pct = usage_data['session_pct']
        if time_elapsed_pct > 0:
            predicted_pct = (session_usage_pct / time_elapsed_pct) * 100
        else:
            predicted_pct = 0

        print(f"                   \u2514\u2500 Resets in {time_remaining}, {time_elapsed_pct:.1f}% time passed, {predicted_pct:.1f}% token usage predicated")

    print()

    # Print weekly reset with time remaining and predictions
    week_reset_str = usage_data['week_reset']
    time_remaining, time_elapsed_pct = parse_reset_time_and_calculate_remaining(week_reset_str, WEEKLY_DURATION_MINUTES)
    print(f"Weekly resets at:  {week_reset_str}")
    if time_remaining:
        # Calculate predicted token consumption
        week_usage_pct = usage_data['week_all_pct']
        if time_elapsed_pct > 0:
            predicted_pct = (week_usage_pct / time_elapsed_pct) * 100
        else:
            predicted_pct = 0

        print(f"                   \u2514\u2500 Resets in {time_remaining}, {time_elapsed_pct:.1f}% time passed, {predicted_pct:.1f}% token usage predicated")
