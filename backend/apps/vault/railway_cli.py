"""Fallback Railway credential from the local Railway CLI login (local installs only)."""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path


def _read_cli_token() -> tuple[str, float]:
    path = Path.home() / ".railway" / "config.json"
    try:
        user = json.loads(path.read_text(encoding="utf-8")).get("user") or {}
    except (OSError, ValueError):
        return "", 0.0
    return str(user.get("accessToken") or "").strip(), float(user.get("tokenExpiresAt") or 0)


def railway_cli_token() -> str | None:
    """Return the Railway CLI session token, refreshing it through the CLI when expired."""
    if os.environ.get("SERVER_WORKSPACES_ENABLED", "").lower() in {"1", "true", "yes"}:
        return None
    token, expires = _read_cli_token()
    if token and expires and expires <= time.time() + 60:
        cli = shutil.which("railway")
        if cli:
            try:
                subprocess.run([cli, "whoami"], capture_output=True, timeout=30, check=False)
            except (OSError, subprocess.SubprocessError):
                pass
            token, expires = _read_cli_token()
            if expires and expires <= time.time():
                return None
    return token or None
