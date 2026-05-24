# Prerequisites

## Hardware

- Beflo Tenon or Tenon mini.
- Mac with Bluetooth enabled.
- Tenon close enough for stable BLE.

## Software

- macOS.
- Python 3.11 or newer.
- Python dependencies listed in `requirements.txt`.

Install dependencies:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e .
```

For development and tests:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install -e .
```

## macOS Permissions

The terminal app or Codex app may need Bluetooth permission:

```text
System Settings -> Privacy & Security -> Bluetooth
```

If scanning returns no devices while Bluetooth is on, check this first.

On newer macOS versions, raw Homebrew Python may crash before the permission prompt if its `Python.app` bundle does not include `NSBluetoothAlwaysUsageDescription`. This is a macOS privacy requirement, not a Tenon error. Use the native macOS app path below for real hardware access.

Build and run the native scan app:

```bash
scripts/build-macos-scan-app
open "build/Tenon Codex Light Scan.app" --args --duration 8 --verbose
```

For service discovery:

```bash
open "build/Tenon Codex Light Scan.app" --args --duration 8 --services --verbose
```

Read the log:

```bash
tail -n 120 ~/Library/Logs/TenonCodexLight/scan.log
```

## BLE Discovery Requirements

The first real hardware task is local service and characteristic discovery:

```bash
.venv/bin/python scripts/tenon-light scan --services --verbose
```

The scan output should show enough local detail to choose the intended Tenon:

- device name
- device identifier
- advertised service UUIDs
- discovered service UUIDs
- characteristic UUIDs
- characteristic properties

Do not start write probes until the LED strip characteristic is confirmed.
Do not publish scan logs with private device identifiers.

## Write Probe Requirements

Start with dry-run:

```bash
.venv/bin/python scripts/tenon-light color --h 210 --s 80 --v 50 --dry-run --verbose
```

Then test the response write mode against the explicit device and LED characteristic:

```bash
.venv/bin/python scripts/tenon-light color \
  --address <TENON_DEVICE_ID> \
  --service-uuid 4D543739-3333-2E4F-4E4F-4F2E4445534B \
  --characteristic-uuid 4D543739-3333-2E4F-4E4F-4F2E434C4544 \
  --h 210 --s 80 --v 20 \
  --write-mode response \
  --verbose
```

Use low brightness first.

## Tenon Preparation

- Keep Tenon powered on.
- Keep the desk in a normal operating mode.
- Do not start OTA update flows while testing this project.
- In the official Beflo/Tenon mobile app, confirm the desk is disconnected. If
  it is connected, tap disconnect before testing BLE writes.

## Troubleshooting

If BLE scan finds nothing:

- confirm Bluetooth is enabled
- confirm the terminal or Codex app has Bluetooth permission
- move Tenon closer to the Mac
- in the official Beflo/Tenon mobile app, confirm the desk is disconnected; if
  it is connected, tap disconnect
- retry after power-cycling Tenon

If macOS blocks the locally built app the first time:

- open System Settings -> Privacy & Security
- allow the app to run
- start the scan or daemon again

If scan finds Tenon but write fails:

- retry with `--write-mode response`
- verify the characteristic has a compatible write property
- lower brightness and use a known-safe HSV payload

If the light stays in a status color:

- write `idle`, `off`, or `restore`; these are safe fallback states, not previous-setting recovery
- use the official app or Tenon UI to restore normal lighting
