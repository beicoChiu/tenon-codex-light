# Tenon Light Presets

This document records the known Tenon two-color light presets so Codex state
mapping can reuse the original Tenon palette instead of inventing new colors.

## Sources

These public-safe preset values are recorded for interoperability and local
hardware validation. Private source paths, firmware source references, raw BLE
captures, and private device identifiers must not be added to this file.

For the user-facing preset names and visual designs, see the official
[Beflo app](https://apps.apple.com/us/app/beflo/id1590130814).

## Data Model

Tenon light effects are represented as two colors plus an animation:

- `colorPrimary`: first color
- `colorSecondary`: second color
- `animation`: `none`, `blink`, `breathe`, `moving`, `dancing`, or `rolling`

The iOS app stores preset colors as RGB. The BLE effect payload uses HSV, so the
table below includes both the original RGB values and the converted HSV values.
HSV values are formatted as `h,s,v`, with `h` in `0..359` and `s`/`v` in
`0..100`.

## Original Two-Color Presets

| Preset | RGB primary | RGB secondary | HSV primary | HSV secondary | Original animation |
| --- | --- | --- | --- | --- | --- |
| Cotton | `255,108,35` | `255,161,66` | `20,86,100` | `30,74,100` | `none` |
| Grass Land | `130,255,58` | `155,255,218` | `98,77,100` | `158,39,100` | `none` |
| Sunrise | `196,227,255` | `255,127,48` | `208,23,100` | `23,81,100` | `none` |
| Lavender Sunset | `217,63,255` | `255,99,38` | `288,75,100` | `17,85,100` | `none` |
| Sunset Glow | `255,83,10` | `255,66,72` | `18,96,100` | `358,74,100` | `none` |
| Aurora | `77,204,255` | `153,51,255` | `197,70,100` | `270,80,100` | `breathe` |
| Galaxy | `51,26,128` | `153,51,204` | `255,80,50` | `280,75,80` | `breathe` |
| Cloudy | `204,217,230` | `153,166,179` | `210,11,90` | `210,15,70` | `blink` |

Notes:

- The app uses the name `Grass Land`; the user-facing/older naming may refer to
  it as `Grass Island`.
- Cloudy's original app animation is `blink`; the Codex idle mapping
  intentionally uses Cloudy colors with `none` for a steady idle state.

## Final Codex State Mapping

This finalized mapping uses Tenon two-color colors and existing Tenon animation
types only. It does not require firmware changes, OTA, persistent Tenon config
writes, Codex hook changes, or new BLE protocol behavior.

| Codex state | Color / preset | HSV primary | HSV secondary | Animation | Speed |
| --- | --- | --- | --- | --- | --- |
| `idle` | Cloudy | `210,11,90` | `210,15,70` | `none` | `1000 ms` |
| `working` | Aurora | `197,70,100` | `270,80,100` | `breathe` | `1000 ms` |
| `needs_input` | Lavender Sunset | `288,75,100` | `17,85,100` | `moving` | `5000 ms` |
| `error` | Yellow Alert | `45,100,100` | `45,100,100` | `blink` | `300 ms` |
| `off` | Off | `0,0,0` | `0,0,0` | `none` | n/a |

`Yellow Alert` is an error-state status color, not an original named Tenon
preset. It still uses the existing two-color effect payload shape and the
allowlisted `blink` action.

## Internal Fallback State

`restore` is an internal cleanup/fallback command, not a user-facing Codex state
effect. For now, it should behave the same as `idle`:

| Internal command | Alias behavior | Meaning |
| --- | --- | --- |
| `restore` | Cloudy + `none` at `1000 ms` | Safe fallback to an idle-like light state. This does not restore previous desk settings. |

## Implementation Notes

- The native macOS daemon is the production hardware path for this mapping.
- The daemon uses existing allowlisted Tenon effect payloads for these
  presets and keeps HSV response-mode fallback for every state.
- `--disable-effects` forces the native daemon to use HSV fallback only.
- Cleanup on exit uses safe HSV idle/off behavior, not effect writes and not
  restoration of previous desk settings.
