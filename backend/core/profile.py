from django.db.models import Avg, F, ExpressionWrapper, FloatField
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiTypes, OpenApiParameter
from accounts.permissions import PasswordChanged, TenantMember, membership_for
from accounts.schema import TENANT_HEADERS
from .permissions import student_for, tenant, SensitiveResponse


@extend_schema(
    parameters=TENANT_HEADERS + [OpenApiParameter("pk", int, OpenApiParameter.PATH)],
    responses=OpenApiTypes.OBJECT,
)
class ProfileInsights(SensitiveResponse, APIView):
    permission_classes = [IsAuthenticated, PasswordChanged, TenantMember]

    def get(self, request, pk):
        from attendance.models import Attendance
        from exams.models import Mark, MarkSheetHold
        from events.models import EventParticipation

        student = student_for(request, pk)
        attendance = Attendance.objects.filter(
            institution=tenant(request),
            student=student,
            date__year=timezone.localdate().year,
        )
        total = attendance.count()
        attended = attendance.exclude(status="ABSENT").count()
        streak = 0
        for status in attendance.order_by("-date", "-session").values_list(
            "status", flat=True
        ):
            if status == "ABSENT":
                break
            streak += 1
        marks = Mark.objects.filter(
            institution=tenant(request),
            student=student,
            exam_subject__exam__published=True,
        )
        if membership_for(request).role in ["PARENT", "STUDENT"]:
            marks = marks.exclude(
                exam_subject__exam_id__in=MarkSheetHold.objects.filter(
                    institution=tenant(request), student=student, released_at=None
                ).values("exam_id")
            )
        trend = (
            marks.values(
                "exam_subject__exam_id",
                "exam_subject__exam__name",
                "exam_subject__exam__date",
            )
            .annotate(
                percentage=Avg(
                    ExpressionWrapper(
                        F("score") * 100.0 / F("exam_subject__max_marks"),
                        output_field=FloatField(),
                    )
                )
            )
            .order_by("exam_subject__exam__date")
        )
        events = (
            EventParticipation.objects.filter(
                institution=tenant(request), student=student
            )
            .select_related("event")
            .order_by("-event__starts_on")[:20]
        )
        return Response(
            {
                "attendance": {
                    "total": total,
                    "attended": attended,
                    "percentage": round(attended * 100 / total, 1) if total else None,
                    "streak": streak,
                },
                "trend": [
                    {
                        "exam": r["exam_subject__exam__name"],
                        "percentage": round(r["percentage"], 1),
                    }
                    for r in trend
                ],
                "events": [
                    {
                        "id": e.pk,
                        "name": e.event.name,
                        "date": e.event.starts_on,
                        "status": e.status,
                    }
                    for e in events
                ],
            }
        )
