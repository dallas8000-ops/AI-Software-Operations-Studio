# AI Software Operations Studio

> Current repository: [dallas8000-ops/AI-Software-Operations-Studio](https://github.com/dallas8000-ops/AI-Software-Operations-Studio)
>
> Active build branch: `codex/studio-foundation`
>
> Local workspace: `C:\Software Projects\AI Software Operations Studio`

AI Software Operations Studio is a protected Django and React workspace for managing software projects, quality evidence, Stripe configuration, and production deployments. It integrates selected capabilities from **Specwright** and **Deployment-Stripe-center** while allowing both source applications to remain independent products.

Secrets are write-only from the browser, encrypted server-side, masked in API responses, and excluded from Git. Production credentials belong in Railway Variables or a protected vault, not source code, frontend code, prompts, or logs.

Version 2.0 is the current production release. This README now documents the merged Operations Center experience, while the Version 1 launch and cutover details remain as historical deployment context.

## What Studio Does

Studio is an operations control plane for software projects. It provides account login and MFA, personal and organization workspaces with role-based access, an encrypted per-project vault, repository scanning, readiness and quality reporting, run history, guarded deployment preparation, provider migration workflows, billing, and operational reporting. The React application is served by Django; project secrets remain server-side and are masked in all normal API responses.

The primary workflows are:

- **Project operations:** create or import a project, connect a repository and local workspace, scan its stack, manage environments, archive or restore it, and retain audit evidence.
- **Secure configuration:** write provider credentials to the encrypted vault, inspect only masked status, import supported environment keys, and use vault secrets for server-side automation.
- **Stripe and billing:** verify project Stripe credentials, provision supported Stripe catalog resources, generate integration code, monitor webhooks, run diagnostics, and manage Studio subscription billing.
- **Deployment and reliability:** build readiness reports, generate deployment artifacts, prepare provider migrations, push approved Railway configuration, track pipeline runs, and use health, drift, webhook, backup, and recovery tools.
- **Teams and automation:** manage organizations and roles, invite members, connect GitHub, inspect CI status, generate a GitHub Actions readiness workflow, and expose a project-scoped CI readiness endpoint.
- **AI assistance:** provide secret-free diagnostics, readiness coaching, configuration guidance, and handoff material. AI context excludes vault values.

### Automated Keys

Studio handles several distinct key types. It never claims to create provider dashboard credentials, such as Stripe secret keys, GitHub tokens, Neon keys, or Railway tokens; those are created by their respective providers and stored in the project vault by an authorized user.

| Key type | How it is created | Storage and use |
|---|---|---|
| Project CI key (`si_...`) | An authorized project administrator selects **Create CI API key** in the CI gate. Studio generates it with Python's cryptographic random source. | Only the SHA-256 hash and a short prefix are stored. The full key is displayed once, then belongs in the GitHub repository's `STRIPE_INSTALLER_API_KEY` secret. It authorizes only that project's `POST /api/v1/ci/readiness/` call. Administrators can revoke it at any time. |
| License key | A verified `checkout.session.completed` billing event with a subscription and domain metadata automatically creates a license. | The key is tied to subscription, customer email, registered domain, status, and instance limit. Subscription deletion revokes it. Deployed instances validate it with `POST /api/v1/license/validate/`. |
| Vault and provider secrets | Created outside Studio by the provider or platform operator. | Stored encrypted in the per-project vault or Railway Variables, never returned as plaintext through normal Studio APIs. |

For CI setup, create the project key in the project workspace, save it immediately, and configure the repository secrets `STRIPE_INSTALLER_URL`, `STRIPE_INSTALLER_PROJECT`, and `STRIPE_INSTALLER_API_KEY`. Studio can display the corresponding GitHub Actions workflow. Do not create CI keys automatically during project creation: a secret that can only be displayed once must be intentionally retrieved and placed in the destination secret store by an authorized administrator.

## Build status and release attribution

| Build | App attribution | Status |
|-------|-----------------|--------|
| Version 2.0 | Account-wide Operations Center: portfolio-wide readiness, release recovery, organization visibility, GitHub connectivity reporting, and secret-free operations reporting. | **100%** |
| Version 1.1 | Portfolio-scale usability: search, readiness and running filters, archive/restore, mobile-friendly controls, and the preserved safety baseline. | **100%** |
| Version 1.0 | Core platform foundation: auth, projects, vault, agency, quality, workflows, transfer, billing, diagnostics, guide, deployment, and customer self-service. | **100%** |
| Migrated Studio data | Project records, run history, settings, and encrypted vault records required for launch are present in production. | **100%** |
| Production readiness | Railway, custom-domain TLS, data, workers, restricted Stripe key, billing, signed webhook, migrations, health checks, and a controlled live Starter purchase are verified. | **100%** |

Green UI indicators mean that available evidence passed. They do **not** prove that Railway, Stripe, DNS, or every external source record has already been changed.

## Three independent products

| Product | Role | Independent operation |
|---------|------|-----------------------|
| AI Software Operations Studio | Unified operations product and optional subscription offering | New Railway service, database, URL, Stripe catalog, and webhook |
| Specwright | Quality/review application | May continue operating and selling independently |
| Deployment-Stripe-center | Deployment and Stripe automation application | May continue operating and selling independently |

Integration does not delete, overwrite, redeploy, or automatically synchronize the two source applications. Keep their services, databases, domains, environment variables, and Stripe webhooks active unless their owner separately approves a retirement.

Recommended public layout:

| Product | Custom domain example | Stripe setup |
|---------|-----------------------|--------------|
| Studio | `studio.example.com` | Separate Product, Prices, endpoint, and signing secret |
| Specwright | `specwright.example.com` | Separate Product, Prices, endpoint, and signing secret |
| Deployment Center | `deploy.example.com` | Separate Product, Prices, endpoint, and signing secret |

All three may use one Stripe account. Distinguish them with separate Products and Prices plus application metadata. Use separate least-privilege restricted keys wherever supported and always verify webhook signatures server-side.

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
| [docs/PRODUCT.md](docs/PRODUCT.md) | Product wedge + ICP |
| [docs/LEGACY-ARCHIVE.md](docs/LEGACY-ARCHIVE.md) | Legacy CLI retirement policy |
| [deploy/COMPLIANCE.md](deploy/COMPLIANCE.md) | SOC 2 readiness + audit retention |
| [docs/STRUCTURE.md](docs/STRUCTURE.md) | Repo layout |
| [docs/AUTOMATION-CENTER.md](docs/AUTOMATION-CENTER.md) | Merge vision + secret rules |
| [docs/CUTOVER.md](docs/CUTOVER.md) | Retire old production apps |
| [docs/MERGE-STATUS.md](docs/MERGE-STATUS.md) | Cutover checklist (live) |
| [docs/RAILWAY.md](docs/RAILWAY.md) | Railway deploy + vault key |
| [docs/DEPLOYMENT-HANDOFF.md](docs/DEPLOYMENT-HANDOFF.md) | Production cutover, split domains, operator runbook |
| [docs/DEMO-SCRIPT.md](docs/DEMO-SCRIPT.md) | 3–5 min stakeholder demo script |
| [docs/GO-LIVE.md](docs/GO-LIVE.md) | Client project → production |
| [docs/PRODUCTION.md](docs/PRODUCTION.md) | Docker prod stack |
| [backend/apps/api_transfer/README.md](backend/apps/api_transfer/README.md) | Transfer API reference |

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
| **Portfolio audit** | Account-wide webhook probe + local report (`~/.stripe-installer/reports/`) — [docs/PORTFOLIO-AUDIT.md](docs/PORTFOLIO-AUDIT.md) |
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

## Architecture

```
backend/          Django — vault, pipeline, stripe_engine, billing, deploy, api_transfer, ai, organizations
frontend/         React — dashboard, agency, vault UI, transfer panel, live pipeline terminal
legacy/node/      Archived Node CLI + Electron (reference only)
~/.stripe-installer/   Local vault master key, portfolio registry, per-project vault mirror (dev)
```

### One database, one vault

| Data | Stored | Exposed via API? |
|------|--------|------------------|
| Stripe keys, deploy tokens | AES-256-GCM in Postgres | **Never** — write-only, masked display only |
| Projects, runs, manifest | Django ORM | Yes (no secret values) |
| Scan / readiness | JSON on `Project` | Yes (sanitized) |

### Where deploy credentials live

Platform tokens (`RAILWAY_API_TOKEN`, `GITHUB_TOKEN`, `RENDER_*`, `FLY_API_TOKEN`) are stored **per project in the vault** — not as Railway service env vars. Optional server-level copies in Railway Variables enable live deploy without per-project setup. See [docs/CUTOVER.md](docs/CUTOVER.md).

### Vault master key (critical on Railway)

Project secrets are encrypted with scrypt + AES-GCM from **`VAULT_MASTER_KEY`**. If the key changes between deploys, stored secrets become undecryptable.

| Environment | Resolution |
|-------------|------------|
| **Railway** | `VAULT_MASTER_KEY` env wins (64-char hex) — see [docs/RAILWAY.md](docs/RAILWAY.md) |
| **Local dev** | `~/.stripe-installer/vault-master-key` (file first; env migrates to file) |

Generate once: `python -c "import secrets; print(secrets.token_hex(32))"`

---

## Quick start

```powershell
.\scripts\setup.ps1          # first time: venv, .env + vault key, migrate, npm
npm run dev                  # backend :8000 + frontend :5173
```

Open **http://127.0.0.1:5173** (API on `:8000`)

**Port already in use?**

```powershell
npm run dev:stop
npm run dev
```

---

## UI (after sign-in)

| Page | Route |
|------|--------|
| Projects dashboard | `/` |
| **Transfer / deploy hub** | `/deploy` — queue metrics, audit chain, migration controls |
| Project workspace | `/projects/{slug}` — vault, pipeline, runs, database, **Transfer panel**, AI, monitoring |
| Project settings | `/projects/{slug}/settings` — paths, git, org assignment, production URL |
| Agency | `/agency` — orgs, members, email invites, GitHub App, org projects |
| GitHub App callback | `/agency/github/callback` |
| Billing | `/billing` — personal + org subscriptions, deployment domain, license keys |

### Demo flow

**First run** — 3-step onboarding: GitHub → Stripe keys → create project.

**Project workspace:** readiness score, live pipeline, vault, AI copilot, diagnostics, codegen, deploy prep, **Transfer panel** (dry-run deploy, provider status), monitoring.

### Agency invites

1. **Agency** → invite by email (admin/owner).
2. **Existing user** — added immediately.
3. **New user** — `/register?invite=TOKEN` (email in prod, or copy link from pending invites).

Dev: invite emails print to the backend console (`EMAIL_BACKEND=console`).

---

## API Transfer module

Merged from the former API Transfer repo into `backend/apps/api_transfer/`.

**UI:** `/deploy` page + **Transfer** tab on each project.

**Worker** (queued Render→Railway migrations):

```powershell
npm run transfer:worker          # continuous
npm run transfer:worker:once     # one batch
```

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/transfer/status/` | Module status |
| GET | `/api/v1/transfer/providers/status/` | Railway / Render / GitHub / Fly readiness |
| GET | `/api/v1/transfer/runs/metrics/` | Queue counts |
| GET | `/api/v1/transfer/audit/` | Tamper-evident audit log |
| POST | `/api/v1/transfer/start/` | Start migration run |
| POST | `/api/v1/projects/{slug}/transfer/deploy/` | Full deploy pipeline |
| POST | `/api/v1/transfer/github/import/` | GitHub repo import |

Full route list: [backend/apps/api_transfer/README.md](backend/apps/api_transfer/README.md)

---

## Production deployment

### Railway (Gilliom production)

Split-domain layout (recommended):

| Host | Role |
|------|------|
| `studio.gilliomfrontlinedigital.com` | React UI (`APP_PUBLIC_URL`) |
| `api.gilliomfrontlinedigital.com` | REST API, WebSockets, SaaS billing webhook (`STUDIO_API_URL`) |

1. Attach **PostgreSQL** plugin → `DATABASE_URL` auto-set.
2. Set **`VAULT_MASTER_KEY`** (64-char hex) — pin once, never rotate without `rotate_vault_key`.
3. Set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, Stripe keys (`SAAS_STRIPE_*`).
4. Custom domains on the **web service**: `studio.*` (UI) and `api.*` (API/webhooks) when ready.
5. Build vars for split frontend (redeploy after change): `VITE_API_BASE=https://api.gilliomfrontlinedigital.com/api/v1`, `VITE_WS_BASE=wss://api.gilliomfrontlinedigital.com`.
6. Stripe webhook (SaaS billing): `https://api.gilliomfrontlinedigital.com/api/v1/billing/webhook/`

Until step 4–5 are complete, production continues on unified routing (`studio.*` + `/api/v1`).

Details: [docs/RAILWAY.md](docs/RAILWAY.md) · [docs/DEPLOYMENT-HANDOFF.md](docs/DEPLOYMENT-HANDOFF.md)

### Docker / self-hosted

```powershell
npm run build:frontend
npm run check:prod
npm run deploy:prod             # build + check + docker prod
```

Stack: Postgres, Redis, Daphne, Celery worker + Beat. Health: `GET /health/`.

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

## License protection (deployed instances)

When you sell this platform as a product, deployed copies validate against your licensing server:

```env
STRIPE_INSTALLER_LICENSE_KEY=<from billing or email>
STRIPE_INSTALLER_DOMAIN=app.client.com
STRIPE_INSTALLER_VALIDATION_SERVER=https://your-licensing-server.com
LICENSE_ENFORCEMENT_ENABLED=true
LICENSE_ENFORCEMENT_MODE=readonly
```

Enforcement is **off by default**. See [backend/apps/licenses/README.md](backend/apps/licenses/README.md).

**Local dev test:**

```powershell
cd backend
python manage.py issue_dev_license --email you@test.com --domain localhost
```

---

## MCP (Cursor)

```powershell
# Copy .cursor/mcp.json.example → .cursor/mcp.json, set your email
cd backend
$env:STRIPE_INSTALLER_USER = "you@example.com"
python manage.py run_mcp_server
```

Tools: `list_projects`, `project_readiness`, `project_drift`, `project_diagnose`, `project_vault_status`, `start_pipeline`, `project_open_pr_prep`

See [docs/MCP.md](docs/MCP.md).

---

## API (base `/api/v1/`)

| Method | Path |
|--------|------|
| POST | `/auth/register/`, `/auth/login/` |
| GET | `/invites/{token}/` |
| GET/POST | `/organizations/`, `.../invite/`, `.../pending-invites/` |
| GET | `/agency/dashboard/` |
| GET/POST | `/projects/` |
| POST | `/projects/{slug}/vault/init/`, `.../vault/keys/set/`, `.../vault/import/` |
| POST | `/projects/{slug}/verify/`, `.../runs/`, `.../diagnose/`, `.../fix/` |
| POST | `/projects/{slug}/clone/`, `.../open-pr/`, `.../deploy/run/` |
| POST | `/projects/{slug}/transfer/deploy/` |
| GET | `/projects/{slug}/readiness/`, `.../audit/` |
| GET | `/transfer/providers/status/`, `/transfer/audit/`, `/transfer/runs/metrics/` |
| GET | `/billing/plans/`, `.../org/subscription/` |
| POST | `/billing/org/checkout/`, `/billing/webhook/` |
| POST | `/webhooks/github/` |
| POST | `/ci/readiness/` |
| POST | `/license/validate/` |
| WS | `/ws/runs/{run_id}/?token={jwt}` |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Dev environment

`backend/.env` (see `backend/.env.example`):

| Variable | Purpose |
|----------|---------|
| `VAULT_MASTER_KEY` | **Required** — 64 hex chars |
| `CELERY_EAGER=true` | Run pipeline in-process (no worker) |
| `CHANNEL_LAYER_INMEMORY=true` | WebSocket without Redis |
| `SAAS_STRIPE_*` / `STRIPE_*` | Platform billing (optional) |
| `GITHUB_APP_*` | GitHub App install + PR checks (optional) |
| `EMAIL_*` / `APP_PUBLIC_URL` | Org invite emails (optional) |
| `STRIPE_INSTALLER_*` / `LICENSE_ENFORCEMENT_*` | License protection (optional) |

Optional local platform tokens: copy `private_env/*.env.example` → `private_env/*.env` (gitignored). See [private_env/README.md](private_env/README.md).

---

## Verify

```powershell
npm run test
npm run smoke
npm run check:prod              # fails in dev mode — expected
cd frontend; npm run build
cd backend; python manage.py verify_cutover
python scripts/run_webhook_auto_repair.py stripe-installer
```

---

## CLI

```powershell
cd backend
python manage.py stripe_core run <project-slug>
python manage.py stripe_core deploy <project-slug> --push
python manage.py rotate_vault_key --new-key <hex> --dry-run
python manage.py check_production
python manage.py verify_cutover
python manage.py issue_dev_license --email you@test.com --domain localhost
python manage.py validate_license_startup
python manage.py transfer_worker --once
```

---

## npm scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Backend + frontend |
| `npm run dev:stop` | Kill processes on ports 8000, 5173 |
| `npm run transfer:worker` | Process queued migration runs |
| `npm run transfer:worker:once` | One migration batch |
| `npm run docker:prod` | Docker Compose prod profile |
| `npm run deploy:prod` | Build frontend, check env, start Docker prod |
| `npm run check:prod` | Production env validation |

---

## Legacy Node CLI

The v0.6 CLI and Electron app live in [`legacy/node/`](legacy/node/README.md) for reference only.

---

## Repository

GitHub: [dallas8000-ops/AI-Software-Operations-Studio](https://github.com/dallas8000-ops/AI-Software-Operations-Studio)

Use pull requests to merge the active build branch into the default branch. Never commit `.env` files, vault master keys, Stripe secrets, webhook signing secrets, Railway tokens, database URLs, or GitHub tokens.
