# Railway portfolio split — manual runbook only

**Status:** There is no reliable automated split in Studio. A prior attempt (`split_railway_portfolio`, Deploy UI panel) was **removed** because it did not complete cutover: Postgres, URLs, and database copy require manual Railway dashboard steps.

Production SilverFox today: **`hearty-enjoyment`** hub, URL `https://silverfox-production.up.railway.app`.

An orphan Railway project **`silverfox`** may exist from the failed attempt (web + Postgres, no public URL). Delete it in the Railway dashboard when you are ready — it is not serving traffic.

---

## Why automation failed

| Step | What automation tried | What actually works |
|------|----------------------|---------------------|
| Postgres | `serviceCreate` + Docker image | Railway **Postgres template** in dashboard (“Add PostgreSQL”) |
| Public URL | Copied domain names in plan only | **Networking → Generate domain** on the new service |
| Database | `pg_dump` in split command | Manual copy with Docker running, or Railway Data panel |
| Cutover | Optional “delete from hub” | Manual order: copy DB → test new URL → attach domain → delete hub |

Deleting the hub service **does not** move the URL or database to the new project.

---

## Manual split checklist (per app)

Do this in the **Railway dashboard** and Studio vault. Repeat for each app leaving `hearty-enjoyment`.

### 1. Create new Railway project

- Railway → **New Project** → name after catalog slug (e.g. `silverfox`)
- **New Service** → connect same GitHub repo / branch as hub copy
- Match root directory and build settings from the hub service

### 2. Add Postgres in the new project

- In the new project: **+ New** → **Database** → **PostgreSQL**
- Name it to match env references (e.g. `PostgreSQL-silverfox` for SilverFox)
- Wait until **Variables** shows `DATABASE_URL` (real `postgresql://…`, not empty)

### 3. Copy environment variables

- Hub service → **Variables** → copy app vars (not `RAILWAY_SERVICE_*` sibling URLs)
- New web service → paste vars
- Set `DATABASE_URL` to `${{PostgreSQL-silverfox.DATABASE_URL}}` (use your Postgres service name)

Studio (after you have new IDs):

```powershell
cd backend
python manage.py push_railway_env silverfox --project-id <new-project-uuid> --service-id <new-web-service-uuid>
```

### 4. Copy database data

With **Docker Desktop running**:

```powershell
# From hub public DATABASE_URL → new project public DATABASE_URL
docker run --rm postgres:16-alpine pg_dump --no-owner --no-acl "<HUB_DATABASE_URL>" | docker run --rm -i postgres:16-alpine psql "<NEW_DATABASE_URL>"
```

Or use Railway **Data** panel on both databases.

### 5. Generate URL on the new service

- New web service → **Settings** → **Networking** → **Generate domain**
- Test: `curl https://<new-domain>/health/` and `/shop/` (SilverFox)

### 6. Cut over production URL (optional: keep same hostname)

Railway hostnames attach to **one** service at a time.

**Safe order:**

1. New project works on its **new** `*.up.railway.app` URL (step 5)
2. Delete **hub** web service (frees `silverfox-production.up.railway.app` if that was its domain)
3. New web service → **Networking** → generate domain again (may reclaim same name) or add custom domain
4. Update `portfolio_catalog.py` / vault if URL changed
5. Delete hub Postgres after confirming new DB has data

### 7. Update Studio vault

```powershell
python manage.py push_railway_env <slug> --project-id <new-project-uuid> --service-id <new-web-service-uuid>
python manage.py reconfirm_portfolio_links --save-report
```

### 8. Remove hub duplicate

- Delete old web + Postgres services from `hearty-enjoyment`
- Disconnect GitHub deploy from hub copy so pushes only hit the new project

---

## What stays in `hearty-enjoyment`

- **Elite Fintech** (`elite-fintech-systems-*`) — intentional hub resident
- **Operations Studio** (`operations-studio-*`)
- **AgriPay** — already standalone project `agripay-logistics-ai`

---

## Suggested migration order

1. Demos: `silverfox`, `kistie-store`, `blog-2`, `react-store-catalog`
2. Standalone: `pc-checker-extreme`, `enpowercommand`, `righand`
3. Monorepos: `specwright`, `dbops-control-center`, `eastbridge-ops`

Use a maintenance window. Verify each app before deleting hub copies.
