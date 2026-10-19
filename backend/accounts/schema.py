from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.utils import OpenApiParameter
from rest_framework import serializers
from .serializers import MemberSerializer

TENANT_HEADERS = [
    OpenApiParameter("X-Institution-ID", int, OpenApiParameter.HEADER, required=True),
    OpenApiParameter("X-Role", str, OpenApiParameter.HEADER, required=True),
]


class ActiveJWTScheme(OpenApiAuthenticationExtension):
    target_class = "accounts.authentication.ActiveJWTAuthentication"
    name = "jwtAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


class CsrfSerializer(serializers.Serializer):
    csrfToken = serializers.CharField()


class GroupSerializer(serializers.Serializer):
    primary = serializers.CharField()
    secondary = serializers.CharField()


class ConfigSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    type = serializers.CharField()
    role = serializers.CharField()
    label = serializers.CharField()
    roles = serializers.DictField(child=serializers.CharField())
    groups = GroupSerializer()
    attendance_mode = serializers.CharField()
    modules = serializers.ListField(child=serializers.CharField())


class ContextSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    institution_id = serializers.IntegerField()
    institution_name = serializers.CharField()
    type = serializers.CharField()
    role = serializers.CharField()
    config = ConfigSerializer()


class MeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField(allow_null=True)
    login_id = serializers.CharField(allow_null=True)
    must_change_password = serializers.BooleanField()
    memberships = ContextSerializer(many=True)


class SessionSerializer(serializers.Serializer):
    access = serializers.CharField()
    must_change_password = serializers.BooleanField()
    user = MeSerializer()


class RequestPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class SetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=200)
    password = serializers.CharField(
        write_only=True, max_length=128, trim_whitespace=False
    )


class InviteResponseSerializer(serializers.Serializer):
    member = MemberSerializer()
    temporary_password = serializers.CharField(required=False)


class ActivationSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


class TemporarySerializer(serializers.Serializer):
    temporary_password = serializers.CharField()
