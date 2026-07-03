# Architecture

Tenon Signal Light is a local-first ambient workspace feedback system. It turns
software workflow state into physical Tenon light state without sending prompt
content, file paths, or local activity to a cloud service.

## System Flow

```text
Agent lifecycle event
  -> safe command hook
  -> tenon-hook-state
  -> user-private state file
  -> native macOS daemon
  -> allowlisted Tenon light payload
  -> Tenon ambient workspace signal
```

The hook layer is intentionally boring. It writes one fixed enum state and exits
quickly. It does not read prompts, log hook payloads, call Bluetooth, or upload
data.

The native macOS daemon is the current real-hardware path. It watches the state
file, maps each allowed state to a public-safe Tenon preset, writes the selected
light state over Bluetooth, and falls back to response-mode HSV if an effect
write fails.

## Components

| Component | Responsibility |
| --- | --- |
| Agent hooks | Convert lifecycle events into fixed local states |
| `tenon-hook-state` | Validate and atomically write the local state file |
| State file | Store the current workspace signal enum in a user-private path |
| Native macOS daemon | Watch state changes and write allowlisted light commands |
| Tenon device | Render the ambient workspace signal |

## State Mapping

| State | Signal |
| --- | --- |
| `idle` | Cloudy, steady |
| `working` | Aurora, breathing |
| `needs_input` | Lavender Sunset, moving |
| `error` | Yellow fast blink |
| `off` | Light off |
| `restore` | Internal cleanup fallback, currently idle-like |

## Local-First Boundary

Tenon Signal Light is not a cloud service and is not an official product
integration. It is a local automation bridge:

- no prompt upload
- no tool input upload
- no analytics
- no firmware modification
- no OTA behavior
- no persistent Tenon configuration writes

Bluetooth access depends on the Tenon device and the local macOS Bluetooth
permission model. Use this project only in trusted physical environments.

## Current Limits

- The daemon must be running for the light to follow state changes.
- This project does not install a LaunchAgent yet.
- Forced quits, crashes, or `kill -9` can skip cleanup behavior.
- Tenon may allow only one active Bluetooth central connection at a time.
- If the official mobile app is connected to the desk, disconnect it before
  running the daemon.
