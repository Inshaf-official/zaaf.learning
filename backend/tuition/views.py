from django.db import transaction
from django.db.models import ExpressionWrapper, FloatField, F, Avg
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiTypes
from accounts.permissions import (
    PasswordChanged,
    TenantMember,
    TenantQuerysetMixin,
    membership_for,
)
from accounts.schema import TENANT_HEADERS
from accounts.views import audit
from core.permissions import (
    tenant,
    student_for,
    group_write,
    AdminWrite,
    SensitiveResponse,
)
from students.permissions import visible_students, annotated_students
from students.models import Student
from exams.permissions import EnterMarks
from exams.models import MarkSheetHold
from exams.serializers import PublicationSerializer
from madrasa.views import InstitutionTypePermission
from .models import FeeInstallment, FeePayment, TestSeries, TestResult
from .serializers import (
    FeeSerializer,
    PaymentSerializer,
    SeriesSerializer,
    TestBulkSerializer,
    TestResultSerializer,
)


def release_fee_holds(request, student):
    if not FeeInstallment.objects.filter(
        institution=student.institution,
        student=student,
        due_date__lte=timezone.localdate(),
        paid_amount__lt=F("amount"),
    ).exists():
        for hold in MarkSheetHold.objects.filter(
            institution=student.institution,
            student=student,
            reason_type="FEES",
            released_at=None,
        ):
            hold.released_at = timezone.now()
            hold.save(update_fields=["released_at"])
            audit(request, student.institution, "marks.auto_release", hold.pk)


@extend_schema(parameters=TENANT_HEADERS)
class FeeViewSet(
    SensitiveResponse,
    TenantQuerysetMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    institution_type = "TUITION"
    permission_classes = [
        IsAuthenticated,
        PasswordChanged,
        TenantMember,
        InstitutionTypePermission,
        AdminWrite,
    ]
    queryset = FeeInstallment.objects.select_related("student").all()
    serializer_class = FeeSerializer
    filterset_fields = ["student", "due_date"]

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(student__in=visible_students(self.request))
            .order_by("due_date", "id")
        )

    def perform_create(self, serializer):
        student_for(self.request, serializer.validated_data["student"].pk, True)
        record = serializer.save(institution=tenant(self.request))
        audit(self.request, tenant(self.request), "fee.create", record.pk)

    @extend_schema(request=PaymentSerializer, responses=FeeSerializer)
    @action(detail=True, methods=["post"])
    def payment(self, request, pk=None):
        installment = self.get_object()
        serializer = PaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            row = FeeInstallment.objects.select_for_update().get(pk=installment.pk)
            prior = FeePayment.objects.filter(
                institution=tenant(request),
                installment=row,
                reference=data["reference"],
            ).first()
            if prior:
                if prior.amount != data["amount"]:
                    raise ValidationError(
                        "Reference already exists with a different amount."
                    )
                return Response(self.get_serializer(row).data)
            if row.paid_amount + data["amount"] > row.amount:
                raise ValidationError("Payment exceeds the outstanding balance.")
            FeePayment.objects.create(
                institution=tenant(request),
                installment=row,
                amount=data["amount"],
                reference=data["reference"],
                recorded_by=request.user,
            )
            row.paid_amount += data["amount"]
            row.save(update_fields=["paid_amount"])
            audit(request, tenant(request), "fee.payment", row.pk)
            release_fee_holds(request, row.student)
        return Response(self.get_serializer(row).data)

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["post"])
    def remind(self, request, pk=None):
        row = self.get_object()
        from .tasks import remind_installment

        remind_installment(row.pk)
        return Response(
            {"detail": "Reminder recorded for delivery if a balance is due."}
        )


@extend_schema(parameters=TENANT_HEADERS)
class SeriesViewSet(SensitiveResponse, TenantQuerysetMixin, viewsets.ModelViewSet):
    institution_type = "TUITION"
    permission_classes = [
        IsAuthenticated,
        PasswordChanged,
        TenantMember,
        InstitutionTypePermission,
    ]
    queryset = TestSeries.objects.select_related("subject", "class_group").all()
    serializer_class = SeriesSerializer

    def get_queryset(self):
        query = (
            super()
            .get_queryset()
            .filter(
                class_group_id__in=visible_students(self.request).values(
                    "class_group_id"
                )
            )
            if membership_for(self.request).role != "ADMIN"
            else super().get_queryset()
        )
        if membership_for(self.request).role in ["PARENT", "STUDENT"]:
            query = query.filter(published=True)
        return query.order_by("-date", "-id")

    def perform_create(self, serializer):
        group_write(self.request, serializer.validated_data["class_group"])
        serializer.save(institution=tenant(self.request))

    def perform_update(self, serializer):
        group_write(self.request, serializer.instance.class_group)
        if serializer.instance.results.exists():
            raise ValidationError("Series with scores cannot change structure.")
        group_write(
            self.request,
            serializer.validated_data.get(
                "class_group", serializer.instance.class_group
            ),
        )
        serializer.save()

    def perform_destroy(self, instance):
        group_write(self.request, instance.class_group)
        if instance.results.exists():
            raise ValidationError("Series has scores.")
        instance.delete()

    @extend_schema(request=PublicationSerializer, responses=SeriesSerializer)
    @action(detail=True, methods=["post"])
    def publication(self, request, pk=None):
        row = self.get_object()
        group_write(request, row.class_group)
        serializer = PublicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            row = TestSeries.objects.select_for_update().get(pk=row.pk)
            if serializer.validated_data["published"]:
                count = Student.objects.filter(
                    institution=tenant(request),
                    class_group=row.class_group,
                    deleted_at=None,
                ).count()
                if (
                    not count
                    or row.results.filter(student__deleted_at=None).count() != count
                ):
                    raise ValidationError(
                        "Enter results for all active batch students before publishing."
                    )
            row.published = serializer.validated_data["published"]
            row.save(update_fields=["published"])
            audit(request, tenant(request), "test.publication", row.pk)
        return Response(self.get_serializer(row).data)

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["get"])
    def ranks(self, request, pk=None):
        series = self.get_object()
        rows = list(
            series.results.select_related("student")
            .filter(student__deleted_at=None)
            .order_by("-score", "student_id")
        )
        allowed = set(visible_students(request).values_list("pk", flat=True))
        output = []
        previous = None
        rank = 0
        for index, row in enumerate(rows, 1):
            if row.score != previous:
                rank = index
            previous = row.score
            if row.student_id in allowed:
                output.append(
                    {
                        "student": row.student_id,
                        "name": row.student.name,
                        "score": row.score,
                        "maximum": series.max_marks,
                        "rank": rank,
                    }
                )
        page = self.paginate_queryset(output)
        return self.get_paginated_response(page)

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=False, methods=["get"])
    def performance(self, request):
        if membership_for(request).role not in ["ADMIN", "TEACHER"]:
            raise PermissionDenied("Performance summaries are staff-only.")
        query = (
            TestResult.objects.filter(
                institution=tenant(request),
                student__in=visible_students(request),
                series__published=True,
            )
            .values(
                "series__class_group_id", "series__class_group__name", "series__name"
            )
            .annotate(
                average=Avg(
                    ExpressionWrapper(
                        F("score") * 100.0 / F("series__max_marks"),
                        output_field=FloatField(),
                    )
                )
            )
            .order_by("series__class_group__name")
        )
        page = self.paginate_queryset(query)
        return self.get_paginated_response(page)


@extend_schema(parameters=TENANT_HEADERS)
class TestResultViewSet(
    SensitiveResponse, mixins.ListModelMixin, viewsets.GenericViewSet
):
    institution_type = "TUITION"
    permission_classes = [
        IsAuthenticated,
        PasswordChanged,
        TenantMember,
        InstitutionTypePermission,
    ]
    queryset = TestResult.objects.none()
    serializer_class = TestResultSerializer
    filterset_fields = ["student", "series"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return TestResult.objects.none()
        query = TestResult.objects.filter(
            institution=tenant(self.request), student__in=visible_students(self.request)
        ).select_related("student")
        if membership_for(self.request).role in ["PARENT", "STUDENT"]:
            query = query.filter(series__published=True)
        return query.order_by("-score", "id")

    @extend_schema(
        request=TestBulkSerializer, responses=TestResultSerializer(many=True)
    )
    @action(detail=False, methods=["post"])
    def bulk(self, request):
        serializer = TestBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            series = get_object_or_404(
                TestSeries.objects.select_for_update().select_related(
                    "subject", "class_group"
                ),
                institution=tenant(request),
                pk=data["series"],
            )
            if series.published:
                raise ValidationError("Unpublish before changing scores.")
            if len({r["student"] for r in data["rows"]}) != len(data["rows"]):
                raise ValidationError("Duplicate students.")
            scope = {
                s.pk: s
                for s in annotated_students(request).filter(
                    pk__in=[r["student"] for r in data["rows"]], deleted_at=None
                )
            }
            from students.permissions import can_read
            from rest_framework.exceptions import NotFound

            for row in data["rows"]:
                student = scope.get(row["student"])
                if not student:
                    raise NotFound("Student not found.")
                if not can_read(request, student):
                    raise PermissionDenied("Assigned class required.")
                if (
                    student.class_group_id != series.class_group_id
                    or row["score"] > series.max_marks
                ):
                    raise ValidationError("Invalid batch or score.")
                if not EnterMarks().has_object_permission(
                    request, self, (student, series)
                ):
                    raise PermissionDenied("Assigned subject and batch required.")
                result, _ = TestResult.objects.update_or_create(
                    institution=tenant(request),
                    series=series,
                    student=student,
                    defaults={"score": row["score"], "recorded_by": request.user},
                )
                audit(request, tenant(request), "test.mark", result.pk)
            return Response(
                TestResultSerializer(
                    series.results.filter(
                        student_id__in=[r["student"] for r in data["rows"]]
                    ).select_related("student"),
                    many=True,
                ).data
            )
