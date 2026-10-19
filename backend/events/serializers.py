from rest_framework import serializers
from students.serializers import TenantPK
from students.models import AcademicYear, ClassGroup, Division
from .models import Event, EventEligibility, EventParticipation, TimelineEntry


class EligibilitySerializer(serializers.ModelSerializer):
    event = TenantPK(queryset=Event.objects.all())
    class_group = TenantPK(
        queryset=ClassGroup.objects.all(), allow_null=True, required=False
    )
    division = TenantPK(
        queryset=Division.objects.all(), allow_null=True, required=False
    )
    interest_tags = serializers.ListField(
        child=serializers.CharField(max_length=50), max_length=20, required=False
    )

    class Meta:
        model = EventEligibility
        fields = ["id", "event", "class_group", "division", "interest_tags"]

    def validate(self, data):
        if self.instance:
            data = {
                **{
                    key: getattr(self.instance, key)
                    for key in ["event", "class_group", "division", "interest_tags"]
                },
                **data,
            }
        group = data.get("class_group")
        division = data.get("division")
        if division and (not group or division.class_group_id != group.pk):
            raise serializers.ValidationError(
                "Division must belong to the selected class."
            )
        if group and group.academic_year_id != data["event"].academic_year_id:
            raise serializers.ValidationError(
                "Eligibility must use the event academic year."
            )
        data["interest_tags"] = [
            x.strip().lower() for x in data.get("interest_tags", []) if x.strip()
        ]
        return data


class EventSerializer(serializers.ModelSerializer):
    academic_year = TenantPK(queryset=AcademicYear.objects.all())
    eligibility = EligibilitySerializer(many=True, read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "name",
            "description",
            "academic_year",
            "starts_on",
            "eligibility",
        ]


class ParticipantSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="student.name", read_only=True)

    class Meta:
        model = EventParticipation
        fields = ["id", "event", "student", "name", "status", "recorded_at"]
        read_only_fields = fields


class SelectionSerializer(serializers.Serializer):
    students = serializers.ListField(
        child=serializers.IntegerField(min_value=1), allow_empty=False, max_length=500
    )
    status = serializers.ChoiceField(
        choices=["SELECTED", "PARTICIPATED"], default="SELECTED"
    )


class TimelineSerializer(serializers.ModelSerializer):
    from students.models import Student

    student = TenantPK(queryset=Student.objects.all())

    class Meta:
        model = TimelineEntry
        fields = ["id", "student", "kind", "text", "visible_to_family", "created_at"]
        read_only_fields = ["created_at"]
