"""Console entry point for the safe Codex hook state writer."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .hook_writer import write_hook_state
from .state_file import default_state_file


def main() -> int:
    parser = argparse.ArgumentParser(prog="tenon-hook-state")
    parser.add_argument("state", help="working, needs_input, idle, error, off, or restore")
    parser.add_argument("--state-file", type=Path, default=default_state_file())
    args = parser.parse_args()

    try:
        write_hook_state(args.state, args.state_file)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except OSError:
        print("state write failed", file=sys.stderr)
        return 1
    return 0
