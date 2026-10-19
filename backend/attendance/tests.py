from datetime import timedelta
import pytest
from django.utils import timezone
from students.tests import school, actor
from .models import Attendance

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "name,expected",
    [
        ("admin", 200),
        ("class", 200),
        ("subject", 403),
        ("unassigned", 403),
        ("parent", 403),
        ("student", 403),
    ],
)
def test_bulk_permission(school, name, expected):
    response = actor(school, name).post(
        "/api/attendance/bulk/",
        {
            "date": timezone.localdate().isoformat(),
            "session": "DAY",
            "rows": [
                {"student": school["target"].pk, "status": "ABSENT", "revision": 0}
            ],
        },
        format="json",
    )
    assert response.status_code == expected, response.data


def test_conflict_and_late_edit(school):
    path = "/api/attendance/bulk/"
    data = {
        "date": timezone.localdate().isoformat(),
        "session": "DAY",
        "rows": [{"student": school["target"].pk, "status": "PRESENT", "revision": 0}],
    }
    client = actor(school, "class")
    assert client.post(path, data, format="json").status_code == 200
    data["rows"][0]["status"] = "ABSENT"
    assert client.post(path, data, format="json").status_code == 409
    data["rows"][0]["revision"] = 1
    Attendance.objects.update(created_at=timezone.now() - timedelta(hours=25))
    assert client.post(path, data, format="json").status_code == 403
    assert actor(school, "admin").post(path, data, format="json").status_code == 200
    data["rows"][0].update(revision=2, status="LATE")
    school["institution"].attendance_rules["late_edit_policy"] = "BLOCK"
    school["institution"].save()
    assert actor(school, "admin").post(path, data, format="json").status_code == 403


def test_atomic_and_child_reports(school):
    data = {
        "date": timezone.localdate().isoformat(),
        "rows": [
            {"student": school["target"].pk, "status": "PRESENT"},
            {"student": school["outside"].pk, "status": "ABSENT"},
        ],
    }
    assert (
        actor(school, "class")
        .post("/api/attendance/bulk/", data, format="json")
        .status_code
        == 403
    )
    assert Attendance.objects.count() == 0
    assert (
        actor(school, "admin")
        .post("/api/attendance/bulk/", data, format="json")
        .status_code
        == 200
    )
    report = actor(school, "parent").get("/api/attendance/summary/").data
    assert {r["student"] for r in report["results"]} == {
        school["target"].pk,
        school["sibling"].pk,
    }
    assert (
        actor(school, "parent")
        .get(f"/api/attendance/?student={school['outside'].pk}")
        .status_code
        == 403
    )
