from rest_framework import serializers

from .models import Function


class UserFunctionAssignSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    function_codes = serializers.ListField(
        child=serializers.CharField(trim_whitespace=True, max_length=50),
        allow_empty=True,
    )

    def validate_function_codes(self, value):
        normalized = []
        seen = set()
        for code in value:
            cleaned = code.strip().upper()
            if not cleaned:
                raise serializers.ValidationError('Permission codes cannot be blank.')
            if cleaned in seen:
                continue
            seen.add(cleaned)
            normalized.append(cleaned)

        known_codes = set(Function.objects.filter(code__in=normalized).values_list('code', flat=True))
        unknown_codes = sorted(set(normalized) - known_codes)
        if unknown_codes:
            raise serializers.ValidationError(
                f"Unknown permission code(s): {', '.join(unknown_codes)}."
            )

        return normalized


# The following serializers describe the read-only responses of the permission
# endpoints. They are used for validation-free documentation (OpenAPI schema
# generation) and are not involved in authorization, which is driven entirely by
# HasFunctionPermission and each view's required_function declaration.


class CurrentPermissionsSerializer(serializers.Serializer):
    """Response body of GET /api/permissions/me/."""

    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)
    is_superuser = serializers.BooleanField(read_only=True)
    permissions = serializers.ListField(child=serializers.CharField(), read_only=True)


class PermissionTargetSerializer(serializers.Serializer):
    """One assignable user inside PermissionAdminOptionsSerializer."""

    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)
    permissions = serializers.ListField(child=serializers.CharField(), read_only=True)


class FunctionCatalogEntrySerializer(serializers.Serializer):
    """One registered Function code inside PermissionAdminOptionsSerializer."""

    code = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)


class PermissionAdminOptionsSerializer(serializers.Serializer):
    """Response body of GET /api/permissions/manage/."""

    users = PermissionTargetSerializer(many=True, read_only=True)
    functions = FunctionCatalogEntrySerializer(many=True, read_only=True)


class PermissionAssignResultSerializer(serializers.Serializer):
    """Response body of POST /api/permissions/assign/."""

    detail = serializers.CharField(read_only=True)
    user_id = serializers.IntegerField(read_only=True)
    permissions = serializers.ListField(child=serializers.CharField(), read_only=True)
