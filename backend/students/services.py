import secrets
from smtplib import SMTPException
from rest_framework.exceptions import ValidationError
from accounts.models import User, Membership
from accounts.views import grant_password, deliver_grant, audit
from .models import ParentStudentLink


def invite_account(request, name, role, delivery, email=None, login_id=None):
    institution = request._membership.institution
    email = email.lower() if email else None
    login_id = login_id.lower() if login_id else None
    existing = (
        User.objects.select_for_update().filter(email=email).first()
        if email
        else User.objects.select_for_update().filter(login_id=login_id).first()
    )
    if existing:
        membership = existing.memberships.filter(
            institution=institution, role=role
        ).first()
        if not membership or not membership.is_active or not existing.is_active:
            raise ValidationError(
                "This account is unavailable for linking. Ask an administrator to review it."
            )
        return existing, None
    temporary = secrets.token_urlsafe(18) if delivery == "temporary" else None
    user = User.objects.create_user(
        email, temporary, name=name, login_id=login_id, must_change_password=True
    )
    Membership.objects.create(user=user, institution=institution, role=role)
    if delivery == "email":
        try:
            deliver_grant(user, institution, grant_password(user, institution))
        except (OSError, SMTPException):
            raise ValidationError(
                "Email delivery failed. Configure SMTP or use a temporary password."
            )
    audit(request, institution, "membership.invite", user.pk)
    return user, {
        "identity": email or login_id,
        **({"temporary_password": temporary} if temporary else {}),
    }


def link_guardian(request, student, data):
    user, credential = invite_account(
        request, data["name"], "PARENT", data["delivery"], email=data["email"]
    )
    link, created = ParentStudentLink.objects.get_or_create(
        institution=student.institution,
        student=student,
        parent=user,
        defaults={"phone": data["phone"], "relationship": data["relationship"]},
    )
    if not created:
        raise ValidationError("This guardian is already linked to the student.")
    audit(request, student.institution, "guardian.link", f"{student.pk}:{link.pk}")
    return link, credential
