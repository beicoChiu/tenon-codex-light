# Claude Code Hooks Integration

Claude Code is a supported workflow for Tenon Signal Light, alongside Codex.
Claude Code lifecycle hooks turn local agent events into an ambient Tenon
workspace signal, using the exact same state file and daemon as every other
source.

Reference: <https://docs.claude.com/en/docs/claude-code/hooks>

## Architecture

```text
Claude Code hooks
  -> tenon-hook-state --source claude
  -> active-source gate (see docs/multi-agent-routing.md)
  -> ~/Library/Application Support/TenonSignalLight/state
  -> native macOS daemon
  -> allowlisted effect write, with response-mode HSV fallback
  -> Tenon LED
```

Nothing about the daemon or the state file is Claude-specific. The only
Claude-specific part is the hook wiring below. If you also run Codex, read
[docs/multi-agent-routing.md](multi-agent-routing.md) first so the two do not
fight over the light.

## Event Mapping

Claude Code fires different lifecycle events than Codex, but they map onto the
same fixed states:

```text
SessionStart      -> idle
UserPromptSubmit  -> working
PreToolUse        -> working
PostToolUse       -> working
Notification      -> needs_input   (Claude needs permission or input)
Stop              -> idle
SessionEnd        -> off           (optional)
```

`Notification` is the Claude Code equivalent of Codex's `PermissionRequest`: it
fires when Claude is waiting on you for a permission decision or input. Unlike
`PreToolUse`, a `Notification` hook needs an explicit `matcher` naming the
notification type (`permission_prompt`, `idle_prompt`, `agent_needs_input`); an
entry with no matcher does not fire.

## Hook Locations

Claude Code reads hooks from its settings files:

```text
~/.claude/settings.json          (user-level, applies everywhere)
<repo>/.claude/settings.json     (project-level, shared/committed)
<repo>/.claude/settings.local.json   (project-level, personal, gitignored)
```

For light behavior across every project, user-level `~/.claude/settings.json` is
easiest. These files are separate from Codex's `~/.codex/hooks.json`, so the two
integrations never overwrite each other.

## The `tenon-hook-state` Command

Install the package once with `.venv/bin/python -m pip install -e .`, then hooks
can call `tenon-hook-state`.

Hooks run in a clean shell that may not have your virtualenv on `PATH`. If
Claude Code cannot find `tenon-hook-state`, use the absolute path printed by:

```bash
command -v tenon-hook-state
```

Substitute that path for `tenon-hook-state` in the example below.

The `--source claude` flag tags these writes so the active-source selector can
route between agents. If you only ever use Claude Code, the flag is harmless and
the selector can stay unset.

## Example `~/.claude/settings.json`

Replace `tenon-hook-state` with the absolute path from `command -v
tenon-hook-state` if Claude Code cannot find it on `PATH`.

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          { "type": "command", "command": "tenon-hook-state --source claude idle" }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          { "type": "command", "command": "tenon-hook-state --source claude working" }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          { "type": "command", "command": "tenon-hook-state --source claude working" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [
          { "type": "command", "command": "tenon-hook-state --source claude working" }
        ]
      }
    ],
    "Notification": [
      {
        "matcher": "permission_prompt",
        "hooks": [
          { "type": "command", "command": "tenon-hook-state --source claude needs_input" }
        ]
      },
      {
        "matcher": "idle_prompt",
        "hooks": [
          { "type": "command", "command": "tenon-hook-state --source claude needs_input" }
        ]
      },
      {
        "matcher": "agent_needs_input",
        "hooks": [
          { "type": "command", "command": "tenon-hook-state --source claude needs_input" }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "tenon-hook-state --source claude idle" }
        ]
      }
    ]
  }
}
```

`SessionEnd -> off` is optional; add it the same way if you want the light to
turn off when a Claude Code session ends.

Do not build hook commands by concatenating prompt text, tool input, file paths,
or other untrusted strings. The command takes only a fixed state enum and the
routing flags.

## Running Alongside Codex

If both Codex and Claude Code are configured, pick who owns the light:

```bash
tenon-light source claude   # Claude drives the light
tenon-light source codex    # Codex drives the light
tenon-light source off      # neither; return the light to you
tenon-light source          # show the current owner
```

See [docs/multi-agent-routing.md](multi-agent-routing.md) for the full model.

## Manual Test

Start the daemon separately, then simulate hook events by writing states:

```bash
tenon-hook-state --source claude idle
tenon-hook-state --source claude working
tenon-hook-state --source claude needs_input
tenon-hook-state --source claude idle
```

If the selector is set to `codex`, these `--source claude` writes are correctly
ignored. Run `tenon-light source claude` (or `tenon-light source` to check)
first.
