from django.db import transaction
from django.db.models import F
from students.models import ParentStudentLink
from .models import Notification, EmailDelivery


def notify(institution, users, title, body, kind="NOTICE", student=None, key=""):
    users = set(users)
    for user_id in users:
        notification, created = (
            Notification.objects.get_or_create(
                institution=institution,
                recipient_id=user_id,
                delivery_key=f"{kind}:{key}:{user_id}" if key else None,
                defaults={
                    "title": title[:200],
                    "body": body[:2000],
                    "kind": kind,
                    "student": student,
                },
            )
            if key
            else (
                Notification.objects.create(
                    institution=institution,
                    recipient_id=user_id,
                    title=title[:200],
                    body=body[:2000],
                    kind=kind,
                    student=student,
                ),
                True,
            )
        )
        if created:
            delivery = EmailDelivery.objects.create(
                institution=institution, notification=notification
            )

            def enqueue(pk=delivery.pk):
                from .tasks import deliver_email

                try:
                    deliver_email.delay(pk)
                except Exception:
                    # The persisted pending row is recovered by the scheduled dispatcher.
                    import logging

                    logging.getLogger(__name__).warning(
                        "Mail broker unavailable; delivery %s remains pending", pk
                    )

            transaction.on_commit(enqueue)


def family_ids(students):
    return (
        ParentStudentLink.objects.filter(
            student__in=students,
            parent__is_active=True,
            parent__memberships__institution_id=F("institution_id"),
            parent__memberships__role="PARENT",
            parent__memberships__is_active=True,
        )
        .values_list("parent_id", flat=True)
        .distinct()
    )
