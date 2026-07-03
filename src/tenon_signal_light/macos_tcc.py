"""macOS privacy preflight checks."""

from __future__ import annotations

import plistlib
import sys
from pathlib import Path


BLUETOOTH_USAGE_KEY = "NSBluetoothAlwaysUsageDescription"


class MacOSBluetoothUsageDescriptionError(RuntimeError):
    """Raised when the active Python app bundle cannot request Bluetooth access."""


def python_app_info_plist(base_prefix: str | None = None) -> Path | None:
    prefix = Path(base_prefix or sys.base_prefix)
    candidate = prefix / "Resources" / "Python.app" / "Contents" / "Info.plist"
    if candidate.exists():
        return candidate
    return None


def has_bluetooth_usage_description(info_plist: Path) -> bool:
    try:
        with info_plist.open("rb") as handle:
            plist = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException):
        return False
    value = plist.get(BLUETOOTH_USAGE_KEY)
    return isinstance(value, str) and bool(value.strip())


def require_bluetooth_usage_description() -> None:
    if sys.platform != "darwin":
        return

    info_plist = python_app_info_plist()
    if info_plist is None:
        return

    if has_bluetooth_usage_description(info_plist):
        return

    raise MacOSBluetoothUsageDescriptionError(
        "macOS will crash this Python before BLE scan because its app bundle is missing "
        f"{BLUETOOTH_USAGE_KEY}. Use a packaged Tenon Signal Light app/launcher with a Bluetooth "
        "usage description, or a Python distribution whose Python.app declares Bluetooth usage."
    )
