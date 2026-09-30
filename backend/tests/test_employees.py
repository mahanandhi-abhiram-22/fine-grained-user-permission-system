from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from urllib.parse import urlsplit

from employees.models import Employee
from permissions.models import Function, Module, UserFunction

User = get_user_model()


class EmployeeAccessTests(APITestCase):
    employee_action_permissions = (
        ('list', 'VIEW_EMPLOYEE', status.HTTP_200_OK),
        ('retrieve', 'VIEW_EMPLOYEE', status.HTTP_200_OK),
        ('create', 'CREATE_EMPLOYEE', status.HTTP_201_CREATED),
        ('update', 'EDIT_EMPLOYEE', status.HTTP_200_OK),
        ('partial_update', 'EDIT_EMPLOYEE', status.HTTP_200_OK),
        ('destroy', 'DELETE_EMPLOYEE', status.HTTP_204_NO_CONTENT),
    )

    def setUp(self):
        self.user = User.objects.create_user(email='manager@example.com', password='StrongPass123!')
        self.module, _ = Module.objects.get_or_create(code='core', defaults={'name': 'Core', 'description': 'Core permissions'})
        self.view_self_function, _ = Function.objects.get_or_create(
            module=self.module,
            code='VIEW_SELF',
            defaults={'name': 'View Self', 'description': 'Allows viewing personal profile'},
        )
        self.grant_permission(self.user, 'VIEW_EMPLOYEE')

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

    def grant_permission(self, user, code):
        function, _ = Function.objects.get_or_create(
            module=self.module,
            code=code,
            defaults={'name': code.replace('_', ' ').title(), 'description': code},
        )
        UserFunction.objects.get_or_create(user=user, function=function)

    def request_employee_action(self, action):
        list_url = reverse('employee-list')
        detail_url = reverse('employee-detail', args=[self.employee.id])
        employee_data = {
            'employee_code': 'EMP-002',
            'first_name': 'Alex',
            'last_name': 'Staff',
            'department': 'Finance',
        }

        if action == 'list':
            return self.client.get(list_url)
        if action == 'retrieve':
            return self.client.get(detail_url)
        if action == 'create':
            return self.client.post(list_url, employee_data, format='json')
        if action == 'update':
            employee_data['employee_code'] = self.employee.employee_code
            return self.client.put(detail_url, employee_data, format='json')
        if action == 'partial_update':
            return self.client.patch(detail_url, {'department': 'Finance'}, format='json')
        if action == 'destroy':
            return self.client.delete(detail_url)
        raise AssertionError(f'Unsupported employee action: {action}')

    def test_employee_actions_allow_the_required_permission(self):
        for action, permission_code, expected_status in self.employee_action_permissions:
            with self.subTest(action=action):
                self.user.user_functions.all().delete()
                self.grant_permission(self.user, permission_code)
                self.authenticate(self.user)

                response = self.request_employee_action(action)

                self.assertEqual(response.status_code, expected_status)

    def test_employee_actions_deny_users_without_the_required_permission(self):
        restricted_user = User.objects.create_user(email='staff@example.com', password='StrongPass123!')
        self.authenticate(restricted_user)

        for action, _, _ in self.employee_action_permissions:
            with self.subTest(action=action):
                response = self.request_employee_action(action)

                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_employee_actions_require_explicit_permissions(self):
        superuser = User.objects.create_superuser(email='root@example.com', password='StrongPass123!')
        self.authenticate(superuser)

        for action, _, _ in self.employee_action_permissions:
            with self.subTest(action=action):
                response = self.request_employee_action(action)

                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_employee_actions_allow_explicit_permissions(self):
        superuser = User.objects.create_superuser(email='root@example.com', password='StrongPass123!')

        for action, permission_code, expected_status in self.employee_action_permissions:
            with self.subTest(action=action):
                superuser.user_functions.all().delete()
                self.grant_permission(superuser, permission_code)
                self.authenticate(superuser)

                response = self.request_employee_action(action)

                self.assertEqual(response.status_code, expected_status)

    def test_employee_actions_require_authentication(self):
        self.client.credentials()

        for action, _, _ in self.employee_action_permissions:
            with self.subTest(action=action):
                response = self.request_employee_action(action)

                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_employee_list_returns_first_page_with_twenty_results(self):
        for index in range(20):
            Employee.objects.create(
                user=self.user,
                employee_code=f'EMP-{index + 2:03}',
                first_name='Page',
                last_name=f'Employee {index}',
                department='Engineering',
            )
        self.authenticate(self.user)

        response = self.client.get(reverse('employee-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data), {'count', 'next', 'previous', 'results'})
        self.assertEqual(response.data['count'], 21)
        self.assertEqual(len(response.data['results']), 20)
        self.assertIsNotNone(response.data['next'])
        self.assertIsNone(response.data['previous'])

    def test_employee_list_next_link_returns_remaining_records(self):
        for index in range(20):
            Employee.objects.create(
                user=self.user,
                employee_code=f'EMP-{index + 2:03}',
                first_name='Page',
                last_name=f'Employee {index}',
                department='Engineering',
            )
        self.authenticate(self.user)

        first_page = self.client.get(reverse('employee-list'))
        next_url = urlsplit(first_page.data['next'])
        second_page = self.client.get(f'{next_url.path}?{next_url.query}')

        self.assertEqual(second_page.status_code, status.HTTP_200_OK)
        self.assertEqual(second_page.data['count'], 21)
        self.assertEqual(len(second_page.data['results']), 1)
        self.assertIsNone(second_page.data['next'])
        self.assertIsNotNone(second_page.data['previous'])
        self.assertNotEqual(
            first_page.data['results'][0]['id'],
            second_page.data['results'][0]['id'],
        )

    def test_employee_list_invalid_page_returns_not_found(self):
        self.authenticate(self.user)

        response = self.client.get(reverse('employee-list'), {'page': 'invalid'})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_employee_list_out_of_range_page_returns_not_found(self):
        self.authenticate(self.user)

        response = self.client.get(reverse('employee-list'), {'page': 2})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_self_profile_endpoint_requires_view_self_permission(self):
        self.user.user_functions.filter(function__code='VIEW_SELF').delete()
        self.authenticate(self.user)

        response = self.client.get(reverse('employee-self'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        UserFunction.objects.get_or_create(user=self.user, function=self.view_self_function)

        response = self.client.get(reverse('employee-self'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user'], self.user.id)

    def test_self_profile_requires_authentication(self):
        self.client.credentials()

        response = self.client.get(reverse('employee-self'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_self_profile_without_employee_returns_not_found(self):
        user_without_employee = User.objects.create_user(
            email='no-employee@example.com',
            password='StrongPass123!',
        )
        self.grant_permission(user_without_employee, 'VIEW_SELF')
        self.authenticate(user_without_employee)

        response = self.client.get(reverse('employee-self'))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_self_profile_returns_only_the_authenticated_users_record(self):
        other_user = User.objects.create_user(email='other@example.com', password='StrongPass123!')
        other_employee = Employee.objects.create(
            user=other_user,
            employee_code='EMP-002',
            first_name='Other',
            last_name='Employee',
            department='Finance',
        )
        self.grant_permission(self.user, 'VIEW_SELF')
        self.authenticate(self.user)

        response = self.client.get(f"{reverse('employee-self')}?user_id={other_user.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.employee.id)
        self.assertNotEqual(response.data['id'], other_employee.id)
        self.assertEqual(response.data['user'], self.user.id)

    def test_superuser_requires_explicit_view_self_permission(self):
        superuser = User.objects.create_superuser(email='root@example.com', password='StrongPass123!')
        Employee.objects.create(
            user=superuser,
            employee_code='EMP-003',
            first_name='Root',
            last_name='User',
            department='IT',
        )
        self.authenticate(superuser)

        response = self.client.get(reverse('employee-self'))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_multiple_employee_records_return_conflict(self):
        Employee.objects.create(
            user=self.user,
            employee_code='EMP-002',
            first_name='Jane',
            last_name='Second',
            department='Finance',
        )
        self.grant_permission(self.user, 'VIEW_SELF')
        self.authenticate(self.user)

        response = self.client.get(reverse('employee-self'))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
