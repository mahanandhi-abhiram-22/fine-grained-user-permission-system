from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import PermissionAudit
from permissions.models import Function, UserFunction
from permissions.permissions import HasFunctionPermission
from permissions.serializers import UserFunctionAssignSerializer

User = get_user_model()


class UserPermissionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        permissions = list(
            request.user.user_functions.values_list('function__code', flat=True).order_by('function__code')
        )
        return Response({
            'id': request.user.id,
            'email': request.user.email,
            'is_superuser': request.user.is_superuser,
            'permissions': permissions,
        })


class ManagePermissionsView(APIView):
    permission_classes = [IsAuthenticated, HasFunctionPermission]
    required_function = 'ASSIGN_PERMISSION'

    def post(self, request):
        serializer = UserFunctionAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data['user_id']
        function_codes = serializer.validated_data['function_codes']

        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        existing_permissions = set(
            target_user.user_functions.values_list('function__code', flat=True)
        )
        requested_permissions = set(function_codes)

        valid_functions = []
        valid_codes = set()
        module = Function._meta.get_field('module').remote_field.model.objects.first()
        if module is None:
            module = Function._meta.get_field('module').remote_field.model.objects.create(
                code='core',
                name='Core',
                description='Default module for system permissions.',
            )

        for code in sorted(requested_permissions):
            function, _ = Function.objects.get_or_create(
                code=code,
                defaults={
                    'name': code.replace('_', ' ').title(),
                    'description': f'Permission for {code}.',
                    'module': module,
                },
            )
            valid_functions.append(function)
            valid_codes.add(function.code)

        to_remove = existing_permissions - valid_codes
        to_add = valid_codes - existing_permissions

        if to_remove:
            UserFunction.objects.filter(user=target_user, function__code__in=to_remove).delete()
            for code in sorted(to_remove):
                function = Function.objects.get(code=code)
                PermissionAudit.objects.create(
                    actor=request.user,
                    target_user=target_user,
                    function=function,
                    action=PermissionAudit.Action.REVOKED,
                )

        for code in sorted(to_add):
            function = Function.objects.get(code=code)
            UserFunction.objects.get_or_create(user=target_user, function=function, defaults={'granted_by': request.user})
            PermissionAudit.objects.create(
                actor=request.user,
                target_user=target_user,
                function=function,
                action=PermissionAudit.Action.ASSIGNED,
            )

        return Response({
            'detail': 'Permissions updated successfully.',
            'user_id': target_user.id,
            'permissions': sorted(requested_permissions),
        }, status=status.HTTP_200_OK)
