# Deployment and operations

The application has a Django web process, PostgreSQL database, Redis broker, Celery worker and a single Celery beat scheduler. The frontend is a static Vite build. Use an HTTPS edge and a same-origin `/api` proxy so rotating refresh cookies remain HttpOnly, Secure and SameSite=Lax. No JWT is placed in browser persistent storage.

## Local Docker

Copy `.env.example` to `.env` only if `.env` does not exist. Generate a random `DJANGO_SECRET_KEY`, choose a PostgreSQL password, and put the matching credentials in `DATABASE_URL`. Development defaults use `DEBUG=true` and console email. They are not production settings.

```sh
docker compose up --build -d
docker compose exec -e DEMO_PASSWORD='Local!Office!Seed!2026' backend python manage.py seed_demo
docker compose exec backend pytest -q
docker compose exec frontend npm test
docker compose exec frontend npm run build
docker compose exec frontend npm run check:budget
```

Services are `backend`, `frontend`, `db`, `redis`, `worker`, and `beat`. The normal Compose file runs Vite for development. Only development ports are published; PostgreSQL and Redis are private to the Compose network. Do not seed development identities into a production database.

The production frontend Dockerfile builds immutable assets and serves them through Nginx on port 8080 with SPA fallback, gzip, cache policies and security headers. `compose.production.yaml` is an override, used behind a TLS ingress that replaces `X-Forwarded-Proto` and prevents untrusted direct access to the private application network:

```sh
docker compose -f compose.yaml -f compose.production.yaml build
docker compose -f compose.yaml -f compose.production.yaml run --rm backend python manage.py migrate --noinput
docker compose -f compose.yaml -f compose.production.yaml up -d
```

Set `DEBUG=false`, `TRUST_PROXY=true`, actual HTTPS frontend origins and allowed hosts in production. Nginx forwards the ingress's protocol header; access without HTTPS is redirected by Django. An HTTP-only invocation of this production stack is deliberately not a working production deployment. Use local development Compose for HTTP testing. Use Docker Compose 2.24.4 or later for `!reset`/`!override` in the production override.

This cloud machine cannot resolve external package registries inside Docker build containers. That has been reproduced independently of the Dockerfiles. Native installation and application validation pass; full image builds require a Docker host with registry and OS-package network access. Package signature and TLS verification have not been disabled.

## Render / Railway backend and workers

1. Create managed PostgreSQL (or a Supabase project) and a Redis service supporting Celery's Redis protocol/commands. Use the provider's TLS connection URLs. `DATABASE_URL` must use an appropriate direct/session connection for Django migrations; follow the provider's current pooling limits and TLS instructions.
2. Create a web service from `backend/Dockerfile`. Its start command is the image's Gunicorn command. Set the real `DJANGO_SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `ALLOWED_HOSTS`, `FRONTEND_ORIGINS`, `DEBUG=false`, and SMTP settings in provider-managed secret/environment settings. No secret belongs in Git. `FRONTEND_ORIGINS` is a comma-separated list of actual HTTPS frontend origins and also supplies trusted CSRF origins and email-link destinations; put the canonical frontend first.
3. Run `python manage.py migrate --noinput` as the platform's release/predeploy command. Run `python manage.py check --deploy` with production settings. HSTS preload is intentionally not automatic; decide whether to submit your own domain after confirming HTTPS on all subdomains.
4. Run a background worker using the same backend image and environment: `celery -A config worker --loglevel=INFO --concurrency=2`. Run **one** scheduler: `celery -A config beat --loglevel=INFO --schedule=/tmp/celerybeat-schedule`. Persist the broker volume/service and take database backups. Email delivery rows are retained in PostgreSQL, with bounded retries; the dispatcher recovers pending deliveries after broker outages.
5. Use SMTP credentials and a verified sender domain. Console email is for local development only. A successful Celery console delivery does not establish external SMTP deliverability. Test a real invitation and notice after configuring your provider.
6. Configure the hosting edge to replace forwarded headers. Enable `TRUST_PROXY` only behind that edge. Keep backend/worker networking private where supported and use separate production/development databases.

Free plans and trials change. A free Render web service can sleep; it does not supply a free always-on Celery worker. Railway trials are not a permanent free production guarantee. Supabase and static frontend providers may offer free quotas, but an always-on worker, scheduler, Redis and reliable backups can require paid hosting or a self-managed machine. Do not deploy a workerless configuration and claim automatic reminders work.

## Vercel / Netlify frontend

The root `frontend` directory contains the package and lockfile. Use Node 24, `npm ci`, build command `npm run build`, and output directory `dist`. Configure SPA route fallback and an HTTPS same-origin API proxy; Vite's development proxy does not exist in the deployed build.

Once the actual backend origin exists, set a local non-secret `BACKEND_URL` variable to that HTTPS origin, with no path. Generate the matching host configuration:

```sh
node scripts/configure-static-host.mjs "$BACKEND_URL" vercel
# Or:
node scripts/configure-static-host.mjs "$BACKEND_URL" netlify
```

The script validates the origin and writes a complete `frontend/vercel.json` or `frontend/netlify.toml`, including the API proxy, SPA rewrite, CSP and security headers. Set the hosting project's root/base directory to `frontend`. Add its real HTTPS origin to the backend's `FRONTEND_ORIGINS`, and configure the backend's allowed host. The proxy must preserve `Set-Cookie`, cookie paths, CSRF headers and request bodies. Cookie domain is intentionally unset, so the frontend origin owns the refresh cookie. There is no public build-time API key.

## Release checks

- Run backend permission tests, frontend tests, schema validation, type checking, build and `npm run check:budget`.
- Use HTTPS and verify Secure/HttpOnly/SameSite refresh cookies, `/api/auth/` cookie path, token rotation and logout.
- Verify the active-role switch changes API authorization, and a foreign-tenant object yields no data.
- Exercise an invitation, a notice delivery, an attendance save, a held report, a fee payment, and scheduled reminders with production test identities.
- Inspect `EmailDelivery` pending/failed counts and worker/scheduler health. SMTP retries stop after six failed sends; investigate and reset failed rows only after correcting the delivery configuration.
- Use `python manage.py flushexpiredtokens` regularly. Define retention for consumed password grants, authentication-attempt metadata, audit logs and backups according to institutional policy.
- Verify database restores using a separate environment. Pin provider/network configuration as well as application dependencies. Updates are migrations plus an immutable frontend release; back up before schema changes.

## Export and deletion

An administrator can download a ZIP of tenant CSV files from Settings. Export excludes password hashes, password-reset grants and JWTs, escapes spreadsheet formulas, and scopes every data table to the selected institution. Treat exports as sensitive. Medical access and the export action are auditable.

Student deletion is soft by default. Permanent student deletion requires an administrator and exact admission-number confirmation; dependent domain records are explicitly removed and audit history is retained. Institution deletion requires typing `DELETE` plus its exact name and removes tenant-owned data transactionally. Global accounts with no other institution are deactivated; shared accounts and other institutions remain intact. Retention/erasure of hosting backups is a separate provider operation. Verify legal retention obligations before using permanent deletion in production.

## PWA and performance verification

Install the manifest from an HTTPS origin (localhost is permitted for development). App-shell files and low-sensitivity lookup/config responses are cached; medical, profile, marks, report, notification and payment APIs are excluded. Attendance outbox records use IndexedDB and contain membership IDs, student IDs, statuses, dates and revisions, never JWTs. They are replayed only for the selected membership and fully reauthorized on the server. Conflicts remain visible for reconciliation/discard. Signing in and bootstrapping a fresh session require the network.

Run `npm run build && npm run check:budget` in `frontend`. The script resolves the manifest's login/dashboard dependency graph, including shared chunks and service-worker scripts, and fails at 180,000 gzipped JavaScript bytes. Lazy module chunks are cached when visited, not downloaded indiscriminately during initial login.

For Lighthouse, serve the production build with the API proxy and actual trusted frontend origin configured, run a cold mobile navigation, and record the Lighthouse version, throttling settings, browser and server conditions. Measure login and an authenticated dashboard separately. Repeat with the deployment's real latency and hardware; cloud localhost measurements do not guarantee every device's timing. Test attendance toggle input-to-paint under CPU slowdown and require under 100 ms. Check 360/768/1280 layouts, English/Malayalam, light/dark themes, keyboard focus, screen-reader labels, error states, font scaling and reduced motion. Automated Axe results supplement a manual accessibility review rather than certify universal compliance.
