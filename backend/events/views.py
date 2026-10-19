from django.db import transaction
from django.db.models import ExpressionWrapper, FloatField, Q, Count, Avg, F, Prefetch
from rest_framework import viewsets, mixins
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiTypes, OpenApiParameter
from accounts.permissions import (
    PasswordChanged,
    TenantMember,
    TenantQuerysetMixin,
    InstitutionAdmin,
    membership_for,
)
from accounts.schema import TENANT_HEADERS
from accounts.views import audit
from core.permissions import tenant, student_for, AdminWrite, SensitiveResponse
from students.permissions import visible_students
from students.models import Student
from students.views import IntegrityMixin
from notices.services import notify, family_ids
from .models import Event, EventEligibility, EventParticipation, TimelineEntry
from .serializers import (
    EventSerializer,
    EligibilitySerializer,
    ParticipantSerializer,
    SelectionSerializer,
    TimelineSerializer,
)


def eligible(event):
    students = Student.objects.filter(
        institution=event.institution,
        deleted_at=None,
        class_group__academic_year=event.academic_year,
    )
    rows = list(event.eligibility.all())
    if not rows:
        return students
    criteria = Q(pk__in=[])
    for row in rows:
        clause = Q()
        if row.class_group_id:
            clause &= Q(class_group_id=row.class_group_id)
        if row.division_id:
            clause &= Q(division_id=row.division_id)
        if row.interest_tags:
            tags = Q(pk__in=[])
            for tag in row.interest_tags:
                tags |= Q(interest_tags__contains=[tag])
            clause &= tags
        criteria |= clause
    return students.filter(criteria)


@extend_schema(parameters=TENANT_HEADERS)
class EventViewSet(
    IntegrityMixin, SensitiveResponse, TenantQuerysetMixin, viewsets.ModelViewSet
):
    permission_classes = [IsAuthenticated, PasswordChanged, TenantMember, AdminWrite]
    queryset = (
        Event.objects.select_related("academic_year")
        .prefetch_related("eligibility")
        .all()
    )
    serializer_class = EventSerializer

    def get_queryset(self):
        query = super().get_queryset()
        if membership_for(self.request).role in ["PARENT", "STUDENT"]:
            children = list(
                visible_students(self.request).values(
                    "id",
                    "class_group_id",
                    "division_id",
                    "class_group__academic_year_id",
                    "interest_tags",
                )
            )
            query = query.prefetch_related(
                Prefetch(
                    "participants",
                    queryset=EventParticipation.objects.filter(
                        student_id__in=[s["id"] for s in children]
                    ),
                    to_attr="family_participations",
                )
            )
            ids = []
            for event in query:
                rows = list(event.eligibility.all())
                allowed = any(
                    child["class_group__academic_year_id"] == event.academic_year_id
                    and (
                        not rows
                        or any(
                            (
                                not rule.class_group_id
                                or rule.class_group_id == child["class_group_id"]
                            )
                            and (
                                not rule.division_id
                                or rule.division_id == child["division_id"]
                            )
                            and (
                                not rule.interest_tags
                                or set(rule.interest_tags) & set(child["interest_tags"])
                            )
                            for rule in rows
                        )
                    )
                    for child in children
                )
                if allowed or event.family_participations:
                    ids.append(event.pk)
            query = query.filter(pk__in=ids)
        return query.order_by("-starts_on", "-id")

    def perform_create(self, serializer):
        serializer.save(institution=tenant(self.request))

    def perform_update(self, serializer):
        if serializer.instance.participants.exists():
            raise ValidationError(
                "Events with selected participants cannot change their academic year or eligibility."
            )
        serializer.save()

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["get"])
    def fair_selection(self, request, pk=None):
        event = self.get_object()
        if membership_for(request).role not in ["ADMIN", "TEACHER"]:
            raise PermissionDenied("Selection statistics are restricted to staff.")
        query = (
            eligible(event)
            .filter(pk__in=visible_students(request))
            .annotate(
                event_count=Count(
                    "event_participations",
                    filter=Q(
                        event_participations__status="PARTICIPATED",
                        event_participations__event__academic_year=event.academic_year,
                    ),
                )
            )
            .order_by("event_count", "name", "id")
        )
        page = self.paginate_queryset(query)
        return self.get_paginated_response(
            [
                {
                    "id": s.pk,
                    "name": s.name,
                    "event_count": s.event_count,
                    "never_selected": s.event_count == 0,
                }
                for s in page
            ]
        )

    @extend_schema(
        request=SelectionSerializer, responses=ParticipantSerializer(many=True)
    )
    @action(detail=True, methods=["post"])
    def select(self, request, pk=None):
        event = self.get_object()
        serializer = SelectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            Event.objects.select_for_update().get(pk=event.pk)
            ids = set(data["students"])
            students = list(eligible(event).filter(pk__in=ids))
            if len(students) != len(ids):
                raise ValidationError(
                    "One or more students are not eligible for this event."
                )
            for student in students:
                entry, _ = EventParticipation.objects.update_or_create(
                    institution=tenant(request),
                    event=event,
                    student=student,
                    defaults={"status": data["status"]},
                )
                audit(request, tenant(request), "event.participation", entry.pk)
                notify(
                    tenant(request),
                    family_ids([student]),
                    event.name,
                    f"{student.name}: {event.name} — {data['status']}",
                    kind="EVENT",
                    student=student,
                    key=f"{entry.pk}:{data['status']}",
                )
            return Response(
                ParticipantSerializer(
                    event.participants.filter(student_id__in=ids).select_related(
                        "student"
                    ),
                    many=True,
                ).data
            )

    @extend_schema(responses=ParticipantSerializer(many=True))
    @action(detail=True, methods=["get"])
    def participation(self, request, pk=None):
        event = self.get_object()
        query = (
            event.participants.filter(student__in=visible_students(request))
            .select_related("student")
            .order_by("student__name", "id")
        )
        page = self.paginate_queryset(query)
        return self.get_paginated_response(ParticipantSerializer(page, many=True).data)


@extend_schema(parameters=TENANT_HEADERS)
class EligibilityViewSet(TenantQuerysetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, PasswordChanged, InstitutionAdmin]
    queryset = EventEligibility.objects.select_related(
        "event", "class_group", "division"
    ).order_by("id")
    serializer_class = EligibilitySerializer

    def perform_create(self, serializer):
        if serializer.validated_data["event"].participants.exists():
            raise ValidationError("Eligibility is locked after selection.")
        serializer.save(institution=tenant(self.request))

    def perform_update(self, serializer):
        if serializer.instance.event.participants.exists():
            raise ValidationError("Eligibility is locked after selection.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.event.participants.exists():
            raise ValidationError("Eligibility is locked after selection.")
        instance.delete()


@extend_schema(parameters=TENANT_HEADERS)
class TimelineEntryViewSet(
    TenantQuerysetMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    permission_classes = [IsAuthenticated, PasswordChanged, TenantMember]
    queryset = TimelineEntry.objects.none()
    serializer_class = TimelineSerializer

    def perform_create(self, serializer):
        student_for(self.request, serializer.validated_data["student"].pk, write=True)
        record = serializer.save(
            institution=tenant(self.request), created_by=self.request.user
        )
        audit(self.request, tenant(self.request), "timeline.add", record.pk)


@extend_schema(
    parameters=TENANT_HEADERS + [OpenApiParameter("pk", int, OpenApiParameter.PATH)],
    responses=OpenApiTypes.OBJECT,
)
class TimelineView(SensitiveResponse, APIView):
    permission_classes = [IsAuthenticated, PasswordChanged, TenantMember]

    def get(self, request, pk):
        from attendance.models import Attendance
        from exams.models import Mark, MarkSheetHold
        from django.db.models import CharField, Value
        from django.db.models.functions import Cast, Concat

        student = student_for(request, pk)
        family = membership_for(request).role in ["PARENT", "STUDENT"]
        attendance = (
            Attendance.objects.filter(institution=tenant(request), student=student)
            .order_by()
            .annotate(
                entry_id=Concat(Value("attendance-"), Cast("pk", CharField())),
                entry_date=Cast("date", CharField()),
                entry_kind=Value("ATTENDANCE", output_field=CharField()),
                entry_text=Concat("session", Value(": "), "status"),
            )
            .values_list("entry_id", "entry_date", "entry_kind", "entry_text")
        )
        marks = Mark.objects.filter(institution=tenant(request), student=student)
        if family:
            marks = marks.filter(exam_subject__exam__published=True).exclude(
                exam_subject__exam_id__in=MarkSheetHold.objects.filter(
                    institution=tenant(request), student=student, released_at=None
                ).values("exam_id")
            )
        marks = (
            marks.order_by()
            .annotate(
                entry_id=Concat(Value("mark-"), Cast("pk", CharField())),
                entry_date=Cast("exam_subject__exam__date", CharField()),
                entry_kind=Value("MARK", output_field=CharField()),
                entry_text=Concat(
                    "exam_subject__subject__name",
                    Value(": "),
                    Cast("score", CharField()),
                    Value("/"),
                    Cast("exam_subject__max_marks", CharField()),
                ),
            )
            .values_list("entry_id", "entry_date", "entry_kind", "entry_text")
        )
        events = (
            EventParticipation.objects.filter(
                institution=tenant(request), student=student
            )
            .order_by()
            .annotate(
                entry_id=Concat(Value("event-"), Cast("pk", CharField())),
                entry_date=Cast("event__starts_on", CharField()),
                entry_kind=Value("EVENT", output_field=CharField()),
                entry_text=Concat("event__name", Value(": "), "status"),
            )
            .values_list("entry_id", "entry_date", "entry_kind", "entry_text")
        )
        notes = student.timeline_entries.filter(institution=tenant(request))
        if family:
            notes = notes.filter(visible_to_family=True)
        notes = (
            notes.order_by()
            .annotate(
                entry_id=Concat(Value("note-"), Cast("pk", CharField())),
                entry_date=Cast("created_at", CharField()),
                entry_kind=F("kind"),
                entry_text=F("text"),
            )
            .values_list("entry_id", "entry_date", "entry_kind", "entry_text")
        )
        query = attendance.union(marks, events, notes).order_by(
            "-entry_date", "-entry_id"
        )
        try:
            page = int(request.query_params.get("page", 1))
        except ValueError:
            raise ValidationError("Invalid page.")
        if page < 1:
            raise ValidationError("Invalid page.")
        count = query.count()
        rows = query[(page - 1) * 25 : page * 25]

        def link(number):
            params = request.query_params.copy()
            params["page"] = number
            return request.build_absolute_uri(request.path + "?" + params.urlencode())

        return Response(
            {
                "count": count,
                "next": link(page + 1) if page * 25 < count else None,
                "previous": link(page - 1) if page > 1 else None,
                "results": [
                    dict(
                        zip(
                            ["id", "date", "kind", "text"],
                            [row[0], row[1].replace(" ", "T"), row[2], row[3]],
                        )
                    )
                    for row in rows
                ],
            }
        )


@extend_schema(parameters=TENANT_HEADERS, responses=OpenApiTypes.OBJECT)
class WarningView(SensitiveResponse, APIView):
    permission_classes = [IsAuthenticated, PasswordChanged, TenantMember]

    def get(self, request):
        from attendance.views import summary_rows
        from exams.models import Mark

        if membership_for(request).role not in ["ADMIN", "TEACHER"]:
            raise PermissionDenied("Warnings are restricted to staff.")
        attendance = [r for r in summary_rows(request) if r["alert"]]
        rows = (
            Mark.objects.filter(
                institution=tenant(request),
                student__in=visible_students(request),
                exam_subject__exam__published=True,
            )
            .values(
                "student_id",
                "student__name",
                "exam_subject__exam_id",
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
            .order_by(
                "student_id", "-exam_subject__exam__date", "-exam_subject__exam_id"
            )
        )
        grouped = {}
        for row in rows:
            grouped.setdefault(row["student_id"], []).append(row)
        threshold = tenant(request).attendance_rules.get("marks_drop_threshold", 20)
        drops = []
        for student, marks in grouped.items():
            if (
                len(marks) > 1
                and marks[1]["percentage"] - marks[0]["percentage"] >= threshold
            ):
                drops.append(
                    {
                        "student": student,
                        "name": marks[0]["student__name"],
                        "previous": round(marks[1]["percentage"], 1),
                        "current": round(marks[0]["percentage"], 1),
                    }
                )
        return Response({"attendance": attendance[:100], "marks": drops[:100]})
