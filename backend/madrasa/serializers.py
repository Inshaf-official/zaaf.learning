from rest_framework import serializers
from students.serializers import TenantPK
from students.models import Student, ClassGroup
from .models import HifzProgress, TimetableEntry


class HifzSerializer(serializers.ModelSerializer):
    student = TenantPK(queryset=Student.objects.all())
    student_name = serializers.CharField(source="student.name", read_only=True)
    surah = serializers.IntegerField(min_value=1, max_value=114)
    juz = serializers.IntegerField(min_value=1, max_value=30)

    class Meta:
        model = HifzProgress
        fields = [
            "id",
            "student",
            "student_name",
            "date",
            "surah",
            "juz",
            "lines",
            "revision_status",
            "note",
        ]


class TimetableSerializer(serializers.ModelSerializer):
    class_group = TenantPK(queryset=ClassGroup.objects.all())
    class_group_name = serializers.CharField(source="class_group.name", read_only=True)
    weekday = serializers.IntegerField(min_value=0, max_value=6)

    class Meta:
        model = TimetableEntry
        fields = [
            "id",
            "class_group",
            "class_group_name",
            "kind",
            "weekday",
            "starts_at",
            "ends_at",
            "label",
        ]

    def validate(self, data):
        if self.instance:
            data = {
                **{
                    key: getattr(self.instance, key)
                    for key in [
                        "class_group",
                        "kind",
                        "weekday",
                        "starts_at",
                        "ends_at",
                        "label",
                    ]
                },
                **data,
            }
        if data["ends_at"] <= data["starts_at"]:
            raise serializers.ValidationError("End time must follow start time.")
        query = TimetableEntry.objects.filter(
            institution=data["class_group"].institution,
            class_group=data["class_group"],
            kind=data["kind"],
            weekday=data["weekday"],
            starts_at__lt=data["ends_at"],
            ends_at__gt=data["starts_at"],
        )
        if self.instance:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise serializers.ValidationError(
                "This timetable slot overlaps another lesson."
            )
        return data
