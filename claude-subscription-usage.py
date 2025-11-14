#!/usr/bin/env python3
"""
Programmatically interact with Claude Code CLI to get usage information.
Requires: pip install pexpect
"""

import pexpect
import sys
import re
import time

def strip_ansi_codes(text):
    """Remove ANSI color/formatting codes from text."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def get_claude_usage(verbose=False):
    """
    Spawn a Claude Code session, send /usage command, and capture the output.
    """
    if verbose:
        print("Starting Claude Code session...")

    # Spawn with dimensions set to ensure proper rendering
    child = pexpect.spawn('claude', encoding='utf-8', timeout=60)
    child.setwinsize(50, 120)  # rows, cols

    # Buffer to collect all output
    all_output = ""

    try:
        # Wait for the welcome screen to finish
        if verbose:
            print("Waiting for Claude Code to initialize...")
        time.sleep(4)

        # Read any initial output
        try:
            while True:
                child.expect(r'.+', timeout=0.5)
                all_output += child.after
        except pexpect.TIMEOUT:
            pass

        if verbose:
            print("Sending /usage command...")

        # Send the /usage command
        child.send('/usage')
        time.sleep(0.5)

        # Press Enter to execute (autocomplete might be showing)
        child.send('\r')

        # Give it time to process and render the usage display
        if verbose:
            print("Waiting for usage display to render...")
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

        return usage_output if usage_output else all_output

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        try:
            child.close(force=True)
        except:
            pass
        return None

def extract_usage_data(output):
    """
    Extract usage data from Claude Code output.
    Returns a dict with percentages and reset times, or None if failed.
    """
    if not output:
        return None

    # Strip ANSI codes for parsing
    clean_output = strip_ansi_codes(output)

    # Try to extract percentage values
    percentages = re.findall(r'(\d+)%\s+used', clean_output)

    # Extract reset times
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

def print_usage_table(usage_data):
    """
    Print usage information in a 5-line table format, with reset info below.
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

def parse_usage_output(output, compact=False, show_full=False):
    """
    Parse the usage output to extract useful information.
    """
    if not output:
        return None

    # Strip ANSI codes for parsing
    clean_output = strip_ansi_codes(output)

    # Try to extract percentage values
    percentages = re.findall(r'(\d+)%\s+used', clean_output)

    # Extract reset times
    reset_times = re.findall(r'Resets\s+(.+)', clean_output)

    if compact:
        # Compact output - just the numbers
        labels = ["session", "week_all", "week_opus"]
        for i, pct in enumerate(percentages):
            if i < len(labels):
                print(f"{labels[i]}:{pct}")
        return output

    # Standard output
    if percentages:
        print("\n" + "="*80)
        print("CLAUDE CODE USAGE SUMMARY")
        print("="*80)
        labels = ["Current session", "Current week (all models)", "Current week (Opus)"]
        for i, pct in enumerate(percentages):
            if i < len(labels):
                bar = "█" * int(int(pct) / 2)  # Simple progress bar
                print(f"{labels[i]:30s}: {bar:50s} {pct}% used")

        if reset_times:
            print("\n" + "-"*80)
            print("RESET TIMES:")
            print("-"*80)
            for i, reset in enumerate(reset_times):
                if i == 0:
                    print(f"  Session resets: {reset}")
                elif i == 1:
                    print(f"  Weekly resets:  {reset}")
        print("="*80)

    if show_full:
        print("\n" + "="*80)
        print("FULL OUTPUT:")
        print("="*80)
        print(clean_output)
        print("="*80)

    return output

if __name__ == '__main__':
    import argparse

    # Check if pexpect is installed
    try:
        import pexpect
    except ImportError:
        print("Error: pexpect library not found.", file=sys.stderr)
        print("Please install it with: pip install pexpect", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description='Get Claude Code usage information programmatically',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s                    # Show usage summary
  %(prog)s --compact          # Machine-readable output
  %(prog)s --full             # Show full output with ANSI codes stripped
  %(prog)s --verbose          # Show progress messages
        '''
    )
    parser.add_argument('--compact', action='store_true',
                        help='Output in compact machine-readable format (key:value)')
    parser.add_argument('--full', action='store_true',
                        help='Show full output from Claude Code')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show progress messages')

    args = parser.parse_args()

    usage_output = get_claude_usage(verbose=args.verbose)

    if usage_output:
        if args.compact:
            # Use old compact format
            parse_usage_output(usage_output, compact=True, show_full=False)
        else:
            # Use new 7-line table format
            usage_data = extract_usage_data(usage_output)
            print_usage_table(usage_data)
            if args.full:
                print("\n" + "="*80)
                print("FULL OUTPUT:")
                print("="*80)
                clean_output = strip_ansi_codes(usage_output)
                print(clean_output)
                print("="*80)
    else:
        print("Failed to get usage information", file=sys.stderr)
        sys.exit(1)
