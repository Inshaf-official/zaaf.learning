# Phase 6 — madrasa and tuition

Files: `backend/madrasa/{models,serializers,views,tests}.py`, `backend/tuition/{models,serializers,views,tasks,tests}.py`, their migrations, `frontend/src/features/{Madrasa,Tuition}.tsx`, seed extensions and module navigation.

Madrasa APIs: `/api/hifz/` and `/api/timetable/`. Hifz records store student, date, surah (1–114), juz (1–30), lines, revision status, notes and recording user. Administrators/class teachers write permitted students; families read only linked children. Islamic studies uses the common exam/marks/report system. Timetables distinguish SCHOOL and MADRASA, validate weekday/time order, and reject overlaps within the same group/kind. These APIs reject other institution types.

Tuition APIs: `/api/fees/`, installment `payment/` and `remind/`, `/api/test-series/`, series `publication/`, `ranks/`, `performance/`, and `/api/test-results/bulk/`. Finance writes are administrator-only. Payments require a unique reference, replay idempotently, reject overpayment, and release fee holds once all overdue balances are cleared. The scheduled reminder checks due/near-due unpaid installments and sends at most once per day. Test results require subject/class permissions, score bounds and complete publication. Competition ranks are computed across the batch before filtering family responses, so a parent sees the correct global rank without classmates' names/results.

Run:

```sh
set -a
. /workspace/zaaf-cloud.env
set +a
cd backend
/workspace/zaaf-venv/bin/pytest madrasa tuition -q
/workspace/zaaf-venv/bin/celery -A config inspect ping
```

Manual checks: record Hifz, reject invalid Quran locations, inspect parent isolation and two timetable kinds. Create an installment, record/replay a payment reference, reject an overpayment, clear an overdue balance and verify fee-hold release. Trigger a reminder twice and inspect one daily notification. Create a test series, enter and publish all batch scores, verify ties and child-only global rank, and inspect batch averages. Attempt each specialized API from another institution type and expect denial.

Limitations: payments are recorded ledger entries, not a payment-gateway transaction or bank reconciliation integration. Reminders require the worker, scheduler and broker; no always-on free hosting is implied. Published results must be unpublished before correction. Tuition batches use subject assignments; optional legacy division records are not presented as a second subject selector in the new tuition forms.
