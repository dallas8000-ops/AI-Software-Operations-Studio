# Demo script — Agency onboards EastBridge to production (3–5 min)

Use this script to record a screen capture for stakeholders. Replace spoken names if you use a different demo project.

**URLs**

- Studio UI: https://studio.gilliomfrontlinedigital.com/login
- Demo project: **EastBridge Ops Intelligence** (`eastbridge-ops`)
- Live client app: https://eastbridge.gilliomfrontlinedigital.com

**Prerequisites before recording**

- Logged-in operator account (agency org)
- EastBridge project already exists with vault Stripe test keys (or create fresh — add ~2 min)
- Celery worker running (pipeline steps complete in background)

---

## Recording setup

| Setting | Recommendation |
|---------|----------------|
| Resolution | 1920×1080 |
| Tool | OBS, Loom, or Windows Game Bar (Win+G) |
| Audio | Short intro + optional voiceover on key clicks |
| Browser | Chrome, zoom 100%, hide bookmarks bar |
| Duration target | **3:30–4:30** (sections marked with ⏱) |

---

## Scene 1 — Problem & product (0:00–0:30) ⏱ 30s

**Show:** Studio login page → dashboard after login.

**Say:**

> "Gilliom Frontline Digital runs many client apps on Railway with Stripe billing. Operations Studio is where an agency connects a repo, stores Stripe keys safely, runs automated setup, and monitors webhooks — without hand-editing dashboards for every client."

**Click:** Projects list — briefly scroll so **EastBridge Ops Intelligence** is visible.

---

## Scene 2 — Open the client workspace (0:30–1:00) ⏱ 30s

**Show:** Click **EastBridge Ops Intelligence** → project overview.

**Say:**

> "Each client is a workspace. Secrets never appear in git — they live in an encrypted vault per project."

**Click:** Expand or open **Secure vault** (show locked state or "keys configured" — do not reveal key values).

**Highlight on screen:**

- Production URL pointing at `eastbridge.gilliomfrontlinedigital.com`
- Stripe config / deploy config tabs exist

---

## Scene 3 — Run the automation pipeline (1:00–2:15) ⏱ 75s

**Show:** Pipeline section → select **Run full setup** (or **Readiness** if already run).

**Say:**

> "Full setup clones the repo, validates Stripe products against our manifest, registers webhooks at the client's production URL, and scores readiness for go-live."

**Click:** Start run.

**Show:** Live pipeline log via WebSocket (steps turning green). If slow, jump cut after 20–30s of real progress.

**Highlight:** A step like `webhook.register` or `readiness.score` completing.

**Optional cut:** Jump to completed run with readiness score ≥ 80.

---

## Scene 4 — Monitoring & webhook health (2:15–3:15) ⏱ 60s

**Show:** Scroll to **Monitoring** panel.

**Say:**

> "Stripe delivery errors are common after URL or secret drift. Studio reads real delivery stats from Stripe and can auto-repair — rotate the signing secret, update the vault, and push to Railway."

**Click:** **Webhook health**

**Show panel data:**

- Expected URL (EastBridge: `…/webhooks/stripe/` on client domain)
- Delivery success rate (or "no recent activity" for quiet projects)
- Live probe classification

**If `autoRepairRecommended` appears:** Click **Auto-repair webhook** → show success toast / updated probe.

**For hub demo (optional 15s):** Switch to **Deployment & Stripe Automation Center** (`stripe-installer`) and show expected URL = `https://api.gilliomfrontlinedigital.com/api/v1/billing/webhook/`

---

## Scene 5 — Real business outcome (3:15–4:15) ⏱ 60s

**Show:** Open new tab → https://eastbridge.gilliomfrontlinedigital.com

**Say:**

> "This is the live EastBridge product — EU to East Africa trade intelligence. Studio didn't replace their app; it operationalized Stripe and deployment from the agency side."

**Demonstrate one user-visible action** (pick one that works in your build):

- Login / dashboard loads
- Demo route or health endpoint
- Billing or subscription UI if enabled

**Return to Studio tab** → **Audit log** in Monitoring (last few entries: `pipeline.run`, `webhook.repair`, etc.)

---

## Scene 6 — Close (4:15–4:30) ⏱ 15s

**Show:** Dashboard or Platform card noting split domains.

**Say:**

> "Studio UI lives at studio dot gilliom frontline digital dot com; API and SaaS billing webhooks at api dot the same domain. One Railway stack, operator-grade monitoring, clients self-register and subscribe without us creating accounts by hand."

**End card (optional overlay):**

- Studio: studio.gilliomfrontlinedigital.com
- Docs: repo `docs/DEPLOYMENT-HANDOFF.md`

---

## B-roll checklist (if main flow fails mid-record)

- [ ] `/health/` on api host returning `"status":"ok"`
- [ ] Stripe Dashboard → Webhooks → successful delivery row
- [ ] Billing page → Subscribe button (Studio SaaS flow)
- [ ] `python scripts/run_webhook_auto_repair.py stripe-installer` terminal output

---

## One-line summary for email / README

> "Watch how an agency connects EastBridge on Railway, runs full Stripe setup from Operations Studio, verifies webhook health with auto-repair, and opens the live client app — in under five minutes."
