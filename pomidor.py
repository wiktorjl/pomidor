#!/usr/bin/env python3
"""Minimalistic Pomodoro timer."""

import json
import subprocess
import sys
import termios
import time
import tty
from pathlib import Path

CACHE_FILE = Path.home() / ".cache" / "pomodoro_config.json"
SOUND_FILE = Path("/usr/share/sounds/freedesktop/stereo/complete.oga")

# ANSI colors
RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
MAGENTA = "\033[95m"


def load_defaults():
    """Load saved defaults from cache (stored in seconds)."""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"focus": 1500, "break": 300}  # 25min, 5min in seconds


def save_defaults(focus_secs, break_secs):
    """Save defaults to cache in seconds."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump({"focus": focus_secs, "break": break_secs}, f)


def parse_duration(value, default_secs):
    """Parse duration in XhYmZs format. Bare numbers = minutes. Returns seconds."""
    if not value:
        return default_secs
    import re
    value = value.strip().lower()
    # Try XhYmZs format
    match = re.match(r'^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?$', value)
    if match and any(match.groups()):
        hours = int(match.group(1) or 0)
        mins = int(match.group(2) or 0)
        secs = float(match.group(3) or 0)
        return hours * 3600 + mins * 60 + secs
    # Bare number = minutes
    try:
        return float(value) * 60
    except ValueError:
        return default_secs


def format_duration(secs):
    """Format duration as XhYmZs."""
    parts = []
    if secs >= 3600:
        h = int(secs // 3600)
        parts.append(f"{h}h")
        secs %= 3600
    if secs >= 60:
        m = int(secs // 60)
        parts.append(f"{m}m")
        secs %= 60
    if secs > 0 or not parts:
        if secs == int(secs):
            parts.append(f"{int(secs)}s")
        else:
            parts.append(f"{secs:.2g}s")
    return "".join(parts)


def get_input(prompt, default_secs):
    """Get duration input with default value."""
    hint = format_duration(default_secs)
    value = input(f"{prompt} [{hint}]: ").strip()
    return parse_duration(value, default_secs)


def get_key():
    """Get a single keypress without blocking."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        import select
        if select.select([sys.stdin], [], [], 0.1)[0]:
            return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return None


def play_sound():
    """Play completion sound."""
    if SOUND_FILE.exists():
        try:
            subprocess.Popen(
                ["paplay", str(SOUND_FILE)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except FileNotFoundError:
            pass
    print("\a", end="", flush=True)


def format_time(seconds):
    """Format seconds as XhYmZs for timer display."""
    seconds = max(0, seconds)
    h = int(seconds // 3600)
    seconds %= 3600
    m = int(seconds // 60)
    s = seconds % 60
    if h > 0:
        return f"{h}h{m:02d}m{int(s):02d}s"
    if m > 0:
        return f"{m}m{int(s):02d}s"
    return f"{s:.1f}s"


def run_timer(duration_secs, label, autostart=False):
    """Run timer with start/stop and quit controls."""
    remaining = duration_secs
    running = autostart
    last_tick = time.time()

    label_color = CYAN if label == "FOCUS" else GREEN

    print(f"\n{BOLD}{label_color}{label}{RESET}")
    print(f"{DIM}[SPACE] start/stop  [s] skip  [q] quit{RESET}")
    status = "Running" if running else "Paused "
    print(f"{status} {MAGENTA}{format_time(remaining)}{RESET}", end="", flush=True)

    while remaining > 0:
        key = get_key()

        if key == " ":
            running = not running
            last_tick = time.time()
        elif key == "s":
            print(f"\n\n{DIM}Skipping...{RESET}")
            return "skip"
        elif key == "q":
            print(f"\n\n{DIM}Quitting...{RESET}")
            return None

        if running:
            now = time.time()
            elapsed = now - last_tick
            remaining -= elapsed
            last_tick = now

        status = "Running" if running else "Paused "
        print(f"\r{status} {MAGENTA}{format_time(remaining)}{RESET}  ", end="", flush=True)

    print(f"\r{BOLD}{YELLOW}{label} complete!{RESET} {DIM}(press key to continue){RESET}  ")
    last_sound = 0
    while True:
        if time.time() - last_sound >= 2:
            play_sound()
            last_sound = time.time()
        key = get_key()
        if key:
            if key == "q":
                print(f"\n{DIM}Quitting...{RESET}")
                return None
            return True


def main():
    defaults = load_defaults()

    print(f"{BOLD}=== Pomodoro Timer ==={RESET}")
    print(f"{DIM}(format: 25, 1h30m, 25m, 90s){RESET}\n")

    focus = get_input("Focus time", defaults["focus"])
    break_time = get_input("Break time", defaults["break"])

    save_defaults(focus, break_time)

    print(f"\n{CYAN}Focus: {format_duration(focus)}{RESET} | {GREEN}Break: {format_duration(break_time)}{RESET}")

    try:
        autostart = False
        while True:
            if run_timer(focus, "FOCUS", autostart) is None:
                break
            if run_timer(break_time, "BREAK", autostart=True) is None:
                break
            autostart = True

    except KeyboardInterrupt:
        print("\n\nInterrupted.")


if __name__ == "__main__":
    main()
