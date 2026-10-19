from rest_framework import serializers
from .models import StudentMedical, BreakGlassAccess


class EmergencyContactSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    relationship = serializers.CharField(max_length=50, allow_blank=True, default="")
    phone = serializers.RegexField(r"^\+?[0-9 ()-]{6,25}$")


class MedicalSerializer(serializers.ModelSerializer):
    emergency_contacts = EmergencyContactSerializer(many=True, max_length=10)

    class Meta:
        model = StudentMedical
        fields = [
            "blood_group",
            "allergies",
            "conditions",
            "emergency_contacts",
            "doctor",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]


class BreakGlassSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=10, max_length=1000, trim_whitespace=True)


class GrantSerializer(serializers.ModelSerializer):
    class Meta:
        model = BreakGlassAccess
        fields = ["id", "reason", "granted_at", "expires_at"]


class MedicalResponseSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    student_name = serializers.CharField()
    can_edit = serializers.BooleanField()
    access_expires_at = serializers.DateTimeField(allow_null=True)
    card = MedicalSerializer(allow_null=True)
