from rest_framework import serializers
from .models import Employee

class EmployeeSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True, default=serializers.CurrentUserDefault())

    class Meta:
        model = Employee
        fields = ['id', 'user', 'employee_code', 'first_name', 'last_name', 'department', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
