from rest_framework import serializers
from decimal import Decimal
from students.serializers import TenantPK
from students.models import Student, ClassGroup, Subject
from .models import FeeInstallment, TestSeries, TestResult


class FeeSerializer(serializers.ModelSerializer):
    student = TenantPK(queryset=Student.objects.all())
    student_name = serializers.CharField(source="student.name", read_only=True)

    class Meta:
        model = FeeInstallment
        fields = [
            "id",
            "student",
            "student_name",
            "label",
            "amount",
            "paid_amount",
            "due_date",
            "last_reminded",
        ]
        read_only_fields = ["paid_amount", "last_reminded"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value


class PaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    reference = serializers.CharField(max_length=100)


class SeriesSerializer(serializers.ModelSerializer):
    class_group = TenantPK(queryset=ClassGroup.objects.all())
    subject = TenantPK(queryset=Subject.objects.all())

    class Meta:
        model = TestSeries
        fields = [
            "id",
            "name",
            "class_group",
            "subject",
            "date",
            "max_marks",
            "published",
        ]
        read_only_fields = ["published"]

    def validate_max_marks(self, value):
        if value <= 0:
            raise serializers.ValidationError("Maximum must be positive.")
        return value


class TestRowSerializer(serializers.Serializer):
    student = serializers.IntegerField(min_value=1)
    score = serializers.DecimalField(max_digits=7, decimal_places=2, min_value=0)


class TestBulkSerializer(serializers.Serializer):
    series = serializers.IntegerField(min_value=1)
    rows = TestRowSerializer(many=True, allow_empty=False, max_length=500)


class TestResultSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)

    class Meta:
        model = TestResult
        fields = ["id", "student", "student_name", "series", "score"]
        read_only_fields = fields
