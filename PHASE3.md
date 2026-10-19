# Phase 3 — attendance and dashboards

Files: `backend/attendance/{models,serializers,views,tests}.py`, attendance migrations, `backend/core/{permissions,pdf,views}.py`, the bundled font/license, institution settings migration, `frontend/src/features/{Attendance,Attendance.test,DashboardSummary,Roster}.tsx`, `frontend/src/lib/offline.ts`, and shared route/API/style/translation updates. The complete source archive contains every file.

Assumptions: present and late count as attended; a session code identifies a daily or session register; school session codes must be enabled in settings. The 24-hour edit window starts at record creation. Backdated first entries older than 24 hours need administrator action. `ADMIN_ONLY` means direct administrator correction/approval; `BLOCK` locks everyone. Existing identical-value replays are idempotent, while stale conflicting revisions return 409.

APIs: `/api/attendance/`, `POST /api/attendance/bulk/`, `/api/attendance/summary/`, `/api/attendance/export/?file=csv|pdf`, `/api/dashboard/`. Filters use student, class group, session and date; report ranges use `start`/`end` in ISO format. Lists and summaries paginate. Bulk saves validate the entire permitted roster inside a transaction, including first-save concurrency. Parents/students see only permitted children/self; subject teachers cannot mark attendance.

Run:

```sh
bash scripts/cloud-start.sh
set -a
. /workspace/zaaf-cloud.env
set +a
cd backend
/workspace/zaaf-venv/bin/pytest attendance -q
cd ../frontend
npm test
npm run build
```

Manual checks: choose a class and date; toggle present/absent/late and inspect live counts; save once and reload. Disconnect networking, save, reconnect and verify replay. Modify the same record from another session and confirm a stale queue entry remains visible rather than silently overwriting it. Try a subject teacher, parent, foreign student and late correction. Export both CSV and PDF; compare daily/monthly percentages with the roster. Check role dashboards and low-attendance alerts.

Limitations: a new sign-in needs network access; offline replay occurs while the app is open, not via unsupported mobile background execution. The outbox is scoped to membership IDs and contains attendance fields but no tokens. Queue conflicts require review/discard. Device storage is not a substitute for an institutional shared-device policy. The bilingual PDF uses the bundled Noto Sans Malayalam font and WeasyPrint.
