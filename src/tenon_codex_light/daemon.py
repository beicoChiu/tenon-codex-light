"""Local state-file daemon for Tenon Codex Light."""

from __future__ import annotations

import subprocess
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .ble_write import ColorWriteRequest, WriteMode
from .protocol import (
    TENON_DESK_SERVICE_UUID,
    TENON_LEDSTRIP_CHARACTERISTIC_UUID,
    HsvColor,
    build_hsv_payload,
)
from .state_file import default_state_file, read_state_file
from .states import CodexLightState, color_for_state


DEFAULT_LOG_FILE = Path("/tmp/tenon_codex_light_daemon.log")


class ColorWriter(Protocol):
    def write_color(self, color: HsvColor) -> None:
        ...


@dataclass(frozen=True)
class NativeAppColorWriter:
    app_path: Path
    address: str
    service_uuid: str = TENON_DESK_SERVICE_UUID
    characteristic_uuid: str = TENON_LEDSTRIP_CHARACTERISTIC_UUID

    def write_color(self, color: HsvColor) -> None:
        request = ColorWriteRequest(
            address=self.address,
            service_uuid=self.service_uuid,
            characteristic_uuid=self.characteristic_uuid,
            color=color,
            write_mode=WriteMode.RESPONSE,
        )
        request.validate()
        payload = build_hsv_payload(color)

        command = [
            "/usr/bin/open",
            "-W",
            str(self.app_path),
            "--args",
            "--write-color",
            "--address",
            self.address,
            "--service-uuid",
            self.service_uuid,
            "--characteristic-uuid",
            self.characteristic_uuid,
            "--h",
            str(color.hue),
            "--s",
            str(color.saturation),
            "--v",
            str(color.value),
            "--write-mode",
            "response",
        ]
        result = subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise RuntimeError("native writer failed")


@dataclass(frozen=True)
class NativeAppDaemonRunner:
    app_path: Path
    address: str
    state_file: Path = field(default_factory=default_state_file)
    service_uuid: str = TENON_DESK_SERVICE_UUID
    characteristic_uuid: str = TENON_LEDSTRIP_CHARACTERISTIC_UUID
    poll_interval: float = 0.25
    disable_effects: bool = False

    def command(self, *, once: bool = False) -> list[str]:
        request = ColorWriteRequest(
            address=self.address,
            service_uuid=self.service_uuid,
            characteristic_uuid=self.characteristic_uuid,
            color=HsvColor(hue=0, saturation=0, value=0),
            write_mode=WriteMode.RESPONSE,
        )
        request.validate()

        command = [
            "/usr/bin/open",
            "-n",
            "-W",
            str(self.app_path.resolve()),
            "--args",
            "--daemon",
            "--address",
            self.address,
            "--service-uuid",
            self.service_uuid,
            "--characteristic-uuid",
            self.characteristic_uuid,
            "--state-file",
            str(self.state_file),
            "--poll-interval",
            str(self.poll_interval),
        ]
        if once:
            command.append("--once")
        if self.disable_effects:
            command.append("--disable-effects")
        return command

    def run(self, *, once: bool = False) -> int:
        command = self.command(once=once)
        os.execv(command[0], ["open", *command[1:]])
        return 1


@dataclass
class DaemonConfig:
    state_file: Path = field(default_factory=default_state_file)
    log_file: Path = DEFAULT_LOG_FILE
    poll_interval: float = 0.25
    debounce_seconds: float = 0.2


class StateDaemon:
    def __init__(self, config: DaemonConfig, writer: ColorWriter) -> None:
        self.config = config
        self.writer = writer
        self.last_state: CodexLightState | None = None
        self.last_write_at = 0.0

    def run_once(self) -> bool:
        try:
            state = read_state_file(self.config.state_file)
        except ValueError as exc:
            self._log(f"invalid_state: {exc}")
            return False

        if state is None:
            return False

        if state == self.last_state:
            return False

        now = time.monotonic()
        if now - self.last_write_at < self.config.debounce_seconds:
            return False

        color = color_for_state(state)
        payload = build_hsv_payload(color)
        try:
            self.writer.write_color(color)
        except Exception as exc:
            self._log(f"write_error: {type(exc).__name__}")
            return False

        self.last_state = state
        self.last_write_at = now
        self._log(f"state: {state.value} payload: {format_payload(payload)}")
        return True

    def run_forever(self) -> None:
        self._log("daemon: started")
        try:
            while True:
                self.run_once()
                time.sleep(self.config.poll_interval)
        except KeyboardInterrupt:
            self._log("daemon: stopped")

    def _log(self, line: str) -> None:
        self.config.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.config.log_file.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def format_payload(payload: bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in payload)
