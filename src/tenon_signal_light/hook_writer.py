"""Safe hook state writer for supported AI coding agents."""

from __future__ import annotations

from pathlib import Path

from .state_file import default_state_file, write_state_file
from .states import SignalLightState, parse_state


def write_hook_state(value: str, state_file: Path | None = None) -> SignalLightState:
    state = parse_state(value)
    write_state_file(state, state_file or default_state_file())
    return state
