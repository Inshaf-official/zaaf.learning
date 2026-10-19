from rest_framework import serializers
from accounts.models import AuditLog


class AuditSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.name", allow_null=True)

    class Meta:
        model = AuditLog
        fields = ["id", "user_name", "action", "object", "timestamp", "ip"]


class DeleteInstitutionSerializer(serializers.Serializer):
    confirmation = serializers.CharField(max_length=250)
