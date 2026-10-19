from django.urls import path, include
from rest_framework.permissions import AllowAny
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerSplitView
from institutions.views import ConfigView, SettingsView, LogoView
from audit.views import AuditViewSet, ExportView, DeleteInstitutionView
from rest_framework.routers import DefaultRouter
from attendance.views import AttendanceViewSet
from core.views import DashboardView
from core.profile import ProfileInsights
from madrasa.views import HifzViewSet, TimetableViewSet
from tuition.views import FeeViewSet, SeriesViewSet, TestResultViewSet
from events.views import (
    EventViewSet,
    EligibilityViewSet,
    TimelineEntryViewSet,
    TimelineView,
    WarningView,
)
from notices.views import NoticeViewSet
from exams.views import ExamViewSet, ExamSubjectViewSet, MarkViewSet, HoldViewSet

router = DefaultRouter()
router.register("audit-log", AuditViewSet, basename="audit-log")
router.register("hifz", HifzViewSet, basename="hifz")
router.register("timetable", TimetableViewSet, basename="timetable")
router.register("fees", FeeViewSet, basename="fees")
router.register("test-series", SeriesViewSet, basename="test-series")
router.register("test-results", TestResultViewSet, basename="test-results")
router.register("events", EventViewSet, basename="events")
router.register("event-eligibility", EligibilityViewSet, basename="event-eligibility")
router.register("timeline-entries", TimelineEntryViewSet, basename="timeline-entries")
router.register("notices", NoticeViewSet, basename="notices")
router.register("exams", ExamViewSet, basename="exams")
router.register("exam-subjects", ExamSubjectViewSet, basename="exam-subjects")
router.register("marks", MarkViewSet, basename="marks")
router.register("holds", HoldViewSet, basename="holds")
router.register("attendance", AttendanceViewSet, basename="attendance")
urlpatterns = [
    path("api/students/<int:pk>/insights/", ProfileInsights.as_view()),
    path("api/institution/settings/", SettingsView.as_view()),
    path("api/institution/logo/", LogoView.as_view()),
    path("api/institution/export/", ExportView.as_view()),
    path("api/institution/delete/", DeleteInstitutionView.as_view()),
    path("api/students/<int:pk>/timeline/", TimelineView.as_view()),
    path("api/warnings/", WarningView.as_view()),
    path("api/dashboard/", DashboardView.as_view()),
    path("api/", include(router.urls)),
    path("api/", include("accounts.urls")),
    path("api/", include("students.urls")),
    path("api/institution/config/", ConfigView.as_view()),
    path(
        "api/schema/",
        SpectacularAPIView.as_view(permission_classes=[AllowAny]),
        name="schema",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerSplitView.as_view(
            url_name="schema", permission_classes=[AllowAny]
        ),
    ),
]
