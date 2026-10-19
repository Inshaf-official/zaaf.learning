# Phase 2: academic setup, students, guardians and medical access

This phase adds tenant-scoped academic records, teacher assignments, student management, parent linking and invitations, and audited emergency medical access. Attendance, marks, events and timeline data remain in their specified later phases. No new runtime package was required; exact versions remain in the Phase 1 manifests and lockfiles.

## Assumptions

- An assignment with no division covers the whole class. A division-specific assignment covers only that division. A teacher can have both class and subject duties, but the selected membership role governs each request.
- Subject teachers may read the basic roster and profile in their assigned groups. Their response omits date of birth and guardian contact data. Parents see only linked children; student logins see only their own record and no guardian contacts or medical information.
- Guardian contacts are available to administrators, the student's class teacher, and the linked parents. Adding an existing parent does not change their name or password.
- Every newly created student needs at least one guardian. Add more through the profile. Unlinking the last guardian is blocked. Parent accounts from another institution cannot be claimed by an invitation.
- Medical cards use a dedicated API. The emergency directory returns only name, admission number, and ID, requires at least two search characters, and is restricted to staff. It does not grant access to a student's general profile.
- Any active teacher can request a read-only 30-minute grant with a reason of 10–1000 characters. Parent/student roles cannot use a grant, including when the same person has another teacher membership.
- Break-glass notifications are stored immediately for active administrators. The administrator overview polls every 30 seconds. This is the minimum notification support needed for medical access; general notices, email notification jobs and Celery remain Phase 5.
- All successful medical views are audited, including empty cards and the card returned by an update. Medical edits, emergency grants, student edits/deletions, guardian links and academic changes are audited. Reasons remain on the linked grant, without copying medical contents into the audit log.
- Students are archived by default. Permanent deletion requires administrator privileges and exact admission-number confirmation. The audit history and global user account are retained. An administrator can permanently delete an archived student through the API with its ID and confirmation.

## Models and tenant integrity

`AcademicYear`, `ClassGroup`, `Division`, `Subject`, `TeacherAssignment`, `Student`, and `ParentStudentLink` are in `students`. `StudentMedical` and `BreakGlassAccess` are in `medical`. Minimal `Notification` support is in `notices`. Each table has `institution_id` and indexes/constraints for its common filters. Only one academic year can be current. Admission numbers are unique inside an institution. Class and division IDs must agree. Referenced IDs are resolved inside the selected tenant; foreign references return 404. In-use divisions cannot move to another class, and in-use classes cannot change academic year.

Class-level authorization uses correlated `EXISTS` queries. Lists are paginated at 25 rows. Student lists select related class/year/division/user records; profile guardians are prefetched with their users. A query-count regression test covers a multi-page roster. Pages never request more than 25 students, so list virtualization is not needed in this phase. Academic dropdowns load paginated lookup results, not a large unpaginated student list.

## API

Every endpoint requires a bearer access token, `X-Institution-ID`, and `X-Role`. The existing active-user, password-change, and tenant membership checks apply.

| Method | Endpoint | Behavior |
| --- | --- | --- |
| GET, POST | `/api/academic-years/` | List or create academic years |
| GET, PATCH, PUT, DELETE | `/api/academic-years/{id}/` | Read or manage a year |
| GET, POST | `/api/class-groups/` | List or create classes/batches/levels |
| GET, PATCH, PUT, DELETE | `/api/class-groups/{id}/` | Read or manage a group |
| GET, POST | `/api/divisions/` | List or create divisions |
| GET, PATCH, PUT, DELETE | `/api/divisions/{id}/` | Read or manage a division |
| GET, POST | `/api/subjects/` | List or create subjects |
| GET, PATCH, PUT, DELETE | `/api/subjects/{id}/` | Read or manage a subject |
| GET, POST | `/api/teacher-assignments/` | List or create class/subject duties |
| GET, PATCH, PUT, DELETE | `/api/teacher-assignments/{id}/` | Read or manage an assignment |
| GET | `/api/teachers/` | Active teacher choices for administrators |
| GET | `/api/students/capabilities/` | Creation and emergency-search capabilities |
| GET | `/api/students/?search=&class_group=&division=&page=1` | Search and filter permitted students |
| POST | `/api/students/` | Create student and guardian accounts/links atomically |
| GET, PATCH, DELETE | `/api/students/{id}/` | Read, edit or archive a student |
| POST | `/api/students/{id}/guardians/` | Invite/link another guardian |
| DELETE | `/api/students/{id}/guardians/{link_id}/` | Unlink guardian, retaining at least one |
| POST | `/api/students/{id}/account/` | Create/link a school student login |
| POST | `/api/students/{id}/hard-delete/` | Permanently delete with confirmation |
| GET, PUT | `/api/students/{id}/medical/` | Audited medical read or replacement |
| POST | `/api/students/{id}/break-glass/` | Create a 30-minute medical grant |
| GET | `/api/medical/directory/?search=&page=1` | Minimal staff-only emergency search |
| GET | `/api/notifications/?page=1` | Current user's tenant notifications |
| POST | `/api/notifications/{id}/read/` | Mark a notification as read |

Academic writes are administrator-only. Teacher assignments are readable by administrators and the assigned teacher. Student mutations are administrator/class-teacher only; the destination class is checked again on writes. In-tenant forbidden student detail actions return 403. Foreign student objects return 404. Parent/student medical reads always return 403. Break-glass does not enable editing or viewing unrelated profiles. All medical responses use `Cache-Control: no-store`; the frontend keeps medical responses in short-lived memory with no retained cache after unmounting and hides the card when a grant expires.

The OpenAPI schema documents payloads and responses. Student creation accepts `name`, `admission_number`, `class_group`, nullable `division`, optional `date_of_birth`, `joined_on`, and a nonempty `guardians` list. A guardian contains `name`, `email`, optional `phone`, `relationship`, and `delivery` (`temporary` or `email`). Successful creation returns `{student, credentials}`; existing parent accounts do not produce a new password. Student login creation accepts either `email` or `login_id`, plus `delivery`. The one-time credential response has `identity` and an optional `temporary_password`. Medical replacement accepts `blood_group`, `allergies`, `conditions`, `doctor`, and `emergency_contacts` (up to 10 objects with name, relationship, and validated phone).

## Permission test matrix

| Role | Assigned student read | Assigned student write | Other class read/write | Guardian contacts | Medical read/edit | Break-glass |
| --- | --- | --- | --- | --- | --- | --- |
| Administrator | 200 | 200 | 200 | Yes | 200 / 200 | 403; already authorized |
| Class teacher | 200 | 200 | 403 / 403 unless separately assigned | Yes, own class | 200 / 200, own class | 201 |
| Subject teacher | 200 | 403 | 403 / 403 unless separately assigned | Omitted | 403 / 403 without grant | 201 |
| Unassigned teacher | 403 | 403 | 403 / 403 | Omitted | 403 / 403 without grant | 201 |
| Linked parent | 200 | 403 | Linked children only / 403 | Yes, linked children | 403 / 403 | 403 |
| Unlinked parent | 403 | 403 | Own linked children only / 403 | Omitted | 403 / 403 | 403 |
| Student | 200 for self | 403 | 403 / 403 | Omitted | 403 / 403 | 403 |
| Teacher with active grant | General profile rules unchanged | Unchanged | Unchanged | Unchanged | 200 / 403 for granted child | Expires after 30 minutes |

The automated suite also covers forged roles, foreign tenants/relations, division boundaries, null-division assignments, parent reuse across classes, duplicate records, last-guardian protection, invitation rollback on SMTP failure, non-school login rejection, soft deletion, permanent deletion, grant/student/role isolation, notification ownership, and invalid medical contact data. Attendance and exam rules are tested when their models arrive in Phases 3 and 4.

## Run

Use the current cloud checkout:

```sh
cd /workspace/zaaf.learning
bash scripts/cloud-install.sh
bash scripts/cloud-start.sh
set -a
. /workspace/zaaf-cloud.env
set +a
cd backend
DEMO_PASSWORD='Local!Office!Seed!2026' /workspace/zaaf-venv/bin/python manage.py seed_demo
/workspace/zaaf-venv/bin/pytest -q
/workspace/zaaf-venv/bin/python manage.py makemigrations --check --dry-run
/workspace/zaaf-venv/bin/python manage.py spectacular --file /tmp/schema.yaml --validate --fail-on-warn
cd ../frontend
npm test
npm run build
npm audit
```

If a backend started before this phase is still running with `--noreload`, restart that process before using the new URLs. Do not stop unrelated services. The helper starts a missing backend; it does not replace an already listening process.

On a local Docker host with registry access, use the existing README setup and then:

```sh
docker compose up --build -d
docker compose exec -e DEMO_PASSWORD='Local!Office!Seed!2026' backend python manage.py seed_demo
docker compose exec backend pytest -q
docker compose exec frontend npm test
```

The existing cloud draft scripts already run all migrations and build these screens, so no new environment variables or dependencies are needed. Docker image-build registry DNS remains the previously diagnosed infrastructure limitation in this cloud machine.

## Seeded roles and records

The seed is repeatable and preserves existing passwords and student records. Each institution has a current year, two groups, a division/level, a subject, class-teacher and subject-teacher assignments, three students, parent links across classes, and sample medical cards. Sample telephone numbers are intentionally non-working and labelled as test numbers.

For each `school`, `tuition`, and `madrasa` prefix:

- `admin@{type}.example.test`: institution administrator.
- `teacher@{type}.example.test`: class teacher, with a separate Parent role linked to one student.
- `subject@{type}.example.test`: subject teacher in the seeded class.
- `relief@{type}.example.test`: unassigned teacher for emergency-access testing.
- `parent@{type}.example.test`: linked to children across both groups.
- `student@school.example.test`: school student linked to Amina's profile.

Passwords are the value supplied to `DEMO_PASSWORD` on the initial seed. Newly invited people receive their own one-time credentials. Browser QA records added during validation are explicitly named `QA` and are development-only.

## Manual test checklist

1. As administrator, open Academic setup. Create a year, class/batch, division/level, subject, and teacher assignment. Confirm duplicate records and deleting in-use groups are rejected.
2. Add a student with a guardian using a temporary password. Copy the password once; sign in as that parent and complete the forced password change.
3. Link the same parent to a student in another class. Confirm both children appear and unrelated children remain inaccessible.
4. Sign in as the seeded class teacher. Search by name or admission number, filter by class/division, edit an assigned student, add a guardian, and create a school student login. Try moving the student into another teacher's class and expect 403.
5. Sign in as a subject teacher. Confirm the roster is read-only, guardian contacts are absent, and the medical card is locked.
6. Open Emergency search as the relief teacher, search for Amina, enter a reason and unlock the card. Confirm allergies, conditions and tap-to-call links are visible, while Edit is absent. The normal profile remains forbidden.
7. As administrator, check the medical alert on Overview, inspect the teacher's reason, and mark it read. Another user must not read or mark that notification.
8. Let the grant expire (or set its `expires_at` into the past in a local test database); confirm the card closes and a new server request returns 403. Parent/student roles must remain unable to open medical details.
9. Update a medical card as the class teacher. Check valid phone numbers, blood group choices, emergency contact additions/removals, audit records, and rejection of invalid contact data.
10. Archive a student. Confirm disappearance from active lists, parent lists and medical search. Only an administrator can permanently delete after typing the exact admission number.
11. Repeat in all three institution themes, both appearance modes, and English/Malayalam at 360px, 768px and 1280px. Use keyboard navigation through sheets and check focus returns to the triggering control.
12. Disconnect networking. Confirm the offline banner, a readable request error and retry. Account and medical writes require connectivity in Phase 2.

## Known limitations

- No external SMTP delivery was exercised without configured credentials. In-memory/console delivery and SMTP-failure rollback are tested; production must configure and verify SMTP.
- Emergency grants and administrator alerts are fully persisted. Alerts poll at 30 seconds; push, general notifications, SMTP notification jobs and Celery are Phase 5.
- Medical responses do not use persistent browser storage. The PWA phase must continue to exclude them from service-worker/data caching.
- Authored record content, server validation messages and the server-generated alert body are not translated. Interface labels and forms have English/Malayalam translations and a bundled Malayalam font.
- Roster pages are bounded at 25 records. Lookup dropdowns currently load all permitted academic choices; remote comboboxes would be appropriate for unusually large academic catalogues.
- No attendance/marks summaries, events or timeline panels are shown until their real data exists in the corresponding phase.
- This is Phase 2 of the platform. Full production security, accessibility and throttled-device performance reviews remain Phase 7.

## Verification results

- Full PostgreSQL-backed suite: **163 passed**. After extracting the reusable medical permission classes, the affected medical suite was rerun: **36 passed**.
- Frontend: **8 tests passed** across login, search/capabilities, profile privacy, and the break-glass flow.
- TypeScript and production build passed. All **21 JavaScript chunks combined** total **149,710 bytes gzipped** (146.2 KiB), so even the complete application bundle remains below the 180 KB first-path budget. This does not claim throttled-device LCP or interaction latency.
- Schema generation passed with validation and `--fail-on-warn`; Django system checks and migration-drift checks passed.
- Chromium: 648 bilingual screen/form/theme/viewport checks passed after fixing a Malayalam tab overflow at 360px; the 126 existing route/theme/viewport checks also passed.
- Browser workflows passed: student creation and guardian linking for all three types, all five academic creation forms, medical editing with a callable contact link, emergency grant, administrator notification and mark-read, and parent restrictions. No page errors were recorded.
- Seed rerun and backend restart checks passed. The restarted API served student search, permitted administrator medical access and denied parent medical access.
- Production dependency audit: zero advisories.

Browser scripts, logs and screenshots used for this run are retained outside the checkout under `/workspace/zaaf-qa` and `/tmp/zaaf-phase2-*`. They contain development-only records. Do not publish browser QA output or console mail logs as application assets.
