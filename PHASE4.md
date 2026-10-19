# Phase 4 — exams, marks and report cards

Files: `backend/exams/{models,serializers,permissions,views,tests}.py`, exam migrations, `frontend/src/features/{Exams,EntityForm}.tsx`, common PDF helpers and route/translation updates.

Models: Exam, ExamSubject, Mark, ReportCard and MarkSheetHold. Scores are bounded by the subject maximum; absence requires zero. Drafts remain staff-only. Publishing requires a complete result for every active student and subject. Published exams must be unpublished before mark edits. Class teachers can enter own-class marks; subject teachers require the exact subject/class/division assignment. All mark changes are audited.

APIs: `/api/exams/`, `/api/exam-subjects/`, `/api/marks/`, `POST /api/marks/bulk/`, exam `publication/`, `result/?student=`, `report/?student=` or class `report/`, `/api/holds/`, and hold `release/`. Grades use institution thresholds. PDF report cards have English/Malayalam headings and an embedded Malayalam font. Family access to held marks is removed from the marks list, result, PDF, timeline and profile trend; the result displays an office-contact message.

Run:

```sh
set -a
. /workspace/zaaf-cloud.env
set +a
cd backend
/workspace/zaaf-venv/bin/pytest exams -q
cd ../frontend
npm run build
```

Manual checks: create an exam, add subjects/maxima, enter a full grid including an absence, reject negative/excess marks and publish. Confirm the exact teacher assignment boundary. Download a student and class report. Place a hold, sign in as the parent/student and verify all score channels are hidden; release and verify access returns. Change a grade threshold in Settings and inspect the calculated grade.

Limitations: changing a grading scale recalculates displayed/generated grades; generated-report metadata is retained, while PDFs are rendered from current authorized data. The application does not upload PDFs to a public storage bucket. Large class exports should be capacity-tested on the chosen deployment. Fee-based automatic release occurs after all overdue tuition installments are cleared; other reasons release manually.
