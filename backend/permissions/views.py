from django.contrib.auth import get_user_model
from django.db import transaction
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


class PermissionAdminOptionsView(APIView):
    permission_classes = [IsAuthenticated, HasFunctionPermission]
    required_function = 'ASSIGN_PERMISSION'

    def get(self, request):
        users = User.objects.exclude(id=request.user.id).order_by('email').prefetch_related(
            'user_functions__function'
        )
        return Response({
            'users': [
                {
                    'id': user.id,
                    'email': user.email,
                    'permissions': [assignment.function.code for assignment in user.user_functions.all()],
                }
                for user in users
            ],
            'functions': list(Function.objects.order_by('code').values('code', 'name')),
        })


class ManagePermissionsView(APIView):
    permission_classes = [IsAuthenticated, HasFunctionPermission]
    required_function = 'ASSIGN_PERMISSION'

    def post(self, request):
        serializer = UserFunctionAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data['user_id']
        requested_permissions = set(serializer.validated_data['function_codes'])

        with transaction.atomic():
            try:
                target_user = User.objects.select_for_update().get(id=user_id)
            except User.DoesNotExist:
                return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

            if target_user.id == request.user.id:
                return Response(
                    {'detail': 'You cannot manage your own permissions.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

            existing_functions = {
                assignment.function.code: assignment.function
                for assignment in UserFunction.objects.filter(user=target_user).select_related('function')
            }
            requested_functions = {
                function.code: function
                for function in Function.objects.filter(code__in=requested_permissions)
            }

            to_remove = set(existing_functions) - requested_permissions
            to_add = requested_permissions - set(existing_functions)

            if to_remove:
                UserFunction.objects.filter(user=target_user, function__code__in=to_remove).delete()
                for code in sorted(to_remove):
                    PermissionAudit.objects.create(
                        actor=request.user,
                        target_user=target_user,
                        function=existing_functions[code],
                        action=PermissionAudit.Action.REVOKED,
                    )

            for code in sorted(to_add):
                assignment, created = UserFunction.objects.get_or_create(
                    user=target_user,
                    function=requested_functions[code],
                    defaults={'granted_by': request.user},
                )
                if created:
                    PermissionAudit.objects.create(
                        actor=request.user,
                        target_user=target_user,
                        function=assignment.function,
                        action=PermissionAudit.Action.ASSIGNED,
                    )

        return Response({
            'detail': 'Permissions updated successfully.',
            'user_id': target_user.id,
            'permissions': sorted(requested_permissions),
        }, status=status.HTTP_200_OK)
