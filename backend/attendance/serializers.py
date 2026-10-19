from rest_framework import serializers
from .models import Attendance


class AttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)

    class Meta:
        model = Attendance
        fields = [
            "id",
            "student",
            "student_name",
            "date",
            "session",
            "status",
            "marked_by",
            "edited_at",
            "revision",
        ]
        read_only_fields = fields


class AttendanceRowSerializer(serializers.Serializer):
    student = serializers.IntegerField(min_value=1)
    status = serializers.ChoiceField(choices=Attendance.Status.choices)
    revision = serializers.IntegerField(min_value=0, default=0)


class BulkAttendanceSerializer(serializers.Serializer):
    date = serializers.DateField()
    session = serializers.RegexField(r"^[A-Z0-9_-]{1,40}$", default="DAY")
    rows = AttendanceRowSerializer(many=True, allow_empty=False, max_length=500)

    def validate_rows(self, value):
        if len({x["student"] for x in value}) != len(value):
            raise serializers.ValidationError("Do not repeat students.")
        return value


class SummarySerializer(serializers.Serializer):
    student = serializers.IntegerField()
    name = serializers.CharField()
    total = serializers.IntegerField()
    attended = serializers.IntegerField()
    percentage = serializers.FloatField()
    alert = serializers.BooleanField()
