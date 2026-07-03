# Security Model

Tenon Signal Light is a local automation tool. It runs inside the developer's local AI coding agent environment (Codex, Claude Code) and uses lifecycle hooks, local files, and Bluetooth. Treat it with the same care as any tool that can execute hook commands on a workstation.

It is local convenience automation, not a security boundary. BLE access depends on Tenon's firmware pairing and encryption behavior, and users should run it only in trusted physical environments.

## Highest-Risk Area

The highest-risk area is agent hook command execution.

The risk is acceptable only if hooks remain boring:

- fixed command paths
- fixed enum state values
- no shell interpolation
- no prompt reads
- no sensitive logging
- no network upload
- short runtime

## MUST Requirements

Hook scripts:

- MUST NOT read prompt text
- MUST NOT log prompt text
- MUST NOT read or log tool input
- MUST NOT upload any data
- MUST only write one fixed state enum
- MUST use atomic write-and-rename
- MUST exit `0` quickly

State file:

- MUST default to a user-private path:

```text
~/Library/Application Support/TenonSignalLight/state
```

- MUST accept only these exact values:

```text
working
needs_input
idle
error
off
restore
```

- MUST reject all other content
- MUST ignore oversized or malformed files
- MUST be written atomically
- MUST use user-only permissions where the platform supports them

Daemon:

- MUST only connect to an allowlisted Tenon device
- MUST debounce state changes
- MUST keep logs free of prompts, tool input, file paths, secrets, and raw hook payloads
- MUST use the native macOS app daemon as the public hardware path
- MUST prevent duplicate native daemons for the same state file and device
- MUST treat `restore` as a safe fallback color/off state, not previous-setting recovery

Future daemon hardening:

- SHOULD reconnect with backoff
- SHOULD improve launch-agent lifecycle management

BLE writer:

- MUST allow only light-status commands
- MUST deny OTA commands
- MUST deny firmware commands
- MUST deny persistent config commands

Repository:

- MUST run secret scanning
- MUST run firmware/binary denylist checks
- MUST keep firmware source and OTA payloads out of git
- MUST keep BLE capture files out of git unless explicitly sanitized and reviewed

## Allowed Data Flow

```text
Agent lifecycle event
  -> hook writes enum only
  -> user-private local state file
  -> native macOS daemon maps enum to allowlisted Tenon light command
  -> response-mode HSV fallback if needed
  -> BLE write to allowlisted Tenon
```

No prompt, tool input, file content, file path, API key, token, or user text should enter this flow.

## Denied Data Flow

```text
prompt/tool input -> hook log
prompt/tool input -> state file
prompt/tool input -> daemon log
prompt/tool input -> network
raw hook payload -> log
arbitrary user string -> shell command
unknown BLE device -> write
OTA/firmware command -> BLE write
```

## Ongoing Repository Hygiene

For public development:

- run the secret scan
- run the firmware/binary denylist
- inspect logs and examples for private paths or identifiers
- confirm hook docs state that prompt content is never read or logged
- confirm BLE writer code has an explicit command allowlist
- confirm setup docs explain device allowlisting
