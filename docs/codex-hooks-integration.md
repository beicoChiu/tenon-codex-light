# Codex Hooks Integration

Codex lifecycle hooks are the first supported workflow integration for Tenon
Codex Light. They turn local agent lifecycle events into an ambient Tenon
workspace signal.

Reference: <https://developers.openai.com/codex/hooks>

## Architecture

```text
Codex hooks
  -> tenon-hook-state
  -> ~/Library/Application Support/TenonSignalLight/state
  -> native macOS daemon
  -> allowlisted effect write, with response-mode HSV fallback
  -> Tenon LED
```

The hook layer should never talk to BLE directly. It should only write the
desired state and exit quickly. The current production hardware path is the
native macOS daemon, which watches the state file and writes allowlisted light
states to the selected Tenon device. Effects are used by default for reviewed
states, and response-mode HSV remains the fallback path.

The native daemon prevents duplicate runs for the same state file and device. On
clean exit, SIGINT, SIGTERM, or app termination where practical, it attempts one
final safe `idle` HSV write. This is a fallback status color, not restoration of
previous desk settings.

Future daemon hardening may add stronger launch-agent lifecycle management. Do
not rely on automatic startup or restart until it is implemented and tested.

Hooks must be privacy-preserving. They must not read prompt text, tool input,
file paths, or raw event payloads except for the minimum event metadata needed
to choose a fixed state enum.

## Event Mapping

```text
SessionStart      -> idle
UserPromptSubmit  -> working
PreToolUse        -> working
PermissionRequest -> needs_input
PostToolUse       -> working
Stop              -> idle
```

## Hook Locations

Codex can discover hooks from:

```text
~/.codex/hooks.json
~/.codex/config.toml
<repo>/.codex/hooks.json
<repo>/.codex/config.toml
```

For a single project, repo-local `.codex/hooks.json` is easiest. A user-level
`~/.codex/hooks.json` can be used for global behavior across projects.

## Constraints

- Hooks are enabled by default unless `[features].hooks = false`.
- Non-managed command hooks must be reviewed and trusted before they run.
- Only `type: "command"` handlers run today.
- `async: true` is parsed but skipped.
- `prompt` and `agent` handlers are parsed but skipped.
- Multiple matching command hooks may run concurrently.
- `PreToolUse` is useful for status transitions, but it is not a complete
  enforcement boundary.

## Hook Script Behavior

Hook scripts should:

- avoid reading prompt text or tool input
- avoid logging raw hook input
- write one validated state value
- use atomic write-and-rename
- avoid BLE calls
- avoid network calls
- avoid shell interpolation and dynamic command construction
- exit `0`
- keep runtime under one second in normal cases

Allowed state values:

```text
working
needs_input
idle
error
off
restore
```

All other values must be rejected.

## Safe Hook Writer

After installing the package with `.venv/bin/python -m pip install -e .`, use
the `tenon-hook-state` command:

```bash
tenon-hook-state working
```

If Codex cannot find `tenon-hook-state`, activate the virtual environment before
launching Codex, or replace `tenon-hook-state` in the examples below with the
absolute path printed by:

```bash
command -v tenon-hook-state
```

The command:

- accepts only one fixed enum argument
- writes only `~/Library/Application Support/TenonSignalLight/state` by default
- supports `--state-file` and `TENON_SIGNAL_LIGHT_STATE_FILE` for tests and
  advanced users
- returns quickly
- does not read stdin
- does not read prompt text
- does not log hook payloads
- does not upload data
- does not call BLE directly

## Example ~/.codex/hooks.json

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "tenon-hook-state idle"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "tenon-hook-state working"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "tenon-hook-state working"
          }
        ]
      }
    ],
    "PermissionRequest": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "tenon-hook-state needs_input"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "tenon-hook-state working"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "tenon-hook-state idle"
          }
        ]
      }
    ]
  }
}
```

Do not build hook commands by concatenating prompt text, tool input, file paths,
or other untrusted strings.

## Manual Test

Start the daemon separately, then simulate hook events by writing states:

```bash
scripts/build-macos-scan-app
open -n -W "build/Tenon Signal Light Scan.app" --args \
  --daemon \
  --address <TENON_DEVICE_ID>
```

In another terminal:

```bash
tenon-hook-state idle
tenon-hook-state working
tenon-hook-state needs_input
tenon-hook-state idle
```
