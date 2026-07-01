from __future__ import annotations

import json
import sqlite3
from pathlib import Path
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
    if settings.SPECWRIGHT_API_URL:
        return _fetch_json(_dashboard_url(), required_key="summary")
    return _sqlite_dashboard()


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
        return _sqlite_project_health(project_id)
    _dashboard_url()  # validates configured origin
    return _fetch_json(f"{base}/projects/{project_id}/health", required_key="score")


def _sqlite_connection() -> sqlite3.Connection:
    raw = str(getattr(settings, "SPECWRIGHT_SQLITE_PATH", "") or "").strip()
    path = Path(raw)
    if not raw or not path.is_file():
        raise SpecwrightUnavailable("Specwright is not connected")
    connection = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _stats(raw: str | None) -> dict:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def _sqlite_project_health(project_id: int) -> dict:
    db = _sqlite_connection()
    try:
        project = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not project:
            raise SpecwrightUnavailable("Linked Specwright project was not found")
        scan = db.execute(
            "SELECT * FROM scans WHERE project_id = ? AND status = 'completed' ORDER BY created_at DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        stats = _stats(scan["stats"] if scan else None)
        if not isinstance(stats.get("score"), dict):
            stats["score"] = {"score": project["last_score"] or None, "breakdown": {}, "gaps": {}}
        stats.setdefault("drift", {})
        stats.setdefault("route_count", stats.get("routes_found", 0))
        stats["last_scanned_at"] = scan["created_at"] if scan else None
        return stats
    finally:
        db.close()


def _sqlite_dashboard() -> dict:
    db = _sqlite_connection()
    try:
        projects = list(db.execute("SELECT * FROM projects ORDER BY name"))
        rows = []
        for project in projects:
            scan = db.execute(
                "SELECT * FROM scans WHERE project_id = ? AND status = 'completed' ORDER BY created_at DESC LIMIT 1",
                (project["id"],),
            ).fetchone()
            stats = _stats(scan["stats"] if scan else None)
            score = stats.get("score") or {}
            breakdown = score.get("breakdown") or {}
            drift = stats.get("drift") or {}
            rows.append(
                {
                    "id": project["id"], "name": project["name"], "root_path": project["root_path"],
                    "framework": project["framework"], "github_repo": project["github_repo"],
                    "watch_enabled": bool(project["watch_enabled"]), "score": score.get("score") or project["last_score"],
                    "grade": score.get("grade"), "last_scanned_at": scan["created_at"] if scan else None,
                    "documentation_pct": breakdown.get("documentation_pct"), "test_coverage_pct": breakdown.get("test_coverage_pct"),
                    "routes_found": stats.get("routes_found", 0), "drift_detected": bool(drift.get("drift_detected")),
                    "spec_in_sync": not bool(drift.get("drift_detected")), "commits_behind": drift.get("commits_behind", 0),
                    "score_delta_7d": None, "needs_attention": bool(drift.get("drift_detected")),
                    "never_scanned": scan is None, "drift_this_week": False,
                }
            )
    finally:
        db.close()
    scored = [row for row in rows if row["score"] is not None]
    docs = [row["documentation_pct"] for row in rows if row["documentation_pct"] is not None]
    tests = [row["test_coverage_pct"] for row in rows if row["test_coverage_pct"] is not None]
    return {
        "summary": {
            "total_projects": len(rows), "scored_projects": len(scored),
            "avg_score": round(sum(row["score"] for row in scored) / len(scored)) if scored else None,
            "avg_documentation_pct": round(sum(docs) / len(docs), 1) if docs else None,
            "avg_test_coverage_pct": round(sum(tests) / len(tests), 1) if tests else None,
            "drifted_this_week": 0, "needs_attention": sum(bool(row["needs_attention"]) for row in rows),
        },
        "projects": rows, "drifted_this_week": [], "team_trend": [], "project_trends": [],
    }
