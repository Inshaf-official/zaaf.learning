# Phase 5 — events, communication, timeline and warnings

Files: `backend/events/{models,serializers,views,tests}.py`, notice models/serializers/views/services/tasks and migrations, Celery configuration, student interest-tag migration, `frontend/src/features/{Events,Notices,Timeline,Warnings}.tsx`, and student profile/dashboard integration.

Assumptions: eligibility rules combine year, optional class/division and any matching interest tag. Multiple rules are alternatives; no rules means all active students in the event academic year. Fairness counts actual participation, not merely selection. Administrators select/record participants. Class teachers may send notices only to their own group; institution-wide notices are administrator-only. Incidents/remarks default to staff-private unless explicitly shared with the family.

APIs: `/api/events/`, `/api/event-eligibility/`, event `fair_selection/`, `select/`, `participation/`, `/api/notices/`, `/api/notifications/`, notification `read/`, `/api/timeline-entries/`, student `timeline/` and `insights/`, and `/api/warnings/`. Timelines use a database union and pagination over full history rather than silently truncating old records. Profile insights include attendance/streaks, published mark trends and events. Warning thresholds come from Settings; marks compare the two most recent published exam percentage averages.

Notification rows and email delivery jobs are persisted together; Celery sends via configured SMTP, and beat redispatches pending rows. Retries are bounded at six attempts. Event and fee keys deduplicate notifications. WhatsApp links contain authored message templates and no credentials. There is no live WhatsApp API integration or invented provider token.

Run:

```sh
bash scripts/cloud-start.sh
set -a
. /workspace/zaaf-cloud.env
set +a
cd backend
/workspace/zaaf-venv/bin/pytest events -q
/workspace/zaaf-venv/bin/celery -A config inspect ping
```

Manual checks: edit a student's interests, create matching/nonmatching event rules, inspect zero-participation highlights and select eligible students. Record participation, check family notifications and fairness counts. Send institution/class/division notices and verify audience isolation. Mark notices/notifications read, share a WhatsApp template, and inspect SMTP/worker delivery status. Add private/shared incidents and verify the parent's timeline. Create attendance and marks drops and inspect warnings.

Limitations: notification polling is every 30 seconds; no WebSocket/push delivery is claimed. External SMTP deliverability requires real credentials and provider validation. Authored content and server-generated notification text retain their original language. Historical class transfers should be reviewed against the institution's enrollment policy; current class assignment governs staff access.
