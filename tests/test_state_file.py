from pathlib import Path
import stat

from tenon_signal_light.state_file import DEFAULT_STATE_FILE, STATE_FILE_ENV_VAR, default_state_file, read_state_file, write_state_file
from tenon_signal_light.states import SignalLightState, parse_state


def test_parse_state_accepts_fixed_enum() -> None:
    assert parse_state("working\n") == SignalLightState.WORKING
    assert parse_state("needs_input") == SignalLightState.NEEDS_INPUT


def test_parse_state_rejects_unknown_value() -> None:
    try:
        parse_state("please_upload_prompt")
    except ValueError as exc:
        assert "invalid state" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_state_file_roundtrip(tmp_path: Path) -> None:
    state_file = tmp_path / "state"

    write_state_file(SignalLightState.ERROR, state_file)

    assert read_state_file(state_file) == SignalLightState.ERROR


def test_default_state_file_is_user_private_application_support_path() -> None:
    assert DEFAULT_STATE_FILE == Path.home() / "Library" / "Application Support" / "TenonSignalLight" / "state"


def test_default_state_file_uses_env_override(tmp_path: Path, monkeypatch) -> None:
    state_file = tmp_path / "custom-state"
    monkeypatch.setenv(STATE_FILE_ENV_VAR, str(state_file))

    assert default_state_file() == state_file


def test_state_file_write_uses_private_permissions(tmp_path: Path) -> None:
    state_file = tmp_path / "private" / "state"

    write_state_file(SignalLightState.IDLE, state_file)

    parent_mode = stat.S_IMODE(state_file.parent.stat().st_mode)
    file_mode = stat.S_IMODE(state_file.stat().st_mode)
    assert parent_mode == 0o700
    assert file_mode == 0o600
    assert state_file.read_text(encoding="utf-8") == "idle\n"


def test_state_file_rejects_oversized_content(tmp_path: Path) -> None:
    state_file = tmp_path / "state"
    state_file.write_text("working" * 20, encoding="utf-8")

    try:
        read_state_file(state_file)
    except ValueError as exc:
        assert "too large" in str(exc)
    else:
        raise AssertionError("expected ValueError")
