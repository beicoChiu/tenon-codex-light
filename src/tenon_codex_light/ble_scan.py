"""BLE scanning helpers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from .macos_tcc import MacOSBluetoothUsageDescriptionError, require_bluetooth_usage_description


TENON_UUID_HINTS = {
    "4d54373933332e4f4e4f4f2e4445534b",  # MT7933.ONOO.DESK
    "4d54373933332e4f4e4f4f2e434c4544",  # MT7933.ONOO.CLED
    "4d54373933332e4f4e4f4f2e434c5257",  # MT7933.ONOO.WRLC
}


@dataclass(frozen=True)
class CharacteristicInfo:
    uuid: str
    properties: tuple[str, ...]
    description: str | None = None


@dataclass(frozen=True)
class ServiceInfo:
    uuid: str
    characteristics: tuple[CharacteristicInfo, ...] = ()


@dataclass(frozen=True)
class DeviceInfo:
    name: str | None
    address: str
    rssi: int | None = None
    advertised_service_uuids: tuple[str, ...] = ()
    manufacturer_data_keys: tuple[int, ...] = ()
    service_data_uuids: tuple[str, ...] = ()
    services: tuple[ServiceInfo, ...] = ()
    errors: tuple[str, ...] = ()
    is_likely_tenon: bool = False


@dataclass(frozen=True)
class ScanResult:
    devices: tuple[DeviceInfo, ...]
    duration: float
    services_requested: bool


class BleakMissingError(RuntimeError):
    """Raised when the optional BLE dependency is not installed."""


class BleScanError(RuntimeError):
    """Raised when BLE scanning cannot start or complete."""


def normalize_uuid(value: str) -> str:
    return value.lower().replace("-", "")


def looks_like_tenon(
    name: str | None,
    advertised_service_uuids: tuple[str, ...],
    services: tuple[ServiceInfo, ...] = (),
) -> bool:
    normalized_name = (name or "").lower()
    if "tenon" in normalized_name or "beflo" in normalized_name or normalized_name == "onoo":
        return True

    uuid_values = list(advertised_service_uuids)
    uuid_values.extend(service.uuid for service in services)
    for uuid in uuid_values:
        if normalize_uuid(uuid) in TENON_UUID_HINTS:
            return True
    return False


async def scan_devices(duration: float = 5.0, include_services: bool = False) -> ScanResult:
    try:
        require_bluetooth_usage_description()
    except MacOSBluetoothUsageDescriptionError as exc:
        raise BleScanError(str(exc)) from exc

    try:
        from bleak import BleakClient, BleakScanner
        from bleak.exc import BleakError
    except ImportError as exc:
        raise BleakMissingError("The optional dependency 'bleak' is required for BLE scanning.") from exc

    try:
        discovered = await BleakScanner.discover(timeout=duration, return_adv=True)
    except BleakError as exc:
        raise BleScanError(f"BLE scan failed: {exc}") from exc

    devices: list[DeviceInfo] = []

    for device, advertisement in discovered.values():
        advertised_service_uuids = tuple(str(uuid) for uuid in (advertisement.service_uuids or ()))
        services: tuple[ServiceInfo, ...] = ()
        errors: list[str] = []

        if include_services:
            try:
                async with BleakClient(device) as client:
                    services = tuple(_service_info(service) for service in client.services)
            except Exception as exc:  # pragma: no cover - hardware/OS dependent
                errors.append(f"service discovery failed: {exc}")

        name = device.name or advertisement.local_name
        device_info = DeviceInfo(
            name=name,
            address=device.address,
            rssi=getattr(advertisement, "rssi", None),
            advertised_service_uuids=advertised_service_uuids,
            manufacturer_data_keys=tuple(sorted((advertisement.manufacturer_data or {}).keys())),
            service_data_uuids=tuple(str(uuid) for uuid in (advertisement.service_data or {}).keys()),
            services=services,
            errors=tuple(errors),
            is_likely_tenon=looks_like_tenon(name, advertised_service_uuids, services),
        )
        devices.append(device_info)

    devices.sort(key=lambda item: (not item.is_likely_tenon, item.name or "", item.address))
    return ScanResult(devices=tuple(devices), duration=duration, services_requested=include_services)


def run_scan(duration: float = 5.0, include_services: bool = False) -> ScanResult:
    return asyncio.run(scan_devices(duration=duration, include_services=include_services))

def redact_identifier(value: str) -> str:
    if len(value) <= 12:
        return value
    return f"{value[:8]}...{value[-4:]}"


def _service_info(service: Any) -> ServiceInfo:
    characteristics = []
    for characteristic in service.characteristics:
        characteristics.append(
            CharacteristicInfo(
                uuid=str(characteristic.uuid),
                properties=tuple(characteristic.properties),
                description=getattr(characteristic, "description", None),
            )
        )
    return ServiceInfo(uuid=str(service.uuid), characteristics=tuple(characteristics))


def format_scan_result(result: ScanResult, verbose: bool = False, show_full_identifiers: bool = False) -> str:
    lines: list[str] = []
    lines.append(f"scan_duration: {result.duration:.1f}s")
    lines.append(f"devices_found: {len(result.devices)}")

    for index, device in enumerate(result.devices, start=1):
        marker = " likely_tenon" if device.is_likely_tenon else ""
        rssi = f" rssi={device.rssi}" if device.rssi is not None else ""
        name = device.name or "(unknown)"
        address = device.address if show_full_identifiers else redact_identifier(device.address)
        lines.append(f"{index}. {name} [{address}]{rssi}{marker}")

        if verbose or device.is_likely_tenon:
            if device.advertised_service_uuids:
                lines.append("   advertised_services:")
                for uuid in device.advertised_service_uuids:
                    lines.append(f"   - {uuid}")
            if device.manufacturer_data_keys:
                keys = ", ".join(f"0x{key:04X}" for key in device.manufacturer_data_keys)
                lines.append(f"   manufacturer_data_keys: {keys}")
            if device.service_data_uuids:
                lines.append("   service_data:")
                for uuid in device.service_data_uuids:
                    lines.append(f"   - {uuid}")

        if result.services_requested:
            if device.services:
                lines.append("   services:")
                for service in device.services:
                    lines.append(f"   - {service.uuid}")
                    for characteristic in service.characteristics:
                        props = ", ".join(characteristic.properties) or "none"
                        lines.append(f"     - {characteristic.uuid} ({props})")
            if device.errors:
                lines.append("   errors:")
                for error in device.errors:
                    lines.append(f"   - {error}")

    return "\n".join(lines)
