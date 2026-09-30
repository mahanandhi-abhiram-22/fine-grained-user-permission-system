import getpass
import sys
import warnings

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from audit.models import PermissionAudit
from permissions.models import Function, UserFunction
from permissions.bootstrap_security import (
    acquire_bootstrap_lock,
    ensure_trusted_settings,
    get_os_principal,
    load_operator_account,
    resolve_operator_id,
    validate_bootstrap_lock_path,
)

BOOTSTRAP_PERMISSION_CODE = 'ASSIGN_PERMISSION'


def resolve_operator():
    ensure_trusted_settings()
    principal = get_os_principal()
    validate_bootstrap_lock_path(principal)
    operator_id = resolve_operator_id(principal)
    return load_operator_account(operator_id), principal


def ensure_bootstrap_available(function):
    if UserFunction.objects.filter(function=function).exists():
        raise CommandError('ASSIGN_PERMISSION is already assigned; bootstrap is one-time only.')
    if PermissionAudit.objects.filter(
        function=function,
        action=PermissionAudit.Action.ASSIGNED,
    ).exists():
        raise CommandError('ASSIGN_PERMISSION has already been granted; bootstrap is one-time only.')


def has_secure_terminal():
    return sys.stdin.isatty() and sys.stderr.isatty()


def prompt_hidden_password(prompt):
    if not has_secure_terminal():
        raise CommandError('A secure interactive terminal is required for bootstrap credentials.')
    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter('always', getpass.GetPassWarning)
        password = getpass.getpass(prompt)
    if any(issubclass(warning.category, getpass.GetPassWarning) for warning in caught_warnings):
        raise CommandError('A secure terminal is required to enter the bootstrap password.')
    return password


class Command(BaseCommand):
    help = 'Create the initial permission administrator through a trusted server-side bootstrap.'

    def handle(self, *args, **options):
        ensure_trusted_settings()
        principal = get_os_principal()
        validate_bootstrap_lock_path(principal)
        operator_id = resolve_operator_id(principal)
        operator = load_operator_account(operator_id)
        User = get_user_model()
        function = Function.objects.filter(code=BOOTSTRAP_PERMISSION_CODE).first()
        if function is None:
            raise CommandError('Run seed_permissions before bootstrapping the permission administrator.')
        ensure_bootstrap_available(function)

        try:
            email = input('Initial permission administrator email: ').strip().lower()
        except EOFError as error:
            raise CommandError('Bootstrap requires interactive input.') from error
        if email == operator.email.lower():
            raise CommandError('The bootstrap operator and target account must be distinct.')
        try:
            validate_email(email)
        except ValidationError as error:
            raise CommandError('Enter a valid email address for the new administrator.') from error
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError('An account with that email already exists; bootstrap requires a distinct new account.')

        password = prompt_hidden_password('New administrator password: ')
        confirmation = prompt_hidden_password('Confirm password: ')
        if password != confirmation:
            raise CommandError('The passwords do not match.')
        candidate = User(email=email)
        try:
            validate_password(password, user=candidate)
        except ValidationError as error:
            raise CommandError('; '.join(error.messages)) from error

        # Re-verify the lock-path security policy immediately before acquiring the
        # lock so a path weakened after the initial preconditions were checked
        # cannot be used for the privileged bootstrap transaction.
        validate_bootstrap_lock_path(principal)
        with acquire_bootstrap_lock(principal):
            with transaction.atomic():
                operator = User.objects.select_for_update().get(pk=operator.pk, is_active=True)
                function = Function.objects.select_for_update().filter(code=BOOTSTRAP_PERMISSION_CODE).first()
                if function is None:
                    raise CommandError('The ASSIGN_PERMISSION seed definition is missing.')
                ensure_bootstrap_available(function)
                if User.objects.filter(email__iexact=email).exists():
                    raise CommandError('An account with that email already exists.')

                target_user = User.objects.create_user(email=email, password=password)
                UserFunction.objects.create(
                    user=target_user,
                    function=function,
                    granted_by=operator,
                )
                PermissionAudit.objects.create(
                    actor=operator,
                    target_user=target_user,
                    function=function,
                    action=PermissionAudit.Action.ASSIGNED,
                )

        self.stdout.write(self.style.SUCCESS(
            f'Created permission administrator account with user ID {target_user.pk}.'
        ))