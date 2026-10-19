import pytest
from decimal import Decimal
from django.utils import timezone
from students.tests import school, actor
from .models import FeeInstallment, TestSeries as Series
from exams.models import Exam, MarkSheetHold

pytestmark = pytest.mark.django_db


def test_payment_idempotency_balance_and_hold_release(school):
    school["institution"].type = "TUITION"
    school["institution"].save()
    fee = FeeInstallment.objects.create(
        institution=school["institution"],
        student=school["target"],
        label="October",
        amount=100,
        due_date=timezone.localdate(),
    )
    exam = Exam.objects.create(
        institution=school["institution"],
        name="Test",
        class_group=school["group"],
        date=timezone.localdate(),
    )
    hold = MarkSheetHold.objects.create(
        institution=school["institution"],
        student=school["target"],
        exam=exam,
        reason_type="FEES",
        note="Due",
    )
    admin = actor(school, "admin")
    path = f"/api/fees/{fee.pk}/payment/"
    assert (
        actor(school, "parent")
        .post(path, {"amount": "100", "reference": "P1"}, format="json")
        .status_code
        == 403
    )
    assert (
        admin.post(path, {"amount": "50", "reference": "P1"}, format="json").status_code
        == 200
    )
    assert (
        admin.post(path, {"amount": "50", "reference": "P1"}, format="json").status_code
        == 200
    )
    fee.refresh_from_db()
    assert fee.paid_amount == 50
    assert (
        admin.post(path, {"amount": "51", "reference": "P2"}, format="json").status_code
        == 400
    )
    assert (
        admin.post(path, {"amount": "50", "reference": "P2"}, format="json").status_code
        == 200
    )
    hold.refresh_from_db()
    assert hold.released_at
    assert actor(school, "otherparent").get("/api/fees/").data["count"] == 0


def test_rank_is_global_but_parent_sees_linked_child_only(school):
    school["institution"].type = "TUITION"
    school["institution"].save()
    series = Series.objects.create(
        institution=school["institution"],
        name="Series",
        class_group=school["group"],
        subject=school["subject"],
        date=timezone.localdate(),
        max_marks=100,
    )
    admin = actor(school, "admin")
    data = {
        "series": series.pk,
        "rows": [
            {"student": school["target"].pk, "score": "80"},
            {"student": school["outside"].pk, "score": "90"},
        ],
    }
    assert admin.post("/api/test-results/bulk/", data, format="json").status_code == 200
    assert actor(school, "parent").get("/api/test-results/").data["count"] == 0
    assert (
        admin.post(
            f"/api/test-series/{series.pk}/publication/",
            {"published": True},
            format="json",
        ).status_code
        == 200
    )
    ranks = actor(school, "parent").get(f"/api/test-series/{series.pk}/ranks/").data
    assert ranks["count"] == 1 and ranks["results"][0]["rank"] == 2
