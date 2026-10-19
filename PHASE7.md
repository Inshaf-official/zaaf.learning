# Phase 7 — delivery, PWA, performance and security

Files: PWA worker/config/manifest icons/pattern, `PwaUpdate`, `InstitutionLogo`, `Settings`, profile insights, audit/export/deletion APIs, security tests, production Docker/Nginx/Compose configuration, `scripts/configure-static-host.mjs`, `frontend/scripts/check-budget.mjs`, cloud helper updates, deployment documentation and resolved lockfiles. Source was formatted with Prettier 3.9.10 and Ruff 0.17.1; application imports/undefined names and TypeScript unused symbols are checked.

PWA: the app shell and only scoped low-sensitivity lookup/config API responses are cached. Lazy modules cache when visited. Medical, profile, marks, reports, finance and notifications are not persistently API-cached. An update prompt lets users finish work before activation. Attendance outbox fields are scoped to membership and reauthorized on replay. A fresh login/session bootstrap needs the network.

Security: active JWT/version checks and tenant membership remain universal. Export is administrator-only and omits hashes, grants and tokens; CSV formulas are escaped. Logo upload validates size, actual type and dimensions and normalizes images. PDF resource loading is restricted to bundled fonts. Confirmed deletion is transactional and preserves other institutions; global unshared accounts are deactivated. Real deployment requires trusted HTTPS edges, secure origin settings, backups and actual SMTP configuration.

Run:

```sh
set -a
. /workspace/zaaf-cloud.env
set +a
cd backend
/workspace/zaaf-venv/bin/pytest -q
/workspace/zaaf-venv/bin/python manage.py check
/workspace/zaaf-venv/bin/python manage.py makemigrations --check --dry-run
/workspace/zaaf-venv/bin/python manage.py spectacular --file /tmp/schema.yaml --validate --fail-on-warn
DEBUG=false /workspace/zaaf-venv/bin/python manage.py check --deploy
cd ../frontend
npm test
npm run build
npm run check:budget
npm audit
```

Manual release checklist: inspect all supported roles/themes/languages at 360/768/1280, keyboard focus and sheet controls, offline queue/reconciliation, parent medical/held-mark exclusion, CSRF and refresh replay, logo validation, formula-safe export, confirmed deletion in a disposable test institution, broker recovery and real SMTP delivery. Test installation/update from HTTPS and verify private API exclusions in Cache Storage.

Measured evidence is in VALIDATION.md. Lighthouse measurements are mobile simulations on the current cloud instance and production preview, not guarantees for every real Android/network. Automated Axe scans do not replace testing with assistive technology. Full Docker image builds are blocked by this machine's container DNS; no deployment or external SMTP delivery is claimed. HSTS preload is an explicit domain-owner decision, so Django's preload warning is deliberate.
