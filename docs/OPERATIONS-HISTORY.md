# Studio Operations History

Launch notes, deployment lineage and release history moved from the README. These sections are kept verbatim for reference; checklists here may describe steps that are already complete. For current behavior, see the [README](../README.md).

## Completion roadmap

### Live Studio deployment

| Item | Current state |
|------|---------------|
| Railway project | `hearty-enjoyment` |
| Web service | `operations-studio-web` - deployed successfully |
| Canonical URL | [studio.gilliomfrontlinedigital.com](https://studio.gilliomfrontlinedigital.com) |
| API + webhooks (split domain) | [api.gilliomfrontlinedigital.com](https://api.gilliomfrontlinedigital.com) — attach in Railway when ready; catalog + backend already target this host |
| Railway fallback | [operations-studio-web-production-d4ad.up.railway.app](https://operations-studio-web-production-d4ad.up.railway.app) |
| Health endpoint | [Live health](https://studio.gilliomfrontlinedigital.com/health/) |
| PostgreSQL | Dedicated `Postgres-V92Q` service connected; health passing |
| Redis | Existing managed Redis, isolated to logical database 15; health passing |
| Worker | `operations-studio-worker` deployed and healthy |
| Beat scheduler | `operations-studio-beat` deployed and healthy |
| Studio billing | Active Product; Starter $9/month; Pro $79/month; Enterprise contact sales |
| Stripe API key | Dedicated live restricted key verified for the six minimum runtime permissions |
| Stripe webhook | Studio SaaS billing at `https://api.gilliomfrontlinedigital.com/api/v1/billing/webhook/` (catalog target); live deploy may still use same-origin `studio.*` until `VITE_API_BASE` rebuild |
| Webhook monitoring | Delivery stats from Stripe, signed live probe, **Auto-repair webhook** in Monitoring + `python scripts/run_webhook_auto_repair.py` |
| Custom domain | `studio.gilliomfrontlinedigital.com` active with valid Railway TLS certificate |

The existing Specwright and Deployment-Stripe-center Railway services were not changed during this deployment.

### Complete locally

- Django and React foundation, authentication, and application navigation.
- Projects, settings, environments, organizations, roles, and agency assignment.
- Encrypted project vault with masked, server-side-only secret handling.
- Imported project metadata, pipeline history, logs, and encrypted vault records.
- Specwright quality-evidence adapter and workflow/readiness surfaces.
- Deployment transfer module, provider checks, audit evidence, dry-run planning, and explicit approval gate.
- Stripe diagnostics, webhook delivery-state reporting, billing framework, and license support.
- In-app tutorial, phase roadmap, deployment runbook, and GitHub publishing.

### Required before Studio production launch

1. Review and merge `codex/studio-foundation` into the protected default branch.
2. Create a new Railway service and PostgreSQL database for Studio.
3. Configure `VAULT_MASTER_KEY`, `DJANGO_SECRET_KEY`, database, allowed-host, CORS, and production variables in Railway.
4. Deploy and verify `/health/`, authentication, projects, agency, guide, workflows, and transfer using the Railway URL.
5. Assign the Studio custom domain and update allowed origins after TLS activates.
6. Create Studio-specific Stripe Products and Prices in test mode first.
7. Register the Studio webhook and store its signing secret only in Railway.
8. Complete a test subscription lifecycle and verify webhook signatures, idempotency, cancellation, and access updates.
9. Back up the production database and vault-key recovery material.
10. Run the complete test/build/production-check suite and record go-live evidence.

**Encrypted vault + Stripe automation for agencies shipping client apps to production** — one login to scan repos, wire billing, and push deploys without secrets leaving the server.

Combined platform for **deployment / API transfer** and **Stripe setup** — one login, one database, one encrypted vault per project.

This repo merges the former **Stripe Installer** and **API Transfer** products into a single Django + React app. Never exposes secrets to the frontend, AI, or logs.

| Doc | Purpose |
|-----|---------|
| [docs/PRODUCT.md](PRODUCT.md) | Product wedge + ICP |
| [docs/LEGACY-ARCHIVE.md](LEGACY-ARCHIVE.md) | Legacy CLI retirement policy |
| [deploy/COMPLIANCE.md](../deploy/COMPLIANCE.md) | SOC 2 readiness + audit retention |
| [docs/STRUCTURE.md](STRUCTURE.md) | Repo layout |
| [docs/AUTOMATION-CENTER.md](AUTOMATION-CENTER.md) | Merge vision + secret rules |
| [docs/CUTOVER.md](CUTOVER.md) | Retire old production apps |
| [docs/MERGE-STATUS.md](MERGE-STATUS.md) | Cutover checklist (live) |
| [docs/RAILWAY.md](RAILWAY.md) | Railway deploy + vault key |
| [docs/DEPLOYMENT-HANDOFF.md](DEPLOYMENT-HANDOFF.md) | Production cutover, split domains, operator runbook |
| [docs/DEMO-SCRIPT.md](DEMO-SCRIPT.md) | 3–5 min stakeholder demo script |
| [docs/GO-LIVE.md](GO-LIVE.md) | Client project → production |
| [docs/PRODUCTION.md](PRODUCTION.md) | Docker prod stack |
| [backend/apps/api_transfer/README.md](../backend/apps/api_transfer/README.md) | Transfer API reference |

---

## Existing deployment reference (not the new Studio launch)

The URLs in this section belong to the earlier automation-center deployment lineage. They are retained as migration evidence and do not prove that this Studio repository has completed its own Railway launch.

| Item | URL |
|------|-----|
| **Primary (custom domain)** | https://stripe-installer.gilliomfrontlinedigital.com/login |
| **Railway fallback** | https://stripe-installer-production.up.railway.app/login |
| **Health** | `GET /health/` |
| **SaaS billing webhook** | `POST /api/v1/billing/webhook/` |
| **Portfolio live demo** | [gilliomfrontlinedigital.com](https://gilliomfrontlinedigital.com) → **Deployment & Stripe Automation Center** card |
| **Railway service** | `Stripe-Installer` in project `hearty-enjoyment` |
| **Retiring** | `api-transfer-production` (legacy — delete after cutover) |

**Last verified** (local `python manage.py verify_cutover`):

| Check | Status |
|-------|--------|
| Unified health + vault | OK |
| SaaS billing configured | OK |
| Portfolio registry (`~/.stripe-installer/portfolio-registry.json`) | OK |
| Custom domain TLS | Pending — finish cert in Railway → Networking |
| Legacy api-transfer service | Still up — disable webhook, wait 48h, delete service |

```powershell
curl https://stripe-installer-production.up.railway.app/health/
cd backend; python manage.py verify_cutover
powershell -File scripts/complete-cutover.ps1
```

---

## Integrated source capabilities

Studio incorporates capabilities from earlier applications; it does not require those applications to be shut down. Treat the table below as a code-integration map, not a retirement instruction.

| Old app | Was | Now |
|---------|-----|-----|
| Stripe Installer | `stripe-installer-production.up.railway.app` | Unified app (same service, expanded) |
| API Transfer | `api-transfer-production.up.railway.app` | `backend/apps/api_transfer/` module in this repo |

**Portfolio:** [gilliomfrontlinedigital.com](https://gilliomfrontlinedigital.com) is the marketing site only. Live demo buttons open product Railway URLs — not subdomains of the portfolio root.

---

## Status

**Version 2.0 is the current production release.** Version 1 established the secure deployment, billing, and
project-operations foundation. Version 1.1 added portfolio-scale usability while preserving that safety model.
Version 2 connects the mature automation modules through an account-wide Operations Center.

### Version 2.0 focus

- Account-wide Operations Center for readiness, release, organization, and GitHub connectivity.
- Release-recovery candidates that identify the last successful run after a failure without making an unsafe mutation.
- Secret-free operational reporting for owners, administrators, and viewers.
- Direct navigation from the Studio home and global application header.
- Existing GitHub App automation, organization roles, AI diagnostics, infrastructure generation, guarded Railway delivery, and deployment history are now presented as the Version 2.0 release surface.

### Version 2 additions

- Portfolio-wide readiness, release, organization, and GitHub connectivity reporting.
- Release-recovery candidates that identify the last successful run after a failure without performing an unsafe
  automatic production mutation.
- Recent audit activity across every accessible personal and agency project.
- A secret-free operations report suitable for owners, administrators, and viewers.
- Direct navigation from the Studio home and global application header.
- Existing GitHub App automation, organization roles, AI diagnostics, infrastructure generation, guarded Railway
  delivery, and deployment history form the Version 2 automation layer.

### Version 1.1 additions

- Search projects by name, slug, framework, or language.
- Filter active projects by readiness or running status.
- Archive and restore projects without deleting history, vault metadata, runs, or audit evidence.
- Record archive and restore operations in each project audit log.
- Mobile-friendly project management controls.
- Existing guarded Railway sync, Stripe webhook health, backup/recovery, onboarding, MFA, and audit tooling are
  retained as the Version 1.1 operations baseline.

| Area | Includes |
|------|----------|
| **Core** | Auth, projects, vault (import, rotation), scanner, pipeline, WebSocket logs, runs, diagnose/fix |
| **Stripe** | Verify, provision, codegen, `stripe.config.json` UI |
| **API Transfer** | Railway / Render / Fly deploy, GitHub import, Render→Railway migration, audit log, queue metrics |
| **Deploy** | Unified deploy prep, infra codegen, readiness report, manifest, platform push |
| **Database** | Neon, Supabase, Railway, self-hosted provision + schema apply |
| **Git** | Clone (sync/async), private repo auth (token/SSH/credentials), GitHub PR |
| **Ops** | Docker prod stack, health checks, `check:prod`, `deploy:prod`, GitHub Actions CI, CLI |
| **AI copilot** | Fix copilot, NL→config, readiness coach, handoff pack, catalog strategist, webhook incident |
| **Monitoring** | Catalog drift (Celery Beat), webhook delivery stats + auto-repair, re-sync, audit log |
| **Portfolio audit** | Account-wide webhook probe + local report (`~/.stripe-installer/reports/`) — [docs/PORTFOLIO-AUDIT.md](PORTFOLIO-AUDIT.md) |
| **Environments** | Test / staging / production URLs in `deploy.config.json`, per-project selector |
| **Agency** | Organizations, RBAC, **email invites** (register link → auto-join), shared projects |
| **GitHub App** | Install flow + webhook — PR readiness checks and optional check runs |
| **CI gate** | Readiness gate API (`si_` keys), GitHub CI status, workflow template |
| **Org billing** | Per-org Stripe Checkout, free-tier limits, webhook sync, pipeline upgrade banners |
| **License protection** | Issue keys on SaaS checkout, instance validation, readonly/block enforcement for deployed copies |
| **MCP** | Cursor/stdio tools — projects, readiness, drift, vault status, pipeline, PR prep |

**Optional:** charge for this platform itself via `SAAS_STRIPE_*` (or `STRIPE_*`) in Railway Variables / `backend/.env`.

The archived Node/Electron CLI in `legacy/node/` is reference only — **do not run it alongside Django on the same project.**

---

## Portfolio registry (local machine)

Allowed apps for transfer/deploy linking live at:

```
~/.stripe-installer/portfolio-registry.json
```

Template in code: `backend/apps/stripe_core/portfolio_registry.py` (`EXAMPLE_REGISTRY`).

Current production hub entry: **`automation-center`** → web `https://studio.gilliomfrontlinedigital.com`, API/webhooks `https://api.gilliomfrontlinedigital.com`

---

## Parallel launch and optional future cutover

The current plan is a parallel launch: keep Specwright and Deployment-Stripe-center available while Studio receives its own Railway deployment, database, domain, Stripe catalog, and webhook. Any future retirement is a separate owner-approved operation after backups and production evidence.

Studio launch steps:

1. Deploy Studio to its own staging and production services.
2. Keep the existing application URLs and webhooks enabled.
3. Give Studio its own Stripe endpoint and webhook signing secret.
4. Smoke test login, projects, vault, workflows, transfer, and billing.
5. Add Studio to the public portfolio only after the production evidence passes.

The historical cutover helper is retained for reference only. Do not run it as part of the parallel-launch plan.

---

## MCP (Cursor)

```powershell
# Copy .cursor/mcp.json.example → .cursor/mcp.json, set your email
cd backend
$env:STRIPE_INSTALLER_USER = "you@example.com"
python manage.py run_mcp_server
```

Tools: `list_projects`, `project_readiness`, `project_drift`, `project_diagnose`, `project_vault_status`, `start_pipeline`, `project_open_pr_prep`

See [docs/MCP.md](MCP.md).

---

## Legacy Node CLI

The v0.6 CLI and Electron app live in [`legacy/node/`](../legacy/node/) for reference only.

---

