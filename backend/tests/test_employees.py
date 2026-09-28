from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from employees.models import Employee
from permissions.models import Function, Module, UserFunction

User = get_user_model()


class EmployeeAccessTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='manager@example.com', password='StrongPass123!')
        self.module, _ = Module.objects.get_or_create(code='core', defaults={'name': 'Core', 'description': 'Core permissions'})
        self.function, _ = Function.objects.get_or_create(
            module=self.module,
            code='VIEW_EMPLOYEE',
            defaults={'name': 'View Employee', 'description': 'Allows viewing employees'},
        )
        self.view_self_function, _ = Function.objects.get_or_create(
            module=self.module,
            code='VIEW_SELF',
            defaults={'name': 'View Self', 'description': 'Allows viewing personal profile'},
        )
        UserFunction.objects.get_or_create(user=self.user, function=self.function)

        self.employee = Employee.objects.create(
            user=self.user,
            employee_code='EMP-001',
            first_name='Jane',
            last_name='Manager',
            department='Engineering',
        )

    def authenticate(self, user):
        response = self.client.post(
            reverse('token_obtain_pair'),
            {'email': user.email, 'password': 'StrongPass123!'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_employee_list_requires_view_employee_permission(self):
        self.authenticate(self.user)

        response = self.client.get(reverse('employee-list-create'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_user_without_permission_cannot_access_employee_list(self):
        restricted_user = User.objects.create_user(email='staff@example.com', password='StrongPass123!')
        self.authenticate(restricted_user)

        response = self.client.get(reverse('employee-list-create'))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_self_profile_endpoint_requires_view_self_permission(self):
        self.user.user_functions.filter(function__code='VIEW_SELF').delete()
        self.authenticate(self.user)

        response = self.client.get(reverse('employee-self'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        UserFunction.objects.get_or_create(user=self.user, function=self.view_self_function)

        response = self.client.get(reverse('employee-self'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user'], self.user.id)
