from django.core.management.base import BaseCommand
from permissions.models import Module, Function

class Command(BaseCommand):
    help = 'Seeds initial modules and permissions into the database'

    def handle(self, *args, **options):
        # 1. Ensure parent module exists
        module, _ = Module.objects.get_or_create(
            code='EMPLOYEE_MGMT',
            defaults={'name': 'Employee Management', 'description': 'Employee management module'}
        )

        # 2. Required fine-grained permissions contract
        permissions = [
            {'code': 'CREATE_EMPLOYEE', 'name': 'Create Employee', 'description': 'Permission to create new employees'},
            {'code': 'EDIT_EMPLOYEE', 'name': 'Edit Employee', 'description': 'Permission to update employee records'},
            {'code': 'DELETE_EMPLOYEE', 'name': 'Delete Employee', 'description': 'Permission to delete employees'},
            {'code': 'VIEW_EMPLOYEE', 'name': 'View Employee', 'description': 'Permission to view employee list/details'},
            {'code': 'VIEW_SELF', 'name': 'View Self Profile', 'description': 'Permission to view own profile'},
            {'code': 'ASSIGN_PERMISSION', 'name': 'Assign Permission', 'description': 'Permission to assign/revoke permissions'},
        ]

        # 3. Seed functions linked to the module
        for perm in permissions:
            obj, created = Function.objects.get_or_create(
                code=perm['code'],
                defaults={
                    'module': module,
                    'name': perm['name'],
                    'description': perm['description']
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created permission: {perm['code']}"))
            else:
                self.stdout.write(f"Permission already exists: {perm['code']}")
