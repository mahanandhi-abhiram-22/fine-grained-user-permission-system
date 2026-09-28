from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from permissions.models import Function, Module, UserFunction

User = get_user_model()


class PermissionAssignmentTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email='admin@example.com', password='StrongPass123!')
        self.member = User.objects.create_user(email='member@example.com', password='StrongPass123!')
        self.module, _ = Module.objects.get_or_create(code='core', defaults={'name': 'Core', 'description': 'Core permissions'})

    def assign_permission(self, user, code):
        function, _ = Function.objects.get_or_create(
            module=self.module,
            code=code,
            defaults={'name': code.replace('_', ' ').title(), 'description': code},
        )
        UserFunction.objects.get_or_create(user=user, function=function)

    def authenticate(self, user):
        response = self.client.post(
            reverse('token_obtain_pair'),
            {'email': user.email, 'password': 'StrongPass123!'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_admin_can_assign_permission_to_user(self):
        self.assign_permission(self.admin, 'ASSIGN_PERMISSION')
        self.authenticate(self.admin)

        response = self.client.post(
            reverse('assign-permissions'),
            {'user_id': self.member.id, 'function_codes': ['VIEW_SELF']},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(self.member.user_functions.filter(function__code='VIEW_SELF').exists())

    def test_member_without_assign_permission_cannot_assign_permissions(self):
        self.authenticate(self.member)

        response = self.client.post(
            reverse('assign-permissions'),
            {'user_id': self.admin.id, 'function_codes': ['VIEW_EMPLOYEE']},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_permissions_endpoint_lists_active_permissions(self):
        self.assign_permission(self.member, 'VIEW_SELF')
        self.assign_permission(self.member, 'VIEW_EMPLOYEE')
        self.authenticate(self.member)

        response = self.client.get(reverse('user-permissions'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('permissions', response.data)
        self.assertIn('VIEW_SELF', response.data['permissions'])
        self.assertIn('VIEW_EMPLOYEE', response.data['permissions'])
