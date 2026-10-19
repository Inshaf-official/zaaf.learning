from django.conf import settings
from django.db import models
from students.models import TenantRecord


class Event(TenantRecord):
    name = models.CharField(max_length=200)
    description = models.TextField(max_length=4000, blank=True)
    academic_year = models.ForeignKey("students.AcademicYear", on_delete=models.PROTECT)
    starts_on = models.DateField()

    class Meta:
        ordering = ["-starts_on", "-id"]
        indexes = [models.Index(fields=["institution", "academic_year", "starts_on"])]


class EventEligibility(TenantRecord):
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="eligibility"
    )
    class_group = models.ForeignKey(
        "students.ClassGroup", null=True, blank=True, on_delete=models.PROTECT
    )
    division = models.ForeignKey(
        "students.Division", null=True, blank=True, on_delete=models.PROTECT
    )
    interest_tags = models.JSONField(default=list)


class EventParticipation(TenantRecord):
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="participants"
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.PROTECT,
        related_name="event_participations",
    )
    status = models.CharField(
        max_length=15,
        choices=[("SELECTED", "Selected"), ("PARTICIPATED", "Participated")],
        default="SELECTED",
    )
    recorded_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "event", "student"],
                name="unique_event_participant",
            )
        ]
        indexes = [models.Index(fields=["institution", "student", "event"])]


class TimelineEntry(TenantRecord):
    student = models.ForeignKey(
        "students.Student", on_delete=models.PROTECT, related_name="timeline_entries"
    )
    kind = models.CharField(
        max_length=12,
        choices=[
            ("REMARK", "Remark"),
            ("INCIDENT", "Incident"),
            ("FEE_NOTE", "Fee note"),
        ],
    )
    text = models.CharField(max_length=2000)
    visible_to_family = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["institution", "student", "created_at"])]
