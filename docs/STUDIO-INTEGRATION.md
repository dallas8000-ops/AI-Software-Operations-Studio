# AI Software Operations Studio integration

The Studio is a staged consolidation. Existing Deployment Center and Specwright production services remain independent until a verified cutover.

## Current foundation

- Deployment Center remains the Django control plane and encrypted credential boundary.
- The React shell provides Studio, Projects, Quality, Workflows, Deploy, Agency, and Billing surfaces.
- `apps.quality` is a read-only adapter to Specwright's `/api/v1/dashboard` endpoint.
- The adapter does not copy secrets, mutate Specwright, or require a shared database.
- Missing or unavailable Specwright services return a safe `connected: false` response rather than failing the Studio.

## Local connection

Run Specwright separately on port 8080 and set:

```env
SPECWRIGHT_API_URL=http://127.0.0.1:8080/api/v1
SPECWRIGHT_API_TIMEOUT_SECONDS=3
```

The Studio endpoint is authenticated and read-only:

```text
GET /api/v1/quality/summary/
```

Project Settings can store a database-local identity link without contacting Specwright:

```text
GET | PUT | DELETE /api/v1/projects/{slug}/quality/link/
GET /api/v1/projects/{slug}/quality/health/
```

The link records the numeric Specwright project ID and an optional display name. It is ownership-aware, one-to-one, and does not trigger a scan. The health endpoint reads and normalizes the linked project's score, documentation and test coverage, gaps, route count, freshness, and drift status for the Studio project workspace.

## Migration boundary

Do not point the adapter at production until local and staging validation pass. This phase does not change Railway services, databases, domains, Stripe webhooks, Checkout URLs, or customer data.

Project identity mapping is now in place. Only after local and staging validation should scan triggering be considered, and scan triggering must remain an explicit user action.

## Prepare for Production preflight

The Workflows page evaluates existing repository analysis, Specwright quality, project configuration, and operational readiness. Deployment reaches the human approval stage only when quality and readiness evidence pass.

The preflight does not run scans, generate files, provision services, modify Stripe, migrate data, or deploy.
