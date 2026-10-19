from django.conf import settings
from django.db import models
from students.models import TenantRecord


class Notification(TenantRecord):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    title = models.CharField(max_length=200)
    body = models.TextField(max_length=2000)
    kind = models.CharField(max_length=40, default="MEDICAL_BREAK_GLASS")
    student = models.ForeignKey(
        "students.Student", null=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    delivery_key = models.CharField(max_length=160, null=True, unique=True)
    read_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["institution", "recipient", "read_at"])]


class Notice(TenantRecord):
    title = models.CharField(max_length=200)
    body = models.TextField(max_length=4000)
    audience = models.CharField(
        max_length=10,
        choices=[
            ("ALL", "All"),
            ("CLASS", "Class"),
            ("DIVISION", "Division"),
            ("BATCH", "Batch"),
        ],
        default="ALL",
    )
    class_group = models.ForeignKey(
        "students.ClassGroup", null=True, blank=True, on_delete=models.PROTECT
    )
    division = models.ForeignKey(
        "students.Division", null=True, blank=True, on_delete=models.PROTECT
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["institution", "class_group", "created_at"])]


class EmailDelivery(TenantRecord):
    notification = models.OneToOneField(Notification, on_delete=models.CASCADE)
    attempts = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(null=True)
    skipped_at = models.DateTimeField(null=True)
    last_error = models.CharField(max_length=100, blank=True)
