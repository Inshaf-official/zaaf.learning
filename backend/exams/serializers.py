from rest_framework import serializers
from students.serializers import TenantPK
from students.models import ClassGroup, Subject, Student
from .models import Exam, ExamSubject, Mark, MarkSheetHold


class ExamSubjectSerializer(serializers.ModelSerializer):
    exam = TenantPK(queryset=Exam.objects.all())
    subject = TenantPK(queryset=Subject.objects.all())
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = ExamSubject
        fields = ["id", "exam", "subject", "subject_name", "max_marks"]
        validators = []

    def validate_max_marks(self, value):
        if value <= 0:
            raise serializers.ValidationError("Maximum marks must be positive.")
        return value


class ExamSerializer(serializers.ModelSerializer):
    class_group = TenantPK(queryset=ClassGroup.objects.all())
    class_group_name = serializers.CharField(source="class_group.name", read_only=True)
    exam_subjects = ExamSubjectSerializer(many=True, read_only=True)

    class Meta:
        model = Exam
        fields = [
            "id",
            "name",
            "class_group",
            "class_group_name",
            "date",
            "published",
            "exam_subjects",
        ]
        read_only_fields = ["published"]


class MarkSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)
    subject_name = serializers.CharField(
        source="exam_subject.subject.name", read_only=True
    )
    max_marks = serializers.DecimalField(
        source="exam_subject.max_marks", max_digits=7, decimal_places=2, read_only=True
    )

    class Meta:
        model = Mark
        fields = [
            "id",
            "student",
            "student_name",
            "exam_subject",
            "subject_name",
            "score",
            "absent",
            "max_marks",
            "edited_at",
        ]
        read_only_fields = fields


class MarkRowSerializer(serializers.Serializer):
    student = serializers.IntegerField(min_value=1)
    score = serializers.DecimalField(max_digits=7, decimal_places=2, min_value=0)
    absent = serializers.BooleanField(default=False)


class BulkMarkSerializer(serializers.Serializer):
    exam_subject = serializers.IntegerField(min_value=1)
    rows = MarkRowSerializer(many=True, allow_empty=False, max_length=500)

    def validate_rows(self, value):
        if len({r["student"] for r in value}) != len(value):
            raise serializers.ValidationError("Duplicate students.")
        return value


class HoldSerializer(serializers.ModelSerializer):
    student = TenantPK(queryset=Student.objects.all())
    exam = TenantPK(queryset=Exam.objects.all())
    student_name = serializers.CharField(source="student.name", read_only=True)

    class Meta:
        model = MarkSheetHold
        fields = [
            "id",
            "student",
            "student_name",
            "exam",
            "reason_type",
            "note",
            "released_at",
            "created_at",
        ]
        read_only_fields = ["released_at", "created_at"]
        validators = []

    def validate(self, attrs):
        if attrs["student"].class_group_id != attrs["exam"].class_group_id:
            raise serializers.ValidationError(
                "Student and exam must belong to the same class."
            )
        return attrs


class PublicationSerializer(serializers.Serializer):
    published = serializers.BooleanField()
