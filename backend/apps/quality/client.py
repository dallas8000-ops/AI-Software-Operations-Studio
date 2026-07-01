from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from django.conf import settings


class SpecwrightUnavailable(RuntimeError):
    pass


def _dashboard_url() -> str:
    base = settings.SPECWRIGHT_API_URL
    if not base:
        raise SpecwrightUnavailable("Specwright is not connected")
    parsed = urlparse(base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SpecwrightUnavailable("SPECWRIGHT_API_URL must be an HTTP(S) URL")
    return f"{base}/dashboard"


def fetch_dashboard() -> dict:
    return _fetch_json(_dashboard_url(), required_key="summary")


def _fetch_json(url: str, *, required_key: str | None = None) -> dict:
    request = Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urlopen(request, timeout=settings.SPECWRIGHT_API_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise SpecwrightUnavailable("Specwright did not return a valid dashboard response") from exc
    if not isinstance(payload, dict) or (required_key and not isinstance(payload.get(required_key), dict)):
        raise SpecwrightUnavailable("Specwright response has an invalid shape")
    return payload


def fetch_project_health(project_id: int) -> dict:
    base = settings.SPECWRIGHT_API_URL
    if not base:
        raise SpecwrightUnavailable("Specwright is not connected")
    _dashboard_url()  # validates configured origin
    return _fetch_json(f"{base}/projects/{project_id}/health", required_key="score")
