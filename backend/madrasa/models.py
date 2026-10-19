from django.conf import settings
from django.db import models
from students.models import TenantRecord


class HifzProgress(TenantRecord):
    student = models.ForeignKey(
        "students.Student", on_delete=models.PROTECT, related_name="hifz_progress"
    )
    date = models.DateField()
    surah = models.PositiveSmallIntegerField()
    juz = models.PositiveSmallIntegerField()
    lines = models.PositiveIntegerField()
    revision_status = models.CharField(
        max_length=12,
        choices=[("NEW", "New"), ("REVISING", "Revising"), ("SECURE", "Secure")],
    )
    note = models.CharField(max_length=1000, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["institution", "student", "date"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    surah__gte=1, surah__lte=114, juz__gte=1, juz__lte=30
                ),
                name="valid_quran_location",
            )
        ]


class TimetableEntry(TenantRecord):
    class_group = models.ForeignKey("students.ClassGroup", on_delete=models.PROTECT)
    kind = models.CharField(
        max_length=10, choices=[("SCHOOL", "School"), ("MADRASA", "Madrasa")]
    )
    weekday = models.PositiveSmallIntegerField()
    starts_at = models.TimeField()
    ends_at = models.TimeField()
    label = models.CharField(max_length=150)

    class Meta:
        ordering = ["weekday", "starts_at", "id"]
        indexes = [models.Index(fields=["institution", "class_group", "weekday"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at"), weekday__lte=6),
                name="valid_timetable_slot",
            )
        ]
