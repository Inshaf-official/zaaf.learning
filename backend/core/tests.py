import io, zipfile
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from students.tests import school, actor
from institutions.models import Institution
from accounts.models import User, Membership

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "name,expected",
    [
        ("admin", 200),
        ("class", 403),
        ("subject", 403),
        ("parent", 403),
        ("student", 403),
    ],
)
def test_settings_export_audit_permissions(school, name, expected):
    client = actor(school, name)
    assert client.get("/api/institution/settings/").status_code == expected
    assert client.get("/api/institution/export/").status_code == expected
    assert client.get("/api/audit-log/").status_code == expected


def test_settings_validation_logo_and_export_redaction(school):
    client = actor(school, "admin")
    assert (
        client.patch(
            "/api/institution/settings/",
            {"grading_scale": [{"min": 50, "grade": "A"}]},
            format="json",
        ).status_code
        == 400
    )
    assert (
        client.patch(
            "/api/institution/settings/",
            {"attendance_rules": {"low_threshold": 101}},
            format="json",
        ).status_code
        == 400
    )
    assert (
        client.patch(
            "/api/institution/settings/",
            {"grading_scale": [{"min": 0, "grade": "Pass"}]},
            format="json",
        ).status_code
        == 200
    )
    upload = SimpleUploadedFile(
        "logo.svg", b'<svg onload="alert(1)"/>', content_type="image/svg+xml"
    )
    assert (
        client.post(
            "/api/institution/logo/", {"logo": upload}, format="multipart"
        ).status_code
        == 400
    )
    other = Institution.objects.create(
        name="FOREIGN PRIVATE INSTITUTION", type="SCHOOL"
    )
    export = client.get("/api/institution/export/")
    assert export.status_code == 200
    with zipfile.ZipFile(io.BytesIO(export.content)) as archive:
        assert not any("passwordgrant" in name for name in archive.namelist())
        assert b"password" not in archive.read("users.csv").lower()
        assert b"FOREIGN PRIVATE" not in b"".join(
            archive.read(name) for name in archive.namelist()
        )


def test_delete_requires_confirmation_and_preserves_other_tenant(school):
    client = actor(school, "admin")
    user = school["users"]["admin"][0]
    other = Institution.objects.create(name="Survives", type="SCHOOL")
    Membership.objects.create(institution=other, user=user, role="ADMIN")
    assert (
        client.post(
            "/api/institution/delete/", {"confirmation": "wrong"}, format="json"
        ).status_code
        == 400
    )
    response = client.post(
        "/api/institution/delete/",
        {"confirmation": "DELETE Test School"},
        format="json",
    )
    assert response.status_code == 200, response.data
    assert not Institution.objects.filter(pk=school["institution"].pk).exists()
    assert Institution.objects.filter(pk=other.pk).exists()
    user.refresh_from_db()
    assert user.is_active
    school["users"]["parent"][0].refresh_from_db()
    assert not school["users"]["parent"][0].is_active


def test_held_marks_are_omitted_from_insights_and_timeline(school):
    from exams.models import Exam, ExamSubject, Mark, MarkSheetHold

    exam = Exam.objects.create(
        institution=school["institution"],
        name="Published",
        class_group=school["group"],
        date=timezone.localdate(),
        published=True,
    )
    subject = ExamSubject.objects.create(
        institution=school["institution"],
        exam=exam,
        subject=school["subject"],
        max_marks=100,
    )
    Mark.objects.create(
        institution=school["institution"],
        student=school["target"],
        exam_subject=subject,
        score=85,
        entered_by=school["users"]["class"][0],
    )
    parent = actor(school, "parent")
    path = f"/api/students/{school['target'].pk}"
    assert parent.get(path + "/insights/").data["trend"][0]["percentage"] == 85
    MarkSheetHold.objects.create(
        institution=school["institution"],
        student=school["target"],
        exam=exam,
        reason_type="OTHER",
        note="Review",
    )
    assert parent.get(path + "/insights/").data["trend"] == []
    assert not any(
        r["kind"] == "MARK" for r in parent.get(path + "/timeline/").data["results"]
    )


def test_timeline_paginates_full_history(school):
    from attendance.models import Attendance
    from datetime import date, timedelta

    Attendance.objects.bulk_create(
        [
            Attendance(
                institution=school["institution"],
                student=school["target"],
                date=date(2024, 1, 1) + timedelta(days=i),
                status="PRESENT",
                marked_by=school["users"]["class"][0],
            )
            for i in range(400)
        ]
    )
    response = actor(school, "parent").get(
        f"/api/students/{school['target'].pk}/timeline/?page=16"
    )
    assert response.status_code == 200, response.data
    assert (
        response.data["count"] == 400
        and len(response.data["results"]) == 25
        and response.data["next"] is None
    )
