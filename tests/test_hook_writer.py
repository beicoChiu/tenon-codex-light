from pathlib import Path
import subprocess

from tenon_codex_light.hook_cli import main as hook_cli_main
from tenon_codex_light.hook_writer import write_hook_state
from tenon_codex_light.state_file import STATE_FILE_ENV_VAR, read_state_file
from tenon_codex_light.states import CodexLightState


def test_hook_writer_writes_allowed_enum(tmp_path: Path) -> None:
    state_file = tmp_path / "state"

    state = write_hook_state("needs_input", state_file)

    assert state == CodexLightState.NEEDS_INPUT
    assert read_state_file(state_file) == CodexLightState.NEEDS_INPUT


def test_hook_writer_uses_default_state_file_override(tmp_path: Path, monkeypatch) -> None:
    state_file = tmp_path / "default-state"
    monkeypatch.setenv(STATE_FILE_ENV_VAR, str(state_file))

    state = write_hook_state("idle")

    assert state == CodexLightState.IDLE
    assert read_state_file(state_file) == CodexLightState.IDLE


def test_hook_writer_rejects_invalid_state(tmp_path: Path) -> None:
    state_file = tmp_path / "state"

    try:
        write_hook_state("$(cat ~/.ssh/id_rsa)", state_file)
    except ValueError as exc:
        assert "invalid state" in str(exc)
    else:
        raise AssertionError("expected ValueError")

    assert not state_file.exists()


def test_hook_cli_entrypoint_writes_allowed_enum(tmp_path: Path, monkeypatch) -> None:
    state_file = tmp_path / "state"
    monkeypatch.setattr(
        "sys.argv",
        ["tenon-hook-state", "working", "--state-file", str(state_file)],
    )

    assert hook_cli_main() == 0
    assert read_state_file(state_file) == CodexLightState.WORKING


def test_hook_script_returns_quickly_and_writes_only_state(tmp_path: Path) -> None:
    state_file = tmp_path / "state"
    result = subprocess.run(
        [
            "scripts/tenon-hook-state",
            "working",
            "--state-file",
            str(state_file),
        ],
        check=False,
        input="prompt text must be ignored",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=1,
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
    assert state_file.read_text(encoding="utf-8") == "working\n"


def test_hook_script_rejects_invalid_state(tmp_path: Path) -> None:
    state_file = tmp_path / "state"
    result = subprocess.run(
        [
            "scripts/tenon-hook-state",
            "upload_prompt",
            "--state-file",
            str(state_file),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=1,
    )

    assert result.returncode == 2
    assert "invalid state" in result.stderr
    assert not state_file.exists()
