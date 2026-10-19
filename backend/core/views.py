from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiTypes
from accounts.permissions import PasswordChanged, TenantMember, membership_for
from accounts.schema import TENANT_HEADERS
from students.permissions import visible_students, assignments
from attendance.models import Attendance
from attendance.views import summary_rows
from .permissions import SensitiveResponse


@extend_schema(parameters=TENANT_HEADERS, responses=OpenApiTypes.OBJECT)
class DashboardView(SensitiveResponse, APIView):
    permission_classes = [IsAuthenticated, PasswordChanged, TenantMember]

    def get(self, request):
        students = visible_students(request)
        today = Attendance.objects.filter(
            institution=membership_for(request).institution,
            date=timezone.localdate(),
            student__in=students,
        )
        summaries = summary_rows(request)
        return Response(
            {
                "student_count": students.count(),
                "present_today": today.filter(status__in=["PRESENT", "LATE"]).count(),
                "absent_today": today.filter(status="ABSENT").count(),
                "alerts": [r for r in summaries if r["alert"]][:25],
                "children": summaries[:25],
                "can_mark": membership_for(request).role == "ADMIN"
                or (
                    membership_for(request).role == "TEACHER"
                    and assignments(request, True).exists()
                ),
            }
        )
