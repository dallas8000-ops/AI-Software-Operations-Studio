"""Fail CI when tracked source files contain credential-shaped values."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


PATTERNS = {
    "Stripe API key": re.compile(rb"\b[rs]k_(?:live|test)_[A-Za-z0-9]{16,}"),
    "Stripe webhook secret": re.compile(rb"\bwhsec_[A-Za-z0-9]{16,}"),
    "GitHub token": re.compile(rb"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"),
    "GitHub fine-grained token": re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{20,}"),
}


def tracked_files() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files", "-z"])
    return [Path(raw.decode("utf-8")) for raw in output.split(b"\0") if raw]


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        try:
            content = path.read_bytes()
        except OSError:
            continue
        if b"\0" in content:
            continue
        for label, pattern in PATTERNS.items():
            for match in pattern.finditer(content):
                line = content.count(b"\n", 0, match.start()) + 1
                findings.append(f"{path}:{line}: possible {label}")

    if findings:
        print("Credential-shaped values found in tracked files:")
        print("\n".join(findings))
        return 1
    print("No credential-shaped values found in tracked files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
