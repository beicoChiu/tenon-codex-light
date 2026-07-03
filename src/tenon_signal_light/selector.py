"""Active-source selector.

Routes which AI coding agent (for example ``claude`` or ``codex``) is allowed
to drive the light at any moment, so two agents running at the same time do not
fight over the same state file.

The selector is a tiny user-private file holding one token:

- ``claude`` / ``codex`` (or any agent name) -> only that source may write.
- ``off`` -> no source may write; the light is left to you / the official app.
- missing or empty -> unset; every source is allowed (zero-config default).

Gating happens before the state write, in the hook path (``tenon-hook-state``).
The daemon is untouched: it still watches a single state file.
"""

from __future__ import annotations

import os
from pathlib import Path

from .state_file import DEFAULT_STATE_FILE

SELECTOR_ENV_VAR = "TENON_SIGNAL_LIGHT_SOURCE_FILE"
DEFAULT_SELECTOR_FILE = DEFAULT_STATE_FILE.with_name("active_source")
MAX_SELECTOR_BYTES = 64

# Special token meaning "no agent may drive the light".
SOURCE_OFF = "off"


def default_selector_file() -> Path:
    override = os.environ.get(SELECTOR_ENV_VAR)
    if override:
        return Path(override).expanduser()
    return DEFAULT_SELECTOR_FILE


def read_active_source(path: Path | None = None) -> str | None:
    """Return the active source token, or ``None`` when unset (allow all)."""
    target = Path(path or default_selector_file()).expanduser()
    try:
        data = target.read_bytes()
    except FileNotFoundError:
        return None

    if len(data) > MAX_SELECTOR_BYTES:
        raise ValueError("selector file is too large")

    try:
        text = data.decode("utf-8").strip().lower()
    except UnicodeDecodeError as exc:
        raise ValueError("selector file must be UTF-8") from exc

    return text or None


def write_active_source(value: str, path: Path | None = None) -> str:
    """Atomically set the active source. Returns the normalized token."""
    token = value.strip().lower()
    if not token:
        raise ValueError("source must not be empty")

    target = Path(path or default_selector_file()).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        target.parent.chmod(0o700)
    except OSError:
        pass

    temp_path = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(token + "\n")
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

    return token


def source_allowed(source: str | None, active: str | None) -> bool:
    """Decide whether a write tagged ``source`` may proceed under ``active``.

    - ``source`` is ``None`` (no ``--source`` given): always allowed, so
      pre-routing configs keep working unchanged.
    - ``active`` is ``None`` (selector unset): always allowed (permissive).
    - otherwise the tags must match; ``active == "off"`` blocks every source.
    """
    if source is None:
        return True
    if active is None:
        return True
    return active == source.strip().lower()
