from datetime import timedelta
from celery import shared_task
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from notices.services import notify, family_ids
from .models import FeeInstallment


def remind_installment(pk):
    with transaction.atomic():
        row = (
            FeeInstallment.objects.select_for_update()
            .select_related("student")
            .get(pk=pk)
        )
        today = timezone.localdate()
        if row.paid_amount >= row.amount or row.last_reminded == today:
            return
        notify(
            row.institution,
            family_ids([row.student]),
            "Fee installment reminder",
            f"{row.student.name}: {row.label}. Due {row.due_date:%d/%m/%Y}. Outstanding INR {row.amount - row.paid_amount}.",
            "FEE",
            row.student,
            key=f"{row.pk}:{today}",
        )
        row.last_reminded = today
        row.save(update_fields=["last_reminded"])


@shared_task
def fee_reminders():
    ids = (
        FeeInstallment.objects.filter(
            institution__type="TUITION",
            student__deleted_at=None,
            due_date__lte=timezone.localdate() + timedelta(days=3),
            paid_amount__lt=F("amount"),
        )
        .exclude(last_reminded=timezone.localdate())
        .values_list("pk", flat=True)
    )
    for pk in ids:
        remind_installment(pk)
