from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from permissions.permissions import HasFunctionPermission
from .models import Employee
from .serializers import EmployeeSerializer

class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all().order_by('-id')
    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated, HasFunctionPermission]
    action_permissions = {
        'list': 'VIEW_EMPLOYEE',
        'retrieve': 'VIEW_EMPLOYEE',
        'create': 'CREATE_EMPLOYEE',
        'update': 'EDIT_EMPLOYEE',
        'partial_update': 'EDIT_EMPLOYEE',
        'destroy': 'DELETE_EMPLOYEE',
        'me': 'VIEW_SELF',
    }

    @property
    def required_function(self):
        return self.action_permissions.get(self.action)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'], url_path='me', url_name='self')
    def me(self, request):
        employees = list(self.get_queryset().filter(user=request.user)[:2])
        if not employees:
            return Response(
                {'detail': 'Employee profile not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if len(employees) > 1:
            return Response(
                {'detail': 'Multiple employee records are associated with this user.'},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(self.get_serializer(employees[0]).data)
