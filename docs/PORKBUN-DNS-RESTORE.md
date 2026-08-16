# Porkbun DNS restoration template

Use this checklist to restore `gilliomfrontlinedigital.com` DNS in Porkbun and
verify that each custom hostname is attached to the correct Railway service.

Last live check: **2026-08-16**.

## Current failure

- `gilliomfrontlinedigital.com`: DNS does not resolve.
- `www.gilliomfrontlinedigital.com`: attached in Railway but waiting for DNS ownership validation.
- `api.gilliomfrontlinedigital.com`: DNS does not resolve and is not currently attached in Railway.
- `studio.gilliomfrontlinedigital.com`: resolves and returns HTTP 200 from Railway.
- The marketing app is healthy at `https://frontlinedigital-1-production.up.railway.app`.

## Before changing Porkbun

In Railway, open the intended web service and go to **Settings -> Networking ->
Custom Domain**. Railway's displayed DNS target is authoritative. Do not copy a
service's public `*.up.railway.app` URL unless Railway explicitly gives that URL
as the custom-domain target.

The current service assignments are:

| Hostname | Railway project | Railway service | Service ID |
|---|---|---|---|
| `gilliomfrontlinedigital.com` | `hearty-enjoyment` | `FrontLineDigital-1` | `6592cd9b-10b8-4b0b-9d7f-9d56d4e64365` |
| `www.gilliomfrontlinedigital.com` | `hearty-enjoyment` | `FrontLineDigital-1` | `6592cd9b-10b8-4b0b-9d7f-9d56d4e64365` |
| `studio.gilliomfrontlinedigital.com` | `hearty-enjoyment` | `operations-studio-web` | `0b3a6f73-90e0-4b2e-b3cc-d741bccb8c9b` |
| `api.gilliomfrontlinedigital.com` | Not attached | Attach to `operations-studio-web` before adding DNS | - |

## Records to restore now

In **Porkbun -> Domain Management -> gilliomfrontlinedigital.com -> DNS**, make
the records match this table. Porkbun may call the apex CNAME an `ALIAS` or
flattened `CNAME`.

| Type | Host | Answer / value | TTL | Status |
|---|---|---|---|---|
| `CNAME` or `ALIAS` | `@` | `2nxhdyxx.up.railway.app` | `600` or default | Required; Railway currently reports `REQUIRES_UPDATE` |
| `TXT` | `_railway-verify` | `railway-verify=f30ada098fec51f209241a34f5178b5ba4ffe4478bcf71b200e95bf4ea15d2ba` | `600` or default | Required for Railway verification |
| `CNAME` | `www` | `rapldseu.up.railway.app` | `600` or default | Required; newly attached in Railway |
| `TXT` | `_railway-verify.www` | `railway-verify=38251b654933edf76f1a6663a21c72ca486e1bf6d73150e899f9a06ca1476f52` | `600` or default | Required for `www` ownership validation |
| `CNAME` | `studio` | `esj0sqq6.up.railway.app` | `600` or default | Keep; currently working |

Delete conflicting records for the same host:

- Any root `A` or `AAAA` record for `@`, including the stale `69.46.46.126` record.
- Any other root `CNAME` or `ALIAS` that does not target `2nxhdyxx.up.railway.app`.
- Any duplicate `studio` record that does not target `esj0sqq6.up.railway.app`.
- Stale `api-transfer` CNAME to `ovnxemb3.up.railway.app`.

Do not delete unrelated email records such as `MX`, SPF, DKIM, or DMARC.

## `www` hostname

`www.gilliomfrontlinedigital.com` was added to `FrontLineDigital-1` on
2026-08-16. Add both `www` records from the table above. Railway currently
reports `verified=False` and `VALIDATING_OWNERSHIP`; this should change after
Porkbun publishes the CNAME and TXT records.

## Restore the `api` hostname

`api.gilliomfrontlinedigital.com` is referenced by Studio configuration, but it
is not currently attached to a Railway service. An API creation attempt on
2026-08-16 returned Railway's generic `Failed to create custom domain` error.
Restore it in this order:

1. Railway -> `hearty-enjoyment` -> `operations-studio-web` -> **Settings -> Networking**.
2. Add custom domain `api.gilliomfrontlinedigital.com`.
3. Copy Railway's displayed CNAME target and any verification TXT record.
4. In Porkbun, add `CNAME` host `api` with that exact target.
5. Wait for Railway to show the domain and certificate as valid.
6. Verify `https://api.gilliomfrontlinedigital.com/health/` returns HTTP 200.

Both `studio` and `api` may point to the same Railway web service. They can have
different Railway edge targets, so use the value Railway provides for each one.

## Porkbun review template

Use this table when reviewing the DNS screen. Fill in the Railway target before
adding optional custom hostnames.

| Type | Host | Expected value | Keep / remove | Verified |
|---|---|---|---|---|
| `CNAME` / `ALIAS` | `@` | `2nxhdyxx.up.railway.app` | Keep | [ ] |
| `TXT` | `_railway-verify` | `railway-verify=f30ada098fec51f209241a34f5178b5ba4ffe4478bcf71b200e95bf4ea15d2ba` | Keep | [ ] |
| `CNAME` | `studio` | `esj0sqq6.up.railway.app` | Keep | [ ] |
| `CNAME` | `www` | `rapldseu.up.railway.app` | Keep | [ ] |
| `TXT` | `_railway-verify.www` | `railway-verify=38251b654933edf76f1a6663a21c72ca486e1bf6d73150e899f9a06ca1476f52` | Keep | [ ] |
| `CNAME` | `api` | Fill from Railway after attaching domain | Add later | [ ] |
| `A` / `AAAA` | `@` | Any value | Remove | [ ] |
| `CNAME` | `api-transfer` | `ovnxemb3.up.railway.app` | Remove | [ ] |

## Verification

DNS changes can take time to propagate. Check authoritative results before
testing only in a browser, because browser DNS caches can retain old failures.

```powershell
Resolve-DnsName gilliomfrontlinedigital.com
Resolve-DnsName www.gilliomfrontlinedigital.com
Resolve-DnsName studio.gilliomfrontlinedigital.com -Type CNAME
Resolve-DnsName api.gilliomfrontlinedigital.com -Type CNAME

Invoke-WebRequest https://gilliomfrontlinedigital.com -UseBasicParsing
Invoke-WebRequest https://studio.gilliomfrontlinedigital.com/health/ -UseBasicParsing
Invoke-WebRequest https://api.gilliomfrontlinedigital.com/health/ -UseBasicParsing
```

From the repository root, Railway can reprint the currently required apex
records:

```powershell
backend\.venv\Scripts\python.exe backend\manage.py fix_gilliom_domain
```

Expected final result:

- Apex and `www` open the FrontLineDigital portfolio.
- `studio` opens Operations Studio and `/health/` returns HTTP 200.
- `api` reaches the same Operations Studio service and `/health/` returns HTTP 200.
- Railway reports each attached custom domain as verified with a valid certificate.