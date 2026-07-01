# Studio data migration status

Source databases are opened read-only. Every apply operation creates a timestamped backup under `backend/.migration-backups/` before changing the Studio SQLite database.

## Completed locally

| Data | Migrated | Validation |
|---|---:|---|
| Project records and settings | 12 | Paths, Git URLs, production URLs, framework, language, and cached scan metadata |
| Pipeline runs | 103 | Original run UUIDs and project relationships preserved |
| Pipeline logs | 1,618 | Original run relationships and timestamps preserved |
| Project vaults | 12 | Source project salts preserved |
| Encrypted secrets | 88 | 88/88 decryptable with the Studio master key; plaintext never printed |
| Specwright identity links | 2 | DBOps → project 1; Elite Fintech → project 2 |
| Specwright quality data | Read-only connection | 3 projects, 222 scans, 1,332 artifacts remain in the Specwright database |

The local Specwright fallback reports an average score of 88. DBOps reports 85 across 91 routes; Elite Fintech reports 89 across 43 routes.

## Not yet migrated

- User/account identity and password ownership
- Organizations and memberships
- Studio subscription ownership records
- Production PostgreSQL data, Railway services, or Redis
- Stripe customers, products, prices, subscriptions, or webhooks (these remain in Stripe)
- Production domains and traffic

These items require explicit identity mapping and staging validation. They should not be inferred from local numeric user IDs.

## Commands

Read-only inventory:

```powershell
backend\.venv\Scripts\python.exe scripts\audit-migration-sources.py `
  "C:\Software Projects\Deployment-Stripe-center\backend\db.sqlite3" `
  "C:\Software Projects\Specwright\specwright.db" `
  "backend\db.sqlite3"
```

Dry-run project, history, and vault selection:

```powershell
cd backend
.venv\Scripts\python.exe manage.py import_studio_projects `
  --source-db "C:\Software Projects\Deployment-Stripe-center\backend\db.sqlite3" `
  --specwright-db "C:\Software Projects\Specwright\specwright.db" `
  --source-owner-id 4 `
  --owner-email studio-review@example.local `
  --include-runs --audit-vault
```

Vault import is intentionally non-overwriting: `--include-vault` refuses to run if target projects already contain secrets.
