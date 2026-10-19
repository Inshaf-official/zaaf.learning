from django.conf import settings
from django.db import models
from students.models import TenantRecord


class FeeInstallment(TenantRecord):
    student = models.ForeignKey(
        "students.Student", on_delete=models.PROTECT, related_name="fee_installments"
    )
    label = models.CharField(max_length=150)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    due_date = models.DateField()
    last_reminded = models.DateField(null=True)

    class Meta:
        ordering = ["due_date", "id"]
        indexes = [models.Index(fields=["institution", "student", "due_date"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    amount__gt=0,
                    paid_amount__gte=0,
                    paid_amount__lte=models.F("amount"),
                ),
                name="valid_fee_balance",
            )
        ]


class FeePayment(TenantRecord):
    installment = models.ForeignKey(
        FeeInstallment, on_delete=models.PROTECT, related_name="payments"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference = models.CharField(max_length=100)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "installment", "reference"],
                name="unique_payment_reference",
            )
        ]


class TestSeries(TenantRecord):
    name = models.CharField(max_length=150)
    class_group = models.ForeignKey("students.ClassGroup", on_delete=models.PROTECT)
    subject = models.ForeignKey("students.Subject", on_delete=models.PROTECT)
    date = models.DateField()
    max_marks = models.DecimalField(max_digits=7, decimal_places=2)
    published = models.BooleanField(default=False)

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["institution", "class_group", "date"])]


class TestResult(TenantRecord):
    student = models.ForeignKey(
        "students.Student", on_delete=models.PROTECT, related_name="test_results"
    )
    series = models.ForeignKey(
        TestSeries, on_delete=models.CASCADE, related_name="results"
    )
    score = models.DecimalField(max_digits=7, decimal_places=2)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        ordering = ["-score", "student_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "student", "series"], name="unique_test_result"
            ),
            models.CheckConstraint(
                condition=models.Q(score__gte=0), name="nonnegative_test_result"
            ),
        ]
        indexes = [models.Index(fields=["institution", "student", "series"])]
