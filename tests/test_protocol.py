from tenon_signal_light.protocol import (
    EffectControl,
    LEDSTRIP_SET_CONTROL_FORMAT_CJSON,
    TENON_LEDSTRIP_CHARACTERISTIC_UUID,
    HsvColor,
    action_type_for_effect,
    build_effect_json_payload,
    build_hsv_payload,
    is_allowed_light_characteristic,
    is_allowed_tenon_service,
    validate_effect_command_id,
)


def test_build_hsv_payload() -> None:
    assert build_hsv_payload(HsvColor(hue=210, saturation=80, value=50)) == bytes(
        [0x03, 0x00, 0xD2, 0x50, 0x32]
    )


def test_hsv_payload_validates_ranges() -> None:
    try:
        build_hsv_payload(HsvColor(hue=360, saturation=80, value=50))
    except ValueError as exc:
        assert "hue" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_hsv_payload_rejects_saturation_out_of_range() -> None:
    try:
        build_hsv_payload(HsvColor(hue=210, saturation=101, value=50))
    except ValueError as exc:
        assert "saturation" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_hsv_payload_rejects_value_out_of_range() -> None:
    try:
        build_hsv_payload(HsvColor(hue=210, saturation=80, value=101))
    except ValueError as exc:
        assert "value" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_led_characteristic_allowlist() -> None:
    assert is_allowed_light_characteristic(TENON_LEDSTRIP_CHARACTERISTIC_UUID)
    assert not is_allowed_light_characteristic("4D543739-3333-2E4F-4E4F-4F2E55475244")


def test_tenon_service_allowlist() -> None:
    assert is_allowed_tenon_service("4D543739-3333-2E4F-4E4F-4F2E4445534B")
    assert not is_allowed_tenon_service("0000180F-0000-1000-8000-00805F9B34FB")


def test_build_effect_json_payload_for_breathe() -> None:
    payload = build_effect_json_payload(
        EffectControl(effect="breathe", color=HsvColor(hue=210, saturation=80, value=50), interval_ms=1000)
    )

    assert payload[0] == LEDSTRIP_SET_CONTROL_FORMAT_CJSON
    assert payload[1:].decode("utf-8") == (
        '{"action":{"interval":1000,"type":2},'
        '"color":{"h":[210,0],"s":[80,0],"type":0,"v":[50,0]}}'
    )


def test_effect_action_type_validation() -> None:
    assert action_type_for_effect("none") == 0
    assert action_type_for_effect("blink") == 1
    assert action_type_for_effect("breathe") == 2
    assert action_type_for_effect("moving") == 3
    assert action_type_for_effect("dancing") == 4
    assert action_type_for_effect("rolling") == 5


def test_effect_rejects_unknown_action() -> None:
    try:
        build_effect_json_payload(EffectControl(effect="preview"))
    except ValueError as exc:
        assert "unsupported effect" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_effect_rejects_denied_command_ids() -> None:
    for command_id in (0x00, 0x01, 0x02, 0x10):
        try:
            validate_effect_command_id(command_id)
        except ValueError as exc:
            assert "denied" in str(exc)
        else:
            raise AssertionError("expected ValueError")


def test_effect_rejects_unsupported_command_id() -> None:
    try:
        validate_effect_command_id(0x04)
    except ValueError as exc:
        assert "only existing Tenon effect control" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_effect_rejects_persistent_lighting_command() -> None:
    try:
        build_effect_json_payload(EffectControl(effect="blink", command_id=0x10))
    except ValueError as exc:
        assert "persistent lighting commands are denied" in str(exc)
    else:
        raise AssertionError("expected ValueError")
