#!/usr/bin/env python3
"""Deny firmware, captures, and obvious secrets from the repository."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


DENIED_SUFFIXES = {
    ".bin",
    ".hex",
    ".elf",
    ".map",
    ".img",
    ".dmg",
    ".zip",
    ".tar",
    ".gz",
    ".tgz",
    ".rar",
    ".7z",
    ".payload",
    ".pcap",
    ".pcapng",
    ".hci",
    ".btsnoop",
}

DENIED_NAME_PATTERNS = [
    re.compile(r"firmware", re.IGNORECASE),
    re.compile(r"\bfota\b", re.IGNORECASE),
    re.compile(r"\bota\b", re.IGNORECASE),
    re.compile(r"decompressed", re.IGNORECASE),
]

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{16,}"),
]

TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".toml",
    ".json",
    ".yml",
    ".yaml",
    ".txt",
    ".gitignore",
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return [Path(line) for line in result.stdout.splitlines() if line]


def is_text_candidate(path: Path) -> bool:
    return path.suffix in TEXT_SUFFIXES or path.name in {".gitignore", "LICENSE"}


def main() -> int:
    failures: list[str] = []

    for path in tracked_files():
        lower_name = path.name.lower()
        suffixes = {suffix.lower() for suffix in path.suffixes}

        if suffixes & DENIED_SUFFIXES:
            failures.append(f"denied binary/firmware/capture file: {path}")

        if any(pattern.search(str(path)) for pattern in DENIED_NAME_PATTERNS):
            failures.append(f"denied firmware/OTA-like path: {path}")

        if is_text_candidate(path) and path.exists():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    failures.append(f"possible secret in {path}: {pattern.pattern}")

    if failures:
        print("Repository safety check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Repository safety check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
