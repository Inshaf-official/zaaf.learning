from copy import deepcopy
from drf_spectacular.utils import extend_schema
from accounts.schema import ConfigSerializer, TENANT_HEADERS
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from accounts.permissions import PasswordChanged, TenantMember, membership_for
from .type_config import TYPE_CONFIG


@extend_schema(responses=ConfigSerializer, parameters=TENANT_HEADERS)
class ConfigView(APIView):
    permission_classes = [IsAuthenticated, PasswordChanged, TenantMember]

    def get(self, request):
        membership = membership_for(request)
        institution = membership.institution
        config = deepcopy(TYPE_CONFIG[institution.type])
        response = Response(
            {
                **config,
                "id": institution.id,
                "name": institution.name,
                "type": institution.type,
                "role": membership.role,
            }
        )
        response["Cache-Control"] = "private, max-age=30"
        response["Vary"] = "Authorization, X-Institution-ID, X-Role"
        return response


from io import BytesIO
from PIL import Image, UnidentifiedImageError
from django.http import HttpResponse
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser, FormParser
from accounts.permissions import InstitutionAdmin
from accounts.views import audit
from .serializers import SettingsSerializer
from core.permissions import SensitiveResponse


@extend_schema(
    parameters=TENANT_HEADERS, request=SettingsSerializer, responses=SettingsSerializer
)
class SettingsView(SensitiveResponse, APIView):
    permission_classes = [IsAuthenticated, PasswordChanged, InstitutionAdmin]

    def get(self, request):
        return Response(SettingsSerializer(membership_for(request).institution).data)

    def patch(self, request):
        institution = membership_for(request).institution
        serializer = SettingsSerializer(institution, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        audit(request, institution, "settings.update", institution.pk)
        return Response(serializer.data)


@extend_schema(parameters=TENANT_HEADERS)
class LogoView(SensitiveResponse, APIView):
    permission_classes = [IsAuthenticated, PasswordChanged, TenantMember]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(responses={(200, "image/webp"): bytes})
    def get(self, request):
        institution = membership_for(request).institution
        if not institution.logo:
            from rest_framework.exceptions import NotFound

            raise NotFound("No logo uploaded.")
        return HttpResponse(bytes(institution.logo), content_type=institution.logo_type)

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"logo": {"type": "string", "format": "binary"}},
                "required": ["logo"],
            }
        },
        responses=SettingsSerializer,
    )
    def post(self, request):
        if not InstitutionAdmin().has_permission(request, self):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Administrator required.")
        upload = request.FILES.get("logo")
        if not upload or upload.size > 2 * 1024 * 1024:
            raise ValidationError("Choose an image up to 2 MB.")
        try:
            image = Image.open(upload)
            if (
                image.format not in ["PNG", "JPEG", "WEBP"]
                or image.width > 4096
                or image.height > 4096
            ):
                raise ValidationError(
                    "Choose a PNG, JPEG or WebP image up to 4096 × 4096."
                )
            image.verify()
            upload.seek(0)
            image = Image.open(upload).convert("RGBA")
            image.thumbnail((512, 512))
            stream = BytesIO()
            image.save(stream, format="WEBP", quality=90, method=4)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise ValidationError("Invalid image file.")
        institution = membership_for(request).institution
        institution.logo = stream.getvalue()
        institution.logo_type = "image/webp"
        institution.save(update_fields=["logo", "logo_type"])
        audit(request, institution, "settings.logo", institution.pk)
        return Response(SettingsSerializer(institution).data)
