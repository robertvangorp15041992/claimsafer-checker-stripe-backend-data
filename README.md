# ClaimSafer Membership Backend

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.sample .env
uvicorn app.main:app --reload
```

## Stripe CLI test

```bash
stripe login
stripe listen --forward-to localhost:8000/webhook/stripe
# then complete a test Checkout on the marketing site
```

## Testing

```bash
pytest -q
```

## Railway deploy

Set env vars (DATABASE_URL Postgres, SMTP creds, Stripe keys), then deploy image. 

# Step 3: User DB & Usage

## Schema Overview
- **Users**: email (unique, normalized), tier, is_active, password_hash, stripe_customer_id, created/updated timestamps
- **UsageCounter**: user_id, date (UTC), daily_checks_used (unique per user/date)

## Email Normalization
All emails are stored and queried as `email.strip().lower()`. This ensures uniqueness and prevents duplicates with case/space variants.

## Entitlements
Loaded from `app/entitlements.yaml` at startup. Each tier defines daily limits and features. Use the entitlements service to fetch limits for a user's tier.

## Usage Endpoints

Get your plan:
```bash
curl -H "X-Debug-Email: you@example.com" http://localhost:8000/me/plan
```

Get your usage:
```bash
curl -H "X-Debug-Email: you@example.com" http://localhost:8000/me/usage
```

Increment usage (daily check):
```bash
curl -X POST -H "X-Debug-Email: you@example.com" http://localhost:8000/me/usage/increment
```

If you exceed your daily limit, you'll get a 402/403 error with `{detail: "Upgrade required"}`.

## Admin Endpoints
Set `ADMIN_API_KEY` in your environment. Then:
```bash
curl -H "admin-api-key: <your-key>" http://localhost:8000/admin/users
```

## Cron/Reset
For daily resets, POST to `/internal/cron/daily-reset` (if implemented) or rely on date rollover. 

# Step 4: Membership Upsert Pipeline

## What it does
- On successful Stripe payment (checkout.session.completed, invoice.payment_succeeded, subscription.updated/deleted), the app creates or updates a user’s membership.
- Deduplicates by normalized email, links stripe_customer_id, and sets the highest tier from all price IDs.
- All changes are logged in the MembershipAudit table for traceability.

## Which events call which upsert function?
- `checkout.session.completed` → `upsert_membership_from_checkout`
- `customer.subscription.updated`/`deleted` → `upsert_membership_from_subscription`

## How tier is decided
- Each Stripe Price ID is mapped to a Tier via `PRICE_TO_TIER` in billing.py.
- If multiple price IDs, the highest tier is chosen (free < starter < pro < enterprise).
- If no price IDs match, the default tier is used.

## Where to see history
- All membership changes are recorded in the `membership_audit` table (email, old/new tier, event, reason, timestamp).

## Reminder
- Set your real Stripe Price IDs in `billing.py` for production. 

# Step 5: Onboarding & Login

## Flow
- Payment → webhook → onboarding email
- User clicks activate link → sets password
- Login at /login or use magic link

## Example curl
```bash
curl -X POST -F "email=test@example.com" -F "password=secret123" http://localhost:8000/login
```

## Session
- Session cookies are set on login/magic link (HttpOnly, SameSite=Lax, Secure if HTTPS)
- Access /dashboard to see your user info

## Magic Link
- POST /auth/magic-link with email to receive a login link
- GET /auth/magic-login?token=... to log in 

# Step 9: Production Hardening

## Health Checks
- `/healthz`: liveness (no external calls)
- `/readyz`: readiness (DB, SMTP, Stripe)
- Use for Railway/Kubernetes probes

## Metrics
- `/metrics`: Prometheus endpoint (http_requests_total, http_request_duration_seconds, webhook_events_total, emails_sent_total)
- Scrape with Prometheus or hosted collector

## Logging
- Structured JSON logs with request IDs, redacted secrets
- Wire logs to Railway, Loki, Datadog, etc.

## Security
- HSTS, CSP, X-Frame-Options, etc. (configurable via env)
- Strict CORS

## Background Tasks
- Email and post-webhook work run in a background queue with retries
- Failures are logged

## Webhook Replay
- POST `/internal/replay-webhook` (admin-only) to safely reprocess a stored event

## Example
```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
curl http://localhost:8000/metrics
```

## Env
```
ENABLE_HSTS=true
CSP=default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'
READINESS_STRIPE_CHECK=true
``` 