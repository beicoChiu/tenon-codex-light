"""Minimal BLE write probe for Tenon ambient light state."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum

from .macos_tcc import MacOSBluetoothUsageDescriptionError, require_bluetooth_usage_description
from .protocol import (
    EffectControl,
    HsvColor,
    build_effect_json_payload,
    build_hsv_payload,
    is_allowed_light_characteristic,
    is_allowed_tenon_service,
)


class WriteMode(StrEnum):
    RESPONSE = "response"
    NO_RESPONSE = "no-response"


class BleWriteError(RuntimeError):
    """Raised when the BLE write probe fails."""


@dataclass(frozen=True)
class ColorWriteRequest:
    address: str
    service_uuid: str
    characteristic_uuid: str
    color: HsvColor
    write_mode: WriteMode = WriteMode.RESPONSE

    def validate(self) -> None:
        if not self.address:
            raise ValueError("address is required for real writes")
        if not self.service_uuid:
            raise ValueError("service_uuid is required for real writes")
        if not self.characteristic_uuid:
            raise ValueError("characteristic_uuid is required for real writes")
        if not is_allowed_tenon_service(self.service_uuid):
            raise ValueError("service_uuid is not allowlisted for Tenon light HSV writes")
        if not is_allowed_light_characteristic(self.characteristic_uuid):
            raise ValueError("characteristic_uuid is not allowlisted for light HSV writes")
        self.color.validate()


@dataclass(frozen=True)
class EffectWriteRequest:
    address: str
    service_uuid: str
    characteristic_uuid: str
    control: EffectControl
    write_mode: WriteMode = WriteMode.RESPONSE
    experimental_ack: bool = False

    def validate(self) -> None:
        if not self.experimental_ack:
            raise ValueError("real effect writes require --i-understand-this-is-experimental")
        if not self.address:
            raise ValueError("address is required for real effect writes")
        if not self.service_uuid:
            raise ValueError("service_uuid is required for real effect writes")
        if not self.characteristic_uuid:
            raise ValueError("characteristic_uuid is required for real effect writes")
        if self.write_mode != WriteMode.RESPONSE:
            raise ValueError("effect writes require --write-mode response")
        if not is_allowed_tenon_service(self.service_uuid):
            raise ValueError("service_uuid is not allowlisted for Tenon effect writes")
        if not is_allowed_light_characteristic(self.characteristic_uuid):
            raise ValueError("characteristic_uuid is not allowlisted for Tenon effect writes")
        self.control.validate()


async def write_hsv_color(request: ColorWriteRequest) -> bytes:
    request.validate()

    try:
        require_bluetooth_usage_description()
    except MacOSBluetoothUsageDescriptionError as exc:
        raise BleWriteError(str(exc)) from exc

    try:
        from bleak import BleakClient
        from bleak.exc import BleakError
    except ImportError as exc:
        raise BleWriteError("The optional dependency 'bleak' is required for BLE writes.") from exc

    payload = build_hsv_payload(request.color)
    response = request.write_mode == WriteMode.RESPONSE

    try:
        async with BleakClient(request.address) as client:
            await client.write_gatt_char(request.characteristic_uuid, payload, response=response)
    except BleakError as exc:
        raise BleWriteError(f"BLE write failed: {exc}") from exc

    return payload


def run_write_hsv_color(request: ColorWriteRequest) -> bytes:
    return asyncio.run(write_hsv_color(request))


async def write_effect_control(request: EffectWriteRequest) -> bytes:
    request.validate()

    try:
        require_bluetooth_usage_description()
    except MacOSBluetoothUsageDescriptionError as exc:
        raise BleWriteError(str(exc)) from exc

    try:
        from bleak import BleakClient
        from bleak.exc import BleakError
    except ImportError as exc:
        raise BleWriteError("The optional dependency 'bleak' is required for BLE writes.") from exc

    payload = build_effect_json_payload(request.control)

    try:
        async with BleakClient(request.address) as client:
            await client.write_gatt_char(request.characteristic_uuid, payload, response=True)
    except BleakError as exc:
        raise BleWriteError(f"BLE write failed: {exc}") from exc

    return payload


def run_write_effect_control(request: EffectWriteRequest) -> bytes:
    return asyncio.run(write_effect_control(request))
