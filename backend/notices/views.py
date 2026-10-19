from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from accounts.permissions import PasswordChanged, TenantMember, TenantQuerysetMixin
from accounts.schema import TENANT_HEADERS
from .models import Notification
from .serializers import NotificationSerializer


@extend_schema(parameters=TENANT_HEADERS)
class NotificationViewSet(
    TenantQuerysetMixin, mixins.ListModelMixin, viewsets.GenericViewSet
):
    permission_classes = [IsAuthenticated, PasswordChanged, TenantMember]
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return super().get_queryset().filter(recipient=self.request.user)

    @extend_schema(request=None, responses=NotificationSerializer)
    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return Response(self.get_serializer(notification).data)


from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied
from accounts.models import Membership
from accounts.permissions import membership_for
from accounts.views import audit
from core.permissions import tenant, group_write, SensitiveResponse
from students.models import Student, TeacherAssignment
from students.permissions import visible_students, assignments
from .models import Notice
from .serializers import NoticeSerializer
from .services import notify, family_ids


@extend_schema(parameters=TENANT_HEADERS)
class NoticeViewSet(
    SensitiveResponse,
    TenantQuerysetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated, PasswordChanged, TenantMember]
    queryset = Notice.objects.select_related("class_group", "division").all()
    serializer_class = NoticeSerializer

    def get_queryset(self):
        query = super().get_queryset()
        if membership_for(self.request).role == "ADMIN":
            return query
        criteria = Q(audience="ALL")
        for row in (
            visible_students(self.request)
            .values("class_group_id", "division_id")
            .distinct()
        ):
            criteria |= Q(class_group_id=row["class_group_id"]) & (
                Q(division=None) | Q(division_id=row["division_id"])
            )
        if membership_for(self.request).role == "TEACHER":
            for row in assignments(self.request).values(
                "class_group_id", "division_id"
            ):
                criteria |= Q(class_group_id=row["class_group_id"]) & (
                    Q(division=None) | Q(division_id=row["division_id"])
                    if row["division_id"]
                    else Q()
                )
        return query.filter(criteria).order_by("-created_at", "-id")

    def perform_create(self, serializer):
        data = serializer.validated_data
        role = membership_for(self.request).role
        if role != "ADMIN":
            if role != "TEACHER" or data["audience"] == "ALL":
                raise PermissionDenied(
                    "Only administrators can send institution-wide notices."
                )
            group_write(self.request, data["class_group"], data.get("division"))
        with transaction.atomic():
            notice = serializer.save(
                institution=tenant(self.request), created_by=self.request.user
            )
            if notice.audience == "ALL":
                recipients = Membership.objects.filter(
                    institution=tenant(self.request),
                    is_active=True,
                    user__is_active=True,
                ).values_list("user_id", flat=True)
            else:
                students = Student.objects.filter(
                    institution=tenant(self.request),
                    class_group=notice.class_group,
                    deleted_at=None,
                )
                if notice.division:
                    students = students.filter(division=notice.division)
                parents = list(family_ids(students))
                pupils = list(
                    students.exclude(user=None).values_list("user_id", flat=True)
                )
                teachers = TeacherAssignment.objects.filter(
                    institution=tenant(self.request), class_group=notice.class_group
                )
                if notice.division:
                    teachers = teachers.filter(
                        Q(division=None) | Q(division=notice.division)
                    )
                recipients = (
                    parents
                    + pupils
                    + list(teachers.values_list("teacher_id", flat=True))
                )
            notify(
                tenant(self.request),
                recipients,
                notice.title,
                notice.body,
                "NOTICE",
                key=str(notice.pk),
            )
            audit(self.request, tenant(self.request), "notice.send", notice.pk)
