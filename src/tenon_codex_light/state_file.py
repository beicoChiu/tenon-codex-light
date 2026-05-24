"""Validated local state file helpers."""

from __future__ import annotations

import os
from pathlib import Path

from .states import CodexLightState, parse_state


STATE_FILE_ENV_VAR = "TENON_CODEX_LIGHT_STATE_FILE"
DEFAULT_STATE_FILE = Path.home() / "Library" / "Application Support" / "TenonCodexLight" / "state"
MAX_STATE_FILE_BYTES = 64


def default_state_file() -> Path:
    override = os.environ.get(STATE_FILE_ENV_VAR)
    if override:
        return Path(override).expanduser()
    return DEFAULT_STATE_FILE


def read_state_file(path: Path = DEFAULT_STATE_FILE) -> CodexLightState | None:
    try:
        data = Path(path).expanduser().read_bytes()
    except FileNotFoundError:
        return None

    if len(data) > MAX_STATE_FILE_BYTES:
        raise ValueError("state file is too large")

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("state file must be UTF-8") from exc

    return parse_state(text)


def write_state_file(state: CodexLightState, path: Path = DEFAULT_STATE_FILE) -> None:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        target.parent.chmod(0o700)
    except OSError:
        pass

    temp_path = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(state.value + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, target)
        try:
            target.chmod(0o600)
        except OSError:
            pass
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
