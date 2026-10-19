from datetime import timedelta
import hashlib
import pytest
from django.core import mail
from django.utils import timezone
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.models import User, Membership, LoginAttempt, PasswordGrant, AuditLog
from institutions.models import Institution
from institutions.type_config import TYPE_CONFIG

pytestmark = pytest.mark.django_db
PASSWORD = "Cedar!Orbit!River!729"
NEW_PASSWORD = "Maple!Hill!Winter!842"


@pytest.fixture
def tenant():
    return Institution.objects.create(name="North School", type="SCHOOL")


@pytest.fixture
def admin(tenant):
    user = User.objects.create_user(
        "principal@example.test", PASSWORD, name="Principal"
    )
    member = Membership.objects.create(user=user, institution=tenant, role="ADMIN")
    return user, member


def client_for(user, member):
    client = APIClient()
    token = RefreshToken.for_user(user)
    token["ver"] = user.auth_version
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {token.access_token}",
        HTTP_X_INSTITUTION_ID=str(member.institution_id),
        HTTP_X_ROLE=member.role,
    )
    return client


def login(email, password=PASSWORD):
    client = APIClient()
    response = client.post(
        "/api/auth/login/", {"identifier": email, "password": password}
    )
    return client, response


@pytest.mark.parametrize("kind", TYPE_CONFIG)
def test_register_config(kind):
    client = APIClient()
    response = client.post(
        "/api/auth/register/",
        {
            "institution_name": "New Institution",
            "institution_type": kind,
            "name": "Founder",
            "email": "Founder@example.test",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 200
    assert response.cookies["refresh"]["httponly"]
    user = User.objects.get(email="founder@example.test")
    member = user.memberships.get()
    response = client_for(user, member).get("/api/institution/config/")
    assert response.status_code == 200
    assert response.data["type"] == kind
    assert response.data["roles"] == TYPE_CONFIG[kind]["roles"]


@pytest.mark.parametrize("password", ["123", "123456789012345", "password123456"])
def test_registration_rejects_weak_password(password):
    response = APIClient().post(
        "/api/auth/register/",
        {
            "institution_name": "School",
            "institution_type": "SCHOOL",
            "name": "Founder",
            "email": "test@example.test",
            "password": password,
        },
    )
    assert response.status_code == 400
    assert not Institution.objects.exists()


@pytest.mark.parametrize("role", ["ADMIN", "TEACHER", "PARENT", "STUDENT"])
@pytest.mark.parametrize("action", ["config", "list", "invite"])
def test_role_action_matrix(tenant, role, action):
    user = User.objects.create_user(f"{role}@example.test", PASSWORD, name=role)
    member = Membership.objects.create(user=user, institution=tenant, role=role)
    client = client_for(user, member)
    if action == "config":
        response = client.get("/api/institution/config/")
        expected = 200
    elif action == "list":
        response = client.get("/api/members/")
        expected = 200 if role == "ADMIN" else 403
    else:
        response = client.post(
            "/api/members/",
            {
                "email": "invite@example.test",
                "name": "New Teacher",
                "role": "TEACHER",
                "delivery": "temporary",
            },
        )
        expected = 201 if role == "ADMIN" else 403
    assert response.status_code == expected


def test_tenant_isolation_and_role_header_spoof(admin):
    user, member = admin
    other = Institution.objects.create(name="Other", type="SCHOOL")
    stranger = User.objects.create_user("stranger@example.test", PASSWORD, name="Other")
    target = Membership.objects.create(user=stranger, institution=other, role="TEACHER")
    client = client_for(user, member)
    response = client.get("/api/members/")
    assert response.data["count"] == 1
    assert (
        client.post(
            f"/api/members/{target.id}/activation/", {"is_active": False}, format="json"
        ).status_code
        == 404
    )
    client.credentials(
        HTTP_AUTHORIZATION=client._credentials["HTTP_AUTHORIZATION"],
        HTTP_X_INSTITUTION_ID=str(other.id),
        HTTP_X_ROLE="ADMIN",
    )
    assert client.get("/api/institution/config/").status_code == 404
    teacher = Membership.objects.create(user=user, institution=other, role="TEACHER")
    client = client_for(user, teacher)
    client._credentials["HTTP_X_ROLE"] = "ADMIN"
    assert client.get("/api/members/").status_code == 404


def test_invite_temporary_login_and_forced_change(admin):
    user, member = admin
    response = client_for(user, member).post(
        "/api/members/",
        {
            "email": "invited@example.test",
            "name": "Invited Teacher",
            "role": "TEACHER",
            "delivery": "temporary",
        },
    )
    assert response.status_code == 201
    temporary = response.data["temporary_password"]
    invited = User.objects.get(email="invited@example.test")
    membership = invited.memberships.get()
    client, response = login(invited.email, temporary)
    assert response.status_code == 200 and response.data["must_change_password"]
    client = client_for(invited, membership)
    assert client.get("/api/institution/config/").status_code == 403
    assert client.get("/api/auth/me/").status_code == 200
    response = client.post(
        "/api/auth/change-password/",
        {"current_password": temporary, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 200
    invited.refresh_from_db()
    assert not invited.must_change_password
    assert client.get("/api/auth/me/").status_code == 401
    assert (
        client_for(invited, membership).get("/api/institution/config/").status_code
        == 200
    )
    assert AuditLog.objects.filter(action="membership.invite").exists()


def test_student_login_id(admin):
    response = client_for(*admin).post(
        "/api/members/",
        {
            "login_id": "NORTH-001",
            "name": "Student",
            "role": "STUDENT",
            "delivery": "temporary",
        },
    )
    assert response.status_code == 201
    assert login("north-001", response.data["temporary_password"])[1].status_code == 200


@pytest.mark.parametrize("kind", ["TUITION", "MADRASA"])
def test_no_student_login_for_other_types(admin, kind):
    user, member = admin
    member.institution.type = kind
    member.institution.save()
    response = client_for(user, member).post(
        "/api/members/",
        {
            "login_id": "id-001",
            "name": "Student",
            "role": "STUDENT",
            "delivery": "temporary",
        },
    )
    assert response.status_code == 400


def test_email_invitation_single_use(admin, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    response = client_for(*admin).post(
        "/api/members/",
        {
            "email": "invited@example.test",
            "name": "Teacher",
            "role": "TEACHER",
            "delivery": "email",
        },
    )
    assert response.status_code == 201
    assert "temporary_password" not in response.data
    assert len(mail.outbox) == 1
    token = mail.outbox[0].body.split("token=")[1]
    client = APIClient()
    assert (
        client.post(
            "/api/auth/set-password/", {"token": token, "password": NEW_PASSWORD}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/auth/set-password/", {"token": token, "password": PASSWORD}
        ).status_code
        == 400
    )
    assert login("invited@example.test", NEW_PASSWORD)[1].status_code == 200


def test_expired_password_grant(admin):
    user, member = admin
    PasswordGrant.objects.create(
        user=user,
        institution=member.institution,
        digest=hashlib.sha256(b"expired").hexdigest(),
        expires_at=timezone.now() - timedelta(seconds=1),
    )
    assert (
        APIClient()
        .post("/api/auth/set-password/", {"token": "expired", "password": NEW_PASSWORD})
        .status_code
        == 400
    )


def test_reset_does_not_enumerate_accounts(admin, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    client = APIClient()
    known = client.post("/api/auth/request-password/", {"email": admin[0].email})
    unknown = client.post(
        "/api/auth/request-password/", {"email": "unknown@example.test"}
    )
    assert known.status_code == unknown.status_code == 200
    assert known.data == unknown.data
    assert len(mail.outbox) == 1


def test_refresh_rotation_logout_replay(admin):
    user, _ = admin
    client, response = login(user.email)
    assert response.status_code == 200
    old = client.cookies["refresh"].value
    assert client.post("/api/auth/refresh/").status_code == 200
    rotated = client.cookies["refresh"].value
    assert old != rotated
    client.cookies["refresh"] = old
    assert client.post("/api/auth/refresh/").status_code == 401
    client.cookies["refresh"] = rotated
    assert client.post("/api/auth/logout/").status_code == 204
    client.cookies["refresh"] = rotated
    assert client.post("/api/auth/refresh/").status_code == 401


def test_deactivation_invalidates_access_refresh_and_login(admin):
    principal, member = admin
    user = User.objects.create_user("teacher@example.test", PASSWORD, name="Teacher")
    target = Membership.objects.create(
        user=user, institution=member.institution, role="TEACHER"
    )
    old_access = client_for(user, target)
    refresh_client, _ = login(user.email)
    response = client_for(principal, member).post(
        f"/api/members/{target.id}/activation/", {"is_active": False}, format="json"
    )
    assert response.status_code == 200
    assert old_access.get("/api/auth/me/").status_code == 401
    assert refresh_client.post("/api/auth/refresh/").status_code == 401
    assert login(user.email)[1].status_code == 401
    assert (
        client_for(principal, member)
        .post(
            f"/api/members/{target.id}/activation/", {"is_active": True}, format="json"
        )
        .status_code
        == 200
    )
    assert login(user.email)[1].status_code == 200


def test_admin_reset_forces_change(admin):
    principal, member = admin
    user = User.objects.create_user("teacher@example.test", PASSWORD, name="Teacher")
    target = Membership.objects.create(
        user=user, institution=member.institution, role="TEACHER"
    )
    access = client_for(user, target)
    result = client_for(principal, member).post(
        f"/api/members/{target.id}/reset-password/"
    )
    assert result.status_code == 200
    assert access.get("/api/auth/me/").status_code == 401
    response = login(user.email, result.data["temporary_password"])[1]
    assert response.status_code == 200 and response.data["must_change_password"]


def test_multi_role_and_active_role_permissions(admin):
    user, admin_member = admin
    parent_member = Membership.objects.create(
        user=user, institution=admin_member.institution, role="PARENT"
    )
    assert client_for(user, parent_member).get("/api/members/").status_code == 403
    assert client_for(user, admin_member).get("/api/members/").status_code == 200
    assert (
        len(client_for(user, parent_member).get("/api/auth/me/").data["memberships"])
        == 2
    )


def test_lockout_generic_and_expiration(admin):
    user, _ = admin
    for _ in range(5):
        assert login(user.email, "wrong")[1].status_code == 401
    assert login(user.email)[1].status_code == 429
    LoginAttempt.objects.update(
        locked_until=timezone.now() - timedelta(minutes=1),
        updated_at=timezone.now() - timedelta(minutes=16),
    )
    assert login(user.email)[1].status_code == 200
    assert (
        login("unknown@example.test", "wrong")[1].data
        == login(user.email, "wrong")[1].data
    )


def test_csrf_enforced_on_cookie_mutations(admin):
    client = APIClient(enforce_csrf_checks=True)
    assert (
        client.post(
            "/api/auth/login/", {"identifier": admin[0].email, "password": PASSWORD}
        ).status_code
        == 403
    )
    csrf = client.get("/api/auth/csrf/").data["csrfToken"]
    assert (
        client.post(
            "/api/auth/login/",
            {"identifier": admin[0].email, "password": PASSWORD},
            HTTP_X_CSRFTOKEN=csrf,
        ).status_code
        == 200
    )
    assert client.post("/api/auth/refresh/").status_code == 403
    assert client.post("/api/auth/refresh/", HTTP_X_CSRFTOKEN=csrf).status_code == 200


def test_list_query_count_is_bounded(admin):
    user, member = admin
    for index in range(10):
        person = User.objects.create_user(
            f"user{index}@example.test", PASSWORD, name="Teacher"
        )
        Membership.objects.create(
            user=person, institution=member.institution, role="TEACHER"
        )
    with CaptureQueriesContext(connection) as queries:
        response = client_for(user, member).get("/api/members/")
    assert response.status_code == 200 and response.data["count"] == 11
    assert len(queries) < 10


def test_cross_tenant_account_cannot_be_claimed(admin):
    person = User.objects.create_user("other@example.test", PASSWORD, name="Other")
    other = Institution.objects.create(name="Other", type="SCHOOL")
    Membership.objects.create(user=person, institution=other, role="ADMIN")
    result = client_for(*admin).post(
        "/api/members/",
        {
            "email": person.email,
            "name": "Other",
            "role": "TEACHER",
            "delivery": "temporary",
        },
    )
    assert result.status_code == 400
    person.refresh_from_db()
    assert person.check_password(PASSWORD)


def test_self_deactivation_rejected(admin):
    result = client_for(*admin).post(
        f"/api/members/{admin[1].id}/activation/", {"is_active": False}, format="json"
    )
    assert result.status_code == 400


def test_invite_email_failure_rolls_back(admin, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("SMTP unavailable")

    monkeypatch.setattr("accounts.views.send_mail", fail)
    result = client_for(*admin).post(
        "/api/members/",
        {
            "email": "failed@example.test",
            "name": "Failed",
            "role": "TEACHER",
            "delivery": "email",
        },
    )
    assert result.status_code == 400
    assert not User.objects.filter(email="failed@example.test").exists()


def test_add_role_preserves_existing_password(admin):
    user, member = admin
    result = client_for(user, member).post(
        "/api/members/",
        {
            "email": user.email,
            "name": "Existing",
            "role": "PARENT",
            "delivery": "temporary",
        },
    )
    assert result.status_code == 201 and "temporary_password" not in result.data
    user.refresh_from_db()
    assert user.check_password(PASSWORD)
    assert user.memberships.count() == 2


def test_deactivation_preserves_other_institution_access(admin):
    user = User.objects.create_user("shared@example.test", PASSWORD, name="Shared")
    member = Membership.objects.create(
        user=user, institution=admin[1].institution, role="TEACHER"
    )
    other = Institution.objects.create(name="South", type="SCHOOL")
    Membership.objects.create(user=user, institution=other, role="PARENT")
    assert (
        client_for(*admin)
        .post(
            f"/api/members/{member.id}/activation/", {"is_active": False}, format="json"
        )
        .status_code
        == 200
    )
    user.refresh_from_db()
    assert user.is_active
    assert login(user.email)[1].status_code == 200
    assert client_for(user, member).get("/api/institution/config/").status_code == 404
    assert (
        client_for(*admin).post(f"/api/members/{member.id}/reset-password/").status_code
        == 400
    )


def test_session_bootstrap_includes_only_the_users_active_memberships(admin):
    user, member = admin
    other = Institution.objects.create(name="Second institution", type="TUITION")
    second = Membership.objects.create(user=user, institution=other, role="PARENT")
    payload = login(user.email)[1].data["user"]
    assert {m["id"] for m in payload["memberships"]} == {member.pk, second.pk}
    for context in payload["memberships"]:
        assert context["config"]["id"] == context["institution_id"]
        assert context["config"]["role"] == context["role"]
        assert context["config"]["type"] == context["type"]
    assert "password" not in payload and "auth_version" not in payload
