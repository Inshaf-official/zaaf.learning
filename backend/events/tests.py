import pytest
from students.tests import school, actor
from django.utils import timezone
from .models import Event, EventEligibility, EventParticipation, TimelineEntry
from notices.models import Notification, Notice, EmailDelivery

pytestmark = pytest.mark.django_db


def test_eligibility_fairness_and_parent_notifications(school):
    event = Event.objects.create(
        institution=school["institution"],
        name="Science fair",
        academic_year=school["year"],
        starts_on=timezone.localdate(),
    )
    EventEligibility.objects.create(
        institution=school["institution"],
        event=event,
        class_group=school["group"],
        division=school["a"],
    )
    admin = actor(school, "admin")
    fair = admin.get(f"/api/events/{event.pk}/fair_selection/")
    assert fair.status_code == 200
    assert [r["id"] for r in fair.data["results"]] == [school["target"].pk]
    assert fair.data["results"][0]["never_selected"]
    assert (
        admin.post(
            f"/api/events/{event.pk}/select/",
            {"students": [school["outside"].pk]},
            format="json",
        ).status_code
        == 400
    )
    assert (
        actor(school, "subject")
        .post(
            f"/api/events/{event.pk}/select/",
            {"students": [school["target"].pk]},
            format="json",
        )
        .status_code
        == 403
    )
    assert (
        admin.post(
            f"/api/events/{event.pk}/select/",
            {"students": [school["target"].pk], "status": "PARTICIPATED"},
            format="json",
        ).status_code
        == 200
    )
    assert (
        admin.get(f"/api/events/{event.pk}/fair_selection/").data["results"][0][
            "event_count"
        ]
        == 1
    )
    assert Notification.objects.filter(
        recipient=school["users"]["parent"][0], kind="EVENT"
    ).exists()
    assert (
        actor(school, "parent")
        .get(f"/api/events/{event.pk}/participation/")
        .data["count"]
        == 1
    )


def test_notice_audience_and_timeline_privacy(school):
    client = actor(school, "class")
    assert (
        client.post(
            "/api/notices/",
            {"title": "All", "body": "All families", "audience": "ALL"},
            format="json",
        ).status_code
        == 403
    )
    notice = client.post(
        "/api/notices/",
        {
            "title": "Class trip",
            "body": "Meet at 9am",
            "audience": "DIVISION",
            "class_group": school["group"].pk,
            "division": school["a"].pk,
        },
        format="json",
    )
    assert notice.status_code == 201, notice.data
    assert actor(school, "parent").get("/api/notices/").data["count"] == 1
    assert actor(school, "otherparent").get("/api/notices/").data["count"] == 0
    assert EmailDelivery.objects.exists()
    target = school["target"]
    for public in [True, False]:
        assert (
            client.post(
                "/api/timeline-entries/",
                {
                    "student": target.pk,
                    "kind": "INCIDENT",
                    "text": "Private concern" if not public else "Family update",
                    "visible_to_family": public,
                },
                format="json",
            ).status_code
            == 201
        )
    parent = actor(school, "parent").get(f"/api/students/{target.pk}/timeline/")
    assert parent.status_code == 200
    assert [r["text"] for r in parent.data["results"]] == ["Family update"]
    assert (
        actor(school, "otherparent")
        .get(f"/api/students/{target.pk}/timeline/")
        .status_code
        == 403
    )
