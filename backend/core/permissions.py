from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.exceptions import PermissionDenied
from accounts.permissions import membership_for
from students.permissions import annotated_students, can_manage, can_read, assignments
from django.shortcuts import get_object_or_404
from django.db.models import Q


def tenant(request):
    return membership_for(request).institution


def student_for(request, pk, write=False):
    try:
        pk = int(pk)
    except (TypeError, ValueError):
        from rest_framework.exceptions import ValidationError

        raise ValidationError("A student ID is required.")
    student = get_object_or_404(
        annotated_students(request).filter(deleted_at=None), pk=pk
    )
    if not (can_manage(request, student) if write else can_read(request, student)):
        raise PermissionDenied("This student is outside your assigned access.")
    return student


def group_write(request, group, division=None):
    member = membership_for(request)
    if member.role == "ADMIN":
        return
    if (
        member.role != "TEACHER"
        or not assignments(request, True)
        .filter(class_group=group)
        .filter(Q(division=None) | Q(division=division))
        .exists()
    ):
        raise PermissionDenied("A class-teacher assignment is required.")


class StaffWrite(BasePermission):
    def has_permission(self, request, view):
        role = membership_for(request).role
        return request.method in SAFE_METHODS or role in ["ADMIN", "TEACHER"]


class AdminWrite(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or membership_for(request).role == "ADMIN"


class SensitiveResponse:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response
