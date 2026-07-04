# Tenon Signal Light

A programmable ambient workspace signal layer for AI-assisted workflows.

Tenon Signal Light turns [Beflo Tenon and Tenon mini](https://gobeflo.com)
devices into physical status indicators for local automation systems, coding
agents, focus workflows, and ergonomic routines.

It is local-first: no cloud dependency, no prompt uploading, no analytics, and
no firmware modification. Codex and Claude Code are supported workflows, but the
larger idea is a programmable workspace where software state can become calm
physical feedback. When you run more than one agent, an active-source selector
decides which one drives the light so they never fight over it.

This is an independent side project created by Beico Chiu. It is not an
official Beflo product, firmware release, or supported integration, and it is
not affiliated with or supported by OpenAI or Anthropic.

## What It Does

Tenon Signal Light runs a small native macOS daemon that listens to a local state
file. Agent lifecycle hooks (Codex, Claude Code) write simple state names such as
`working` or `needs_input`, and the daemon maps those states to allowlisted Tenon
light presets over Bluetooth.

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
- [Claude Code Hooks Integration](docs/claude-hooks-integration.md)
- [Multi-Agent Routing](docs/multi-agent-routing.md)
- [Tenon Light Presets](docs/tenon-light-presets.md)
- [Security Model](docs/security-model.md)

## Requirements

- macOS
- [Beflo Tenon or Tenon mini](https://gobeflo.com)
- Codex and/or Claude Code with command hooks enabled
- Python 3.11 or newer for setup scripts
- [Bleak](https://github.com/hbldh/bleak), installed from `requirements.txt`

Tenon may allow only one active Bluetooth connection at a time. Before running
Tenon Signal Light, check the official Beflo/Tenon mobile app and make sure it is
not connected to the desk. If it is connected, tap disconnect in the app so
Tenon releases the Bluetooth connection.

## Quick Start

### 1. Install Dependencies

Tenon Signal Light uses [Bleak](https://github.com/hbldh/bleak) for Python
Bluetooth helper scripts. `requirements.txt` is the project dependency file so
setup, CI, and future runtime dependencies stay consistent.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e .
```

### 2. Build The Native macOS App

```bash
scripts/build-macos-scan-app
```

### 3. Scan For Your Tenon

```bash
open "build/Tenon Signal Light Scan.app" --args --duration 8 --verbose
```

Look in the scan output for your Tenon device identifier. Use that value as
`<TENON_DEVICE_ID>` below.

### 4. Start The Daemon

```bash
open -n -W "build/Tenon Signal Light Scan.app" --args \
  --daemon \
  --address <TENON_DEVICE_ID>
```

Keep this process running while you want the light to follow local workflow
state. This project does not install a macOS LaunchAgent yet, so it will not
automatically restart after logout, reboot, or a forced quit.

### 5. Test The Light

In another terminal:

```bash
tenon-hook-state working
tenon-hook-state needs_input
tenon-hook-state idle
```

Expected result:

```text
working     -> Aurora, breathing
needs_input -> Lavender Sunset, moving
idle        -> Cloudy, steady
```

### 6. Enable Agent Hooks

If the light changes correctly, connect your agent's hooks using the example in
[docs/codex-hooks-integration.md](docs/codex-hooks-integration.md) (Codex) or
[docs/claude-hooks-integration.md](docs/claude-hooks-integration.md) (Claude
Code). The hook command can be used from any project after
`.venv/bin/python -m pip install -e .` installs `tenon-hook-state`. If you run
both agents, see [docs/multi-agent-routing.md](docs/multi-agent-routing.md) to
choose which one drives the light.

## Manual Test In 60 Seconds

After the daemon is running, this should visibly cycle through the core signals:

```bash
tenon-hook-state idle
sleep 1
tenon-hook-state working
sleep 2
tenon-hook-state needs_input
sleep 2
tenon-hook-state error
sleep 2
tenon-hook-state idle
```

## Where Things Live

| Item | Location |
| --- | --- |
| Native macOS app | `build/Tenon Signal Light Scan.app` |
| State file | `~/Library/Application Support/TenonSignalLight/state` |
| Active-source selector | `~/Library/Application Support/TenonSignalLight/active_source` |
| Log file | `~/Library/Logs/TenonSignalLight/scan.log` |
| Hook command | `tenon-hook-state` |
| Codex hooks example | [docs/codex-hooks-integration.md](docs/codex-hooks-integration.md) |
| Claude Code hooks example | [docs/claude-hooks-integration.md](docs/claude-hooks-integration.md) |
| Multi-agent routing | [docs/multi-agent-routing.md](docs/multi-agent-routing.md) |

Do not publish logs that contain your device identifier.

## Agent Hook Setup

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

| State | Codex hook event | Claude Code hook event |
| --- | --- | --- |
| `idle` | `SessionStart`, `Stop` | `SessionStart`, `Stop` |
| `working` | `UserPromptSubmit`, `PreToolUse`, `PostToolUse` | `UserPromptSubmit`, `PreToolUse`, `PostToolUse` |
| `needs_input` | `PermissionRequest` | `PermissionRequest` |

After installation, hooks can call `tenon-hook-state` directly. See
[docs/codex-hooks-integration.md](docs/codex-hooks-integration.md) or
[docs/claude-hooks-integration.md](docs/claude-hooks-integration.md) for a
copy-pasteable example.

### Choosing which agent drives the light

If you run more than one agent, tag each agent's hooks with `--source` (for
example `tenon-hook-state --source claude working`) and pick the owner:

```bash
tenon-light source claude   # Claude drives the light
tenon-light source codex    # Codex drives the light
tenon-light source off      # neither; return the light to you
tenon-light source          # show the current owner
```

A single agent needs no `--source` and no selector. Full model:
[docs/multi-agent-routing.md](docs/multi-agent-routing.md).

## Troubleshooting

### Scan Finds No Tenon

- Make sure Tenon is powered on and close to your Mac.
- Turn Bluetooth on.
- In the official Beflo/Tenon mobile app, confirm the desk is disconnected. If
  it is connected, tap disconnect.
- Check macOS Bluetooth permission for the app you are running.
- Power-cycle Tenon and scan again.

### Daemon Cannot Connect

- Confirm you copied the intended Tenon device identifier.
- Make sure no other daemon instance is already running.
- If the official Beflo/Tenon mobile app is connected, tap disconnect in the
  app so Tenon releases the Bluetooth connection.
- Check the daemon log:

```bash
tail -n 120 ~/Library/Logs/TenonSignalLight/scan.log
```

- Restart the daemon.

### Hooks Run But The Light Does Not Change

- If you just added or edited hook config, restart the agent first. Agents load
  hooks at session start, so a running session keeps the old hook set.
- If you use the active-source selector, check the owner: `tenon-light source`.
  A hook tagged `--source claude` is silently skipped while the selector says
  `codex` or `off` (that is the routing working as designed).
- Confirm the daemon is still running, and that it was restarted after any
  change to the state-file path it watches.
- Check the state file:

```bash
cat "$HOME/Library/Application Support/TenonSignalLight/state"
```

- Run the manual state test again:

```bash
tenon-hook-state working
tenon-hook-state idle
```

### macOS Blocks The App The First Time

- Open System Settings -> Privacy & Security.
- Allow the locally built app to run.
- Start the scan or daemon again.

### Light Is Left In A Workflow Color

```bash
tenon-hook-state idle
```

or:

```bash
tenon-hook-state off
```

You can also use the official Tenon/Beflo app to return to your normal lighting.

## Safety And Privacy

Tenon Signal Light is local convenience automation, not a security boundary.
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
