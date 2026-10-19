import csv
from datetime import datetime, timedelta
from html import escape
from io import StringIO
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied, APIException
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from accounts.permissions import PasswordChanged, TenantMember, membership_for
from accounts.schema import TENANT_HEADERS
from accounts.views import audit
from core.permissions import tenant, student_for, SensitiveResponse
from core.pdf import pdf_response
from students.permissions import visible_students, annotated_students, can_manage
from students.models import Student
from .models import Attendance
from .serializers import (
    AttendanceSerializer,
    BulkAttendanceSerializer,
    SummarySerializer,
)


class Conflict(APIException):
    status_code = 409
    default_detail = (
        "Attendance changed since it was loaded. Reload and reconcile the queued save."
    )


def period(request):
    today = timezone.localdate()
    try:
        start = datetime.strptime(
            request.query_params.get("start", today.replace(day=1).isoformat()),
            "%Y-%m-%d",
        ).date()
        end = datetime.strptime(
            request.query_params.get("end", today.isoformat()), "%Y-%m-%d"
        ).date()
    except ValueError:
        raise ValidationError("Use YYYY-MM-DD dates.")
    if end < start or (end - start).days > 366:
        raise ValidationError("Choose a date range of at most one year.")
    return start, end


def summary_rows(request):
    start, end = period(request)
    students = visible_students(request)
    if request.query_params.get("class_group"):
        try:
            group = int(request.query_params["class_group"])
        except ValueError:
            raise ValidationError("Class group must be an integer.")
        students = students.filter(class_group_id=group)
    if request.query_params.get("student"):
        student_for(request, request.query_params["student"])
        students = students.filter(pk=request.query_params["student"])
    query = students.annotate(
        total=Count(
            "attendance_records", filter=Q(attendance_records__date__range=(start, end))
        ),
        attended=Count(
            "attendance_records",
            filter=Q(
                attendance_records__date__range=(start, end),
                attendance_records__status__in=["PRESENT", "LATE"],
            ),
        ),
    )
    threshold = tenant(request).attendance_rules.get("low_threshold", 75)
    return [
        dict(
            student=s.id,
            name=s.name,
            total=s.total,
            attended=s.attended,
            percentage=round(100 * s.attended / s.total, 1) if s.total else 0,
            alert=bool(s.total and 100 * s.attended / s.total < threshold),
        )
        for s in query
    ]


@extend_schema(parameters=TENANT_HEADERS)
class AttendanceViewSet(
    SensitiveResponse, mixins.ListModelMixin, viewsets.GenericViewSet
):
    permission_classes = [IsAuthenticated, PasswordChanged, TenantMember]
    queryset = Attendance.objects.none()
    serializer_class = AttendanceSerializer
    filterset_fields = ["student", "date", "session", "student__class_group"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Attendance.objects.none()
        if self.request.query_params.get("student"):
            student_for(self.request, self.request.query_params["student"])
        return (
            Attendance.objects.filter(
                institution=tenant(self.request),
                student__in=visible_students(self.request),
            )
            .select_related("student")
            .order_by("-date", "student__name", "id")
        )

    @extend_schema(
        request=BulkAttendanceSerializer, responses=AttendanceSerializer(many=True)
    )
    @action(detail=False, methods=["post"])
    def bulk(self, request):
        serializer = BulkAttendanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        institution = tenant(request)
        if data["date"] > timezone.localdate():
            raise ValidationError("Future attendance is not allowed.")
        if institution.type == "SCHOOL" and data[
            "session"
        ] not in institution.attendance_rules.get("sessions", ["DAY"]):
            raise ValidationError("This attendance session is not enabled.")
        ids = [x["student"] for x in data["rows"]]
        # Row locks serialize first-time creation as well as updates of a class register.
        with transaction.atomic():
            list(
                Student.objects.select_for_update()
                .filter(institution=institution, pk__in=ids)
                .order_by("id")
            )
            scope = {
                s.pk: s
                for s in annotated_students(request).filter(pk__in=ids, deleted_at=None)
            }
            if len(scope) != len(ids):
                from rest_framework.exceptions import NotFound

                raise NotFound("Student not found.")
            if any(not can_manage(request, s) for s in scope.values()):
                raise PermissionDenied("Only your class can be managed.")
            existing = {
                x.student_id: x
                for x in Attendance.objects.filter(
                    institution=institution,
                    student_id__in=ids,
                    date=data["date"],
                    session=data["session"],
                )
            }
            now = timezone.now()
            results = []
            for row in data["rows"]:
                record = existing.get(row["student"])
                # Network replay of an already-applied value is idempotent.
                if record and record.status == row["status"]:
                    results.append(record)
                    continue
                if record and record.revision != row["revision"]:
                    raise Conflict()
                if not record and row["revision"] != 0:
                    raise Conflict()
                cutoff = (
                    record.created_at
                    if record
                    else timezone.make_aware(
                        datetime.combine(data["date"], datetime.min.time())
                    )
                ) + timedelta(hours=24)
                if now > cutoff:
                    policy = institution.attendance_rules.get(
                        "late_edit_policy", "ADMIN_ONLY"
                    )
                    if policy == "BLOCK" or membership_for(request).role != "ADMIN":
                        raise PermissionDenied(
                            "Attendance outside the edit window needs administrator approval or is locked."
                        )
                if record:
                    record.status = row["status"]
                    record.marked_by = request.user
                    record.revision += 1
                    record.save()
                    audit(request, institution, "attendance.edit", record.pk)
                else:
                    record = Attendance.objects.create(
                        institution=institution,
                        student_id=row["student"],
                        date=data["date"],
                        session=data["session"],
                        status=row["status"],
                        marked_by=request.user,
                    )
                    audit(request, institution, "attendance.mark", record.pk)
                results.append(record)
            return Response(
                AttendanceSerializer(
                    Attendance.objects.filter(
                        pk__in=[r.pk for r in results]
                    ).select_related("student"),
                    many=True,
                ).data
            )

    @extend_schema(
        responses=SummarySerializer(many=True),
        parameters=[
            OpenApiParameter("start", str),
            OpenApiParameter("end", str),
            OpenApiParameter("class_group", int),
            OpenApiParameter("student", int),
        ],
    )
    @action(detail=False, methods=["get"])
    def summary(self, request):
        rows = summary_rows(request)
        page = self.paginate_queryset(rows)
        return self.get_paginated_response(SummarySerializer(page, many=True).data)

    @extend_schema(
        responses={(200, "text/csv"): bytes},
        parameters=[OpenApiParameter("format", str)],
    )
    @action(detail=False, methods=["get"], url_path="export")
    def export_report(self, request):
        rows = summary_rows(request)
        if request.query_params.get("file") == "pdf":
            table = "<table><tr><th>Student / വിദ്യാർത്ഥി</th><th>Attended</th><th>Total</th><th>%</th></tr>"
            table += (
                "".join(
                    f"<tr><td>{escape(r['name'])}</td><td>{r['attended']}</td><td>{r['total']}</td><td>{r['percentage']}</td></tr>"
                    for r in rows
                )
                + "</table>"
            )
            return pdf_response("Attendance / ഹാജർ", table, "attendance.pdf")
        stream = StringIO()
        writer = csv.writer(stream)
        writer.writerow(["Student", "Attended", "Total", "Percentage"])
        for row in rows:
            name = row["name"]
            name = "'" + name if name.startswith(("=", "+", "-", "@")) else name
            writer.writerow([name, row["attended"], row["total"], row["percentage"]])
        response = HttpResponse(stream.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="attendance.csv"'
        return response
