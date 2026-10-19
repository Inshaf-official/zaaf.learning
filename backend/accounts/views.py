import hashlib
import secrets
from smtplib import SMTPException
from datetime import timedelta
from urllib.parse import urlencode
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Q, F
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import viewsets
from drf_spectacular.utils import extend_schema
from .schema import (
    SessionSerializer,
    DetailSerializer,
    CsrfSerializer,
    MeSerializer,
    RequestPasswordSerializer,
    SetPasswordSerializer,
    InviteResponseSerializer,
    ActivationSerializer,
    TemporarySerializer,
    TENANT_HEADERS,
)
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import (
    OutstandingToken,
    BlacklistedToken,
)
from institutions.models import Institution
from institutions.type_config import TYPE_CONFIG
from .models import User, Membership, LoginAttempt, PasswordGrant, AuditLog
from .permissions import (
    PasswordChanged,
    InstitutionAdmin,
    TenantQuerysetMixin,
    membership_for,
)
from .serializers import (
    RegistrationSerializer,
    LoginSerializer,
    ChangePasswordSerializer,
    InviteSerializer,
    MemberSerializer,
)


def audit(request, institution, action, obj):
    AuditLog.objects.create(
        institution=institution,
        user=request.user if request.user.is_authenticated else None,
        action=action,
        object=str(obj),
        ip=request.META.get("REMOTE_ADDR"),
    )


def revoke(user):
    User.objects.filter(pk=user.pk).update(auth_version=F("auth_version") + 1)
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)
    user.refresh_from_db()


def user_payload(user):
    memberships = (
        user.memberships.filter(is_active=True)
        .select_related("institution")
        .order_by("id")
    )
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "login_id": user.login_id,
        "must_change_password": user.must_change_password,
        "memberships": [
            {
                "id": m.id,
                "institution_id": m.institution_id,
                "institution_name": m.institution.name,
                "type": m.institution.type,
                "role": m.role,
                "config": {
                    **TYPE_CONFIG[m.institution.type],
                    "id": m.institution_id,
                    "name": m.institution.name,
                    "type": m.institution.type,
                    "role": m.role,
                },
            }
            for m in memberships
        ],
    }


def session_response(user):
    refresh = RefreshToken.for_user(user)
    refresh["ver"] = user.auth_version
    response = Response(
        {
            "access": str(refresh.access_token),
            "user": user_payload(user),
            "must_change_password": user.must_change_password,
        }
    )
    response.set_cookie(
        "refresh",
        str(refresh),
        max_age=604800,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        path="/api/auth/",
    )
    response["Cache-Control"] = "no-store"
    return response


@method_decorator(csrf_protect, name="dispatch")
class PublicMutation(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get_authenticate_header(self, request):
        return "Bearer"


@method_decorator(ensure_csrf_cookie, name="dispatch")
@extend_schema(responses=CsrfSerializer)
class CsrfView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


@extend_schema(request=RegistrationSerializer, responses=SessionSerializer)
class RegisterView(PublicMutation):
    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            with transaction.atomic():
                institution = Institution.objects.create(
                    name=data["institution_name"], type=data["institution_type"]
                )
                user = User.objects.create_user(
                    data["email"], data["password"], name=data["name"]
                )
                Membership.objects.create(
                    user=user, institution=institution, role="ADMIN"
                )
        except IntegrityError:
            raise ValidationError(
                "Registration could not be completed with these details."
            )
        return session_response(user)


@extend_schema(request=LoginSerializer, responses=SessionSerializer)
class LoginView(PublicMutation):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data["identifier"].strip().lower()
        key = hashlib.sha256(identifier.encode()).hexdigest()
        now = timezone.now()
        with transaction.atomic():
            LoginAttempt.objects.get_or_create(key=key)
            attempt = LoginAttempt.objects.select_for_update().get(key=key)
            if attempt.locked_until and attempt.locked_until > now:
                return Response(
                    {"detail": "Unable to sign in. Try again later."}, status=429
                )
            if attempt.updated_at < now - timedelta(minutes=15):
                attempt.failures = 0
            user = User.objects.filter(
                Q(email__iexact=identifier) | Q(login_id=identifier)
            ).first()
            valid = (
                user.check_password(serializer.validated_data["password"])
                if user
                else False
            )
            if not user:
                # Perform the normal password hashing cost for unknown identities.
                User().set_password(serializer.validated_data["password"])
            valid = (
                valid
                and user.is_active
                and user.memberships.filter(is_active=True).exists()
            )
            if not valid:
                attempt.failures += 1
                if attempt.failures >= 5:
                    attempt.locked_until = now + timedelta(minutes=15)
                attempt.save()
                return Response(
                    {
                        "detail": "Unable to sign in. Check your details or try again later."
                    },
                    status=401,
                )
            attempt.failures = 0
            attempt.locked_until = None
            attempt.save()
        return session_response(user)


@extend_schema(request=None, responses=SessionSerializer)
class RefreshView(PublicMutation):
    def post(self, request):
        try:
            with transaction.atomic():
                token = RefreshToken(request.COOKIES.get("refresh", ""))
                user = User.objects.select_for_update().get(
                    pk=token["user_id"], is_active=True
                )
                # Recheck the blacklist under the per-user lock to reject concurrent replay.
                token.check_blacklist()
                if (
                    token.get("ver") != user.auth_version
                    or not user.memberships.filter(is_active=True).exists()
                ):
                    raise AuthenticationFailed("Session expired.")
                token.blacklist()
                return session_response(user)
        except (TokenError, User.DoesNotExist, KeyError):
            raise AuthenticationFailed("Session expired.")


@extend_schema(request=None, responses={204: None})
class LogoutView(PublicMutation):
    def post(self, request):
        try:
            RefreshToken(request.COOKIES.get("refresh", "")).blacklist()
        except TokenError:
            pass
        response = Response(status=204)
        response.delete_cookie(
            "refresh", path="/api/auth/", samesite=settings.REFRESH_COOKIE_SAMESITE
        )
        return response


@extend_schema(request=None, responses=MeSerializer)
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(user_payload(request.user))


@extend_schema(request=ChangePasswordSerializer, responses=SessionSerializer)
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request.user.pk)
            if not user.check_password(serializer.validated_data["current_password"]):
                raise ValidationError(
                    {"current_password": ["Current password is incorrect."]}
                )
            if user.check_password(serializer.validated_data["new_password"]):
                raise ValidationError(
                    {"new_password": ["Choose a different password."]}
                )
            user.set_password(serializer.validated_data["new_password"])
            user.must_change_password = False
            user.save()
            PasswordGrant.objects.filter(user=user, used_at=None).update(
                used_at=timezone.now()
            )
            revoke(user)
        return session_response(user)


def grant_password(user, institution):
    PasswordGrant.objects.filter(user=user, used_at=None).update(used_at=timezone.now())
    raw = secrets.token_urlsafe(32)
    PasswordGrant.objects.create(
        user=user,
        institution=institution,
        digest=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=timezone.now() + timedelta(hours=24),
    )
    return raw


def deliver_grant(user, institution, raw):
    link = (
        settings.FRONTEND_URL.rstrip("/") + "/set-password?" + urlencode({"token": raw})
    )
    send_mail(
        "Set your institution account password",
        f"You have been invited to {institution.name}. Set your password within 24 hours: {link}",
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


@extend_schema(request=RequestPasswordSerializer, responses=DetailSerializer)
class RequestPasswordView(PublicMutation):
    def post(self, request):
        serializer = RequestPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user = User.objects.filter(email__iexact=email.strip(), is_active=True).first()
        if user:
            membership = (
                user.memberships.filter(is_active=True)
                .select_related("institution")
                .first()
            )
            if membership:
                # SMTP failure is deliberately not disclosed to an anonymous caller.
                try:
                    with transaction.atomic():
                        raw = grant_password(user, membership.institution)
                        deliver_grant(user, membership.institution, raw)
                except (OSError, SMTPException):
                    pass
        return Response(
            {
                "detail": "If this email has an active account, a password link will be sent."
            }
        )


@extend_schema(request=SetPasswordSerializer, responses=DetailSerializer)
class SetPasswordView(PublicMutation):
    def post(self, request):
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw = serializer.validated_data["token"]
        password = serializer.validated_data["password"]
        with transaction.atomic():
            grant = (
                PasswordGrant.objects.select_for_update()
                .filter(
                    digest=hashlib.sha256(raw.encode()).hexdigest(),
                    used_at=None,
                    expires_at__gt=timezone.now(),
                )
                .first()
            )
            if not grant:
                raise ValidationError("Password link is invalid or expired.")
            user = User.objects.select_for_update().get(pk=grant.user_id)
            if (
                not user.is_active
                or not user.memberships.filter(
                    institution=grant.institution, is_active=True
                ).exists()
            ):
                raise ValidationError("Password link is invalid or expired.")
            try:
                validate_password(password, user)
            except DjangoValidationError as exc:
                raise ValidationError({"password": exc.messages})
            user.set_password(password)
            user.must_change_password = False
            user.save()
            PasswordGrant.objects.filter(user=user, used_at=None).update(
                used_at=timezone.now()
            )
            revoke(user)
        return Response({"detail": "Password saved. You can now sign in."})


@extend_schema(parameters=TENANT_HEADERS)
class MemberViewSet(TenantQuerysetMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, PasswordChanged, InstitutionAdmin]
    serializer_class = MemberSerializer
    queryset = Membership.objects.select_related("user", "institution").order_by("id")

    def list(self, request):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @extend_schema(request=InviteSerializer, responses={201: InviteResponseSerializer})
    def create(self, request):
        serializer = InviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        institution = membership_for(request).institution
        if data["role"] not in TYPE_CONFIG[institution.type]["roles"]:
            raise ValidationError("This role is unavailable for this institution type.")
        try:
            with transaction.atomic():
                email = data.get("email")
                existing = User.objects.filter(email=email).first() if email else None
                if existing:
                    # Cross-tenant account claiming needs explicit consent, introduced separately.
                    if not existing.memberships.filter(
                        institution=institution
                    ).exists():
                        raise ValidationError(
                            "This identity cannot be invited here. Contact the account owner."
                        )
                    user = User.objects.select_for_update().get(pk=existing.pk)
                    if Membership.objects.filter(
                        user=user, institution=institution, role=data["role"]
                    ).exists():
                        raise ValidationError("This membership already exists.")
                    member = Membership.objects.create(
                        user=user, institution=institution, role=data["role"]
                    )
                    audit(request, institution, "membership.add_role", member.pk)
                    return Response(
                        {"member": MemberSerializer(member).data}, status=201
                    )
                temporary = (
                    secrets.token_urlsafe(18)
                    if data["delivery"] == "temporary"
                    else None
                )
                user = User.objects.create_user(
                    email,
                    temporary,
                    name=data["name"],
                    login_id=data.get("login_id", "").lower() or None,
                    must_change_password=True,
                )
                member = Membership.objects.create(
                    user=user, institution=institution, role=data["role"]
                )
                if data["delivery"] == "email":
                    raw = grant_password(user, institution)
                    try:
                        deliver_grant(user, institution, raw)
                    except (OSError, SMTPException):
                        raise ValidationError(
                            "Email delivery failed. Check SMTP settings or use a temporary password."
                        )
                audit(request, institution, "membership.invite", member.pk)
                result = {"member": MemberSerializer(member).data}
                if temporary:
                    result["temporary_password"] = temporary
                response = Response(result, status=201)
                response["Cache-Control"] = "no-store"
                return response
        except IntegrityError:
            raise ValidationError("This identity or membership is unavailable.")

    @extend_schema(request=ActivationSerializer, responses=ActivationSerializer)
    @action(detail=True, methods=["post"])
    def activation(self, request, pk=None):
        member = self.get_object()
        serializer = ActivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        active = serializer.validated_data["is_active"]
        if member.user_id == request.user.id:
            raise ValidationError("You cannot change your own activation.")
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=member.user_id)
            # Institution administrators cannot deactivate another tenant's membership.
            Membership.objects.filter(user=user, institution=member.institution).update(
                is_active=active
            )
            user.is_active = user.memberships.filter(is_active=True).exists()
            user.save(update_fields=["is_active"])
            revoke(user)
            audit(
                request,
                member.institution,
                "user.reactivate" if active else "user.deactivate",
                user.pk,
            )
        return Response({"is_active": active})

    @extend_schema(request=None, responses=TemporarySerializer)
    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        member = self.get_object()
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=member.user_id)
            if user.memberships.exclude(institution=member.institution).exists():
                raise ValidationError(
                    "Shared accounts must use the self-service password reset."
                )
            temporary = secrets.token_urlsafe(18)
            user.set_password(temporary)
            user.must_change_password = True
            user.save()
            PasswordGrant.objects.filter(user=user, used_at=None).update(
                used_at=timezone.now()
            )
            revoke(user)
            audit(request, member.institution, "user.password_reset", user.pk)
        response = Response({"temporary_password": temporary})
        response["Cache-Control"] = "no-store"
        return response
