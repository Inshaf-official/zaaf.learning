from html import escape
from decimal import Decimal
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiTypes, OpenApiParameter
from accounts.permissions import (
    PasswordChanged,
    TenantMember,
    membership_for,
    TenantQuerysetMixin,
    InstitutionAdmin,
)
from accounts.schema import TENANT_HEADERS
from accounts.views import audit
from core.permissions import tenant, student_for, AdminWrite, SensitiveResponse
from core.pdf import pdf_response
from students.permissions import visible_students, annotated_students
from students.views import IntegrityMixin
from students.models import Student
from .models import Exam, ExamSubject, Mark, ReportCard, MarkSheetHold
from .serializers import (
    ExamSerializer,
    ExamSubjectSerializer,
    MarkSerializer,
    BulkMarkSerializer,
    HoldSerializer,
    PublicationSerializer,
)
from .permissions import EnterMarks


def grade(institution, score, maximum):
    percentage = 100 * Decimal(score) / Decimal(maximum) if maximum else Decimal(0)
    return next(
        (
            str(r["grade"])
            for r in sorted(
                institution.grading_scale, key=lambda r: r["min"], reverse=True
            )
            if percentage >= Decimal(str(r["min"]))
        ),
        "E",
    )


def held(student, exam):
    return MarkSheetHold.objects.filter(
        institution=student.institution, student=student, exam=exam, released_at=None
    ).exists()


def results(request, exam, student, preloaded_marks=None, hold_ids=None):
    private = membership_for(request).role in ["PARENT", "STUDENT"]
    if private and not exam.published:
        raise PermissionDenied("This exam has not been published.")
    if private and (
        held(student, exam) if hold_ids is None else student.pk in hold_ids
    ):
        return {
            "held": True,
            "message": "This mark sheet is on hold. Contact the institution office.",
            "marks": [],
        }
    rows = (
        preloaded_marks
        if preloaded_marks is not None
        else Mark.objects.filter(
            institution=tenant(request), student=student, exam_subject__exam=exam
        ).select_related("student", "exam_subject__subject")
    )
    return {
        "held": False,
        "marks": [
            {
                **MarkSerializer(row).data,
                "grade": grade(tenant(request), row.score, row.exam_subject.max_marks),
            }
            for row in rows
        ],
    }


@extend_schema(parameters=TENANT_HEADERS)
class ExamViewSet(
    IntegrityMixin, SensitiveResponse, TenantQuerysetMixin, viewsets.ModelViewSet
):
    permission_classes = [IsAuthenticated, PasswordChanged, TenantMember, AdminWrite]
    queryset = (
        Exam.objects.select_related("class_group")
        .prefetch_related("exam_subjects__subject")
        .all()
    )
    serializer_class = ExamSerializer
    filterset_fields = ["class_group"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        query = super().get_queryset()
        if membership_for(self.request).role != "ADMIN":
            query = query.filter(
                class_group_id__in=visible_students(self.request).values(
                    "class_group_id"
                )
            )
        if membership_for(self.request).role in ["PARENT", "STUDENT"]:
            query = query.filter(published=True)
        return query.order_by("-date", "-id")

    def perform_create(self, serializer):
        serializer.save(institution=tenant(self.request))

    def perform_update(self, serializer):
        if (
            serializer.instance.published
            or serializer.instance.exam_subjects.filter(marks__isnull=False).exists()
        ):
            raise ValidationError(
                "Exams with marks cannot be moved. Unpublish and use a new exam for structural changes."
            )
        serializer.save()

    def perform_destroy(self, instance):
        if (
            instance.published
            or Mark.objects.filter(exam_subject__exam=instance).exists()
        ):
            raise ValidationError("Exams with marks cannot be deleted.")
        instance.delete()

    @extend_schema(request=PublicationSerializer, responses=ExamSerializer)
    @action(detail=True, methods=["post"])
    def publication(self, request, pk=None):
        exam = self.get_object()
        serializer = PublicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            exam = Exam.objects.select_for_update().get(pk=exam.pk)
            if serializer.validated_data["published"]:
                subjects = list(exam.exam_subjects.all())
                students = Student.objects.filter(
                    institution=tenant(request),
                    class_group=exam.class_group,
                    deleted_at=None,
                )
                if not subjects or not students.exists():
                    raise ValidationError(
                        "Add subjects and student marks before publishing."
                    )
                expected = students.count() * len(subjects)
                if (
                    Mark.objects.filter(
                        institution=tenant(request),
                        student__in=students,
                        exam_subject__exam=exam,
                    ).count()
                    != expected
                ):
                    raise ValidationError(
                        "Every student needs a score or an absence for every subject."
                    )
            exam.published = serializer.validated_data["published"]
            exam.save(update_fields=["published"])
            audit(
                request,
                tenant(request),
                "exam.publish" if exam.published else "exam.unpublish",
                exam.pk,
            )
        return Response(ExamSerializer(exam).data)

    @extend_schema(
        responses=OpenApiTypes.OBJECT,
        parameters=[OpenApiParameter("student", int, required=True)],
    )
    @action(detail=True, methods=["get"])
    def result(self, request, pk=None):
        exam = self.get_object()
        student = student_for(request, request.query_params.get("student"))
        if (
            student.class_group_id != exam.class_group_id
            and not Mark.objects.filter(
                institution=tenant(request), student=student, exam_subject__exam=exam
            ).exists()
        ):
            raise ValidationError("Exam is for another class.")
        return Response(results(request, exam, student))

    @extend_schema(
        responses={(200, "application/pdf"): bytes},
        parameters=[OpenApiParameter("student", int)],
    )
    @action(detail=True, methods=["get"])
    def report(self, request, pk=None):
        exam = self.get_object()
        query = visible_students(request).filter(class_group=exam.class_group)
        if request.query_params.get("student"):
            query = query.filter(
                pk=student_for(request, request.query_params["student"]).pk
            )
        elif membership_for(request).role not in ["ADMIN", "TEACHER"]:
            raise PermissionDenied("Select your child or own student record.")
        students = list(query)
        marks_by_student = {}
        for mark in Mark.objects.filter(
            institution=tenant(request), student__in=students, exam_subject__exam=exam
        ).select_related("student", "exam_subject__subject"):
            marks_by_student.setdefault(mark.student_id, []).append(mark)
        hold_ids = set(
            MarkSheetHold.objects.filter(
                institution=tenant(request),
                exam=exam,
                released_at=None,
                student__in=students,
            ).values_list("student_id", flat=True)
        )
        content = ""
        for student in students:
            data = results(
                request, exam, student, marks_by_student.get(student.pk, []), hold_ids
            )
            if data["held"]:
                raise PermissionDenied(data["message"])
            content += f'<section class="page"><h2>{escape(student.name)} — {escape(student.admission_number)}</h2><p>{escape(tenant(request).name)} · {escape(exam.name)}</p><table><tr><th>Subject / വിഷയം</th><th>Marks / മാർക്ക്</th><th>Grade / ഗ്രേഡ്</th></tr>'
            for mark in data["marks"]:
                content += f"<tr><td>{escape(mark['subject_name'])}</td><td>{'Absent' if mark['absent'] else mark['score']} / {mark['max_marks']}</td><td>{escape(mark['grade'])}</td></tr>"
            content += "</table></section>"
        if students:
            ReportCard.objects.bulk_create(
                [
                    ReportCard(
                        institution=tenant(request),
                        student=student,
                        exam=exam,
                        generated_by=request.user,
                    )
                    for student in students
                ],
                update_conflicts=True,
                update_fields=["generated_by", "generated_at"],
                unique_fields=["institution", "student", "exam"],
            )
            from accounts.models import AuditLog

            AuditLog.objects.bulk_create(
                [
                    AuditLog(
                        institution=tenant(request),
                        user=request.user,
                        action="report.generate",
                        object=f"{exam.pk}:{student.pk}",
                        ip=request.META.get("REMOTE_ADDR"),
                    )
                    for student in students
                ]
            )
        if not content:
            raise ValidationError("No permitted students for this report.")
        return pdf_response(
            "Report card / പ്രോഗ്രസ് റിപ്പോർട്ട്", content, "report-cards.pdf"
        )


@extend_schema(parameters=TENANT_HEADERS)
class ExamSubjectViewSet(IntegrityMixin, TenantQuerysetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, PasswordChanged, TenantMember, AdminWrite]
    queryset = ExamSubject.objects.select_related("subject", "exam").all()
    serializer_class = ExamSubjectSerializer
    filterset_fields = ["exam"]

    def get_queryset(self):
        query = super().get_queryset()
        if membership_for(self.request).role != "ADMIN":
            query = query.filter(
                exam__class_group_id__in=visible_students(self.request).values(
                    "class_group_id"
                )
            )
        if membership_for(self.request).role in ["PARENT", "STUDENT"]:
            query = query.filter(exam__published=True)
        return query.order_by("id")

    def perform_create(self, serializer):
        if serializer.validated_data["exam"].published:
            raise ValidationError("Unpublish before adding subjects.")
        serializer.save(institution=tenant(self.request))

    def perform_update(self, serializer):
        if serializer.instance.exam.published or serializer.instance.marks.exists():
            raise ValidationError(
                "Subject structure is locked after marks are entered."
            )
        if serializer.validated_data.get("exam", serializer.instance.exam).published:
            raise ValidationError("Cannot move to a published exam.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.exam.published or instance.marks.exists():
            raise ValidationError("Subject has marks or is published.")
        instance.delete()


@extend_schema(parameters=TENANT_HEADERS)
class MarkViewSet(SensitiveResponse, mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, PasswordChanged, TenantMember]
    queryset = Mark.objects.none()
    serializer_class = MarkSerializer
    filterset_fields = ["student", "exam_subject", "exam_subject__exam"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Mark.objects.none()
        if self.request.query_params.get("student"):
            student_for(self.request, self.request.query_params["student"])
        query = Mark.objects.filter(
            institution=tenant(self.request), student__in=visible_students(self.request)
        ).select_related("student", "exam_subject__subject")
        if membership_for(self.request).role in ["PARENT", "STUDENT"]:
            hold = MarkSheetHold.objects.filter(
                institution=tenant(self.request),
                student_id=OuterRef("student_id"),
                exam_id=OuterRef("exam_subject__exam_id"),
                released_at=None,
            )
            query = (
                query.filter(exam_subject__exam__published=True)
                .annotate(is_held=Exists(hold))
                .filter(is_held=False)
            )
        return query.order_by("student__name", "exam_subject_id")

    @extend_schema(request=BulkMarkSerializer, responses=MarkSerializer(many=True))
    @action(detail=False, methods=["post"])
    def bulk(self, request):
        serializer = BulkMarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            subject = get_object_or_404(
                ExamSubject.objects.select_related("exam", "subject"),
                institution=tenant(request),
                pk=data["exam_subject"],
            )
            locked = Exam.objects.select_for_update().get(pk=subject.exam_id)
            if locked.published:
                raise ValidationError("Unpublish the exam before changing marks.")
            students = {
                s.pk: s
                for s in annotated_students(request).filter(
                    pk__in=[r["student"] for r in data["rows"]], deleted_at=None
                )
            }
            for row in data["rows"]:
                student = students.get(row["student"])
                if not student:
                    from rest_framework.exceptions import NotFound

                    raise NotFound("Student not found.")
                if student.class_group_id != subject.exam.class_group_id:
                    raise ValidationError("Student is in a different class.")
                if not EnterMarks().has_object_permission(
                    request, self, (student, subject)
                ):
                    raise PermissionDenied(
                        "You are not assigned this subject and class."
                    )
                if row["score"] > subject.max_marks or (
                    row["absent"] and row["score"] != 0
                ):
                    raise ValidationError(
                        "Scores must be within the maximum; absent students have zero."
                    )
                mark, _ = Mark.objects.update_or_create(
                    institution=tenant(request),
                    student=student,
                    exam_subject=subject,
                    defaults={
                        "score": row["score"],
                        "absent": row["absent"],
                        "entered_by": request.user,
                    },
                )
                audit(request, tenant(request), "mark.edit", mark.pk)
            return Response(
                MarkSerializer(
                    Mark.objects.filter(
                        institution=tenant(request),
                        exam_subject=subject,
                        student_id__in=students,
                    ).select_related("student", "exam_subject__subject"),
                    many=True,
                ).data
            )


@extend_schema(parameters=TENANT_HEADERS)
class HoldViewSet(
    IntegrityMixin,
    TenantQuerysetMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated, PasswordChanged, InstitutionAdmin]
    queryset = MarkSheetHold.objects.select_related("student", "exam").all()
    serializer_class = HoldSerializer
    filterset_fields = ["student", "exam"]

    def perform_create(self, serializer):
        with transaction.atomic():
            record = serializer.save(institution=tenant(self.request))
            audit(self.request, tenant(self.request), "marks.hold", record.pk)

    @extend_schema(request=None, responses=HoldSerializer)
    @action(detail=True, methods=["post"])
    def release(self, request, pk=None):
        hold = self.get_object()
        with transaction.atomic():
            hold.released_at = timezone.now()
            hold.save(update_fields=["released_at"])
            audit(request, tenant(request), "marks.release", hold.pk)
        return Response(self.get_serializer(hold).data)
