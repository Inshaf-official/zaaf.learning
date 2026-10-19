from django.conf import settings
from django.db import models
from students.models import TenantRecord


class Exam(TenantRecord):
    name = models.CharField(max_length=150)
    class_group = models.ForeignKey("students.ClassGroup", on_delete=models.PROTECT)
    date = models.DateField()
    published = models.BooleanField(default=False)

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["institution", "class_group", "date"])]


class ExamSubject(TenantRecord):
    exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE, related_name="exam_subjects"
    )
    subject = models.ForeignKey("students.Subject", on_delete=models.PROTECT)
    max_marks = models.DecimalField(max_digits=7, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "exam", "subject"], name="unique_exam_subject"
            ),
            models.CheckConstraint(
                condition=models.Q(max_marks__gt=0), name="positive_max_marks"
            ),
        ]


class Mark(TenantRecord):
    student = models.ForeignKey(
        "students.Student", on_delete=models.PROTECT, related_name="marks"
    )
    exam_subject = models.ForeignKey(
        ExamSubject, on_delete=models.CASCADE, related_name="marks"
    )
    score = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    absent = models.BooleanField(default=False)
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    edited_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["student_id", "exam_subject_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "student", "exam_subject"],
                name="unique_student_mark",
            ),
            models.CheckConstraint(
                condition=models.Q(score__gte=0), name="nonnegative_mark"
            ),
        ]
        indexes = [models.Index(fields=["institution", "student", "exam_subject"])]


class ReportCard(TenantRecord):
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    generated_at = models.DateTimeField(auto_now=True)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "student", "exam"], name="unique_report_card"
            )
        ]


class MarkSheetHold(TenantRecord):
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    reason_type = models.CharField(
        max_length=12,
        choices=[
            ("FEES", "Fees"),
            ("DISCIPLINE", "Discipline"),
            ("DOCUMENTS", "Documents"),
            ("OTHER", "Other"),
        ],
    )
    note = models.CharField(max_length=1000)
    released_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "student", "exam"],
                condition=models.Q(released_at=None),
                name="one_active_hold",
            )
        ]
        indexes = [
            models.Index(fields=["institution", "student", "exam", "released_at"])
        ]
