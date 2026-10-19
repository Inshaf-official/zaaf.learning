# Phase 1 validation

- PostgreSQL-backed pytest: 38 passed.
- Vitest: 3 passed.
- TypeScript and Vite production build: passed.
- OpenAPI validation with fail-on-warn: passed.
- Migration drift check: passed.
- Compose configuration parsing: passed.
- npm audit: zero vulnerabilities.
- Browser dashboard checks: 18 combinations of institution/theme/viewport.
- Browser implemented-route checks: 126 combinations, no horizontal overflow or page errors.
- Temporary-password invitation and Malayalam language switching: passed for all three institution types.
- Native cloud install and startup: passed, including restart and authenticated HTTP checks.
- Login/dashboard dependency gzip total: approximately 116 KB.
- Full Docker image builds: blocked by package-registry DNS inside build containers; host networking and existing proxy settings did not resolve it.
- External SMTP delivery, throttled Android LCP, complete WCAG audit, and later-phase domain tests: not performed.

Browser QA screenshots and runner files are retained outside the checkout at /workspace/zaaf-qa.

# Phase 2 validation

- Full PostgreSQL suite: 163 passed; affected medical suite rerun after permission extraction: 36 passed.
- Frontend suite: 8 passed.
- Type checking, production build, OpenAPI validation, Django checks and migration consistency: passed.
- All built JavaScript: 149,710 bytes gzipped across 21 chunks, below 180 KB.
- Bilingual screen/form checks: 648 passed across three themes, two languages, light/dark modes and 360/768/1280 widths.
- Existing-route checks: 126 passed against the updated application.
- End-to-end browser flows: student creation and guardian linking in three institution types, five academic creation forms, medical editing, break-glass, administrator notification/read acknowledgement, and parent restrictions passed without page errors.
- Native seed repeatability, service restart and authenticated API smoke: passed.
- Production npm audit: zero advisories.
- Previously diagnosed Docker build registry DNS limitation remains. Actual SMTP delivery, throttled Android timing and complete accessibility auditing remain unverified.

See PHASE2.md for scope, assumptions, endpoints, permission matrix and manual checks.

# Phases 3–7 validation

Validated on 19 October 2026 against PostgreSQL and the production Vite build.

- Full backend suite: **195 passed**. Subsequent affected authentication checks: 39 passed; final export/settings/core checks: 9 passed.
- Frontend: **9 tests passed** in 5 files. TypeScript checking and production build passed.
- Django checks, migration drift checks and OpenAPI validation with fail-on-warn passed. Production check retains the deliberate HSTS-preload warning; domain owners must explicitly choose preloading.
- Login/dashboard JavaScript dependency closure including service worker: **139,520 bytes gzipped**, below the strict 180,000-byte budget. Run `npm run check:budget` after a production build.
- Lighthouse production-preview mobile simulation: login LCP **2,393 ms**, performance 96; authenticated dashboard LCP **1,417 ms**, performance 95. Both accessibility scores 100. Simulation uses 150 ms RTT, 1,638.4 kbps throughput and 4x CPU slowdown. This is measured cloud-browser evidence, not a guarantee for every physical phone or deployment.
- Attendance interaction under 4x CPU slowdown: five input-to-second-animation-frame measurements, maximum **55.7 ms**.
- Browser verification: **276** responsive/bilingual/theme route checks at 360/768/1280 widths; attendance save, exam marks/publication, notices, tuition payment and Hifz recording passed without page or server errors.
- Axe: **58 scans**, no WCAG 2 A/AA or 2.1 A/AA violations detected. Human screen-reader testing remains necessary.
- Production service worker: offline attendance queued in IndexedDB and replayed successfully after reconnection; app shell cached; sensitive APIs excluded from persistent response caches.
- Bilingual report card: `pdffonts` verified embedded, subsetted, Unicode Noto Sans and Noto Sans Malayalam fonts.
- Celery worker responded to inspect ping; persisted email outbox delivered nine local-console messages with zero pending. Actual external SMTP delivery is not verified.
- npm audit: zero vulnerabilities. Python import/undefined-name lint checks, schema checks, and Docker Compose configuration parsing passed. API docs use locally served Swagger assets and a separate CSP-compatible initialization script.
- Native cloud install/start and authenticated API smoke checks passed. Generated source archive excludes environment secrets, dependencies, caches and build output; bundled font licenses and binary assets are included.

Full Docker image builds remain blocked by DNS resolution for package registries inside this environment's build containers, including with host networking. Native installation/build/tests passed; actual Docker image execution, hosted HTTPS deployment and third-party SMTP delivery must be verified in the deployment environment. No deployment was performed.

The latest minor logo-header layout and export-settings additions were followed by another production build, frontend suite and affected backend core suite. Lighthouse and broad browser numbers above were measured immediately before those small changes.

## Reproduce performance checks

Build and preview the frontend with the configured API proxy, then use Lighthouse Mobile on `/login`. For the dashboard, log in first and preserve authentication storage while clearing HTTP caches; do not include login navigation in the dashboard trace. Use simulated throttling with the settings above, a clean browser profile, and no other running browser tests. Inspect the Network panel for the measured dependency closure and run `npm run check:budget`. Test input latency with Chrome Performance at 4x CPU slowdown. Install/update testing requires HTTPS or localhost; verify Cache Storage excludes medical, marks, profiles, finance and notifications.

QA harnesses, screenshots and raw reports are retained locally in `/workspace/zaaf-qa`; application tests are included in the source archive.
