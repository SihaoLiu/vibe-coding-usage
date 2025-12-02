#!/usr/bin/env python3
"""
Get Claude Code usage by spawning an interactive session and running /usage.

Usage:
    python get_usage.py          # Returns JSON
    python get_usage.py --raw    # Returns raw terminal output
"""

import sys
import re
import json
import time
import os
import pty
import select
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional


@dataclass
class UsageEntry:
    """Represents a single usage category."""
    name: str
    percentage: int
    reset_time: str
    reset_timezone: str


@dataclass
class UsageReport:
    """Complete usage report from /usage command."""
    entries: list[UsageEntry]
    notice: Optional[str] = None
    parsed_at: str = ""

    def __post_init__(self):
        if not self.parsed_at:
            self.parsed_at = datetime.now().isoformat()


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    # Comprehensive ANSI escape pattern
    ansi_pattern = re.compile(
        r'\x1b\[[0-9;]*[a-zA-Z]'  # CSI sequences
        r'|\x1b\][^\x07]*\x07'     # OSC sequences
        r'|\x1b[PX^_][^\x1b]*\x1b\\'  # DCS, SOS, PM, APC
        r'|\x1b\[[\?]?[0-9;]*[hl]'  # Mode setting
        r'|\x1b[=><]'              # Keypad mode
        r'|\x1b\[\d*[ABCDEFGJKST]'  # Cursor movement
        r'|\x1b\[\d*;\d*[Hf]'       # Cursor position
        r'|\x1b\[[\?]?\d+[hl]'      # Set/Reset modes
    )
    return ansi_pattern.sub('', text)


def clean_output(text: str) -> str:
    """Clean terminal output for parsing."""
    # Strip ANSI codes
    text = strip_ansi(text)
    # Remove carriage returns
    text = text.replace('\r', '')
    # Remove null bytes and other control chars (except newline)
    text = re.sub(r'[\x00-\x09\x0b-\x1f]', '', text)
    return text


def read_until_timeout(fd, timeout=1.0):
    """Read from file descriptor until timeout with no new data."""
    output = b""
    while True:
        ready, _, _ = select.select([fd], [], [], timeout)
        if ready:
            try:
                chunk = os.read(fd, 4096)
                if chunk:
                    output += chunk
                else:
                    break
            except OSError:
                break
        else:
            break
    return output


def get_usage_raw(timeout: int = 30) -> str:
    """
    Spawn claude CLI, run /usage, and capture the output.

    Args:
        timeout: Maximum time to wait for output in seconds

    Returns:
        Raw terminal output from /usage command
    """
    # Create a pseudo-terminal
    master_fd, slave_fd = pty.openpty()

    # Set terminal size
    import fcntl
    import struct
    import termios
    winsize = struct.pack('HHHH', 50, 200, 0, 0)  # rows, cols, xpixel, ypixel
    fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)

    try:
        # Spawn claude
        proc = subprocess.Popen(
            ['claude'],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
        )

        os.close(slave_fd)

        # Wait for Claude to initialize
        time.sleep(3)

        # Read initial output
        output = read_until_timeout(master_fd, timeout=2.0)

        # Type /usage character by character
        for char in '/usage':
            os.write(master_fd, char.encode())
            time.sleep(0.03)

        # Wait for dropdown to appear
        time.sleep(0.5)

        # Read to clear buffer
        read_until_timeout(master_fd, timeout=0.5)

        # Press Enter to select the highlighted /usage command from dropdown
        os.write(master_fd, b'\r')

        # Wait for usage screen to fully render
        time.sleep(5)

        # Read the usage output
        output += read_until_timeout(master_fd, timeout=3.0)

        # Press Escape to close the settings panel
        os.write(master_fd, b'\x1b')
        time.sleep(1)

        # Read more output
        output += read_until_timeout(master_fd, timeout=1.0)

        # Press Escape again if needed
        os.write(master_fd, b'\x1b')
        time.sleep(0.5)

        # Send Ctrl+C then Ctrl+D to exit
        os.write(master_fd, b'\x03')
        time.sleep(0.2)
        os.write(master_fd, b'\x04')

        time.sleep(0.5)

        # Read any remaining output
        output += read_until_timeout(master_fd, timeout=1.0)

        # Terminate the process
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()

    finally:
        os.close(master_fd)

    return output.decode('utf-8', errors='replace')


def parse_usage_output(text: str) -> UsageReport:
    """
    Parse the /usage command output into structured data.

    Args:
        text: Raw output from the /usage command

    Returns:
        UsageReport containing parsed usage entries and any notices
    """
    # Clean the text first
    text = clean_output(text)

    entries = []
    notice = None

    lines = text.strip().split('\n')

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Look for usage category headers
        if line.startswith("Current ") or line.startswith("Daily ") or line.startswith("Monthly "):
            category_name = line

            # Next line should be the progress bar with percentage
            if i + 1 < len(lines):
                progress_line = lines[i + 1].strip()
                # Extract percentage from lines like "██████▌ 13% used"
                percent_match = re.search(r'(\d+)%\s*used', progress_line)

                if percent_match:
                    percentage = int(percent_match.group(1))

                    # Next line should be reset time
                    reset_time = ""
                    reset_timezone = ""
                    if i + 2 < len(lines):
                        reset_line = lines[i + 2].strip()
                        if reset_line.startswith("Resets "):
                            reset_match = re.match(
                                r'Resets\s+(.+?)\s*\(([^)]+)\)',
                                reset_line
                            )
                            if reset_match:
                                reset_time = reset_match.group(1).strip()
                                reset_timezone = reset_match.group(2).strip()

                    entries.append(UsageEntry(
                        name=category_name,
                        percentage=percentage,
                        reset_time=reset_time,
                        reset_timezone=reset_timezone
                    ))
                    i += 3
                    continue

        # Look for notice/update section
        if "update:" in line.lower():
            notice_lines = [line]
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if next_line and not next_line.startswith("─"):
                    notice_lines.append(next_line)
                    i += 1
                else:
                    break
            notice = " ".join(notice_lines)
            continue

        i += 1

    return UsageReport(entries=entries, notice=notice)


def to_dict(report: UsageReport) -> dict:
    """Convert UsageReport to a dictionary."""
    return {
        "entries": [asdict(entry) for entry in report.entries],
        "notice": report.notice,
        "parsed_at": report.parsed_at
    }


def get_usage(timeout: int = 30) -> UsageReport:
    """
    Get and parse Claude Code usage.

    Args:
        timeout: Maximum time to wait in seconds

    Returns:
        Parsed UsageReport
    """
    raw = get_usage_raw(timeout=timeout)
    return parse_usage_output(raw)


def main():
    """Main entry point."""
    raw_mode = "--raw" in sys.argv

    try:
        raw_output = get_usage_raw()

        if raw_mode:
            print(raw_output)
        else:
            report = parse_usage_output(raw_output)
            print(json.dumps(to_dict(report), indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
