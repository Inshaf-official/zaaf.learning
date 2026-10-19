from django.urls import path, include
from rest_framework.routers import DefaultRouter
from medical.views import MedicalView, BreakGlassView, EmergencyDirectory
from notices.views import NotificationViewSet
from .views import (
    YearViewSet,
    GroupViewSet,
    DivisionViewSet,
    SubjectViewSet,
    AssignmentViewSet,
    TeacherViewSet,
    StudentViewSet,
)

router = DefaultRouter()
router.register("academic-years", YearViewSet, basename="academic-years")
router.register("class-groups", GroupViewSet, basename="class-groups")
router.register("divisions", DivisionViewSet, basename="divisions")
router.register("subjects", SubjectViewSet, basename="subjects")
router.register(
    "teacher-assignments", AssignmentViewSet, basename="teacher-assignments"
)
router.register("teachers", TeacherViewSet, basename="teachers")
router.register("students", StudentViewSet, basename="students")
router.register("notifications", NotificationViewSet, basename="notifications")
urlpatterns = [
    path("medical/directory/", EmergencyDirectory.as_view()),
    path("students/<int:pk>/medical/", MedicalView.as_view()),
    path("students/<int:pk>/break-glass/", BreakGlassView.as_view()),
    path("", include(router.urls)),
]
