import subprocess

from tenon_signal_light.ble_write import ColorWriteRequest, EffectWriteRequest, WriteMode
from tenon_signal_light.protocol import (
    EffectControl,
    TENON_DESK_SERVICE_UUID,
    TENON_LEDSTRIP_CHARACTERISTIC_UUID,
    HsvColor,
)


def test_color_write_request_requires_address() -> None:
    request = ColorWriteRequest(
        address="",
        service_uuid=TENON_DESK_SERVICE_UUID,
        characteristic_uuid=TENON_LEDSTRIP_CHARACTERISTIC_UUID,
        color=HsvColor(210, 80, 20),
    )

    try:
        request.validate()
    except ValueError as exc:
        assert "address" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_color_write_request_rejects_non_led_characteristic() -> None:
    request = ColorWriteRequest(
        address="device",
        service_uuid=TENON_DESK_SERVICE_UUID,
        characteristic_uuid="4D543739-3333-2E4F-4E4F-4F2E55475244",
        color=HsvColor(210, 80, 20),
    )

    try:
        request.validate()
    except ValueError as exc:
        assert "allowlisted" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_color_write_request_rejects_non_tenon_service() -> None:
    request = ColorWriteRequest(
        address="device",
        service_uuid="0000180F-0000-1000-8000-00805F9B34FB",
        characteristic_uuid=TENON_LEDSTRIP_CHARACTERISTIC_UUID,
        color=HsvColor(210, 80, 20),
    )

    try:
        request.validate()
    except ValueError as exc:
        assert "service_uuid" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_color_write_request_accepts_response_mode() -> None:
    request = ColorWriteRequest(
        address="device",
        service_uuid=TENON_DESK_SERVICE_UUID,
        characteristic_uuid=TENON_LEDSTRIP_CHARACTERISTIC_UUID,
        color=HsvColor(210, 80, 20),
        write_mode=WriteMode.RESPONSE,
    )

    request.validate()


def test_effect_write_requires_experimental_ack() -> None:
    request = EffectWriteRequest(
        address="device",
        service_uuid=TENON_DESK_SERVICE_UUID,
        characteristic_uuid=TENON_LEDSTRIP_CHARACTERISTIC_UUID,
        control=EffectControl(effect="breathe"),
        write_mode=WriteMode.RESPONSE,
        experimental_ack=False,
    )

    try:
        request.validate()
    except ValueError as exc:
        assert "experimental" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_effect_write_rejects_no_response_mode() -> None:
    request = EffectWriteRequest(
        address="device",
        service_uuid=TENON_DESK_SERVICE_UUID,
        characteristic_uuid=TENON_LEDSTRIP_CHARACTERISTIC_UUID,
        control=EffectControl(effect="blink"),
        write_mode=WriteMode.NO_RESPONSE,
        experimental_ack=True,
    )

    try:
        request.validate()
    except ValueError as exc:
        assert "response" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_effect_write_accepts_explicit_response_probe() -> None:
    request = EffectWriteRequest(
        address="device",
        service_uuid=TENON_DESK_SERVICE_UUID,
        characteristic_uuid=TENON_LEDSTRIP_CHARACTERISTIC_UUID,
        control=EffectControl(effect="blink"),
        write_mode=WriteMode.RESPONSE,
        experimental_ack=True,
    )

    request.validate()


def test_effect_cli_rejects_real_write_without_experimental_ack() -> None:
    result = subprocess.run(
        [
            "scripts/tenon-light",
            "effect",
            "breathe",
            "--address",
            "device",
            "--service-uuid",
            TENON_DESK_SERVICE_UUID,
            "--characteristic-uuid",
            TENON_LEDSTRIP_CHARACTERISTIC_UUID,
            "--write-mode",
            "response",
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=1,
    )

    assert result.returncode == 2
    assert "experimental" in result.stderr
