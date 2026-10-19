from django.conf import settings
from django.db import models
from students.models import TenantRecord


class Attendance(TenantRecord):
    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        ABSENT = "ABSENT", "Absent"
        LATE = "LATE", "Late"

    student = models.ForeignKey(
        "students.Student", on_delete=models.PROTECT, related_name="attendance_records"
    )
    date = models.DateField()
    session = models.CharField(max_length=40, default="DAY")
    status = models.CharField(max_length=8, choices=Status.choices)
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(auto_now=True)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-date", "session", "student_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "student", "date", "session"],
                name="unique_attendance_session",
            )
        ]
        indexes = [
            models.Index(fields=["institution", "date", "session"]),
            models.Index(fields=["institution", "student", "date"]),
        ]
