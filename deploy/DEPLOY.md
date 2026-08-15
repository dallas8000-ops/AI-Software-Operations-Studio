# Deployment Guide

Platform: **railway**
Framework: **django**
Production URL: https://studio.gilliomfrontlinedigital.com

## Pre-deploy checklist
1. Run readiness — aim for 80+ score
2. Switch to **live** Stripe keys in vault
3. Set DATABASE_URL and apply schema
4. Set production URL in project settings

## Environment variables
```
NODE_ENV=production
APP_PUBLIC_URL=https://studio.gilliomfrontlinedigital.com
STRIPE_SECRET_KEY=sk_live_
STRIPE_PUBLISHABLE_KEY=pk_live_
STRIPE_WEBHOOK_SECRET=whsec_
DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require
```

## Deploy
```bash
railway up
```

## Post-deploy
1. Verify SSL: https://studio.gilliomfrontlinedigital.com
2. Test health: https://studio.gilliomfrontlinedigital.com/health/
3. Register production Stripe webhook
4. Schedule backups: scripts/backup-db.sh
