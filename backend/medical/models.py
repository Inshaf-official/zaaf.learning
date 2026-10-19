from django.conf import settings
from django.db import models
from students.models import TenantRecord


class StudentMedical(TenantRecord):
    student = models.OneToOneField(
        "students.Student", on_delete=models.CASCADE, related_name="medical"
    )
    blood_group = models.CharField(
        max_length=3,
        blank=True,
        choices=[(x, x) for x in ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]],
    )
    allergies = models.TextField(blank=True, max_length=4000)
    conditions = models.TextField(blank=True, max_length=4000)
    emergency_contacts = models.JSONField(default=list)
    doctor = models.CharField(max_length=250, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["institution", "student"])]


class BreakGlassAccess(TenantRecord):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE)
    reason = models.CharField(max_length=1000)
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(fields=["institution", "user", "student", "expires_at"])
        ]
