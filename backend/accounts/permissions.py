from rest_framework.permissions import BasePermission
from rest_framework.exceptions import NotFound, PermissionDenied
from .models import Membership


class PasswordChanged(BasePermission):
    message = "Change your temporary password before continuing."

    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated and not request.user.must_change_password
        )


def membership_for(request):
    if hasattr(request, "_membership"):
        return request._membership
    try:
        institution_id = int(request.headers.get("X-Institution-ID", ""))
        role = request.headers.get("X-Role", "")
    except ValueError:
        raise PermissionDenied("Select an institution and role.")
    membership = (
        Membership.objects.select_related("institution", "user")
        .filter(
            user=request.user, institution_id=institution_id, role=role, is_active=True
        )
        .first()
    )
    if not membership:
        raise NotFound("Institution membership not found.")
    request._membership = membership
    return membership


class TenantMember(BasePermission):
    def has_permission(self, request, view):
        membership_for(request)
        return True


class InstitutionAdmin(TenantMember):
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and membership_for(request).role == Membership.Role.ADMIN
        )


class TenantQuerysetMixin:
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(institution_id=membership_for(self.request).institution_id)
        )
