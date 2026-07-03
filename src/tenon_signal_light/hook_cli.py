"""Console entry point for the safe hook state writer."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .hook_writer import write_hook_state
from .selector import default_selector_file, read_active_source, source_allowed
from .state_file import default_state_file


def main() -> int:
    parser = argparse.ArgumentParser(prog="tenon-hook-state")
    parser.add_argument("state", help="working, needs_input, idle, error, off, or restore")
    parser.add_argument("--state-file", type=Path, default=default_state_file())
    parser.add_argument(
        "--source",
        default=None,
        help="agent tag (e.g. claude, codex) for source-based routing; "
        "skipped when the active-source selector points at another agent",
    )
    parser.add_argument("--selector-file", type=Path, default=None)
    args = parser.parse_args()

    # Source gate: if this write is tagged and the selector names a different
    # owner (or is "off"), do nothing and exit cleanly so the hook never fails.
    if args.source is not None:
        try:
            active = read_active_source(args.selector_file or default_selector_file())
        except (OSError, ValueError):
            active = None  # corrupt/unreadable selector -> stay permissive
        if not source_allowed(args.source, active):
            return 0

    try:
        write_hook_state(args.state, args.state_file)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except OSError:
        print("state write failed", file=sys.stderr)
        return 1
    return 0
