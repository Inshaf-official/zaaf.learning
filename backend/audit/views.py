import csv, json, zipfile
from io import StringIO, BytesIO
from django.apps import apps
from django.db import transaction
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from rest_framework import viewsets, mixins
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiTypes
from accounts.models import AuditLog, Membership
from accounts.permissions import PasswordChanged, InstitutionAdmin, TenantQuerysetMixin
from accounts.schema import TENANT_HEADERS
from accounts.views import audit
from core.permissions import tenant, SensitiveResponse
from .serializers import AuditSerializer, DeleteInstitutionSerializer


@extend_schema(parameters=TENANT_HEADERS)
class AuditViewSet(
    SensitiveResponse,
    TenantQuerysetMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated, PasswordChanged, InstitutionAdmin]
    queryset = AuditLog.objects.select_related("user").order_by("-timestamp", "-id")
    serializer_class = AuditSerializer
    filterset_fields = ["action", "user"]


def csv_file(fields, rows):
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(fields)
    for row in rows:
        values = []
        for value in row:
            if isinstance(value, (list, dict)):
                value = json.dumps(value, ensure_ascii=False)
            value = "" if value is None else str(value)
            if value.startswith(("=", "+", "-", "@", "\t", "\r")):
                value = "'" + value
            values.append(value)
        writer.writerow(values)
    return buffer.getvalue().encode("utf-8-sig")


@extend_schema(parameters=TENANT_HEADERS, responses={(200, "application/zip"): bytes})
class ExportView(SensitiveResponse, APIView):
    permission_classes = [IsAuthenticated, PasswordChanged, InstitutionAdmin]

    def get(self, request):
        institution = tenant(request)
        audit(request, institution, "institution.export", institution.pk)
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for model in apps.get_models():
                if model._meta.app_label not in [
                    "accounts",
                    "students",
                    "attendance",
                    "exams",
                    "events",
                    "medical",
                    "notices",
                    "madrasa",
                    "tuition",
                ]:
                    continue
                names = {f.name for f in model._meta.fields}
                if "institution" not in names or model.__name__ == "PasswordGrant":
                    continue
                fields = [
                    f.attname
                    for f in model._meta.fields
                    if not f.is_relation or f.many_to_one or f.one_to_one
                ]
                archive.writestr(
                    model._meta.label_lower.replace(".", "_") + ".csv",
                    csv_file(
                        fields,
                        model.objects.filter(institution=institution)
                        .values_list(*fields)
                        .iterator(),
                    ),
                )
            users = (
                get_user_model()
                .objects.filter(memberships__institution=institution)
                .distinct()
            )
            fields = ["id", "name", "email", "login_id", "is_active"]
            archive.writestr("users.csv", csv_file(fields, users.values_list(*fields)))
            archive.writestr(
                "institution.csv",
                csv_file(
                    ["id", "name", "type", "address", "language"],
                    [
                        (
                            institution.id,
                            institution.name,
                            institution.type,
                            institution.address,
                            institution.language,
                        )
                    ],
                ),
            )
            archive.writestr(
                "settings.json",
                json.dumps(
                    {
                        "name": institution.name,
                        "type": institution.type,
                        "address": institution.address,
                        "language": institution.language,
                        "attendance_rules": institution.attendance_rules,
                        "grading_scale": institution.grading_scale,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
            if institution.logo:
                extension = {
                    "image/webp": "webp",
                    "image/png": "png",
                    "image/jpeg": "jpg",
                }.get(institution.logo_type, "bin")
                archive.writestr("logo." + extension, bytes(institution.logo))
        response = HttpResponse(buffer.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = (
            'attachment; filename="institution-export.zip"'
        )
        return response


@extend_schema(
    parameters=TENANT_HEADERS,
    request=DeleteInstitutionSerializer,
    responses=OpenApiTypes.OBJECT,
)
class DeleteInstitutionView(SensitiveResponse, APIView):
    permission_classes = [IsAuthenticated, PasswordChanged, InstitutionAdmin]

    def post(self, request):
        institution = tenant(request)
        serializer = DeleteInstitutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data["confirmation"] != f"DELETE {institution.name}":
            raise ValidationError("Type DELETE followed by the exact institution name.")
        # Delete dependent financial/history rows explicitly before their protected parents.
        labels = [
            "tuition.FeePayment",
            "tuition.TestResult",
            "tuition.FeeInstallment",
            "madrasa.HifzProgress",
            "attendance.Attendance",
            "exams.Mark",
            "exams.MarkSheetHold",
            "exams.ReportCard",
            "events.EventParticipation",
            "events.TimelineEntry",
            "medical.BreakGlassAccess",
            "medical.StudentMedical",
            "notices.EmailDelivery",
            "notices.Notification",
            "students.ParentStudentLink",
            "students.TeacherAssignment",
            "events.EventEligibility",
            "notices.Notice",
            "madrasa.TimetableEntry",
            "tuition.TestSeries",
            "exams.ExamSubject",
            "exams.Exam",
            "events.Event",
            "students.Student",
            "students.Division",
            "students.ClassGroup",
            "students.Subject",
            "students.AcademicYear",
            "accounts.PasswordGrant",
            "accounts.AuditLog",
            "accounts.Membership",
        ]
        with transaction.atomic():
            type(institution).objects.select_for_update().get(pk=institution.pk)
            user_ids = list(
                Membership.objects.filter(institution=institution).values_list(
                    "user_id", flat=True
                )
            )
            for label in labels:
                apps.get_model(label).objects.filter(institution=institution).delete()
            institution.delete()
            # Global identities with no other institution are deactivated; token tables stay revocable.
            for user in (
                get_user_model()
                .objects.filter(pk__in=user_ids)
                .filter(memberships__isnull=True)
            ):
                from accounts.views import revoke

                user.is_active = False
                user.save(update_fields=["is_active"])
                revoke(user)
        return Response(
            {
                "detail": "Institution data deleted; unshared accounts deactivated. Backups follow the hosting provider retention policy."
            }
        )
