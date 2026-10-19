import pytest
from students.tests import school, actor
from .models import Exam, ExamSubject, Mark, MarkSheetHold

pytestmark = pytest.mark.django_db


@pytest.fixture
def exam(school):
    exam = Exam.objects.create(
        institution=school["institution"],
        class_group=school["group"],
        name="Term 1",
        date="2026-10-01",
    )
    return ExamSubject.objects.create(
        institution=school["institution"],
        exam=exam,
        subject=school["subject"],
        max_marks=100,
    )


@pytest.mark.parametrize(
    "name,expected",
    [
        ("admin", 200),
        ("class", 200),
        ("subject", 200),
        ("unassigned", 403),
        ("parent", 403),
        ("student", 403),
    ],
)
def test_mark_roles(school, exam, name, expected):
    response = actor(school, name).post(
        "/api/marks/bulk/",
        {
            "exam_subject": exam.pk,
            "rows": [{"student": school["target"].pk, "score": "85", "absent": False}],
        },
        format="json",
    )
    assert response.status_code == expected, response.data


def test_validation_and_hold_all_channels(school, exam):
    admin = actor(school, "admin")
    payload = {
        "exam_subject": exam.pk,
        "rows": [{"student": school["target"].pk, "score": "101"}],
    }
    assert admin.post("/api/marks/bulk/", payload, format="json").status_code == 400
    payload["rows"][0]["score"] = "85"
    assert admin.post("/api/marks/bulk/", payload, format="json").status_code == 200
    # Complete the second student in this class before publishing.
    payload["rows"] = [{"student": school["outside"].pk, "score": "75"}]
    assert admin.post("/api/marks/bulk/", payload, format="json").status_code == 200
    parent = actor(school, "parent")
    assert parent.get("/api/marks/").data["count"] == 0
    assert (
        admin.post(
            f"/api/exams/{exam.exam_id}/publication/",
            {"published": True},
            format="json",
        ).status_code
        == 200
    )
    assert parent.get("/api/marks/").data["count"] == 1
    response = admin.post(
        "/api/holds/",
        {
            "student": school["target"].pk,
            "exam": exam.exam_id,
            "reason_type": "FEES",
            "note": "Outstanding installment",
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    assert parent.get("/api/marks/").data["count"] == 0
    assert parent.get(
        f"/api/exams/{exam.exam_id}/result/?student={school['target'].pk}"
    ).data["held"]
    assert (
        parent.get(
            f"/api/exams/{exam.exam_id}/report/?student={school['target'].pk}"
        ).status_code
        == 403
    )
    assert admin.post(f"/api/holds/{response.data['id']}/release/").status_code == 200
    report = parent.get(
        f"/api/exams/{exam.exam_id}/report/?student={school['target'].pk}"
    )
    assert report.status_code == 200 and report.content.startswith(b"%PDF")


def test_subject_assignment_and_published_write(school, exam):
    from students.models import Subject

    other = Subject.objects.create(
        institution=school["institution"], name="English", code="ENG"
    )
    different = ExamSubject.objects.create(
        institution=school["institution"], exam=exam.exam, subject=other, max_marks=50
    )
    payload = {
        "exam_subject": different.pk,
        "rows": [{"student": school["target"].pk, "score": "25"}],
    }
    assert (
        actor(school, "subject")
        .post("/api/marks/bulk/", payload, format="json")
        .status_code
        == 403
    )
    exam.exam.published = True
    exam.exam.save()
    assert (
        actor(school, "admin")
        .post("/api/marks/bulk/", payload, format="json")
        .status_code
        == 400
    )
