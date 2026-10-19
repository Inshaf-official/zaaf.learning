from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from .models import Membership, User
from institutions.models import Institution


class RegistrationSerializer(serializers.Serializer):
    institution_name = serializers.CharField(max_length=200)
    institution_type = serializers.ChoiceField(choices=Institution.Type.choices)
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True, max_length=128, trim_whitespace=False
    )

    def validate(self, attrs):
        attrs["email"] = attrs["email"].lower()
        if User.objects.filter(email__iexact=attrs["email"]).exists():
            raise serializers.ValidationError(
                "Registration could not be completed with these details."
            )
        try:
            validate_password(
                attrs["password"], User(email=attrs["email"], name=attrs["name"])
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages})
        return attrs


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=254)
    password = serializers.CharField(
        max_length=128, trim_whitespace=False, write_only=True
    )


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(
        write_only=True, max_length=128, trim_whitespace=False
    )
    new_password = serializers.CharField(
        write_only=True, max_length=128, trim_whitespace=False
    )

    def validate_new_password(self, value):
        try:
            validate_password(value, self.context["request"].user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return value


class InviteSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    login_id = serializers.RegexField(r"^[a-zA-Z0-9_-]{3,100}$", required=False)
    name = serializers.CharField(max_length=150)
    role = serializers.ChoiceField(choices=Membership.Role.choices)
    delivery = serializers.ChoiceField(choices=["email", "temporary"], default="email")

    def validate(self, attrs):
        if bool(attrs.get("email")) == bool(attrs.get("login_id")):
            raise serializers.ValidationError("Provide either email or login ID.")
        if attrs.get("login_id") and (
            attrs["role"] != "STUDENT" or attrs["delivery"] != "temporary"
        ):
            raise serializers.ValidationError(
                "Login IDs are for students with temporary passwords."
            )
        if attrs.get("email"):
            attrs["email"] = attrs["email"].lower()
        return attrs


class MemberSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    name = serializers.CharField(source="user.name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    login_id = serializers.CharField(source="user.login_id", read_only=True)
    must_change_password = serializers.BooleanField(
        source="user.must_change_password", read_only=True
    )

    class Meta:
        model = Membership
        fields = [
            "id",
            "user_id",
            "name",
            "email",
            "login_id",
            "role",
            "is_active",
            "must_change_password",
        ]
