from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from accounts.models import Membership
from accounts.permissions import (
    PasswordChanged,
    TenantMember,
    TenantQuerysetMixin,
    InstitutionAdmin,
    membership_for,
)
from accounts.schema import TENANT_HEADERS
from accounts.views import audit
from .models import (
    AcademicYear,
    ClassGroup,
    Division,
    Subject,
    TeacherAssignment,
    Student,
    ParentStudentLink,
)
from .permissions import (
    AcademicAccess,
    StudentAccess,
    visible_students,
    annotated_students,
    assignments,
)
from .serializers import (
    AcademicYearSerializer,
    ClassGroupSerializer,
    DivisionSerializer,
    SubjectSerializer,
    AssignmentSerializer,
    TeacherChoiceSerializer,
    StudentSerializer,
    StudentDetailSerializer,
    StudentWriteSerializer,
    GuardianInviteSerializer,
    CredentialSerializer,
    StudentMutationSerializer,
    AccountInviteSerializer,
    CapabilitiesSerializer,
    HardDeleteSerializer,
)
from .services import link_guardian, invite_account


class IntegrityMixin:
    def handle_exception(self, exc):
        if isinstance(exc, IntegrityError):
            exc = ValidationError(
                "A conflicting record already exists. Check unique names, codes, and account links."
            )
        elif isinstance(exc, ProtectedError):
            exc = ValidationError(
                "This record is in use. Remove dependent assignments or records first."
            )
        return super().handle_exception(exc)


@extend_schema(parameters=TENANT_HEADERS)
class AcademicViewSet(IntegrityMixin, TenantQuerysetMixin, viewsets.ModelViewSet):
    permission_classes = [
        IsAuthenticated,
        PasswordChanged,
        TenantMember,
        AcademicAccess,
    ]

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save(
                institution=membership_for(self.request).institution
            )
            audit(
                self.request,
                instance.institution,
                "academic.create",
                f"{instance._meta.label}:{instance.pk}",
            )

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            audit(
                self.request,
                instance.institution,
                "academic.update",
                f"{instance._meta.label}:{instance.pk}",
            )

    def perform_destroy(self, instance):
        with transaction.atomic():
            audit(
                self.request,
                instance.institution,
                "academic.delete",
                f"{instance._meta.label}:{instance.pk}",
            )
            instance.delete()


class YearViewSet(AcademicViewSet):
    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer


class GroupViewSet(AcademicViewSet):
    queryset = ClassGroup.objects.select_related("academic_year").all()
    serializer_class = ClassGroupSerializer
    filterset_fields = ["academic_year"]

    def get_queryset(self):
        query = super().get_queryset()
        role = membership_for(self.request).role
        if role == "ADMIN":
            return query
        if role == "TEACHER":
            return query.filter(
                pk__in=assignments(self.request).values("class_group_id")
            )
        return query.filter(
            pk__in=visible_students(self.request).values("class_group_id")
        )


class DivisionViewSet(AcademicViewSet):
    queryset = Division.objects.select_related("class_group").all()
    serializer_class = DivisionSerializer
    filterset_fields = ["class_group"]

    def get_queryset(self):
        query = super().get_queryset()
        role = membership_for(self.request).role
        if role == "ADMIN":
            return query
        if role == "TEACHER":
            whole = (
                assignments(self.request).filter(division=None).values("class_group_id")
            )
            divisions = (
                assignments(self.request).exclude(division=None).values("division_id")
            )
            return query.filter(Q(class_group_id__in=whole) | Q(pk__in=divisions))
        return query.filter(
            pk__in=visible_students(self.request)
            .exclude(division=None)
            .values("division_id")
        )


class SubjectViewSet(AcademicViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer


class AssignmentViewSet(AcademicViewSet):
    queryset = TeacherAssignment.objects.select_related(
        "teacher", "class_group", "division", "subject"
    ).all()
    serializer_class = AssignmentSerializer
    filterset_fields = ["teacher", "class_group", "is_class_teacher"]

    def get_queryset(self):
        query = super().get_queryset()
        role = membership_for(self.request).role
        if role == "ADMIN":
            return query
        if role == "TEACHER":
            return query.filter(teacher=self.request.user)
        raise PermissionDenied("Teacher assignments are restricted to staff.")


@extend_schema(parameters=TENANT_HEADERS)
class TeacherViewSet(
    TenantQuerysetMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):
    permission_classes = [IsAuthenticated, PasswordChanged, InstitutionAdmin]
    queryset = (
        Membership.objects.filter(role="TEACHER", is_active=True, user__is_active=True)
        .select_related("user")
        .order_by("user__name", "id")
    )
    serializer_class = TeacherChoiceSerializer


@extend_schema(parameters=TENANT_HEADERS)
class StudentViewSet(IntegrityMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, PasswordChanged, TenantMember, StudentAccess]
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    filterset_fields = ["class_group", "division"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        query = (
            visible_students(self.request)
            if self.action == "list"
            else annotated_students(self.request).filter(deleted_at=None)
        )
        if self.action != "list":
            query = query.prefetch_related(
                Prefetch(
                    "parent_links",
                    queryset=ParentStudentLink.objects.select_related(
                        "parent"
                    ).order_by("id"),
                )
            )
        search = self.request.query_params.get("search", "").strip()[:150]
        if search and self.action == "list":
            query = query.filter(
                Q(name__icontains=search) | Q(admission_number__icontains=search)
            )
        return query.order_by("name", "id")

    def get_serializer_class(self):
        if self.action in ["create", "partial_update"]:
            return StudentWriteSerializer
        return (
            StudentDetailSerializer if self.action == "retrieve" else StudentSerializer
        )

    def serialize_detail(self, student_id):
        student = self.get_queryset().get(pk=student_id)
        return StudentDetailSerializer(student, context={"request": self.request}).data

    @extend_schema(
        parameters=[OpenApiParameter("search", str)],
        responses=StudentSerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=StudentWriteSerializer, responses={201: StudentMutationSerializer}
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        guardians = data.pop("guardians")
        with transaction.atomic():
            student = Student.objects.create(
                institution=membership_for(request).institution, **data
            )
            credentials = []
            for guardian in guardians:
                _, credential = link_guardian(request, student, guardian)
                if credential:
                    credentials.append(credential)
            audit(request, student.institution, "student.create", student.pk)
            response = Response(
                {
                    "student": self.serialize_detail(student.pk),
                    "credentials": credentials,
                },
                status=201,
            )
            response["Cache-Control"] = "no-store"
            return response

    @extend_schema(request=StudentWriteSerializer, responses=StudentDetailSerializer)
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save()
            audit(request, instance.institution, "student.update", instance.pk)
            return Response(self.serialize_detail(instance.pk))

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        with transaction.atomic():
            instance.deleted_at = timezone.now()
            instance.save(update_fields=["deleted_at", "updated_at"])
            audit(request, instance.institution, "student.archive", instance.pk)
        return Response(status=204)

    @extend_schema(responses=CapabilitiesSerializer)
    @action(detail=False, methods=["get"])
    def capabilities(self, request):
        role = membership_for(request).role
        return Response(
            {
                "can_create": role == "ADMIN"
                or (role == "TEACHER" and assignments(request, True).exists()),
                "can_emergency_lookup": role in ["ADMIN", "TEACHER"],
            }
        )

    @extend_schema(request=GuardianInviteSerializer, responses=CredentialSerializer)
    @action(detail=True, methods=["post"])
    def guardians(self, request, pk=None):
        student = self.get_object()
        serializer = GuardianInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            _, credential = link_guardian(request, student, serializer.validated_data)
            response = Response(
                credential or {"identity": serializer.validated_data["email"]},
                status=201,
            )
            response["Cache-Control"] = "no-store"
            return response

    @extend_schema(
        request=None,
        responses={204: None},
        parameters=[OpenApiParameter("link_id", int, OpenApiParameter.PATH)],
    )
    @action(detail=True, methods=["delete"], url_path="guardians/(?P<link_id>[0-9]+)")
    def remove_guardian(self, request, pk=None, link_id=None):
        student = self.get_object()
        with transaction.atomic():
            Student.objects.select_for_update().get(pk=student.pk)
            link = get_object_or_404(
                ParentStudentLink,
                pk=link_id,
                student=student,
                institution=student.institution,
            )
            if student.parent_links.count() <= 1:
                raise ValidationError(
                    "Keep at least one guardian linked to the student."
                )
            audit(
                request,
                student.institution,
                "guardian.unlink",
                f"{student.pk}:{link.pk}",
            )
            link.delete()
        return Response(status=204)

    @extend_schema(request=AccountInviteSerializer, responses=CredentialSerializer)
    @action(detail=True, methods=["post"])
    def account(self, request, pk=None):
        student = self.get_object()
        if student.institution.type != "SCHOOL":
            raise ValidationError("Student login is only available for schools.")
        serializer = AccountInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            student = Student.objects.select_for_update().get(pk=student.pk)
            if student.user_id:
                raise ValidationError("A login is already linked to this student.")
            data = serializer.validated_data
            user, credential = invite_account(
                request,
                student.name,
                "STUDENT",
                data["delivery"],
                data.get("email"),
                data.get("login_id"),
            )
            if Student.objects.filter(
                user=user, institution=student.institution
            ).exists():
                raise ValidationError("This login is already assigned to a student.")
            student.user = user
            student.save(update_fields=["user", "updated_at"])
            audit(request, student.institution, "student.account", student.pk)
            response = Response(
                credential or {"identity": user.email or user.login_id}, status=201
            )
            response["Cache-Control"] = "no-store"
            return response

    @extend_schema(request=HardDeleteSerializer, responses={204: None})
    @action(detail=True, methods=["post"], url_path="hard-delete")
    def hard_delete(self, request, pk=None):
        if membership_for(request).role != "ADMIN":
            raise PermissionDenied(
                "Only administrators can permanently delete students."
            )
        student = get_object_or_404(
            Student, pk=pk, institution=membership_for(request).institution
        )
        serializer = HardDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if (
            serializer.validated_data["confirm_admission_number"]
            != student.admission_number
        ):
            raise ValidationError("Admission number confirmation does not match.")
        with transaction.atomic():
            audit(request, student.institution, "student.hard_delete", student.pk)
            from django.apps import apps

            for label in [
                "tuition.FeePayment",
                "tuition.TestResult",
                "tuition.FeeInstallment",
                "madrasa.HifzProgress",
                "attendance.Attendance",
                "exams.Mark",
                "exams.MarkSheetHold",
                "events.EventParticipation",
                "events.TimelineEntry",
            ]:
                model = apps.get_model(label)
                lookup = (
                    {"installment__student": student}
                    if label == "tuition.FeePayment"
                    else {"student": student}
                )
                model.objects.filter(institution=student.institution, **lookup).delete()
            student.delete()
        return Response(status=204)
