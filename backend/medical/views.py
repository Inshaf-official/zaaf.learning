from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.models import Membership
from accounts.permissions import PasswordChanged, TenantMember, membership_for
from accounts.schema import TENANT_HEADERS
from accounts.views import audit
from notices.services import notify
from students.permissions import annotated_students, can_manage
from students.serializers import DirectorySerializer
from students.models import Student
from .models import StudentMedical, BreakGlassAccess
from .permissions import MedicalCardPermission, BreakGlassPermission
from .serializers import (
    MedicalSerializer,
    MedicalResponseSerializer,
    BreakGlassSerializer,
    GrantSerializer,
)


class MedicalAccess:
    def student(self, request, pk):
        return get_object_or_404(
            annotated_students(request).filter(deleted_at=None), pk=pk
        )

    def response(self, request, student, grant=None):
        card = StudentMedical.objects.filter(
            institution=student.institution, student=student
        ).first()
        response = Response(
            {
                "student_id": student.pk,
                "student_name": student.name,
                "can_edit": can_manage(request, student),
                "access_expires_at": grant.expires_at if grant else None,
                "card": MedicalSerializer(card).data if card else None,
            }
        )
        response["Cache-Control"] = "no-store"
        return response


@extend_schema(
    parameters=TENANT_HEADERS + [OpenApiParameter("pk", int, OpenApiParameter.PATH)]
)
class MedicalView(MedicalAccess, APIView):
    permission_classes = [
        IsAuthenticated,
        PasswordChanged,
        TenantMember,
        MedicalCardPermission,
    ]

    @extend_schema(responses=MedicalResponseSerializer)
    def get(self, request, pk):
        student = self.student(request, pk)
        self.check_object_permissions(request, student)
        with transaction.atomic():
            audit(request, student.institution, "medical.view", student.pk)
            return self.response(request, student, request.medical_grant)

    @extend_schema(request=MedicalSerializer, responses=MedicalResponseSerializer)
    def put(self, request, pk):
        student = self.student(request, pk)
        self.check_object_permissions(request, student)
        with transaction.atomic():
            # Serialize first creation and updates against the student's row.
            type(student).objects.select_for_update().get(pk=student.pk)
            card = StudentMedical.objects.filter(
                institution=student.institution, student=student
            ).first()
            serializer = MedicalSerializer(card, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(institution=student.institution, student=student)
            audit(request, student.institution, "medical.update", student.pk)
            audit(request, student.institution, "medical.view", student.pk)
            return self.response(request, student)


@extend_schema(
    parameters=TENANT_HEADERS + [OpenApiParameter("pk", int, OpenApiParameter.PATH)]
)
class BreakGlassView(MedicalAccess, APIView):
    permission_classes = [
        IsAuthenticated,
        PasswordChanged,
        TenantMember,
        BreakGlassPermission,
    ]

    @extend_schema(request=BreakGlassSerializer, responses={201: GrantSerializer})
    def post(self, request, pk):
        student = self.student(request, pk)
        self.check_object_permissions(request, student)
        serializer = BreakGlassSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            grant = BreakGlassAccess.objects.create(
                institution=student.institution,
                student=student,
                user=request.user,
                reason=serializer.validated_data["reason"],
                expires_at=timezone.now() + timedelta(minutes=30),
            )
            audit(
                request,
                student.institution,
                "medical.break_glass",
                f"{student.pk}:{grant.pk}",
            )
            admins = Membership.objects.filter(
                institution=student.institution,
                role="ADMIN",
                is_active=True,
                user__is_active=True,
            ).values_list("user_id", flat=True)
            notify(
                student.institution,
                admins,
                "Emergency medical access",
                f"{request.user.name} opened emergency access for {student.name}. Reason: {grant.reason}",
                kind="MEDICAL_BREAK_GLASS",
                student=student,
                key=str(grant.pk),
            )
        response = Response(GrantSerializer(grant).data, status=201)
        response["Cache-Control"] = "no-store"
        return response


@extend_schema(parameters=TENANT_HEADERS + [OpenApiParameter("search", str)])
class EmergencyDirectory(generics.ListAPIView):
    queryset = Student.objects.none()
    permission_classes = [IsAuthenticated, PasswordChanged, TenantMember]
    serializer_class = DirectorySerializer

    def get_queryset(self):
        if membership_for(self.request).role not in ["ADMIN", "TEACHER"]:
            raise PermissionDenied("Emergency search is restricted to staff.")
        query = annotated_students(self.request).filter(deleted_at=None)
        search = self.request.query_params.get("search", "").strip()[:150]
        # No entire-school dump through the emergency lookup by default.
        return (
            query.filter(
                Q(name__icontains=search) | Q(admission_number__icontains=search)
            ).order_by("name", "id")
            if len(search) >= 2
            else query.none()
        )
