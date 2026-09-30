from rest_framework import serializers

from .models import Function, Module, UserFunction


class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ['id', 'code', 'name', 'description']


class FunctionSerializer(serializers.ModelSerializer):
    module = ModuleSerializer(read_only=True)

    class Meta:
        model = Function
        fields = ['id', 'code', 'name', 'description', 'module']


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


class UserPermissionSerializer(serializers.ModelSerializer):
    permission_codes = serializers.SerializerMethodField()

    class Meta:
        model = UserFunction
        fields = ['user', 'permission_codes']

    def get_permission_codes(self, obj):
        return list(obj.user.user_functions.values_list('function__code', flat=True).order_by('function__code'))
