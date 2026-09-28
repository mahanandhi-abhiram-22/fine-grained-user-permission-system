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
        child=serializers.CharField(trim_whitespace=True),
        allow_empty=True,
    )

    def validate_function_codes(self, value):
        normalized = []
        seen = set()
        for code in value:
            cleaned = code.strip().upper()
            if not cleaned:
                continue
            if cleaned in seen:
                continue
            seen.add(cleaned)
            normalized.append(cleaned)
        return normalized


class UserPermissionSerializer(serializers.ModelSerializer):
    permission_codes = serializers.SerializerMethodField()

    class Meta:
        model = UserFunction
        fields = ['user', 'permission_codes']

    def get_permission_codes(self, obj):
        return list(obj.user.user_functions.values_list('function__code', flat=True).order_by('function__code'))
