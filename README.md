# Tenon Codex Light

A programmable ambient workspace signal layer for AI-assisted workflows.

Tenon Codex Light turns [Beflo Tenon and Tenon mini](https://gobeflo.com)
devices into physical status indicators for local automation systems, coding
agents, focus workflows, and ergonomic routines.

It is local-first: no cloud dependency, no prompt uploading, no analytics, and
no firmware modification. Codex is the first supported workflow, but the larger
idea is a programmable workspace where software state can become calm physical
feedback.

This is an independent side project created by Beico Chiu. It is not an
official Beflo product, firmware release, or supported integration, and it is
not affiliated with or supported by OpenAI.

## What It Does

Tenon Codex Light runs a small native macOS daemon that listens to a local state
file. Codex lifecycle hooks write simple state names such as `working` or
`needs_input`, and the daemon maps those states to allowlisted Tenon light
presets over Bluetooth.

```text
AI agent / local workflow
  -> local hook
  -> user-private state file
  -> native macOS daemon
  -> Bluetooth
  -> ambient Tenon workspace signal
```

This makes long-running local agent work visible without opening another
dashboard, browser tab, or notification surface.

## Workspace Signals

| Workflow state | Tenon signal |
| --- | --- |
| Idle | Cloudy, steady |
| Working | Aurora, breathing |
| Needs input | Lavender Sunset, moving |
| Error | Yellow fast blink |
| Off | Light off |

`restore` is an internal cleanup fallback. It means "return to a safe idle-like
light," not "restore my previous desk lighting settings."

## Design Principles

- Ambient workspace feedback, not a notification spam layer.
- Local-first automation, not cloud IoT.
- Physical AI visibility, not another screen.
- Existing Tenon light behavior, not firmware modification.
- Calm workstation aesthetics, not novelty lighting.

## Learn More

- [Architecture](docs/architecture.md)
- [Workflow Ideas](docs/workflows.md)
- [Setup Requirements](docs/prerequisites.md)
- [Codex Hooks Integration](docs/codex-hooks-integration.md)
- [Tenon Light Presets](docs/tenon-light-presets.md)
- [Security Model](docs/security-model.md)

## Requirements

- macOS
- [Beflo Tenon or Tenon mini](https://gobeflo.com)
- Codex with command hooks enabled
- Python 3.11 or newer for setup scripts
- Bleak, installed automatically from `requirements.txt`

Tenon may allow only one active Bluetooth connection at a time. Before running
Tenon Codex Light, check the official Beflo/Tenon mobile app and make sure it is
not connected to the desk. If it is connected, tap disconnect in the app so
Tenon releases the Bluetooth connection.

## Quick Start

Clone the repository and install dependencies. This installs Bleak, the Python
Bluetooth package used by the setup and helper scripts:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e .
```

Build the macOS Bluetooth app:

```bash
scripts/build-macos-scan-app
```

Scan for your Tenon:

```bash
open "build/Tenon Codex Light Scan.app" --args --duration 8 --verbose
```

Look in the scan output for your Tenon device identifier. Use that value as
`<TENON_DEVICE_ID>` below.

Start the Tenon daemon:

```bash
open -n -W "build/Tenon Codex Light Scan.app" --args \
  --daemon \
  --address <TENON_DEVICE_ID>
```

In another terminal, test a few states:

```bash
tenon-hook-state working
tenon-hook-state needs_input
tenon-hook-state idle
```

If the light changes correctly, connect Codex hooks using the example in
[docs/codex-hooks-integration.md](docs/codex-hooks-integration.md).

Keep the daemon running while you want the light to follow Codex. This project
does not install a macOS LaunchAgent yet, so it will not automatically restart
after logout, reboot, or a forced quit.

## Codex Hook Setup

The hook command is intentionally small and safe. It only writes one of these
fixed states to a local state file:

```text
working
needs_input
idle
error
off
restore
```

It does not read prompts, tool inputs, file paths, secrets, or hook payloads. It
does not call Bluetooth directly.

Recommended event mapping:

| Codex hook event | State |
| --- | --- |
| `SessionStart` | `idle` |
| `UserPromptSubmit` | `working` |
| `PreToolUse` | `working` |
| `PermissionRequest` | `needs_input` |
| `PostToolUse` | `working` |
| `Stop` | `idle` |

After installation, hooks can call `tenon-hook-state` directly. See
[docs/codex-hooks-integration.md](docs/codex-hooks-integration.md) for a
copy-pasteable `hooks.json` example.

## Troubleshooting

If scanning finds no Tenon:

- Make sure Tenon is powered on and close to your Mac.
- Turn Bluetooth on.
- In the official Beflo/Tenon mobile app, confirm the desk is disconnected. If
  it is connected, tap disconnect.
- Check macOS Bluetooth permission for the app you are running.
- Power-cycle Tenon and scan again.

If the daemon cannot connect:

- Confirm you copied the intended Tenon device identifier.
- Make sure no other daemon instance is already running.
- If the official Beflo/Tenon mobile app is connected, tap disconnect in the
  app so Tenon releases the Bluetooth connection.
- Restart the daemon.

If macOS blocks the app the first time:

- Open System Settings -> Privacy & Security.
- Allow the locally built app to run.
- Start the scan or daemon again.

If the light is left in a status color:

```bash
tenon-hook-state idle
```

or:

```bash
tenon-hook-state off
```

You can also use the official Tenon/Beflo app to return to your normal lighting.

Logs are written to:

```text
~/Library/Logs/TenonCodexLight/scan.log
```

Do not publish logs that contain your device identifier.

## Safety And Privacy

Tenon Codex Light is local convenience automation, not a security boundary.
Bluetooth access depends on Tenon's firmware pairing and encryption behavior, so
use it only in trusted physical environments.

Provided as-is for local automation experimentation. Use at your own risk.

This project does not:

- modify Tenon firmware
- flash firmware
- implement OTA updates
- use firmware binaries or proprietary firmware source
- write persistent Tenon configuration
- upload prompts, tool input, file paths, secrets, or analytics

The daemon writes only allowlisted light commands to the Tenon device identifier
you provide.

## Development

Most users only need the Quick Start above. Development and protocol notes live
in:

- [docs/prerequisites.md](docs/prerequisites.md)
- [docs/tenon-light-presets.md](docs/tenon-light-presets.md)
- [docs/tenon-ble-protocol-notes.md](docs/tenon-ble-protocol-notes.md)
- [docs/security-model.md](docs/security-model.md)

Run tests and safety checks:

```bash
.venv/bin/python -m pytest
.venv/bin/python scripts/check_repo_safety.py
```
