from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, BasePermission
from drf_spectacular.utils import extend_schema
from accounts.permissions import (
    PasswordChanged,
    TenantMember,
    TenantQuerysetMixin,
    membership_for,
)
from accounts.schema import TENANT_HEADERS
from accounts.views import audit
from core.permissions import tenant, student_for, group_write, SensitiveResponse
from students.permissions import visible_students
from .models import HifzProgress, TimetableEntry
from .serializers import HifzSerializer, TimetableSerializer


class InstitutionTypePermission(BasePermission):
    def has_permission(self, request, view):
        return tenant(request).type == view.institution_type


@extend_schema(parameters=TENANT_HEADERS)
class HifzViewSet(SensitiveResponse, TenantQuerysetMixin, viewsets.ModelViewSet):
    institution_type = "MADRASA"
    permission_classes = [
        IsAuthenticated,
        PasswordChanged,
        TenantMember,
        InstitutionTypePermission,
    ]
    queryset = HifzProgress.objects.select_related("student").all()
    serializer_class = HifzSerializer
    filterset_fields = ["student", "date", "revision_status"]

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(student__in=visible_students(self.request))
            .order_by("-date", "-id")
        )

    def perform_create(self, serializer):
        student_for(self.request, serializer.validated_data["student"].pk, True)
        row = serializer.save(
            institution=tenant(self.request), recorded_by=self.request.user
        )
        audit(self.request, tenant(self.request), "hifz.record", row.pk)

    def perform_update(self, serializer):
        student_for(self.request, serializer.instance.student_id, True)
        student_for(
            self.request,
            serializer.validated_data.get("student", serializer.instance.student).pk,
            True,
        )
        row = serializer.save()
        audit(self.request, tenant(self.request), "hifz.edit", row.pk)

    def perform_destroy(self, instance):
        student_for(self.request, instance.student_id, True)
        audit(self.request, tenant(self.request), "hifz.delete", instance.pk)
        instance.delete()


@extend_schema(parameters=TENANT_HEADERS)
class TimetableViewSet(TenantQuerysetMixin, viewsets.ModelViewSet):
    institution_type = "MADRASA"
    permission_classes = [
        IsAuthenticated,
        PasswordChanged,
        TenantMember,
        InstitutionTypePermission,
    ]
    queryset = TimetableEntry.objects.select_related("class_group").all()
    serializer_class = TimetableSerializer
    filterset_fields = ["class_group", "kind", "weekday"]

    def get_queryset(self):
        query = super().get_queryset()
        if membership_for(self.request).role != "ADMIN":
            query = query.filter(
                class_group_id__in=visible_students(self.request).values(
                    "class_group_id"
                )
            )
        return query

    def perform_create(self, serializer):
        group_write(self.request, serializer.validated_data["class_group"])
        serializer.save(institution=tenant(self.request))

    def perform_update(self, serializer):
        group_write(self.request, serializer.instance.class_group)
        group_write(
            self.request,
            serializer.validated_data.get(
                "class_group", serializer.instance.class_group
            ),
        )
        serializer.save()

    def perform_destroy(self, instance):
        group_write(self.request, instance.class_group)
        instance.delete()
