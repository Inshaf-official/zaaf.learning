from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from accounts.models import Membership
from accounts.permissions import membership_for
from .models import (
    AcademicYear,
    ClassGroup,
    Division,
    Subject,
    TeacherAssignment,
    Student,
    ParentStudentLink,
)
from .permissions import assignments, can_manage


class TenantPK(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        query = super().get_queryset()
        request = self.context.get("request")
        return (
            query.filter(institution=membership_for(request).institution)
            if request
            else query.none()
        )

    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, int):
            raise serializers.ValidationError("Expected an integer ID.")
        return get_object_or_404(self.get_queryset(), pk=data)


class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = ["id", "name", "starts_on", "ends_on", "is_current"]
        validators = []

    def validate(self, attrs):
        start = attrs.get("starts_on", getattr(self.instance, "starts_on", None))
        end = attrs.get("ends_on", getattr(self.instance, "ends_on", None))
        if start and end and start > end:
            raise serializers.ValidationError(
                "Academic year end must be on or after its start."
            )
        return attrs


class ClassGroupSerializer(serializers.ModelSerializer):
    academic_year = TenantPK(queryset=AcademicYear.objects.all())
    academic_year_name = serializers.CharField(
        source="academic_year.name", read_only=True
    )

    def validate(self, attrs):
        if (
            self.instance
            and "academic_year" in attrs
            and attrs["academic_year"].pk != self.instance.academic_year_id
        ):
            if (
                self.instance.students.exists()
                or self.instance.teacher_assignments.exists()
            ):
                raise serializers.ValidationError(
                    "Create a new class for the new academic year; this class is already in use."
                )
        return attrs

    class Meta:
        model = ClassGroup
        fields = ["id", "name", "academic_year", "academic_year_name"]
        validators = []


class DivisionSerializer(serializers.ModelSerializer):
    class_group = TenantPK(queryset=ClassGroup.objects.all())
    class_group_name = serializers.CharField(source="class_group.name", read_only=True)

    def validate(self, attrs):
        if (
            self.instance
            and "class_group" in attrs
            and attrs["class_group"].pk != self.instance.class_group_id
        ):
            if (
                self.instance.students.exists()
                or TeacherAssignment.objects.filter(division=self.instance).exists()
            ):
                raise serializers.ValidationError(
                    "This division is already in use and cannot move to another class."
                )
        return attrs

    class Meta:
        model = Division
        fields = ["id", "name", "class_group", "class_group_name"]
        validators = []


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ["id", "name", "code"]
        validators = []


class TeacherChoiceSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="user.name")
    user_id = serializers.IntegerField(source="user.id")

    class Meta:
        model = Membership
        fields = ["id", "user_id", "name"]


class TeacherID(serializers.IntegerField):
    def to_representation(self, value):
        return value.pk


class AssignmentSerializer(serializers.ModelSerializer):
    teacher = TeacherID(min_value=1)
    teacher_name = serializers.CharField(source="teacher.name", read_only=True)
    class_group = TenantPK(queryset=ClassGroup.objects.all())
    division = TenantPK(
        queryset=Division.objects.all(), allow_null=True, required=False
    )
    subject = TenantPK(queryset=Subject.objects.all(), allow_null=True, required=False)
    class_group_name = serializers.CharField(source="class_group.name", read_only=True)
    division_name = serializers.CharField(
        source="division.name", allow_null=True, read_only=True
    )
    subject_name = serializers.CharField(
        source="subject.name", allow_null=True, read_only=True
    )

    class Meta:
        model = TeacherAssignment
        fields = [
            "id",
            "teacher",
            "teacher_name",
            "class_group",
            "class_group_name",
            "division",
            "division_name",
            "subject",
            "subject_name",
            "is_class_teacher",
        ]
        validators = []

    def validate_teacher(self, value):
        member = get_object_or_404(
            Membership.objects.select_related("user"),
            institution=membership_for(self.context["request"]).institution,
            user_id=value,
            role="TEACHER",
            is_active=True,
            user__is_active=True,
        )
        return member.user

    def validate(self, attrs):
        group = attrs.get("class_group", getattr(self.instance, "class_group", None))
        division = attrs.get("division", getattr(self.instance, "division", None))
        if division and division.class_group_id != group.id:
            raise serializers.ValidationError(
                {"division": "Division must belong to the selected class."}
            )
        if not attrs.get(
            "is_class_teacher", getattr(self.instance, "is_class_teacher", False)
        ) and not attrs.get("subject", getattr(self.instance, "subject", None)):
            raise serializers.ValidationError(
                "Choose a subject or a class-teacher duty."
            )
        return attrs


class GuardianInviteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone = serializers.RegexField(
        r"^\+?[0-9 ()-]{6,25}$", allow_blank=True, required=False, default=""
    )
    relationship = serializers.CharField(max_length=50, default="Guardian")
    delivery = serializers.ChoiceField(choices=["email", "temporary"], default="email")

    def validate_email(self, value):
        return value.lower()


class GuardianSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="parent.name", read_only=True)
    email = serializers.EmailField(source="parent.email", read_only=True)

    class Meta:
        model = ParentStudentLink
        fields = ["id", "name", "email", "phone", "relationship"]


class StudentWriteSerializer(serializers.ModelSerializer):
    interest_tags = serializers.ListField(
        child=serializers.CharField(max_length=50), max_length=20, required=False
    )

    def validate_interest_tags(self, value):
        return list(dict.fromkeys(x.strip().lower() for x in value if x.strip()))

    class_group = TenantPK(queryset=ClassGroup.objects.all())
    division = TenantPK(
        queryset=Division.objects.all(), required=False, allow_null=True
    )
    guardians = GuardianInviteSerializer(
        many=True, required=False, write_only=True, max_length=10
    )
    joined_on = serializers.DateField(default=timezone.localdate)

    class Meta:
        model = Student
        fields = [
            "id",
            "admission_number",
            "name",
            "date_of_birth",
            "class_group",
            "division",
            "joined_on",
            "guardians",
            "interest_tags",
        ]
        validators = []

    def validate(self, attrs):
        request = self.context["request"]
        group = attrs.get("class_group", getattr(self.instance, "class_group", None))
        division = attrs.get("division", getattr(self.instance, "division", None))
        if division and division.class_group_id != group.id:
            raise serializers.ValidationError(
                {"division": "Division must belong to the selected class."}
            )
        if membership_for(request).role != "ADMIN":
            query = assignments(request, True).filter(class_group=group)
            from django.db.models import Q

            if not query.filter(Q(division=None) | Q(division=division)).exists():
                from rest_framework.exceptions import PermissionDenied

                raise PermissionDenied("Only your class can be managed.")
        if not self.instance and not attrs.get("guardians"):
            raise serializers.ValidationError(
                {"guardians": "Add at least one guardian."}
            )
        if self.instance and "guardians" in attrs:
            raise serializers.ValidationError(
                {"guardians": "Manage guardian links through the dedicated endpoint."}
            )
        if attrs.get("date_of_birth") and attrs["date_of_birth"] > timezone.localdate():
            raise serializers.ValidationError(
                {"date_of_birth": "Date of birth cannot be in the future."}
            )
        if attrs.get("joined_on", timezone.localdate()) > timezone.localdate():
            raise serializers.ValidationError(
                {"joined_on": "Joining date cannot be in the future."}
            )
        emails = [g["email"] for g in attrs.get("guardians", [])]
        if len(set(emails)) != len(emails):
            raise serializers.ValidationError(
                {"guardians": "Do not repeat a guardian email."}
            )
        return attrs


class StudentSerializer(serializers.ModelSerializer):
    class_group_name = serializers.CharField(source="class_group.name")
    division_name = serializers.CharField(source="division.name", allow_null=True)
    academic_year_name = serializers.CharField(source="class_group.academic_year.name")
    can_manage = serializers.SerializerMethodField()
    can_view_guardians = serializers.SerializerMethodField()
    has_login = serializers.BooleanField(read_only=True)

    class Meta:
        model = Student
        fields = [
            "id",
            "name",
            "admission_number",
            "class_group",
            "class_group_name",
            "division",
            "division_name",
            "academic_year_name",
            "can_manage",
            "can_view_guardians",
            "has_login",
            "interest_tags",
        ]

    def get_can_manage(self, obj) -> bool:
        return can_manage(self.context["request"], obj)

    def get_can_view_guardians(self, obj) -> bool:
        request = self.context["request"]
        return can_manage(request, obj) or (
            membership_for(request).role == "PARENT" and obj.linked_parent
        )


class StudentDetailSerializer(StudentSerializer):
    guardians = serializers.SerializerMethodField()

    class Meta(StudentSerializer.Meta):
        fields = StudentSerializer.Meta.fields + [
            "joined_on",
            "date_of_birth",
            "guardians",
        ]

    def get_guardians(self, obj) -> list[dict]:
        if not self.get_can_view_guardians(obj):
            return []
        return GuardianSerializer(obj.parent_links.all(), many=True).data

    def to_representation(self, instance):
        result = super().to_representation(instance)
        if not self.get_can_view_guardians(instance):
            result.pop("guardians")
        if (
            not self.get_can_manage(instance)
            and membership_for(self.context["request"]).role == "TEACHER"
        ):
            result.pop("date_of_birth")
        return result


class CredentialSerializer(serializers.Serializer):
    identity = serializers.CharField()
    temporary_password = serializers.CharField(required=False)


class StudentMutationSerializer(serializers.Serializer):
    student = StudentDetailSerializer()
    credentials = CredentialSerializer(many=True)


class AccountInviteSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    login_id = serializers.RegexField(r"^[a-zA-Z0-9_-]{3,100}$", required=False)
    delivery = serializers.ChoiceField(
        choices=["email", "temporary"], default="temporary"
    )

    def validate(self, attrs):
        if bool(attrs.get("email")) == bool(attrs.get("login_id")):
            raise serializers.ValidationError("Choose email or login ID.")
        if attrs.get("login_id") and attrs["delivery"] != "temporary":
            raise serializers.ValidationError("Login IDs require a temporary password.")
        return attrs


class CapabilitiesSerializer(serializers.Serializer):
    can_create = serializers.BooleanField()
    can_emergency_lookup = serializers.BooleanField()


class HardDeleteSerializer(serializers.Serializer):
    confirm_admission_number = serializers.CharField(max_length=100)


class DirectorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ["id", "name", "admission_number"]
