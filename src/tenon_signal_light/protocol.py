"""BLE payload helpers for Tenon ambient light control."""

from __future__ import annotations

from dataclasses import dataclass
import json

LEDSTRIP_SET_COLOR_HSV = 0x03
LEDSTRIP_SET_CONTROL_FORMAT_CJSON = 0x05
TENON_DESK_SERVICE_UUID = "4D543739-3333-2E4F-4E4F-4F2E4445534B"
TENON_LEDSTRIP_CHARACTERISTIC_UUID = "4D543739-3333-2E4F-4E4F-4F2E434C4544"
DENIED_COMMAND_IDS = frozenset({0x00, 0x01, 0x02, 0x10})
ALLOWED_EFFECT_COMMAND_IDS = frozenset({LEDSTRIP_SET_CONTROL_FORMAT_CJSON})
EFFECT_ACTION_TYPES = {
    "none": 0,
    "blink": 1,
    "breathe": 2,
    "moving": 3,
    "dancing": 4,
    "rolling": 5,
}


@dataclass(frozen=True)
class HsvColor:
    """Tenon HSV color using the supported BLE command ranges."""

    hue: int
    saturation: int
    value: int

    def validate(self) -> None:
        if not 0 <= self.hue <= 359:
            raise ValueError("hue must be between 0 and 359")
        if not 0 <= self.saturation <= 100:
            raise ValueError("saturation must be between 0 and 100")
        if not 0 <= self.value <= 100:
            raise ValueError("value must be between 0 and 100")


def build_hsv_payload(color: HsvColor) -> bytes:
    """Build the 5-byte HSV BLE payload."""

    color.validate()
    return bytes(
        [
            LEDSTRIP_SET_COLOR_HSV,
            (color.hue >> 8) & 0xFF,
            color.hue & 0xFF,
            color.saturation,
            color.value,
        ]
    )


@dataclass(frozen=True)
class EffectControl:
    """Existing Tenon effect control for dry-run payload inspection."""

    effect: str
    color: HsvColor = HsvColor(hue=210, saturation=80, value=50)
    secondary_color: HsvColor = HsvColor(hue=0, saturation=0, value=0)
    interval_ms: int = 1000
    command_id: int = LEDSTRIP_SET_CONTROL_FORMAT_CJSON

    def validate(self) -> None:
        validate_effect_command_id(self.command_id)
        if self.effect not in EFFECT_ACTION_TYPES:
            allowed = ", ".join(EFFECT_ACTION_TYPES)
            raise ValueError(f"unsupported effect '{self.effect}', expected one of: {allowed}")
        if not 0 <= self.interval_ms <= 60000:
            raise ValueError("interval_ms must be between 0 and 60000")
        self.color.validate()
        self.secondary_color.validate()


@dataclass(frozen=True)
class EffectPreset:
    """Named two-color Tenon preset for workflow state mapping."""

    name: str
    effect: str
    color: HsvColor
    secondary_color: HsvColor
    interval_ms: int = 1000

    def validate(self) -> None:
        if not self.name:
            raise ValueError("preset name is required")
        action_type_for_effect(self.effect)
        if not 0 <= self.interval_ms <= 60000:
            raise ValueError("interval_ms must be between 0 and 60000")
        self.color.validate()
        self.secondary_color.validate()


def validate_effect_command_id(command_id: int) -> None:
    if command_id in DENIED_COMMAND_IDS:
        raise ValueError("unsupported command: OTA, firmware, and persistent lighting commands are denied")
    if command_id not in ALLOWED_EFFECT_COMMAND_IDS:
        raise ValueError("unsupported command: only existing Tenon effect control is allowed")


def action_type_for_effect(effect: str) -> int:
    try:
        return EFFECT_ACTION_TYPES[effect]
    except KeyError as exc:
        allowed = ", ".join(EFFECT_ACTION_TYPES)
        raise ValueError(f"unsupported effect '{effect}', expected one of: {allowed}") from exc


def build_effect_json_payload(control: EffectControl) -> bytes:
    """Build dry-run-only existing Tenon effect control payload."""

    control.validate()
    body = {
        "color": {
            "type": 0,
            "h": [control.color.hue, control.secondary_color.hue],
            "s": [control.color.saturation, control.secondary_color.saturation],
            "v": [control.color.value, control.secondary_color.value],
        },
        "action": {
            "type": action_type_for_effect(control.effect),
            "interval": control.interval_ms,
        },
    }
    json_bytes = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return bytes([control.command_id]) + json_bytes


def build_effect_preset_payload(preset: EffectPreset) -> bytes:
    """Build an existing Tenon effect payload for a two-color preset."""

    preset.validate()
    body = {
        "color": {
            "type": 1,
            "h": [preset.color.hue, preset.secondary_color.hue],
            "s": [preset.color.saturation, preset.secondary_color.saturation],
            "v": [preset.color.value, preset.secondary_color.value],
        },
        "action": {
            "type": action_type_for_effect(preset.effect),
            "interval": preset.interval_ms,
        },
    }
    json_bytes = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return bytes([LEDSTRIP_SET_CONTROL_FORMAT_CJSON]) + json_bytes


def normalize_uuid(value: str) -> str:
    return value.lower()


def is_allowed_light_characteristic(uuid: str) -> bool:
    return normalize_uuid(uuid) == normalize_uuid(TENON_LEDSTRIP_CHARACTERISTIC_UUID)


def is_allowed_tenon_service(uuid: str) -> bool:
    return normalize_uuid(uuid) == normalize_uuid(TENON_DESK_SERVICE_UUID)
