# AI Software Operations Studio

AI Software Operations Studio is a protected Django and React workspace for managing software projects, quality evidence, Stripe configuration, and production deployments. It integrates selected capabilities from **Specwright** and **Deployment-Stripe-center** while allowing both source applications to remain independent products.

Secrets are write-only from the browser, encrypted server-side, masked in API responses, and excluded from Git. Production credentials belong in Railway Variables or a protected vault, not source code, frontend code, prompts, or logs.

Version 2.0 is the current production release. This README now documents the merged Operations Center experience, while Version 1 launch and cutover details live in [docs/OPERATIONS-HISTORY.md](docs/OPERATIONS-HISTORY.md).

> **At a glance**
> - **What:** an operations control plane for software agencies: projects, encrypted secrets, Stripe billing, quality evidence and guarded deployments in one protected workspace.
> - **Stack:** Django 5 + DRF · React 18 + TypeScript (Vite) · PostgreSQL · Celery + Redis · Docker · Railway
> - **Security:** AES-256-GCM per-project vault (write-only from the browser, masked in every API response) · TOTP MFA · org RBAC · Stripe webhook signature verification · CI secret-leak gate and dependency audit
> - **Quality:** 230+ backend tests, Django checks, smoke test and production Docker image validation on every push
> - **Pricing:** Starter $9/month · Pro $79/month · Enterprise: contact sales
> - **Live:** https://studio.gilliomfrontlinedigital.com

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

## Feature areas

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


## API Transfer module

Provider migration and deployment (Railway, Render, Fly.io) with an audit log and an explicit approval gate. This module is shared with [Deployment-Stripe-center](https://github.com/dallas8000-ops/Deployment-Stripe-center); its API reference lives in [backend/apps/api_transfer/README.md](backend/apps/api_transfer/README.md).

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


## Verify

```powershell
npm run test
npm run smoke
npm run check:prod              # fails in dev mode — expected
cd frontend; npm run build
cd backend; python manage.py verify_cutover
python scripts/run_webhook_auto_repair.py stripe-installer
```


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


## More documentation

Release history, launch notes and deployment lineage: [docs/OPERATIONS-HISTORY.md](docs/OPERATIONS-HISTORY.md). MCP tools: [docs/MCP.md](docs/MCP.md).

## Repository

GitHub: [dallas8000-ops/AI-Software-Operations-Studio](https://github.com/dallas8000-ops/AI-Software-Operations-Studio)

Changes land on `main` through pull requests, gated by CI. Never commit `.env` files, vault master keys, Stripe secrets, webhook signing secrets, Railway tokens, database URLs, or GitHub tokens.
