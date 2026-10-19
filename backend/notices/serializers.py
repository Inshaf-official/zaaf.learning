from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "title", "body", "kind", "student", "created_at", "read_at"]
        read_only_fields = fields


from .models import Notice
from students.models import ClassGroup, Division
from students.serializers import TenantPK


class NoticeSerializer(serializers.ModelSerializer):
    class_group = TenantPK(
        queryset=ClassGroup.objects.all(), allow_null=True, required=False
    )
    division = TenantPK(
        queryset=Division.objects.all(), allow_null=True, required=False
    )

    class Meta:
        model = Notice
        fields = [
            "id",
            "title",
            "body",
            "audience",
            "class_group",
            "division",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate(self, data):
        audience = data.get("audience", "ALL")
        group = data.get("class_group")
        division = data.get("division")
        if audience == "ALL" and (group or division):
            raise serializers.ValidationError(
                "All-institution notices cannot have a group filter."
            )
        if audience != "ALL" and not group:
            raise serializers.ValidationError("Choose a class or batch.")
        if audience == "DIVISION" and (
            not division or division.class_group_id != group.pk
        ):
            raise serializers.ValidationError("Choose a matching division.")
        if audience != "DIVISION" and division:
            raise serializers.ValidationError(
                "Only division notices can specify a division."
            )
        return data
