from pathlib import Path
import re

from tenon_codex_light.daemon import DaemonConfig, NativeAppColorWriter, NativeAppDaemonRunner, StateDaemon
from tenon_codex_light.protocol import HsvColor, TENON_DESK_SERVICE_UUID, TENON_LEDSTRIP_CHARACTERISTIC_UUID
from tenon_codex_light.state_file import write_state_file
from tenon_codex_light.states import STATE_COLORS, CodexLightState, effect_preset_for_state


class FakeWriter:
    def __init__(self) -> None:
        self.colors: list[HsvColor] = []

    def write_color(self, color: HsvColor) -> None:
        self.colors.append(color)


def test_daemon_writes_state_color_once(tmp_path: Path) -> None:
    state_file = tmp_path / "state"
    log_file = tmp_path / "daemon.log"
    writer = FakeWriter()
    daemon = StateDaemon(
        DaemonConfig(state_file=state_file, log_file=log_file, debounce_seconds=0),
        writer,
    )

    write_state_file(CodexLightState.WORKING, state_file)

    assert daemon.run_once()
    assert not daemon.run_once()
    assert writer.colors == [HsvColor(hue=197, saturation=70, value=100)]
    assert "state: working payload: 03 00 C5 46 64" in log_file.read_text(encoding="utf-8")


def test_daemon_ignores_invalid_state(tmp_path: Path) -> None:
    state_file = tmp_path / "state"
    log_file = tmp_path / "daemon.log"
    state_file.write_text("not_allowed", encoding="utf-8")
    writer = FakeWriter()
    daemon = StateDaemon(DaemonConfig(state_file=state_file, log_file=log_file), writer)

    assert not daemon.run_once()
    assert writer.colors == []
    assert "invalid_state:" in log_file.read_text(encoding="utf-8")


def test_native_writer_validates_allowlists() -> None:
    writer = NativeAppColorWriter(
        app_path=Path("build/Tenon Codex Light Scan.app"),
        address="device",
        service_uuid=TENON_DESK_SERVICE_UUID,
        characteristic_uuid=TENON_LEDSTRIP_CHARACTERISTIC_UUID,
    )

    # Validation happens before any subprocess call. Use invalid color to stop early.
    try:
        writer.write_color(HsvColor(hue=360, saturation=80, value=20))
    except ValueError as exc:
        assert "hue" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_native_daemon_runner_builds_response_mode_command(tmp_path: Path) -> None:
    runner = NativeAppDaemonRunner(
        app_path=Path("build/Tenon Codex Light Scan.app"),
        address="00000000-0000-0000-0000-000000000000",
        service_uuid=TENON_DESK_SERVICE_UUID,
        characteristic_uuid=TENON_LEDSTRIP_CHARACTERISTIC_UUID,
        state_file=tmp_path / "state",
        poll_interval=0.1,
    )

    command = runner.command(once=True)

    assert command[:3] == ["/usr/bin/open", "-n", "-W"]
    assert command[3].endswith("build/Tenon Codex Light Scan.app")
    assert command[4] == "--args"
    assert "--daemon" in command
    assert "--once" in command
    assert "--write-mode" not in command
    assert "--disable-effects" not in command
    assert "--address" in command
    assert "00000000-0000-0000-0000-000000000000" in command


def test_native_daemon_runner_can_disable_effects(tmp_path: Path) -> None:
    runner = NativeAppDaemonRunner(
        app_path=Path("build/Tenon Codex Light Scan.app"),
        address="00000000-0000-0000-0000-000000000000",
        service_uuid=TENON_DESK_SERVICE_UUID,
        characteristic_uuid=TENON_LEDSTRIP_CHARACTERISTIC_UUID,
        state_file=tmp_path / "state",
        disable_effects=True,
    )

    command = runner.command(once=True)

    assert "--disable-effects" in command


def test_state_to_effect_preset_mapping() -> None:
    assert effect_preset_for_state(CodexLightState.IDLE).name == "Cloudy"
    assert effect_preset_for_state(CodexLightState.IDLE).effect == "none"
    assert effect_preset_for_state(CodexLightState.WORKING).name == "Aurora"
    assert effect_preset_for_state(CodexLightState.WORKING).effect == "breathe"
    assert effect_preset_for_state(CodexLightState.NEEDS_INPUT).name == "Lavender Sunset"
    assert effect_preset_for_state(CodexLightState.NEEDS_INPUT).effect == "moving"
    assert effect_preset_for_state(CodexLightState.NEEDS_INPUT).interval_ms == 5000
    assert effect_preset_for_state(CodexLightState.ERROR).name == "Yellow Alert"
    assert effect_preset_for_state(CodexLightState.ERROR).effect == "blink"
    assert effect_preset_for_state(CodexLightState.ERROR).interval_ms == 300
    assert effect_preset_for_state(CodexLightState.OFF) is None


def test_restore_is_idle_cleanup_alias_not_real_restore() -> None:
    restore = effect_preset_for_state(CodexLightState.RESTORE)
    idle = effect_preset_for_state(CodexLightState.IDLE)

    assert restore == idle
    assert STATE_COLORS[CodexLightState.RESTORE] == STATE_COLORS[CodexLightState.IDLE]

    docs = Path("docs/tenon-light-presets.md").read_text(encoding="utf-8")
    assert "internal cleanup/fallback command" in docs
    assert "does not restore previous desk settings" in docs


def test_native_state_mapping_matches_python_mapping() -> None:
    source = Path("macos/TenonCodexLightScan/main.m").read_text(encoding="utf-8")
    matches = re.findall(r'\[state isEqualToString:@"([^"]+)"\]\) \{\n\s+h = (\d+); s = (\d+); v = (\d+);', source)
    native_colors = {state: HsvColor(int(h), int(s), int(v)) for state, h, s, v in matches}

    assert native_colors == {state.value: color for state, color in STATE_COLORS.items()}
