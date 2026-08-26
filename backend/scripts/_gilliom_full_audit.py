#!/usr/bin/env python
"""Full audit: Railway placement + Stripe webhooks + API health for all gilliomfrontlinedigital apps."""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
os.chdir(BACKEND_ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

import stripe
from django.contrib.auth import get_user_model

from apps.deploy.railway_home_audit import audit_railway_home_layout
from apps.projects.models import Project
from apps.stripe_core.hub_keys import get_hub_project
from apps.stripe_core.portfolio_audit import run_portfolio_audit, _probe_url
from apps.stripe_core.portfolio_catalog import (
    PORTFOLIO_CATALOG,
    catalog_live_urls,
    is_stripe_exempt_slug,
)
from apps.stripe_core.portfolio_registry import load_registry
from apps.vault.models import get_secret

EMAIL = "dallas8000@gmail.com"
PASS_MARK = "OK"
FAIL_MARK = "!!"

issues: list[str] = []


def _mark(ok: bool) -> str:
    return f"[{PASS_MARK}]" if ok else f"[{FAIL_MARK}]"


def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# ── 1. RAILWAY PLACEMENT ──────────────────────────────────────────
section("1 / RAILWAY PLACEMENT  (hearty-enjoyment)")

try:
    user = get_user_model().objects.get(email=EMAIL)
    hub = get_hub_project(user)
    if not hub:
        raise RuntimeError("Hub project (stripe-installer) not found")

    token = get_secret(hub, "RAILWAY_API_TOKEN") or ""
    if not token:
        print(f"  {_mark(False)} RAILWAY_API_TOKEN missing from hub vault — skipping Railway checks")
        issues.append("Railway: RAILWAY_API_TOKEN missing")
    else:
        result = audit_railway_home_layout(token)
        home = result["homeProject"]
        print(f"  Home project : {home['name']} ({home['serviceCount']} services)")
        print()
        print(f"  {'App':<32} {'In hearty-enjoyment':<22} Railway service")
        print(f"  {'-' * 80}")
        for row in result["apps"]:
            in_home = row["inHeartyEnjoyment"]
            svc = row["railwayService"] or row["railwayProject"] or "(not found)"
            print(
                f"  {_mark(in_home)} {row['name']:<30} {'YES' if in_home else 'NO — ' + row['railwayProject']:<22} {svc}"
            )
            if not in_home:
                issues.append(f"Railway: {row['name']} not in hearty-enjoyment ({row['railwayProject']})")

        extra = result["extraRailwayProjects"]
        if extra:
            print(f"\n  Extra Railway projects outside allowed list:")
            for p in extra:
                print(f"    {_mark(False)} {p['name']} ({p['serviceCount']} services)")
                issues.append(f"Railway: extra project {p['name']}")

        s = result["summary"]
        print(f"\n  Summary: {s['appsInHome']} in home, {s['appsOutsideHome']} outside, {s['extraProjects']} extra projects")
except Exception as exc:
    print(f"  {_mark(False)} Railway audit error: {exc}")
    issues.append(f"Railway audit exception: {exc}")


# ── 2. STRIPE WEBHOOKS ────────────────────────────────────────────
section("2 / STRIPE WEBHOOK AUDIT")

try:
    sk = get_secret(hub, "STRIPE_SECRET_KEY") or get_secret(hub, "SAAS_STRIPE_SECRET_KEY") or ""
    pk = get_secret(hub, "STRIPE_PUBLISHABLE_KEY") or get_secret(hub, "NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY") or ""
    if not sk:
        print(f"  {_mark(False)} STRIPE_SECRET_KEY missing from hub vault — skipping")
        issues.append("Stripe: STRIPE_SECRET_KEY missing")
    else:
        mode = "LIVE" if sk.startswith("sk_live_") else "TEST"
        print(f"  Key mode: {mode}")
        registry = load_registry()
        audit = run_portfolio_audit(secret_key=sk, publishable_key=pk or None, registry_apps=registry)

        acct = audit.get("account", {})
        print(f"  Account: {acct.get('accountId')} | country={acct.get('country')}")

        rows = audit.get("endpoints", [])
        print(f"\n  {'Endpoint URL':<60} {'Status':<10} {'App match':<26} Issues")
        print(f"  {'-' * 110}")
        for row in rows:
            ok_flag = not row.get("issues") and row.get("probe", {}) and row["probe"].get("reachable", False)
            probe_msg = (row.get("probe") or {}).get("message") or ""
            app_match = row.get("matchedApp") or "(unmatched)"
            row_issues = row.get("issues") or []
            url = row.get("url", "")[:58]
            status = row.get("status", "?")
            print(f"  {_mark(ok_flag)} {url:<58} {status:<10} {app_match:<26} {'; '.join(row_issues) or probe_msg[:40]}")
            for i in row_issues:
                issues.append(f"Stripe webhook [{app_match}]: {i}")

        registry_gaps = audit.get("registryGaps", [])
        if registry_gaps:
            print(f"\n  Registry apps with NO matching Stripe webhook:")
            for gap in registry_gaps:
                name = gap.get("name", "?") if isinstance(gap, dict) else str(gap)
                wh_url = gap.get("webhookUrl", "?") if isinstance(gap, dict) else ""
                print(f"    {_mark(False)} {name} — expected: {wh_url}")
                issues.append(f"Stripe: no webhook for {name}")

        for w in audit.get("deliveryWarnings", []):
            print(f"  [!!] {w}")
            issues.append(f"Stripe delivery: {w}")

except Exception as exc:
    print(f"  {_mark(False)} Stripe audit error: {exc}")
    issues.append(f"Stripe audit exception: {exc}")


# ── 3. API / HEALTH CHECK ─────────────────────────────────────────
section("3 / API HEALTH PROBES")

print(f"  {'App':<32} {'Health URL':<60} Result")
print(f"  {'-' * 110}")

for entry in PORTFOLIO_CATALOG:
    if entry.get("merged"):
        continue
    name = entry.get("name", entry.get("id", "?"))
    health_path = entry.get("healthPath", "/health/")
    api_url = (entry.get("productionUrl") or "").rstrip("/")
    if not api_url:
        continue
    health_url = f"{api_url}{health_path}"
    probe = _probe_url(health_url, timeout=12.0)
    ok = probe.reachable
    msg = probe.message or ""
    latency = f"{probe.latency_ms:.0f}ms"
    print(f"  {_mark(ok)} {name:<32} {health_url:<60} {msg} ({latency})")
    if not ok:
        issues.append(f"Health: {name} — {msg}")

# Also probe custom domain URLs (portfolioDemoUrl)
print()
print(f"  {'App':<32} {'Demo/Web URL':<60} Result")
print(f"  {'-' * 110}")
for entry in PORTFOLIO_CATALOG:
    if entry.get("merged"):
        continue
    name = entry.get("name", entry.get("id", "?"))
    live = catalog_live_urls(entry)
    demo_url = (live.get("portfolioDemoUrl") or live.get("demoUrl") or live.get("webUrl") or "").rstrip("/")
    api_url = (entry.get("productionUrl") or "").rstrip("/")
    if not demo_url or demo_url == api_url:
        continue
    probe = _probe_url(demo_url, timeout=12.0)
    ok = probe.reachable
    msg = probe.message or ""
    latency = f"{probe.latency_ms:.0f}ms"
    print(f"  {_mark(ok)} {name:<32} {demo_url:<60} {msg} ({latency})")
    if not ok:
        issues.append(f"Web/demo: {name} — {msg}")


# ── SUMMARY ───────────────────────────────────────────────────────
section("SUMMARY")
if issues:
    print(f"  {len(issues)} issue(s) found:\n")
    for i in issues:
        print(f"    • {i}")
    sys.exit(1)
else:
    print("  All checks passed — Railway, Stripe, and API configs look good.")
    sys.exit(0)
