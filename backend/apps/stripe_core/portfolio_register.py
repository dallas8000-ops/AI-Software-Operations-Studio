"""Register every live portfolio app as a Studio project for the portfolio owner.

Metadata only: creates Project rows from PORTFOLIO_CATALOG and fills catalog URLs.
Never calls Railway or Stripe, never pushes env, never rotates webhook secrets.
"""

from __future__ import annotations

import os

from apps.stripe_core.portfolio_catalog import HUB_SLUG, PORTFOLIO_CATALOG, CatalogEntry

DEFAULT_PORTFOLIO_OWNER_EMAIL = "dallas8000@gmail.com"


def portfolio_owner_email() -> str:
    return (os.environ.get("PORTFOLIO_OWNER_EMAIL") or DEFAULT_PORTFOLIO_OWNER_EMAIL).strip().lower()


def is_portfolio_owner(user) -> bool:
    email = str(getattr(user, "email", "") or "").strip().lower()
    return bool(email) and email == portfolio_owner_email()


def registrable_entries() -> list[CatalogEntry]:
    """Active catalog apps; the hub is the Studio itself and is shown as the platform card."""
    return [
        e
        for e in PORTFOLIO_CATALOG
        if e.get("projectSlug") and not e.get("merged") and e.get("projectSlug") != HUB_SLUG
    ]


def _host(url: str) -> str:
    from urllib.parse import urlparse

    return (urlparse(url or "").hostname or "").lower()


def _find_existing(owned, entry: CatalogEntry):
    """Match by slug, then name, then production host — avoids duplicating hand-added apps."""
    slug = entry["projectSlug"]
    name = str(entry.get("name") or "").strip().casefold()
    hosts = {
        _host(str(entry.get(key) or ""))
        for key in ("productionUrl", "webProductionUrl")
    } - {""}
    for project in owned:
        if project.slug == slug:
            return project
    for project in owned:
        if name and project.name.strip().casefold() == name:
            return project
    for project in owned:
        scan = project.scan_data or {}
        project_hosts = {
            _host(str(scan.get(key) or ""))
            for key in ("productionUrl", "production_url", "webProductionUrl")
        } - {""}
        if hosts & project_hosts:
            return project
    return None


def register_portfolio_projects(user, *, apply: bool = True) -> dict[str, list[str]]:
    """Create missing portfolio projects for ``user``. Returns created/existing slugs."""
    from apps.projects.models import Project
    from apps.stripe_core.portfolio_workspace import sync_portfolio_scan_metadata

    owned = list(Project.objects.filter(owner=user))
    created: list[str] = []
    existing: list[str] = []
    for entry in registrable_entries():
        match = _find_existing(owned, entry)
        if match:
            existing.append(match.slug)
            continue
        created.append(entry["projectSlug"])
        if not apply:
            continue
        project = Project(
            owner=user,
            name=entry["name"],
            slug=entry["projectSlug"],
            description=str(entry.get("notes") or ""),
            local_path=str(entry.get("defaultLocalPath") or ""),
        )
        sync_portfolio_scan_metadata(project, save=False)
        project.save()
        owned.append(project)
    return {"created": created, "existing": existing}
