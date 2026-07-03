# Tenon BLE Protocol Notes

These notes document the public-safe BLE compatibility surface used by Tenon
Codex Light. They are intentionally minimal and should be validated against a
real device during local setup.

## BLE Light Characteristic

Tenon exposes a BLE service with a dedicated light read/write characteristic.
Discovery should use service and characteristic UUIDs instead of fixed handles.

Discovery output should include the relevant service UUID, characteristic UUID,
and characteristic properties. Review scan output locally before write testing.
Do not commit raw BLE scan logs or captures.

## Compatible BLE UUIDs

A native macOS scan app should discover a nearby Tenon advertising a compatible service:

```text
service: 4D543739-3333-2E4F-4E4F-4F2E4445534B
```

The compatible light characteristic is:

```text
4D543739-3333-2E4F-4E4F-4F2E434C4544
```

It supports `write`, not `write-without-response`, so the first color write should use response mode.

## Minimal HSV Write Probe

Dry-run:

```bash
.venv/bin/python scripts/tenon-light color --h 210 --s 80 --v 50 --dry-run --verbose
```

Expected payload:

```text
payload: 03 00 D2 50 32
```

Real write probe requires explicit device and allowlisted UUIDs:

```bash
.venv/bin/python scripts/tenon-light color \
  --address <TENON_DEVICE_ID> \
  --service-uuid 4D543739-3333-2E4F-4E4F-4F2E4445534B \
  --characteristic-uuid 4D543739-3333-2E4F-4E4F-4F2E434C4544 \
  --h 210 --s 80 --v 20 \
  --write-mode response \
  --verbose
```

Native macOS write probe, used when raw Python cannot access Bluetooth:

```bash
scripts/build-macos-scan-app
open -W "build/Tenon Signal Light Scan.app" --args \
  --write-color \
  --address <TENON_DEVICE_ID> \
  --service-uuid 4D543739-3333-2E4F-4E4F-4F2E4445534B \
  --characteristic-uuid 4D543739-3333-2E4F-4E4F-4F2E434C4544 \
  --h 210 --s 80 --v 20 \
  --write-mode response
```

Example successful response-mode write output:

```text
payload: 03 00 D2 50 14
connected: true
write: ok
```

## State Daemon Path

The local state file accepts only these enum values:

```text
working
needs_input
idle
error
off
restore
```

The native macOS daemon maps each enum to an allowlisted light behavior and
writes only to the allowlisted Tenon LED characteristic using response mode. It
is the current real-hardware path; Python daemon code is reference/test/dev-only.

`restore` means a safe fallback HSV color/off state. It does not restore previous desk lighting settings.

Default state file:

```text
~/Library/Application Support/TenonSignalLight/state
```

Daemon command:

```bash
open -n -W "build/Tenon Signal Light Scan.app" --args \
  --daemon \
  --address <TENON_DEVICE_ID>
```

One-shot test:

```bash
.venv/bin/python scripts/tenon-light state idle
open -n -W "build/Tenon Signal Light Scan.app" --args \
  --daemon \
  --address <TENON_DEVICE_ID> \
  --once
```

Codex hooks are implemented as a thin state-file writer. Hooks do not call BLE directly.

Safety constraints:

- command tags are allowlisted before use
- effect writes are limited to reviewed existing light-effect controls
- OTA/update characteristic UUIDs are rejected
- non-LED characteristics are rejected
- hue is restricted to `0..359`
- saturation and value are restricted to `0..100`

## Light Command Compatibility

Known light command IDs used by this project:

```text
0x03 set color HSV
0x05 set compatible effect payload
0x10 unsupported/persistent lighting command, denied by this project
```

## Minimal HSV Command

The safest first write path is HSV:

```text
byte 0: 0x03
byte 1: hue high byte
byte 2: hue low byte
byte 3: saturation, 0-100
byte 4: value, 0-100
```

Example:

```text
H=210, S=80, V=50
payload: 03 00 D2 50 32
```

## Compatible Effect Payload Structure

Effect control uses a compact payload body after command tag `0x05`. The
project only uses the reviewed light-effect shape:

```json
{
  "color": {
    "type": 0,
    "h": [210, 0],
    "s": [80, 0],
    "v": [50, 0]
  },
  "action": {
    "type": 0,
    "interval": 1000
  }
}
```

Allowlisted action types:

```text
0 none
1 blink
2 breathe
3 moving
4 dancing
5 rolling
```

Effect mode should be tested only after the minimal HSV write works.

Current project status:

- Effect control supports dry-run payload construction, one-shot experimental response-mode probes, and the native daemon's reviewed two-color preset mapping.
- On macOS, the native app is the required real-hardware path for effect probes because raw Python can be blocked by Bluetooth TCC.
- Only command `0x05` is allowlisted for effect payload construction.
- Supported dry-run action types are `none`, `blink`, `breathe`, `moving`, `rolling`, and `dancing`.
- Unsupported action types and OTA/persistent config commands are not supported.
- Dry-run commands do not connect to BLE.
- Real effect probes require explicit address/service/characteristic selection, `--write-mode response`, and `--i-understand-this-is-experimental`.
- Daemon effect integration does not change Codex hook behavior, and HSV response-mode remains the fallback path.

## Write Mode

The verified production path uses response-mode writes:

```text
response
```

Diagnostic tooling may report whether the selected characteristic advertises
`write`, `write-without-response`, or both, but public real-hardware writes use
response mode.

## Explicit Exclusions

This project must not send firmware update, OTA, metadata-transfer, or upgrade
trigger commands. Those operations are outside the project scope and can create
device risk if misused.
