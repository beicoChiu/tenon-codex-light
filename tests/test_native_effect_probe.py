from pathlib import Path

from tenon_codex_light.protocol import EffectControl, HsvColor, build_effect_json_payload, build_effect_preset_payload
from tenon_codex_light.states import CodexLightState, effect_preset_for_state


NATIVE_SOURCE = Path("macos/TenonCodexLightScan/main.m")


def test_native_effect_probe_flags_are_present() -> None:
    source = NATIVE_SOURCE.read_text(encoding="utf-8")

    assert "--write-effect" in source
    assert "--i-understand-this-is-experimental" in source
    assert "--write-mode response" in source


def test_native_effect_probe_uses_allowlisted_command_id() -> None:
    source = NATIVE_SOURCE.read_text(encoding="utf-8")

    assert "{0x05}" in source
    assert "isAllowedLedCharacteristic" in source
    assert "isAllowedTenonService" in source


def test_native_effect_json_matches_python_payload_shape() -> None:
    payload = build_effect_json_payload(
        EffectControl(effect="breathe", color=HsvColor(hue=210, saturation=80, value=50), interval_ms=1000)
    )

    assert payload[0] == 0x05
    assert payload[1:].decode("utf-8") == (
        '{"action":{"interval":1000,"type":2},'
        '"color":{"h":[210,0],"s":[80,0],"type":0,"v":[50,0]}}'
    )


def test_native_daemon_effect_integration_guards_are_present() -> None:
    source = NATIVE_SOURCE.read_text(encoding="utf-8")

    assert "--disable-effects" in source
    assert "pendingFallbackPayload" in source
    assert "fallback: effect failed, using hsv" in source
    assert "daemon: cleanup idle mode: hsv" in source


def test_finalized_mapping_values_are_available_to_native_daemon() -> None:
    presets = {
        CodexLightState.IDLE: ("Cloudy", "none", HsvColor(210, 11, 90), HsvColor(210, 15, 70)),
        CodexLightState.WORKING: ("Aurora", "breathe", HsvColor(197, 70, 100), HsvColor(270, 80, 100)),
        CodexLightState.NEEDS_INPUT: (
            "Lavender Sunset",
            "moving",
            HsvColor(288, 75, 100),
            HsvColor(17, 85, 100),
        ),
        CodexLightState.ERROR: ("Yellow Alert", "blink", HsvColor(45, 100, 100), HsvColor(45, 100, 100)),
    }

    for state, (name, effect, primary, secondary) in presets.items():
        preset = effect_preset_for_state(state)
        assert preset is not None
        assert preset.name == name
        assert preset.effect == effect
        assert preset.color == primary
        assert preset.secondary_color == secondary

    assert effect_preset_for_state(CodexLightState.RESTORE) == effect_preset_for_state(CodexLightState.IDLE)
    assert effect_preset_for_state(CodexLightState.OFF) is None
    assert effect_preset_for_state(CodexLightState.NEEDS_INPUT).interval_ms == 5000
    assert effect_preset_for_state(CodexLightState.ERROR).interval_ms == 300


def test_two_color_preset_payload_shape() -> None:
    preset = effect_preset_for_state(CodexLightState.WORKING)
    assert preset is not None

    payload = build_effect_preset_payload(preset)

    assert payload[0] == 0x05
    assert payload[1:].decode("utf-8") == (
        '{"action":{"interval":1000,"type":2},'
        '"color":{"h":[197,270],"s":[70,80],"type":1,"v":[100,100]}}'
    )
