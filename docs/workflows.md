# Workflow Ideas

Tenon Codex Light is a first step toward an ambient programmable workspace:
software state becomes physical context without adding another screen.

## AI-Assisted Development

Codex can run local hooks when a session starts, when a prompt is submitted,
before and after tool use, when permission is needed, and when the session
stops. Tenon Codex Light maps those lifecycle events to calm physical signals:

| Workflow moment | Ambient signal |
| --- | --- |
| Agent is idle | Cloudy, steady |
| Agent is working | Aurora, breathing |
| Agent needs input | Lavender Sunset, moving |
| Agent hit an error | Yellow fast blink |

The goal is physical AI visibility: you can glance at the workspace instead of
watching a terminal or waiting for a notification.

## Focus Sessions

The same state-file interface can be driven by other local automation tools.
For example, a focus routine could set `working` at the beginning of a session,
`needs_input` for a planned break, and `idle` when the session ends.

## Ergonomic Routines

Tenon is already part of the physical workspace. A future workflow could combine
ambient light state with posture reminders, sit-stand transitions, or local
break routines. This repository currently controls light state only; it does
not change desk height or persistent desk configuration.

## Platform Direction

Codex is the first workflow, not the category limit. The broader direction is a
local-first programmable workspace layer:

- ambient workflow feedback
- developer hardware interfaces
- physical AI status
- ergonomic automation
- calm local control

Any richer light behavior should use existing Tenon-compatible light effects.
This project must not require firmware flashing, OTA, firmware source,
firmware-side APIs, or persistent configuration writes.
