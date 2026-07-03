# Multi-Agent Routing

Tenon Signal Light is agent-neutral. The hook command, the state file, and the
daemon do not care which tool wrote a state. That means more than one AI coding
agent (for example Codex and Claude Code) can drive the same light.

If two agents run at the same time, they would otherwise take turns writing the
shared state file and the light would flicker between their states. The
active-source selector prevents that by letting you choose who owns the light.

## How It Works

Each agent tags its hook writes with a source:

```text
tenon-hook-state --source codex  working
tenon-hook-state --source claude working
```

A small selector file decides who is allowed through:

```text
~/Library/Application Support/TenonSignalLight/active_source
```

The gate runs before the state write, inside `tenon-hook-state`:

```text
Codex  hook --source codex  ─┐   selector = claude
Claude hook --source claude ─┤   codex  != claude -> dropped (no-op, exit 0)
                             │   claude == claude -> written -> daemon -> LED
                             └─
```

The daemon is untouched. It still watches one state file.

## Selector Values

| Selector value        | Behavior |
| --- | --- |
| `claude`              | Only `--source claude` writes drive the light. |
| `codex`               | Only `--source codex` writes drive the light. |
| `off`                 | No agent drives the light. Leave it to you / the official app. |
| unset (file missing)  | Every source is allowed. Zero-config default for a single agent. |

Two backward-compatible rules keep existing setups working:

- A hook with **no** `--source` flag always writes, regardless of the selector.
- An **unset** selector allows every source.

So a single-agent user never has to touch the selector. You only need it when
you run two agents and want exclusivity.

## Switching Owner

The selector file is the source of truth. The portable way to change it, with
no extra tools required, is the CLI:

```bash
tenon-light source            # show current owner (status)
tenon-light source claude     # hand the light to Claude
tenon-light source codex      # hand the light to Codex
tenon-light source off        # no agent drives the light
```

Handing the light to an agent also resets the state to `idle` so it does not
stay stuck in the previous owner's color. `off` leaves the light untouched; to
also turn the LED off use the ungated manual path `tenon-light state off`, or
your official Beflo/Tenon app.

### Gated vs ungated paths

- `tenon-hook-state` is the **gated** path used by agent hooks. It respects the
  selector.
- `tenon-light state <state>` and `tenon-light source ...` are **ungated**
  manual/admin paths. They always act, so you can control the light even while
  the selector is `off`.

## Optional: Menu-Bar Toggle

Any local menu-bar or keyboard-shortcut tool can switch the owner by calling
`tenon-light source ...`. The CLI is the supported interface; wiring it into a
menu bar is left to your own setup.
