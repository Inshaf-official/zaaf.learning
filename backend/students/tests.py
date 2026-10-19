from datetime import date
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.models import User, Membership, AuditLog
from institutions.models import Institution
from .models import (
    AcademicYear,
    ClassGroup,
    Division,
    Subject,
    TeacherAssignment,
    Student,
    ParentStudentLink,
)

pytestmark = pytest.mark.django_db
PASSWORD = "Local!Student!Tests!729"


def authenticated(user, institution, role):
    client = APIClient()
    token = RefreshToken.for_user(user)
    token["ver"] = user.auth_version
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {token.access_token}",
        HTTP_X_INSTITUTION_ID=str(institution.id),
        HTTP_X_ROLE=role,
    )
    return client


@pytest.fixture
def school():
    institution = Institution.objects.create(name="Test School", type="SCHOOL")
    year = AcademicYear.objects.create(
        institution=institution,
        name="2026–27",
        starts_on=date(2026, 6, 1),
        ends_on=date(2027, 3, 31),
        is_current=True,
    )
    group = ClassGroup.objects.create(
        institution=institution, academic_year=year, name="8"
    )
    other_group = ClassGroup.objects.create(
        institution=institution, academic_year=year, name="9"
    )
    a = Division.objects.create(institution=institution, class_group=group, name="A")
    b = Division.objects.create(institution=institution, class_group=group, name="B")
    subject = Subject.objects.create(
        institution=institution, name="Mathematics", code="MATH"
    )
    users = {}
    for name, role in [
        ("admin", "ADMIN"),
        ("class", "TEACHER"),
        ("subject", "TEACHER"),
        ("unassigned", "TEACHER"),
        ("parent", "PARENT"),
        ("otherparent", "PARENT"),
        ("student", "STUDENT"),
        ("otherstudent", "STUDENT"),
    ]:
        user = User.objects.create_user(f"{name}@test.example", PASSWORD, name=name)
        Membership.objects.create(institution=institution, user=user, role=role)
        users[name] = (user, role)
    TeacherAssignment.objects.create(
        institution=institution,
        teacher=users["class"][0],
        class_group=group,
        division=a,
        is_class_teacher=True,
    )
    TeacherAssignment.objects.create(
        institution=institution,
        teacher=users["subject"][0],
        class_group=group,
        division=a,
        subject=subject,
    )
    target = Student.objects.create(
        institution=institution,
        name="Amina",
        admission_number="N001",
        date_of_birth=date(2012, 1, 1),
        class_group=group,
        division=a,
        user=users["student"][0],
        joined_on=date(2026, 6, 1),
    )
    sibling = Student.objects.create(
        institution=institution,
        name="Bilal",
        admission_number="N002",
        class_group=other_group,
        joined_on=date(2026, 6, 1),
    )
    outside = Student.objects.create(
        institution=institution,
        name="Charlie",
        admission_number="N003",
        class_group=group,
        division=b,
        user=users["otherstudent"][0],
        joined_on=date(2026, 6, 1),
    )
    for student in [target, sibling]:
        ParentStudentLink.objects.create(
            institution=institution,
            parent=users["parent"][0],
            student=student,
            phone="+919876543210",
        )
    ParentStudentLink.objects.create(
        institution=institution, parent=users["otherparent"][0], student=outside
    )
    return {
        "institution": institution,
        "year": year,
        "group": group,
        "other_group": other_group,
        "a": a,
        "b": b,
        "subject": subject,
        "users": users,
        "target": target,
        "sibling": sibling,
        "outside": outside,
    }


def actor(school, name):
    user, role = school["users"][name]
    return authenticated(user, school["institution"], role)


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
@pytest.mark.parametrize(
    "operation",
    ["read", "edit", "archive", "guardian", "account", "create", "academic_create"],
)
def test_student_permission_matrix(school, name, operation):
    client = actor(school, name)
    path = f"/api/students/{school['target'].id}/"
    manages = name in ["admin", "class"]
    if operation == "read":
        response = client.get(path)
        expected = (
            200 if name in ["admin", "class", "subject", "parent", "student"] else 403
        )
    elif operation == "edit":
        response = client.patch(path, {"name": "Updated"}, format="json")
        expected = 200 if manages else 403
    elif operation == "archive":
        response = client.delete(path)
        expected = 204 if manages else 403
    elif operation == "guardian":
        response = client.post(
            path + "guardians/",
            {"name": "Guardian", "email": "new@example.test", "delivery": "temporary"},
            format="json",
        )
        expected = 201 if manages else 403
    elif operation == "account":
        response = client.post(
            f"/api/students/{school['sibling'].id}/account/",
            {"login_id": "new-login", "delivery": "temporary"},
            format="json",
        )
        expected = 201 if name == "admin" else 403
    elif operation == "academic_create":
        response = client.post(
            "/api/subjects/", {"name": "English", "code": "ENG"}, format="json"
        )
        expected = 201 if name == "admin" else 403
    else:
        response = client.post(
            "/api/students/",
            {
                "name": "New Student",
                "admission_number": "N004",
                "class_group": school["group"].id,
                "division": school["a"].id,
                "guardians": [
                    {
                        "name": "Guardian",
                        "email": "new@example.test",
                        "delivery": "temporary",
                    }
                ],
            },
            format="json",
        )
        expected = 201 if manages else 403
    assert response.status_code == expected, response.data


@pytest.mark.parametrize(
    "name,count",
    [
        ("admin", 3),
        ("class", 1),
        ("subject", 1),
        ("unassigned", 0),
        ("parent", 2),
        ("otherparent", 1),
        ("student", 1),
        ("otherstudent", 1),
    ],
)
def test_list_visibility(school, name, count):
    response = actor(school, name).get("/api/students/")
    assert response.status_code == 200 and response.data["count"] == count
    assert "guardians" not in response.data["results"][0] if count else True


@pytest.mark.parametrize(
    "name,guardians,dob",
    [
        ("admin", True, True),
        ("class", True, True),
        ("parent", True, True),
        ("subject", False, False),
        ("student", False, True),
    ],
)
def test_profile_redaction(school, name, guardians, dob):
    data = actor(school, name).get(f"/api/students/{school['target'].id}/").data
    assert ("guardians" in data) == guardians
    assert ("date_of_birth" in data) == dob
    assert not any(
        k in data for k in ["medical", "allergies", "conditions", "emergency_contacts"]
    )


def test_class_teacher_cannot_transfer_student_or_create_elsewhere(school):
    client = actor(school, "class")
    response = client.patch(
        f"/api/students/{school['target'].id}/",
        {"class_group": school["other_group"].id, "division": None},
        format="json",
    )
    assert response.status_code == 403
    response = client.post(
        "/api/students/",
        {
            "name": "Forbidden",
            "admission_number": "N009",
            "class_group": school["group"].id,
            "division": school["b"].id,
            "guardians": [
                {
                    "name": "Guardian",
                    "email": "new@example.test",
                    "delivery": "temporary",
                }
            ],
        },
        format="json",
    )
    assert response.status_code == 403


def test_null_division_assignment_covers_whole_class(school):
    TeacherAssignment.objects.create(
        institution=school["institution"],
        teacher=school["users"]["unassigned"][0],
        class_group=school["group"],
        is_class_teacher=True,
    )
    response = actor(school, "unassigned").get("/api/students/")
    assert response.data["count"] == 2
    assert (
        actor(school, "unassigned")
        .patch(
            f"/api/students/{school['outside'].id}/", {"name": "Allowed"}, format="json"
        )
        .status_code
        == 200
    )


def test_parent_reuse_multiple_children_and_create_atomicity(school):
    client = actor(school, "admin")
    payload = {
        "name": "New Student",
        "admission_number": "N004",
        "class_group": school["group"].id,
        "guardians": [
            {
                "name": "Existing parent",
                "email": school["users"]["parent"][0].email,
                "delivery": "temporary",
            }
        ],
    }
    response = client.post("/api/students/", payload, format="json")
    assert response.status_code == 201 and response.data["credentials"] == []
    assert actor(school, "parent").get("/api/students/").data["count"] == 3
    response = client.post("/api/students/", payload, format="json")
    assert response.status_code == 400
    assert Student.objects.count() == 4


def test_invitation_credentials_and_student_login(school):
    client = actor(school, "class")
    student = school["target"]
    student.user = None
    student.save()
    response = client.post(
        f"/api/students/{student.id}/account/",
        {"login_id": "school-001", "delivery": "temporary"},
        format="json",
    )
    assert response.status_code == 201 and "temporary_password" in response.data
    password = response.data["temporary_password"]
    response = APIClient().post(
        "/api/auth/login/",
        {"identifier": "school-001", "password": password},
        format="json",
    )
    assert response.status_code == 200 and response.data["must_change_password"]
    student.refresh_from_db()
    assert student.user.login_id == "school-001"


def test_guardian_removal_requires_one_and_checks_link_scope(school):
    client = actor(school, "class")
    link = school["target"].parent_links.get()
    assert (
        client.delete(
            f"/api/students/{school['target'].id}/guardians/{link.id}/"
        ).status_code
        == 400
    )
    other = school["outside"].parent_links.get()
    assert (
        client.delete(
            f"/api/students/{school['target'].id}/guardians/{other.id}/"
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/students/{school['target'].id}/guardians/",
            {"name": "Second", "email": "second@example.test", "delivery": "temporary"},
            format="json",
        ).status_code
        == 201
    )
    assert (
        client.delete(
            f"/api/students/{school['target'].id}/guardians/{link.id}/"
        ).status_code
        == 204
    )
    assert actor(school, "parent").get("/api/students/").data["count"] == 1


def test_soft_and_confirmed_hard_delete(school):
    client = actor(school, "admin")
    target = school["target"]
    assert client.delete(f"/api/students/{target.id}/").status_code == 204
    assert Student.objects.filter(pk=target.pk, deleted_at__isnull=False).exists()
    assert client.get(f"/api/students/{target.id}/").status_code == 404
    assert (
        client.post(
            f"/api/students/{target.id}/hard-delete/",
            {"confirm_admission_number": "wrong"},
            format="json",
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"/api/students/{target.id}/hard-delete/",
            {"confirm_admission_number": target.admission_number},
            format="json",
        ).status_code
        == 204
    )
    assert not Student.objects.filter(pk=target.pk).exists()
    assert AuditLog.objects.filter(
        action="student.hard_delete", object=str(target.pk)
    ).exists()


def test_search_filter_pagination_and_bounded_queries(school):
    client = actor(school, "admin")
    assert client.get("/api/students/?search=n001").data["count"] == 1
    assert (
        client.get("/api/students/?search=mina").data["results"][0]["name"] == "Amina"
    )
    assert client.get(f"/api/students/?division={school['b'].id}").data["count"] == 1
    for i in range(30):
        Student.objects.create(
            institution=school["institution"],
            name=f"Extra {i}",
            admission_number=f"X{i}",
            class_group=school["group"],
            joined_on=date(2026, 6, 1),
        )
    with CaptureQueriesContext(connection) as queries:
        response = client.get("/api/students/")
    assert len(response.data["results"]) == 25 and response.data["next"]
    assert len(queries) <= 6
    assert client.get("/api/students/?page=2").status_code == 200


def test_foreign_tenant_objects_and_relations_are_404(school):
    other = Institution.objects.create(name="Other", type="SCHOOL")
    year = AcademicYear.objects.create(
        institution=other,
        name="Other",
        starts_on=date(2026, 1, 1),
        ends_on=date(2026, 12, 31),
    )
    group = ClassGroup.objects.create(
        institution=other, academic_year=year, name="Foreign"
    )
    student = Student.objects.create(
        institution=other,
        name="Foreign",
        admission_number="F1",
        class_group=group,
        joined_on=date(2026, 6, 1),
    )
    client = actor(school, "admin")
    for suffix in ["", "medical/", "break-glass/"]:
        path = f"/api/students/{student.pk}/" + suffix
        result = (
            client.post(path, {"reason": "Medical emergency"}, format="json")
            if suffix == "break-glass/"
            else client.get(path)
        )
        assert result.status_code == 404
    assert (
        client.patch(
            f"/api/students/{school['target'].pk}/",
            {"class_group": group.pk, "division": None},
            format="json",
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/class-groups/",
            {"name": "Foreign ref", "academic_year": year.pk},
            format="json",
        ).status_code
        == 404
    )


def test_division_and_assignment_validation(school):
    client = actor(school, "admin")
    assert (
        client.patch(
            f"/api/students/{school['target'].pk}/",
            {"class_group": school["other_group"].pk},
            format="json",
        ).status_code
        == 400
    )
    response = client.post(
        "/api/teacher-assignments/",
        {
            "teacher": school["users"]["unassigned"][0].id,
            "class_group": school["group"].pk,
            "division": school["b"].pk,
            "subject": school["subject"].pk,
            "is_class_teacher": False,
        },
        format="json",
    )
    assert (
        response.status_code == 201
        and response.data["teacher"] == school["users"]["unassigned"][0].id
    )
    assert (
        client.post(
            "/api/teacher-assignments/",
            {
                "teacher": school["users"]["parent"][0].id,
                "class_group": school["group"].pk,
                "is_class_teacher": True,
            },
            format="json",
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/teacher-assignments/",
            {
                "teacher": school["users"]["unassigned"][0].id,
                "class_group": school["group"].pk,
                "is_class_teacher": False,
            },
            format="json",
        ).status_code
        == 400
    )


def test_invalid_dates_and_missing_guardians(school):
    client = actor(school, "admin")
    assert (
        client.post(
            "/api/academic-years/",
            {"name": "Invalid", "starts_on": "2027-06-01", "ends_on": "2026-06-01"},
            format="json",
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/students/",
            {
                "name": "No guardian",
                "admission_number": "G0",
                "class_group": school["group"].pk,
            },
            format="json",
        ).status_code
        == 400
    )


def test_guardian_email_failure_rolls_back_student(school, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("SMTP unavailable")

    monkeypatch.setattr("students.services.deliver_grant", fail)
    response = actor(school, "admin").post(
        "/api/students/",
        {
            "name": "Failed",
            "admission_number": "FAIL",
            "class_group": school["group"].pk,
            "guardians": [
                {
                    "name": "New",
                    "email": "mail-failure@example.test",
                    "delivery": "email",
                }
            ],
        },
        format="json",
    )
    assert response.status_code == 400
    assert not Student.objects.filter(admission_number="FAIL").exists()
    assert not User.objects.filter(email="mail-failure@example.test").exists()


def test_in_use_division_cannot_be_moved_to_another_class(school):
    client = actor(school, "admin")
    assert (
        client.patch(
            f"/api/divisions/{school['a'].id}/",
            {"class_group": school["other_group"].id},
            format="json",
        ).status_code
        == 400
    )
    new_year = AcademicYear.objects.create(
        institution=school["institution"],
        name="2027–28",
        starts_on=date(2027, 6, 1),
        ends_on=date(2028, 3, 31),
    )
    assert (
        client.patch(
            f"/api/class-groups/{school['group'].id}/",
            {"academic_year": new_year.id},
            format="json",
        ).status_code
        == 400
    )


def test_archived_students_are_hidden_from_all_medical_paths(school):
    client = actor(school, "admin")
    target = school["target"]
    assert client.delete(f"/api/students/{target.id}/").status_code == 204
    assert client.get(f"/api/students/{target.id}/medical/").status_code == 404
    assert (
        actor(school, "unassigned")
        .post(
            f"/api/students/{target.id}/break-glass/",
            {"reason": "Emergency health access"},
            format="json",
        )
        .status_code
        == 404
    )
    assert (
        actor(school, "unassigned")
        .get("/api/medical/directory/?search=Amina")
        .data["count"]
        == 0
    )


@pytest.mark.parametrize(
    "name", ["class", "subject", "unassigned", "parent", "student"]
)
def test_non_admin_cannot_permanently_delete_or_change_assignments(school, name):
    client = actor(school, name)
    assert (
        client.post(
            f"/api/students/{school['target'].id}/hard-delete/",
            {"confirm_admission_number": school["target"].admission_number},
            format="json",
        ).status_code
        == 403
    )
    assignment = TeacherAssignment.objects.filter(
        institution=school["institution"]
    ).first()
    assert (
        client.patch(
            f"/api/teacher-assignments/{assignment.id}/",
            {"is_class_teacher": True},
            format="json",
        ).status_code
        == 403
    )
    assert (
        client.delete(f"/api/teacher-assignments/{assignment.id}/").status_code == 403
    )


@pytest.mark.parametrize("kind", ["TUITION", "MADRASA"])
def test_non_school_student_accounts_rejected(school, kind):
    school["institution"].type = kind
    school["institution"].save()
    assert (
        actor(school, "admin")
        .post(
            f"/api/students/{school['sibling'].id}/account/",
            {"login_id": "non-school-student", "delivery": "temporary"},
            format="json",
        )
        .status_code
        == 400
    )
