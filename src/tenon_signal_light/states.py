"""Workflow state to Tenon color mapping."""

from __future__ import annotations

from enum import StrEnum

from .protocol import EffectPreset, HsvColor


class SignalLightState(StrEnum):
    WORKING = "working"
    NEEDS_INPUT = "needs_input"
    IDLE = "idle"
    ERROR = "error"
    OFF = "off"
    RESTORE = "restore"


STATE_COLORS: dict[SignalLightState, HsvColor] = {
    SignalLightState.WORKING: HsvColor(hue=197, saturation=70, value=100),
    SignalLightState.NEEDS_INPUT: HsvColor(hue=288, saturation=75, value=100),
    SignalLightState.IDLE: HsvColor(hue=210, saturation=11, value=90),
    SignalLightState.ERROR: HsvColor(hue=45, saturation=100, value=100),
    SignalLightState.OFF: HsvColor(hue=0, saturation=0, value=0),
    SignalLightState.RESTORE: HsvColor(hue=210, saturation=11, value=90),
}


STATE_EFFECT_PRESETS: dict[SignalLightState, EffectPreset] = {
    SignalLightState.IDLE: EffectPreset(
        name="Cloudy",
        effect="none",
        color=HsvColor(hue=210, saturation=11, value=90),
        secondary_color=HsvColor(hue=210, saturation=15, value=70),
    ),
    SignalLightState.WORKING: EffectPreset(
        name="Aurora",
        effect="breathe",
        color=HsvColor(hue=197, saturation=70, value=100),
        secondary_color=HsvColor(hue=270, saturation=80, value=100),
    ),
    SignalLightState.NEEDS_INPUT: EffectPreset(
        name="Lavender Sunset",
        effect="moving",
        color=HsvColor(hue=288, saturation=75, value=100),
        secondary_color=HsvColor(hue=17, saturation=85, value=100),
        interval_ms=5000,
    ),
    SignalLightState.ERROR: EffectPreset(
        name="Yellow Alert",
        effect="blink",
        color=HsvColor(hue=45, saturation=100, value=100),
        secondary_color=HsvColor(hue=45, saturation=100, value=100),
        interval_ms=300,
    ),
    SignalLightState.RESTORE: EffectPreset(
        name="Cloudy",
        effect="none",
        color=HsvColor(hue=210, saturation=11, value=90),
        secondary_color=HsvColor(hue=210, saturation=15, value=70),
    ),
}


def parse_state(value: str) -> SignalLightState:
    normalized = value.strip()
    try:
        return SignalLightState(normalized)
    except ValueError as exc:
        allowed = ", ".join(state.value for state in SignalLightState)
        raise ValueError(f"invalid state '{normalized}', expected one of: {allowed}") from exc


def color_for_state(state: SignalLightState) -> HsvColor:
    return STATE_COLORS[state]


def effect_preset_for_state(state: SignalLightState) -> EffectPreset | None:
    if state == SignalLightState.OFF:
        return None
    return STATE_EFFECT_PRESETS[state]
