"""Non-interactive creation of the first permission administrator.

This is a deliberately separate, development/seed-only command. It does NOT
weaken or bypass the security design of ``bootstrap_permission_admin``, which
remains the trusted-shell path and is left completely unchanged.

Unlike the bootstrap command, this one is safe to run unattended (containers,
CI, fresh local PostgreSQL instances) because it performs no OS-identity, ACL,
lock-path, or interactive-terminal checks. It therefore:

* requires explicit credentials supplied through the environment
  (``DEMO_ADMIN_EMAIL`` / ``DEMO_ADMIN_PASSWORD``) rather than a prompt,
* never prints, logs, or echoes the password,
* is one-time only, and refuses to run once ``ASSIGN_PERMISSION`` has already
  been granted or audited (same rule as the bootstrap command),
* never reads or copies data from any other database.
"""

import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction

from audit.models import PermissionAudit
from permissions.models import Function, UserFunction

BOOTSTRAP_PERMISSION_CODE = 'ASSIGN_PERMISSION'
DEFAULT_DEMO_ADMIN_EMAIL = 'admin@example.com'


def ensure_permission_available(function):
    """Mirror the bootstrap command's one-time-only rule."""
    if UserFunction.objects.filter(function=function).exists():
        raise CommandError(
            'ASSIGN_PERMISSION is already assigned; the initial administrator '
            'command is one-time only.'
        )
    if PermissionAudit.objects.filter(
        function=function,
        action=PermissionAudit.Action.ASSIGNED,
    ).exists():
        raise CommandError(
            'ASSIGN_PERMISSION has already been granted; the initial '
            'administrator command is one-time only.'
        )


def resolve_credentials():
    """Read credentials from the environment. Never returns them to output."""
    email = (os.getenv('DEMO_ADMIN_EMAIL') or DEFAULT_DEMO_ADMIN_EMAIL).strip().lower()
    password = os.getenv('DEMO_ADMIN_PASSWORD') or ''

    try:
        validate_email(email)
    except ValidationError as error:
        raise CommandError('DEMO_ADMIN_EMAIL is not a valid email address.') from error

    if not password:
        raise CommandError(
            'DEMO_ADMIN_PASSWORD is not set. Provide it through the project-root '
            '.env or the process environment. The password is never prompted for '
            'and never printed.'
        )
    return email, password


class Command(BaseCommand):
    help = (
        'Create a fresh initial permission administrator with an explicit '
        'ASSIGN_PERMISSION grant and audit record, without interactive input. '
        'Development/seed use only; use bootstrap_permission_admin for a '
        'trusted-shell production bootstrap.'
    )

    def handle(self, *args, **options):
        email, password = resolve_credentials()

        function = Function.objects.filter(code=BOOTSTRAP_PERMISSION_CODE).first()
        if function is None:
            raise CommandError(
                'Run seed_permissions before creating the initial administrator.'
            )
        ensure_permission_available(function)

        User = get_user_model()
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError(
                'An account with that email already exists; this command only '
                'creates a new account.'
            )

        candidate = User(email=email)
        try:
            validate_password(password, user=candidate)
        except ValidationError as error:
            raise CommandError('; '.join(error.messages)) from error

        with transaction.atomic():
            # Re-check under the transaction so a concurrent run cannot double-grant.
            ensure_permission_available(function)
            if User.objects.filter(email__iexact=email).exists():
                raise CommandError('An account with that email already exists.')

            target_user = User.objects.create_user(email=email, password=password)
            UserFunction.objects.create(
                user=target_user,
                function=function,
                granted_by=target_user,
            )
            # The creating account is the actor: this command has no separate
            # operator identity, and the record keeps the grant attributable.
            PermissionAudit.objects.create(
                actor=target_user,
                target_user=target_user,
                function=function,
                action=PermissionAudit.Action.ASSIGNED,
            )

        self.stdout.write(self.style.SUCCESS(
            f'Created initial permission administrator (user id {target_user.pk}) '
            f'with {BOOTSTRAP_PERMISSION_CODE}.'
        ))
        self.stdout.write(
            'The password was not displayed. Read it from DEMO_ADMIN_PASSWORD '
            'in your local .env if you need to sign in.'
        )