from datetime import timedelta
import pytest
from django.utils import timezone
from accounts.models import AuditLog
from students.tests import school, actor
from .models import StudentMedical, BreakGlassAccess
from notices.models import Notification

pytestmark = pytest.mark.django_db
CARD = {
    "blood_group": "O+",
    "allergies": "Penicillin",
    "conditions": "Asthma",
    "doctor": "Dr Rao",
    "emergency_contacts": [
        {"name": "Guardian", "phone": "+919876543210", "relationship": "Parent"}
    ],
}


@pytest.mark.parametrize(
    "name",
    [
        "admin",
        "class",
        "subject",
        "unassigned",
        "parent",
        "otherparent",
        "student",
        "otherstudent",
    ],
)
@pytest.mark.parametrize("operation", ["view", "edit", "break_glass", "directory"])
def test_medical_permission_matrix(school, name, operation):
    target = school["target"]
    StudentMedical.objects.create(
        institution=school["institution"], student=target, **CARD
    )
    client = actor(school, name)
    if operation == "view":
        response = client.get(f"/api/students/{target.id}/medical/")
        expected = 200 if name in ["admin", "class"] else 403
    elif operation == "edit":
        response = client.put(
            f"/api/students/{target.id}/medical/", CARD, format="json"
        )
        expected = 200 if name in ["admin", "class"] else 403
    elif operation == "break_glass":
        response = client.post(
            f"/api/students/{target.id}/break-glass/",
            {"reason": "Student collapsed during assembly"},
            format="json",
        )
        expected = 201 if name in ["class", "subject", "unassigned"] else 403
    else:
        response = client.get("/api/medical/directory/?search=Amina")
        expected = 200 if name in ["admin", "class", "subject", "unassigned"] else 403
    assert response.status_code == expected, response.data


def test_grant_expiry_audit_notification_and_read_only(school):
    client = actor(school, "unassigned")
    target = school["target"]
    StudentMedical.objects.create(
        institution=school["institution"], student=target, **CARD
    )
    assert client.get(f"/api/students/{target.id}/medical/").status_code == 403
    response = client.post(
        f"/api/students/{target.id}/break-glass/",
        {"reason": "Student is having breathing difficulty"},
        format="json",
    )
    assert response.status_code == 201
    grant = BreakGlassAccess.objects.get(pk=response.data["id"])
    assert (
        timedelta(minutes=29)
        < grant.expires_at - timezone.now()
        <= timedelta(minutes=30)
    )
    notification = Notification.objects.get()
    assert notification.recipient == school["users"]["admin"][0]
    response = client.get(f"/api/students/{target.id}/medical/")
    assert (
        response.status_code == 200
        and response.data["card"]["allergies"] == "Penicillin"
    )
    assert not response.data["can_edit"] and response.data["access_expires_at"]
    assert response["Cache-Control"] == "no-store"
    assert (
        client.put(
            f"/api/students/{target.id}/medical/", CARD, format="json"
        ).status_code
        == 403
    )
    assert (
        AuditLog.objects.filter(
            action="medical.view", user=school["users"]["unassigned"][0]
        ).count()
        == 1
    )
    assert AuditLog.objects.filter(action="medical.break_glass").count() == 1
    grant.expires_at = timezone.now() - timedelta(seconds=1)
    grant.save()
    assert client.get(f"/api/students/{target.id}/medical/").status_code == 403
    admin_client = actor(school, "admin")
    notifications = admin_client.get("/api/notifications/").data
    assert notifications["count"] == 1
    assert (
        admin_client.post(f"/api/notifications/{notification.id}/read/").status_code
        == 200
    )
    assert client.post(f"/api/notifications/{notification.id}/read/").status_code == 404
    assert actor(school, "parent").get("/api/notifications/").data["count"] == 0


def test_grant_does_not_cross_student_or_role(school):
    teacher = school["users"]["subject"][0]
    BreakGlassAccess.objects.create(
        institution=school["institution"],
        student=school["target"],
        user=teacher,
        reason="Emergency medical care",
        expires_at=timezone.now() + timedelta(minutes=30),
    )
    assert (
        actor(school, "subject")
        .get(f"/api/students/{school['sibling'].id}/medical/")
        .status_code
        == 403
    )
    from accounts.models import Membership

    Membership.objects.create(
        institution=school["institution"], user=teacher, role="PARENT"
    )
    from students.tests import authenticated

    assert (
        authenticated(teacher, school["institution"], "PARENT")
        .get(f"/api/students/{school['target'].id}/medical/")
        .status_code
        == 403
    )


def test_medical_contact_and_reason_validation(school):
    client = actor(school, "class")
    path = f"/api/students/{school['target'].id}/"
    assert (
        client.post(path + "break-glass/", {"reason": " "}, format="json").status_code
        == 400
    )
    invalid = {
        **CARD,
        "emergency_contacts": [{"name": "Bad", "phone": "javascript:alert(1)"}],
    }
    assert client.put(path + "medical/", invalid, format="json").status_code == 400
    assert (
        client.put(
            path + "medical/", {**CARD, "blood_group": "X+"}, format="json"
        ).status_code
        == 400
    )
    assert not StudentMedical.objects.exists()
    assert client.get(path + "medical/").data["card"] is None
    assert AuditLog.objects.filter(action="medical.view").count() == 1


def test_directory_minimal_no_default_dump(school):
    client = actor(school, "unassigned")
    assert client.get("/api/medical/directory/").data["count"] == 0
    response = client.get("/api/medical/directory/?search=n001")
    assert response.data["count"] == 1
    assert set(response.data["results"][0]) == {"id", "name", "admission_number"}
    assert client.get(f"/api/students/{school['target'].id}/").status_code == 403
