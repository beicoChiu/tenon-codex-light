from pathlib import Path

from tenon_signal_light.hook_cli import main as hook_cli_main
from tenon_signal_light.selector import (
    read_active_source,
    source_allowed,
    write_active_source,
)
from tenon_signal_light.state_file import read_state_file
from tenon_signal_light.states import SignalLightState


def test_source_allowed_rules() -> None:
    # No --source tag: always allowed (backward compatible).
    assert source_allowed(None, None) is True
    assert source_allowed(None, "codex") is True
    # Selector unset: any tagged source allowed (permissive default).
    assert source_allowed("claude", None) is True
    # Selector matches: allowed. Mismatch or "off": blocked.
    assert source_allowed("claude", "claude") is True
    assert source_allowed("claude", "codex") is False
    assert source_allowed("codex", "off") is False


def test_read_write_roundtrip_and_unset(tmp_path: Path) -> None:
    selector = tmp_path / "active_source"
    assert read_active_source(selector) is None  # missing -> unset

    assert write_active_source("Claude", selector) == "claude"  # normalized
    assert read_active_source(selector) == "claude"


def _run_hook(state: str, state_file: Path, selector: Path, source: str, monkeypatch) -> int:
    monkeypatch.setattr(
        "sys.argv",
        [
            "tenon-hook-state",
            state,
            "--state-file",
            str(state_file),
            "--selector-file",
            str(selector),
            "--source",
            source,
        ],
    )
    return hook_cli_main()


def test_hook_gate_blocks_non_active_source(tmp_path: Path, monkeypatch) -> None:
    state_file = tmp_path / "state"
    selector = tmp_path / "active_source"
    write_active_source("claude", selector)

    # Codex hook while Claude owns the light: no-op, exits 0, no write.
    assert _run_hook("working", state_file, selector, "codex", monkeypatch) == 0
    assert not state_file.exists()

    # Claude hook while Claude owns the light: writes.
    assert _run_hook("working", state_file, selector, "claude", monkeypatch) == 0
    assert read_state_file(state_file) == SignalLightState.WORKING


def test_hook_gate_off_blocks_all_sources(tmp_path: Path, monkeypatch) -> None:
    state_file = tmp_path / "state"
    selector = tmp_path / "active_source"
    write_active_source("off", selector)

    assert _run_hook("working", state_file, selector, "claude", monkeypatch) == 0
    assert _run_hook("working", state_file, selector, "codex", monkeypatch) == 0
    assert not state_file.exists()


def test_hook_unset_selector_allows_any_source(tmp_path: Path, monkeypatch) -> None:
    state_file = tmp_path / "state"
    selector = tmp_path / "active_source"  # never created

    assert _run_hook("idle", state_file, selector, "claude", monkeypatch) == 0
    assert read_state_file(state_file) == SignalLightState.IDLE


def test_hook_without_source_flag_always_writes(tmp_path: Path, monkeypatch) -> None:
    state_file = tmp_path / "state"
    selector = tmp_path / "active_source"
    write_active_source("codex", selector)  # someone else owns it

    # No --source given: legacy behavior, write regardless of selector.
    monkeypatch.setattr(
        "sys.argv",
        ["tenon-hook-state", "working", "--state-file", str(state_file),
         "--selector-file", str(selector)],
    )
    assert hook_cli_main() == 0
    assert read_state_file(state_file) == SignalLightState.WORKING
