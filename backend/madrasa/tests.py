import pytest
from students.tests import school, actor

pytestmark = pytest.mark.django_db


def test_type_and_hifz_permissions(school):
    data = {
        "student": school["target"].pk,
        "date": "2026-10-01",
        "surah": 1,
        "juz": 1,
        "lines": 7,
        "revision_status": "SECURE",
    }
    assert (
        actor(school, "admin").post("/api/hifz/", data, format="json").status_code
        == 403
    )
    school["institution"].type = "MADRASA"
    school["institution"].save()
    assert (
        actor(school, "class").post("/api/hifz/", data, format="json").status_code
        == 201
    )
    assert (
        actor(school, "subject").post("/api/hifz/", data, format="json").status_code
        == 403
    )
    assert actor(school, "parent").get("/api/hifz/").data["count"] == 1
    assert actor(school, "otherparent").get("/api/hifz/").data["count"] == 0
    data["surah"] = 115
    assert (
        actor(school, "admin").post("/api/hifz/", data, format="json").status_code
        == 400
    )


def test_dual_timetable_overlap(school):
    school["institution"].type = "MADRASA"
    school["institution"].save()
    data = {
        "class_group": school["group"].pk,
        "kind": "MADRASA",
        "weekday": 0,
        "starts_at": "17:00",
        "ends_at": "18:00",
        "label": "Quran",
    }
    client = actor(school, "admin")
    assert client.post("/api/timetable/", data, format="json").status_code == 201
    assert client.post("/api/timetable/", data, format="json").status_code == 400
    data["kind"] = "SCHOOL"
    assert client.post("/api/timetable/", data, format="json").status_code == 201
