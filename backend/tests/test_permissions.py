from contextlib import nullcontext
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from audit.models import PermissionAudit
from permissions.models import Function, Module, UserFunction
from permissions.management.commands.bootstrap_permission_admin import prompt_hidden_password, resolve_operator

User = get_user_model()


class PermissionAssignmentTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email='admin@example.com', password='StrongPass123!')
        self.member = User.objects.create_user(email='member@example.com', password='StrongPass123!')
        self.module, _ = Module.objects.get_or_create(code='core', defaults={'name': 'Core', 'description': 'Core permissions'})

    def assign_permission(self, user, code):
        function = self.create_function(code)
        UserFunction.objects.get_or_create(user=user, function=function)

    def create_function(self, code):
        function, _ = Function.objects.get_or_create(
            module=self.module,
            code=code,
            defaults={'name': code.replace('_', ' ').title(), 'description': code},
        )
        return function

    def authenticate(self, user):
        response = self.client.post(
            reverse('token_obtain_pair'),
            {'email': user.email, 'password': 'StrongPass123!'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def run_bootstrap(self, email='permission-admin@example.com', password='StrongPass123!'):
        with (
            patch(
                'permissions.management.commands.bootstrap_permission_admin.get_os_principal',
                return_value='uid:1001',
            ),
            patch(
                'permissions.bootstrap_security.load_operator_mapping',
                return_value={'uid:1001': self.admin.id},
            ),
            patch('permissions.management.commands.bootstrap_permission_admin.validate_bootstrap_lock_path'),
            patch(
                'permissions.management.commands.bootstrap_permission_admin.acquire_bootstrap_lock',
                return_value=nullcontext(),
            ),
            patch('permissions.management.commands.bootstrap_permission_admin.has_secure_terminal', return_value=True),
            patch('builtins.input', return_value=email),
            patch('getpass.getpass', side_effect=[password, password]),
        ):
            call_command('bootstrap_permission_admin', stdout=StringIO())

    def test_bootstrap_resolves_operator_from_verified_os_mapping(self):
        with (
            patch(
                'permissions.management.commands.bootstrap_permission_admin.get_os_principal',
                return_value='uid:1001',
            ),
            patch(
                'permissions.bootstrap_security.load_operator_mapping',
                return_value={'uid:1001': self.admin.id},
            ),
            patch('permissions.management.commands.bootstrap_permission_admin.validate_bootstrap_lock_path'),
        ):
            self.assertEqual(resolve_operator()[0].id, self.admin.id)

    def test_bootstrap_rejects_unmapped_or_invalid_operator_mapping(self):
        for mapping in ({}, {'uid:1001': 'admin@example.com'}, {'uid:1001': 99999}):
            with self.subTest(mapping=mapping):
                with (
                    patch(
                        'permissions.management.commands.bootstrap_permission_admin.get_os_principal',
                        return_value='uid:1001',
                    ),
                    patch(
                        'permissions.bootstrap_security.load_operator_mapping',
                        return_value=mapping,
                    ),
                    patch('permissions.management.commands.bootstrap_permission_admin.validate_bootstrap_lock_path'),
                ):
                    with self.assertRaises(CommandError):
                        resolve_operator()

    def test_bootstrap_requires_seeded_assignment_function(self):
        with (
            patch(
                'permissions.management.commands.bootstrap_permission_admin.get_os_principal',
                return_value='uid:1001',
            ),
            patch(
                'permissions.bootstrap_security.load_operator_mapping',
                return_value={'uid:1001': self.admin.id},
            ),
            patch('permissions.management.commands.bootstrap_permission_admin.validate_bootstrap_lock_path'),
            patch('builtins.input') as input_prompt,
        ):
            with self.assertRaises(CommandError):
                call_command('bootstrap_permission_admin', stdout=StringIO())
        input_prompt.assert_not_called()

    def test_bootstrap_password_prompt_refuses_echo_fallback(self):
        with (
            patch('permissions.management.commands.bootstrap_permission_admin.has_secure_terminal', return_value=False),
            patch('getpass.getpass') as password_prompt,
        ):
            with self.assertRaises(CommandError):
                prompt_hidden_password('Password: ')
        password_prompt.assert_not_called()

    def test_bootstrap_creates_distinct_regular_admin_and_audits_mapped_operator(self):
        function = self.create_function('ASSIGN_PERMISSION')

        self.run_bootstrap()

        target = User.objects.get(email='permission-admin@example.com')
        assignment = UserFunction.objects.get(user=target, function=function)
        audit = PermissionAudit.objects.get(target_user=target, function=function)
        self.assertNotEqual(target.id, self.admin.id)
        self.assertFalse(target.is_superuser)
        self.assertFalse(target.is_staff)
        self.assertTrue(target.check_password('StrongPass123!'))
        self.assertEqual(assignment.granted_by, self.admin)
        self.assertEqual(audit.actor, self.admin)
        self.assertEqual(audit.action, PermissionAudit.Action.ASSIGNED)

    def test_bootstrap_rejects_operator_as_target(self):
        self.create_function('ASSIGN_PERMISSION')

        with (
            patch(
                'permissions.management.commands.bootstrap_permission_admin.get_os_principal',
                return_value='uid:1001',
            ),
            patch(
                'permissions.bootstrap_security.load_operator_mapping',
                return_value={'uid:1001': self.admin.id},
            ),
            patch('permissions.management.commands.bootstrap_permission_admin.validate_bootstrap_lock_path'),
            patch('permissions.management.commands.bootstrap_permission_admin.has_secure_terminal', return_value=True),
            patch('builtins.input', return_value=self.admin.email),
        ):
            with self.assertRaises(CommandError):
                call_command('bootstrap_permission_admin', stdout=StringIO())
        self.assertEqual(User.objects.count(), 2)
        self.assertFalse(UserFunction.objects.filter(function__code='ASSIGN_PERMISSION').exists())

    def test_bootstrap_cannot_run_again_after_permission_is_revoked(self):
        self.create_function('ASSIGN_PERMISSION')
        self.run_bootstrap()
        target = User.objects.get(email='permission-admin@example.com')
        target.user_functions.all().delete()

        with (
            patch(
                'permissions.management.commands.bootstrap_permission_admin.get_os_principal',
                return_value='uid:1001',
            ),
            patch(
                'permissions.bootstrap_security.load_operator_mapping',
                return_value={'uid:1001': self.admin.id},
            ),
            patch('permissions.management.commands.bootstrap_permission_admin.validate_bootstrap_lock_path'),
            patch('builtins.input') as input_prompt,
        ):
            with self.assertRaises(CommandError):
                call_command('bootstrap_permission_admin', stdout=StringIO())
        input_prompt.assert_not_called()
        self.assertEqual(User.objects.count(), 3)

    def test_bootstrap_rechecks_lock_path_before_acquiring_the_lock(self):
        """A lock path that weakens after prompting must abort before the lock is taken."""
        function = self.create_function('ASSIGN_PERMISSION')
        lock_checks = []

        def weaken_lock_after_prompts(principal):
            lock_checks.append(principal)
            if len(lock_checks) > 1:
                raise CommandError('The bootstrap lock path failed security validation.')

        with (
            patch(
                'permissions.management.commands.bootstrap_permission_admin.get_os_principal',
                return_value='uid:1001',
            ),
            patch(
                'permissions.bootstrap_security.load_operator_mapping',
                return_value={'uid:1001': self.admin.id},
            ),
            patch(
                'permissions.management.commands.bootstrap_permission_admin.validate_bootstrap_lock_path',
                side_effect=weaken_lock_after_prompts,
            ),
            patch(
                'permissions.management.commands.bootstrap_permission_admin.acquire_bootstrap_lock',
            ) as acquire_lock,
            patch('permissions.management.commands.bootstrap_permission_admin.has_secure_terminal', return_value=True),
            patch('builtins.input', return_value='permission-admin@example.com'),
            patch('getpass.getpass', side_effect=['StrongPass123!', 'StrongPass123!']),
        ):
            with self.assertRaises(CommandError):
                call_command('bootstrap_permission_admin', stdout=StringIO())

        # Once as a precondition and once again immediately before the lock.
        self.assertEqual(lock_checks, ['uid:1001', 'uid:1001'])
        acquire_lock.assert_not_called()
        self.assertFalse(User.objects.filter(email='permission-admin@example.com').exists())
        self.assertFalse(UserFunction.objects.filter(function=function).exists())
        self.assertFalse(PermissionAudit.objects.exists())

    def test_bootstrap_rolls_back_user_and_permission_if_audit_fails(self):
        self.create_function('ASSIGN_PERMISSION')

        with (
            patch(
                'permissions.management.commands.bootstrap_permission_admin.get_os_principal',
                return_value='uid:1001',
            ),
            patch(
                'permissions.bootstrap_security.load_operator_mapping',
                return_value={'uid:1001': self.admin.id},
            ),
            patch('permissions.management.commands.bootstrap_permission_admin.validate_bootstrap_lock_path'),
            patch(
                'permissions.management.commands.bootstrap_permission_admin.acquire_bootstrap_lock',
                return_value=nullcontext(),
            ),
            patch('permissions.management.commands.bootstrap_permission_admin.has_secure_terminal', return_value=True),
            patch('builtins.input', return_value='permission-admin@example.com'),
            patch('getpass.getpass', side_effect=['StrongPass123!', 'StrongPass123!']),
            patch('permissions.management.commands.bootstrap_permission_admin.PermissionAudit.objects.create', side_effect=RuntimeError('audit failed')),
        ):
            with self.assertRaises(RuntimeError):
                call_command('bootstrap_permission_admin', stdout=StringIO())

        self.assertFalse(User.objects.filter(email='permission-admin@example.com').exists())
        self.assertFalse(UserFunction.objects.filter(function__code='ASSIGN_PERMISSION').exists())
        self.assertFalse(PermissionAudit.objects.exists())

    def test_admin_can_assign_permission_to_user(self):
        self.assign_permission(self.admin, 'ASSIGN_PERMISSION')
        self.create_function('VIEW_SELF')
        self.authenticate(self.admin)

        response = self.client.post(
            reverse('assign-permissions'),
            {'user_id': self.member.id, 'function_codes': ['VIEW_SELF']},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(self.member.user_functions.filter(function__code='VIEW_SELF').exists())
        audit = PermissionAudit.objects.get(
            actor=self.admin,
            target_user=self.member,
            function__code='VIEW_SELF',
        )
        self.assertEqual(audit.action, PermissionAudit.Action.ASSIGNED)

    def test_assigner_cannot_assign_permissions_to_themselves(self):
        self.assign_permission(self.admin, 'ASSIGN_PERMISSION')
        self.create_function('VIEW_SELF')
        self.authenticate(self.admin)

        response = self.client.post(
            reverse('assign-permissions'),
            {'user_id': self.admin.id, 'function_codes': ['ASSIGN_PERMISSION', 'VIEW_SELF']},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(self.admin.user_functions.filter(function__code='VIEW_SELF').exists())
        self.assertFalse(PermissionAudit.objects.filter(target_user=self.admin).exists())

    def test_unknown_code_in_mixed_list_rejects_the_entire_request(self):
        self.assign_permission(self.admin, 'ASSIGN_PERMISSION')
        self.create_function('VIEW_SELF')
        self.authenticate(self.admin)

        response = self.client.post(
            reverse('assign-permissions'),
            {'user_id': self.member.id, 'function_codes': ['VIEW_SELF', 'NOT_A_PERMISSION']},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(self.member.user_functions.exists())
        self.assertFalse(Function.objects.filter(code='NOT_A_PERMISSION').exists())
        self.assertFalse(PermissionAudit.objects.exists())

    def test_nonexistent_target_user_returns_not_found(self):
        self.assign_permission(self.admin, 'ASSIGN_PERMISSION')
        self.create_function('VIEW_SELF')
        self.authenticate(self.admin)

        response = self.client.post(
            reverse('assign-permissions'),
            {'user_id': self.member.id + 1000, 'function_codes': ['VIEW_SELF']},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(PermissionAudit.objects.exists())

    def test_replacing_permissions_revokes_omitted_codes_and_audits(self):
        self.assign_permission(self.admin, 'ASSIGN_PERMISSION')
        self.assign_permission(self.member, 'VIEW_EMPLOYEE')
        function = Function.objects.get(code='VIEW_EMPLOYEE')
        self.authenticate(self.admin)

        response = self.client.post(
            reverse('assign-permissions'),
            {'user_id': self.member.id, 'function_codes': []},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(self.member.user_functions.filter(function=function).exists())
        self.assertTrue(PermissionAudit.objects.filter(
            actor=self.admin,
            target_user=self.member,
            function=function,
            action=PermissionAudit.Action.REVOKED,
        ).exists())

    def test_permission_changes_roll_back_when_audit_write_fails(self):
        self.assign_permission(self.admin, 'ASSIGN_PERMISSION')
        self.assign_permission(self.member, 'VIEW_EMPLOYEE')
        self.create_function('VIEW_SELF')
        original_create = PermissionAudit.objects.create
        audit_calls = 0

        def create_then_fail_on_assignment(*args, **kwargs):
            nonlocal audit_calls
            audit_calls += 1
            if audit_calls == 2:
                raise RuntimeError('Simulated audit failure')
            return original_create(*args, **kwargs)

        self.authenticate(self.admin)

        with patch('permissions.views.PermissionAudit.objects.create', side_effect=create_then_fail_on_assignment):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    reverse('assign-permissions'),
                    {'user_id': self.member.id, 'function_codes': ['VIEW_SELF']},
                    format='json',
                )

        self.assertTrue(self.member.user_functions.filter(function__code='VIEW_EMPLOYEE').exists())
        self.assertFalse(self.member.user_functions.filter(function__code='VIEW_SELF').exists())
        self.assertFalse(PermissionAudit.objects.filter(target_user=self.member).exists())

    def test_member_without_assign_permission_cannot_assign_permissions(self):
        self.authenticate(self.member)

        response = self.client.post(
            reverse('assign-permissions'),
            {'user_id': self.admin.id, 'function_codes': ['VIEW_EMPLOYEE']},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_with_explicit_assign_permission_can_assign(self):
        superuser = User.objects.create_superuser(email='root@example.com', password='StrongPass123!')
        self.assign_permission(superuser, 'ASSIGN_PERMISSION')
        self.create_function('VIEW_SELF')
        self.authenticate(superuser)

        response = self.client.post(
            reverse('assign-permissions'),
            {'user_id': self.member.id, 'function_codes': ['VIEW_SELF']},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(self.member.user_functions.filter(function__code='VIEW_SELF').exists())

    def test_superuser_without_assign_permission_cannot_assign_permissions(self):
        superuser = User.objects.create_superuser(email='root@example.com', password='StrongPass123!')
        self.create_function('VIEW_SELF')
        self.authenticate(superuser)

        response = self.client.post(
            reverse('assign-permissions'),
            {'user_id': self.member.id, 'function_codes': ['VIEW_SELF']},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(self.member.user_functions.exists())

    def test_permissions_endpoint_lists_active_permissions(self):
        self.assign_permission(self.member, 'VIEW_SELF')
        self.assign_permission(self.member, 'VIEW_EMPLOYEE')
        self.authenticate(self.member)

        response = self.client.get(reverse('user-permissions'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('permissions', response.data)
        self.assertIn('VIEW_SELF', response.data['permissions'])
        self.assertIn('VIEW_EMPLOYEE', response.data['permissions'])

    def test_permission_admin_options_require_assign_permission_and_exclude_caller(self):
        self.assign_permission(self.admin, 'ASSIGN_PERMISSION')
        self.assign_permission(self.member, 'VIEW_EMPLOYEE')
        self.create_function('VIEW_SELF')

        self.authenticate(self.member)
        denied = self.client.get(reverse('permission-admin-options'))
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        self.authenticate(self.admin)
        response = self.client.get(reverse('permission-admin-options'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['users'], [{
            'id': self.member.id,
            'email': self.member.email,
            'permissions': ['VIEW_EMPLOYEE'],
        }])
        self.assertEqual(
            {function['code'] for function in response.data['functions']},
            {'ASSIGN_PERMISSION', 'VIEW_EMPLOYEE', 'VIEW_SELF'},
        )

class FunctionCodeValidationTests(APITestCase):
    """The assignment requires unique uppercase permission codes.

    The RegexValidator is declared on the model, so Django enforces it wherever
    model validation runs: the Django admin, serializers, and any explicit
    full_clean() call. These tests call full_clean() because a direct
    .save() deliberately skips validation.
    """

    def setUp(self):
        self.module = Module.objects.create(code='CORE', name='Core')

    def build(self, code):
        return Function(module=self.module, name='Sample', code=code)

    def test_uppercase_code_passes_validation(self):
        self.build('VIEW_EMPLOYEE').full_clean()

    def test_lowercase_code_is_rejected(self):
        with self.assertRaises(ValidationError) as context:
            self.build('view_employee').full_clean()

        self.assertIn('code', context.exception.error_dict)

    def test_codes_with_punctuation_or_spaces_are_rejected(self):
        for code in ('VIEW EMPLOYEE', 'view-Employee', 'VIEW$', 'VIEW.EMPLOYEE', ''):
            with self.subTest(code=code):
                with self.assertRaises(ValidationError):
                    self.build(code).full_clean()

    def test_module_code_is_validated_the_same_way(self):
        with self.assertRaises(ValidationError):
            Module(code='lowercase', name='Bad').full_clean()

    def test_seeded_codes_all_pass_validation(self):
        call_command('seed_permissions', verbosity=0)

        self.assertEqual(sorted(Function.objects.values_list('code', flat=True)), [
            'ASSIGN_PERMISSION',
            'CREATE_EMPLOYEE',
            'DELETE_EMPLOYEE',
            'EDIT_EMPLOYEE',
            'VIEW_EMPLOYEE',
            'VIEW_SELF',
        ])
        for function in Function.objects.all():
            with self.subTest(code=function.code):
                function.full_clean(exclude=['module'])

    def test_seed_command_is_idempotent(self):
        call_command('seed_permissions', verbosity=0)
        call_command('seed_permissions', verbosity=0)

        self.assertEqual(Function.objects.count(), 6)