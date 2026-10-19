from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from .models import EmailDelivery


@shared_task(bind=True, max_retries=5)
def deliver_email(self, pk):
    with transaction.atomic():
        row = (
            EmailDelivery.objects.select_for_update()
            .select_related("notification__recipient")
            .filter(pk=pk)
            .first()
        )
        if not row or row.sent_at or row.skipped_at or row.attempts >= 6:
            return
        notification = row.notification
        user = notification.recipient
        if (
            not user.is_active
            or not user.email
            or not user.memberships.filter(
                institution=row.institution, is_active=True
            ).exists()
        ):
            row.skipped_at = timezone.now()
            row.save(update_fields=["skipped_at"])
            return
        try:
            send_mail(
                notification.title,
                notification.body,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
        except Exception as exc:
            row.attempts += 1
            row.last_error = type(exc).__name__
            row.save(update_fields=["attempts", "last_error"])
            transaction.on_commit(
                lambda: deliver_email.apply_async(
                    args=[pk], countdown=min(3600, 60 * 2 ** min(row.attempts, 5))
                )
            )
            return
        row.sent_at = timezone.now()
        row.last_error = ""
        row.save(update_fields=["sent_at", "last_error"])


@shared_task
def dispatch_pending():
    for pk in EmailDelivery.objects.filter(
        sent_at=None, skipped_at=None, attempts__lt=6
    ).values_list("pk", flat=True)[:200]:
        deliver_email.delay(pk)
