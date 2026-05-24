"""Codex state to Tenon color mapping."""

from __future__ import annotations

from enum import StrEnum

from .protocol import EffectPreset, HsvColor


class CodexLightState(StrEnum):
    WORKING = "working"
    NEEDS_INPUT = "needs_input"
    IDLE = "idle"
    ERROR = "error"
    OFF = "off"
    RESTORE = "restore"


STATE_COLORS: dict[CodexLightState, HsvColor] = {
    CodexLightState.WORKING: HsvColor(hue=197, saturation=70, value=100),
    CodexLightState.NEEDS_INPUT: HsvColor(hue=288, saturation=75, value=100),
    CodexLightState.IDLE: HsvColor(hue=210, saturation=11, value=90),
    CodexLightState.ERROR: HsvColor(hue=45, saturation=100, value=100),
    CodexLightState.OFF: HsvColor(hue=0, saturation=0, value=0),
    CodexLightState.RESTORE: HsvColor(hue=210, saturation=11, value=90),
}


STATE_EFFECT_PRESETS: dict[CodexLightState, EffectPreset] = {
    CodexLightState.IDLE: EffectPreset(
        name="Cloudy",
        effect="none",
        color=HsvColor(hue=210, saturation=11, value=90),
        secondary_color=HsvColor(hue=210, saturation=15, value=70),
    ),
    CodexLightState.WORKING: EffectPreset(
        name="Aurora",
        effect="breathe",
        color=HsvColor(hue=197, saturation=70, value=100),
        secondary_color=HsvColor(hue=270, saturation=80, value=100),
    ),
    CodexLightState.NEEDS_INPUT: EffectPreset(
        name="Lavender Sunset",
        effect="moving",
        color=HsvColor(hue=288, saturation=75, value=100),
        secondary_color=HsvColor(hue=17, saturation=85, value=100),
        interval_ms=5000,
    ),
    CodexLightState.ERROR: EffectPreset(
        name="Yellow Alert",
        effect="blink",
        color=HsvColor(hue=45, saturation=100, value=100),
        secondary_color=HsvColor(hue=45, saturation=100, value=100),
        interval_ms=300,
    ),
    CodexLightState.RESTORE: EffectPreset(
        name="Cloudy",
        effect="none",
        color=HsvColor(hue=210, saturation=11, value=90),
        secondary_color=HsvColor(hue=210, saturation=15, value=70),
    ),
}


def parse_state(value: str) -> CodexLightState:
    normalized = value.strip()
    try:
        return CodexLightState(normalized)
    except ValueError as exc:
        allowed = ", ".join(state.value for state in CodexLightState)
        raise ValueError(f"invalid state '{normalized}', expected one of: {allowed}") from exc


def color_for_state(state: CodexLightState) -> HsvColor:
    return STATE_COLORS[state]


def effect_preset_for_state(state: CodexLightState) -> EffectPreset | None:
    if state == CodexLightState.OFF:
        return None
    return STATE_EFFECT_PRESETS[state]
