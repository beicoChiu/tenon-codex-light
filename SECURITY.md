# Security Policy

Tenon Signal Light is a local automation tool for Codex and Beflo Tenon. It should not collect, store, or upload prompts, tool input, file paths, secrets, or source code.

This is an unofficial local automation side project, not an official Beflo or
OpenAI product. It is provided as-is with no service-level agreement, support
commitment, or warranty beyond the license terms.

## Core Guarantees

- Hook scripts write fixed state enums only.
- Hook scripts do not read or log prompt text.
- Hook scripts do not upload data.
- The daemon writes only allowlisted light commands.
- The daemon connects only to an allowlisted Tenon device.
- OTA, firmware, and persistent config commands are denied by design.

## Reporting Issues

Report issues through the repository's GitHub issue tracker or the maintainer
contact listed on the public repository.

## Repository Hygiene

- Run repository safety checks.
- Run secret scanning.
- Review all examples and logs for private paths or identifiers.
- Confirm no firmware source, OTA payloads, BLE captures, or secrets are committed.
