"""Railway GraphQL — shared client with headers Cloudflare accepts."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request

RAILWAY_GQL = "https://backboard.railway.app/graphql/v2"
USER_AGENT = "Deployment-Stripe-Center/1.0"


def _post(token: str, body: dict, *, header_style: str) -> tuple[int, dict | str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if header_style == "bearer":
        headers["Authorization"] = f"Bearer {token}"
    else:
        headers["Project-Access-Token"] = token

    req = urllib.request.Request(
        RAILWAY_GQL,
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST",
    )
    started = time.time()
    op = str(body.get("query", "")).strip().split("(")[0].split("{")[0][:40]
    verbose = bool(os.environ.get("RAILWAY_VERBOSE"))
    if verbose:
        print(f"    [railway] {op} ...", end="", flush=True, file=sys.stderr)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if verbose:
                print(f" {resp.status} {time.time() - started:.1f}s", file=sys.stderr, flush=True)
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()[:500]
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw
    except (TimeoutError, urllib.error.URLError, ConnectionError) as exc:
        if verbose:
            print(f" FAILED {time.time() - started:.1f}s", file=sys.stderr, flush=True)
        return 599, f"network error: {exc}"


def railway_gql(token: str, query: str, variables: dict | None = None) -> dict:
    """Run GraphQL query/mutation; returns the `data` object.

    A stale stored token that Railway rejects falls back to the logged-in CLI token.
    """
    try:
        return _railway_gql(token, query, variables)
    except RuntimeError as exc:
        if "not authorized" not in str(exc).lower():
            raise
        from apps.vault.railway_cli import railway_cli_token

        cli = railway_cli_token()
        if not cli or cli == token:
            raise
        return _railway_gql(cli, query, variables)


def _railway_gql(token: str, query: str, variables: dict | None = None) -> dict:
    body = {"query": query, "variables": variables or {}}
    last_error = ""

    for attempt in range(1, 4):
        for style in ("bearer", "project"):
            status, payload = _post(token, body, header_style=style)
            if status == 200 and isinstance(payload, dict):
                if payload.get("errors"):
                    messages = "; ".join(
                        str(e.get("message", e)) for e in payload["errors"]
                    )
                    if "not authorized" in messages.lower() and style == "bearer":
                        continue
                    raise RuntimeError(messages[:300])
                return payload.get("data") or {}

            last_error = (
                f"Railway API {status}: {payload}"
                if not isinstance(payload, dict)
                else f"Railway API {status}: {json.dumps(payload)[:300]}"
            )
            if status in (403, 429, 503) and attempt < 3:
                time.sleep(min(8, 2**attempt))
                break
        else:
            continue
        break

    raise RuntimeError(last_error or "Railway API request failed")
