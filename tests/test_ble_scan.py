from tenon_signal_light.ble_scan import (
    BleScanError,
    CharacteristicInfo,
    DeviceInfo,
    ScanResult,
    ServiceInfo,
    format_scan_result,
    looks_like_tenon,
    normalize_uuid,
    redact_identifier,
)
from tenon_signal_light.macos_tcc import BLUETOOTH_USAGE_KEY, has_bluetooth_usage_description


def test_normalize_uuid() -> None:
    assert normalize_uuid("4D543739-3333-2E4F-4E4F-4F2E4445534B") == "4d54373933332e4f4e4f4f2e4445534b"


def test_looks_like_tenon_by_name() -> None:
    assert looks_like_tenon("Beflo Tenon", ())
    assert looks_like_tenon("ONOO", ())


def test_looks_like_tenon_by_service_uuid() -> None:
    assert looks_like_tenon(None, ("4d543739-3333-2e4f-4e4f-4f2e4445534b",))


def test_format_scan_result_includes_services() -> None:
    result = ScanResult(
        duration=1.0,
        services_requested=True,
        devices=(
            DeviceInfo(
                name="Tenon",
                address="ABC",
                rssi=-55,
                advertised_service_uuids=("4d543739-3333-2e4f-4e4f-4f2e4445534b",),
                services=(
                    ServiceInfo(
                        uuid="service",
                        characteristics=(
                            CharacteristicInfo(uuid="char", properties=("write", "notify")),
                        ),
                    ),
                ),
                is_likely_tenon=True,
            ),
        ),
    )

    output = format_scan_result(result, verbose=True)

    assert "devices_found: 1" in output
    assert "likely_tenon" in output
    assert "advertised_services" in output
    assert "char (write, notify)" in output


def test_format_scan_result_redacts_identifiers_by_default() -> None:
    result = ScanResult(
        duration=1.0,
        services_requested=False,
        devices=(DeviceInfo(name="Tenon", address="12345678-1234-1234-1234-123456789ABC"),),
    )

    output = format_scan_result(result)

    assert "12345678...9ABC" in output
    assert "12345678-1234-1234-1234-123456789ABC" not in output


def test_format_scan_result_can_show_full_identifiers() -> None:
    result = ScanResult(
        duration=1.0,
        services_requested=False,
        devices=(DeviceInfo(name="Tenon", address="12345678-1234-1234-1234-123456789ABC"),),
    )

    output = format_scan_result(result, show_full_identifiers=True)

    assert "12345678-1234-1234-1234-123456789ABC" in output


def test_redact_identifier_shortens_long_values() -> None:
    assert redact_identifier("12345678-1234-1234-1234-123456789ABC") == "12345678...9ABC"


def test_scan_error_is_runtime_error() -> None:
    assert issubclass(BleScanError, RuntimeError)


def test_has_bluetooth_usage_description(tmp_path) -> None:
    info_plist = tmp_path / "Info.plist"
    info_plist.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>{BLUETOOTH_USAGE_KEY}</key>
  <string>Scan for Tenon over Bluetooth.</string>
</dict>
</plist>
""",
        encoding="utf-8",
    )

    assert has_bluetooth_usage_description(info_plist)


def test_missing_bluetooth_usage_description(tmp_path) -> None:
    info_plist = tmp_path / "Info.plist"
    info_plist.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>Python</string>
</dict>
</plist>
""",
        encoding="utf-8",
    )

    assert not has_bluetooth_usage_description(info_plist)
