from django.db import models


def attendance_defaults():
    return {
        "low_threshold": 75,
        "late_edit_policy": "ADMIN_ONLY",
        "sessions": ["DAY"],
        "marks_drop_threshold": 20,
    }


def grading_defaults():
    return [
        {"min": 90, "grade": "A+"},
        {"min": 80, "grade": "A"},
        {"min": 70, "grade": "B"},
        {"min": 60, "grade": "C"},
        {"min": 50, "grade": "D"},
        {"min": 0, "grade": "E"},
    ]


class Institution(models.Model):
    class Type(models.TextChoices):
        SCHOOL = "SCHOOL", "School"
        TUITION = "TUITION", "Tuition centre"
        MADRASA = "MADRASA", "Madrasa"

    name = models.CharField(max_length=200)
    type = models.CharField(max_length=10, choices=Type.choices)
    attendance_rules = models.JSONField(default=attendance_defaults)
    grading_scale = models.JSONField(default=grading_defaults)
    language = models.CharField(
        max_length=2, default="en", choices=[("en", "English"), ("ml", "Malayalam")]
    )
    address = models.CharField(max_length=500, blank=True)
    logo = models.BinaryField(null=True, blank=True)
    logo_type = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
