from django.utils import timezone
from rest_framework.permissions import BasePermission, SAFE_METHODS
from accounts.permissions import membership_for
from students.permissions import can_manage
from .models import BreakGlassAccess


class MedicalCardPermission(BasePermission):
    message = (
        "Medical access requires a class-teacher assignment or an emergency grant."
    )

    def has_object_permission(self, request, view, student):
        request.medical_grant = None
        if can_manage(request, student):
            return True
        if (
            request.method not in SAFE_METHODS
            or membership_for(request).role != "TEACHER"
        ):
            return False
        request.medical_grant = (
            BreakGlassAccess.objects.filter(
                institution=student.institution,
                student=student,
                user=request.user,
                expires_at__gt=timezone.now(),
            )
            .order_by("-expires_at")
            .first()
        )
        return request.medical_grant is not None


class BreakGlassPermission(BasePermission):
    message = "Emergency grants are available only to teachers."

    def has_object_permission(self, request, view, student):
        return membership_for(request).role == "TEACHER"
