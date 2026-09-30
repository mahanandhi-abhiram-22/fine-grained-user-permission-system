import os
import stat
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

from django.conf import settings
from django.core.management.base import CommandError

from permissions.bootstrap_security import (
    ADMINISTRATORS_SID,
    FILE_WRITE_MASK,
    SYSTEM_SID,
    _acquire_windows_lock,
    _validate_mapping,
    _windows_handle,
    acquire_posix_lock_descriptor,
    ensure_trusted_settings,
    get_os_principal,
    _unique_json_keys,
    validate_posix_lock_stats,
    validate_posix_mapping_stats,
    validate_windows_acl_policy,
)


class BootstrapSettingsTests(unittest.TestCase):
    def test_canonical_settings_module_is_accepted(self):
        ensure_trusted_settings()

    def test_settings_override_is_rejected(self):
        with patch.object(settings, 'SETTINGS_MODULE', 'tests.untrusted_settings'):
            with self.assertRaises(CommandError):
                ensure_trusted_settings()

    def test_canonical_name_with_unexpected_source_path_is_rejected(self):
        impostor = types.SimpleNamespace(__file__=__file__)
        with (
            patch.object(settings, 'SETTINGS_MODULE', 'config.settings'),
            patch.dict('sys.modules', {'config.settings': impostor}),
        ):
            with self.assertRaises(CommandError):
                ensure_trusted_settings()

    def test_settings_override_is_rejected_before_operator_resolution(self):
        from permissions.management.commands.bootstrap_permission_admin import Command

        command = Command()
        with (
            patch.object(settings, 'SETTINGS_MODULE', 'tests.untrusted_settings'),
            patch('permissions.management.commands.bootstrap_permission_admin.get_os_principal') as get_principal,
        ):
            with self.assertRaises(CommandError):
                command.handle()
        get_principal.assert_not_called()

    def test_unsafe_lock_fails_before_operator_database_lookup_or_prompts(self):
        from permissions.management.commands.bootstrap_permission_admin import Command

        command = Command()
        with (
            patch('permissions.management.commands.bootstrap_permission_admin.ensure_trusted_settings'),
            patch('permissions.management.commands.bootstrap_permission_admin.get_os_principal', return_value='uid:1001'),
            patch(
                'permissions.management.commands.bootstrap_permission_admin.validate_bootstrap_lock_path',
                side_effect=CommandError('unsafe lock path'),
            ),
            patch(
                'permissions.management.commands.bootstrap_permission_admin.resolve_operator_id',
            ) as resolve_operator_id,
            patch('permissions.management.commands.bootstrap_permission_admin.load_operator_account') as load_operator,
            patch('builtins.input') as input_prompt,
        ):
            with self.assertRaises(CommandError):
                command.handle()
        resolve_operator_id.assert_not_called()
        load_operator.assert_not_called()
        input_prompt.assert_not_called()

    def test_lock_path_is_revalidated_before_lock_acquisition(self):
        """The lock path must be checked before mapping resolution and again before locking."""
        from permissions.management.commands.bootstrap_permission_admin import Command

        command = Command()
        lock_checks = []

        with (
            patch('permissions.management.commands.bootstrap_permission_admin.ensure_trusted_settings'),
            patch('permissions.management.commands.bootstrap_permission_admin.get_os_principal', return_value='uid:1001'),
            patch(
                'permissions.management.commands.bootstrap_permission_admin.validate_bootstrap_lock_path',
                side_effect=lambda principal: lock_checks.append(principal),
            ),
            patch('permissions.management.commands.bootstrap_permission_admin.resolve_operator_id', return_value=7),
            patch(
                'permissions.management.commands.bootstrap_permission_admin.load_operator_account',
                side_effect=CommandError('stop after preconditions'),
            ),
            patch('builtins.input') as input_prompt,
        ):
            with self.assertRaises(CommandError):
                command.handle()

        # The precondition check runs before any operator/database/prompt work.
        self.assertEqual(lock_checks, ['uid:1001'])
        input_prompt.assert_not_called()

    def test_prompts_follow_the_lock_path_precondition(self):
        """A prompt must never be reached when the lock path cannot be validated."""
        from permissions.management.commands.bootstrap_permission_admin import Command

        command = Command()
        call_order = []

        with (
            patch('permissions.management.commands.bootstrap_permission_admin.ensure_trusted_settings'),
            patch('permissions.management.commands.bootstrap_permission_admin.get_os_principal', return_value='uid:1001'),
            patch(
                'permissions.management.commands.bootstrap_permission_admin.validate_bootstrap_lock_path',
                side_effect=lambda principal: call_order.append('lock'),
            ),
            patch(
                'permissions.management.commands.bootstrap_permission_admin.resolve_operator_id',
                side_effect=lambda principal: call_order.append('operator') or 7,
            ),
            patch(
                'permissions.management.commands.bootstrap_permission_admin.load_operator_account',
                side_effect=lambda operator_id: call_order.append('account'),
            ),
            patch('builtins.input', side_effect=lambda *a, **k: call_order.append('prompt')),
            patch('getpass.getpass', side_effect=lambda *a, **k: call_order.append('password')),
        ):
            with self.assertRaises(CommandError):
                command.handle()

        self.assertEqual(call_order[:3], ['lock', 'operator', 'account'])
        self.assertNotIn('prompt', call_order)
        self.assertNotIn('password', call_order)


class BootstrapIdentityTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'posix', 'POSIX real/effective UID behavior only')
    def test_posix_principal_uses_effective_uid_when_real_and_effective_match(self):
        with (
            patch('permissions.bootstrap_security.os.getresuid', return_value=(1001, 1001, 1001)),
            patch('permissions.bootstrap_security.os.getresgid', return_value=(1002, 1002, 1002)),
        ):
            self.assertEqual(get_os_principal(), 'uid:1001')

    @unittest.skipUnless(os.name == 'posix', 'POSIX real/effective UID behavior only')
    def test_posix_principal_rejects_real_effective_identity_transition(self):
        with (
            patch('permissions.bootstrap_security.os.getresuid', return_value=(1001, 0, 0)),
            patch('permissions.bootstrap_security.os.getresgid', return_value=(1002, 1002, 1002)),
        ):
            with self.assertRaises(CommandError):
                get_os_principal()

    def test_mapping_rejects_empty_duplicate_or_invalid_entries(self):
        with self.assertRaises(CommandError):
            _validate_mapping({})
        with self.assertRaises(ValueError):
            _unique_json_keys([('uid:1001', 7), ('uid:1001', 8)])
        with self.assertRaises(CommandError):
            _validate_mapping({'uid:1001': True})


class BootstrapAclPolicyTests(unittest.TestCase):
    def test_registry_acl_allows_trusted_writers_and_read_only_users(self):
        validate_windows_acl_policy(
            SYSTEM_SID,
            [
                (0, 0x00000002, ADMINISTRATORS_SID),
                (0, 0x00000001, 'S-1-5-32-545'),
                (1, 0x00000002, 'S-1-5-32-545'),
            ],
            {SYSTEM_SID, ADMINISTRATORS_SID},
            {SYSTEM_SID, ADMINISTRATORS_SID},
            'registry fixture',
            0x00000002,
        )

    def test_registry_acl_rejects_untrusted_write_permission(self):
        with self.assertRaises(CommandError):
            validate_windows_acl_policy(
                SYSTEM_SID,
                [(0, 0x00000002, 'S-1-5-21-999-1001')],
                {SYSTEM_SID, ADMINISTRATORS_SID},
                {SYSTEM_SID, ADMINISTRATORS_SID},
                'registry fixture',
                0x00000002,
            )

    def test_lock_directory_acl_rejects_delete_child_for_untrusted_principal(self):
        with self.assertRaises(CommandError):
            validate_windows_acl_policy(
                SYSTEM_SID,
                [(0, 0x00000040, 'S-1-5-21-999-1001')],
                {SYSTEM_SID},
                {SYSTEM_SID},
                'lock directory fixture',
                FILE_WRITE_MASK,
            )

    def test_acl_rejects_untrusted_owner_and_unsupported_ace(self):
        with self.assertRaises(CommandError):
            validate_windows_acl_policy(
                'S-1-5-21-999-1001', [], {SYSTEM_SID}, {SYSTEM_SID}, 'lock fixture', 0x2
            )
        with self.assertRaises(CommandError):
            validate_windows_acl_policy(
                SYSTEM_SID, [(5, 0, SYSTEM_SID)], {SYSTEM_SID}, {SYSTEM_SID}, 'lock fixture', 0x2
            )

    def test_lock_acl_allows_operator_lock_access_but_rejects_delete_or_acl_rights(self):
        operator_sid = 'S-1-5-21-100-200-300-1001'
        validate_windows_acl_policy(
            operator_sid,
            [(0, 0x00000002 | 0x00100000, operator_sid)],
            {SYSTEM_SID},
            {SYSTEM_SID},
            'lock fixture',
            0x00000002,
            operator_sid=operator_sid,
        )
        with self.assertRaises(CommandError):
            validate_windows_acl_policy(
                SYSTEM_SID,
                [(0, 0x00000002 | 0x00010000, operator_sid)],
                {SYSTEM_SID},
                {SYSTEM_SID},
                'lock fixture',
                0x00000002,
                operator_sid=operator_sid,
            )

    def test_posix_mapping_and_lock_stat_validation(self):
        root_directory = types.SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
        mapping_file = types.SimpleNamespace(st_mode=stat.S_IFREG | 0o640, st_uid=0, st_nlink=1)
        validate_posix_mapping_stats(mapping_file, root_directory)

        with self.assertRaises(CommandError):
            validate_posix_mapping_stats(
                types.SimpleNamespace(st_mode=stat.S_IFREG | 0o666, st_uid=0, st_nlink=1),
                root_directory,
            )

        operator_lock = types.SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=1001, st_nlink=1)
        validate_posix_lock_stats(root_directory, operator_lock, 1001)
        with self.assertRaises(CommandError):
            validate_posix_lock_stats(root_directory, operator_lock, 2002)


@unittest.skipUnless(os.name == 'posix', 'POSIX flock contention test')
class BootstrapLockTests(unittest.TestCase):
    def test_posix_lock_serializes_concurrent_callers_and_releases(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            lock_path = os.path.join(temp_directory, 'bootstrap.lock')
            first_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
            second_fd = os.open(lock_path, os.O_RDWR)
            first_holds_lock = threading.Event()
            release_first = threading.Event()
            second_acquired = threading.Event()

            def first_worker():
                with acquire_posix_lock_descriptor(first_fd):
                    first_holds_lock.set()
                    release_first.wait(timeout=5)

            def second_worker():
                with acquire_posix_lock_descriptor(second_fd):
                    second_acquired.set()

            first_thread = threading.Thread(target=first_worker)
            second_thread = threading.Thread(target=second_worker)
            try:
                first_thread.start()
                self.assertTrue(first_holds_lock.wait(timeout=2))
                second_thread.start()
                self.assertFalse(second_acquired.wait(timeout=0.1))
                release_first.set()
                first_thread.join(timeout=2)
                second_thread.join(timeout=2)
                self.assertTrue(second_acquired.is_set())
            finally:
                release_first.set()
                first_thread.join(timeout=2)
                second_thread.join(timeout=2)
                os.close(first_fd)
                os.close(second_fd)

    def test_posix_lock_is_released_when_work_raises(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            lock_path = os.path.join(temp_directory, 'bootstrap.lock')
            descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
            try:
                with self.assertRaises(RuntimeError):
                    with acquire_posix_lock_descriptor(descriptor):
                        raise RuntimeError('transaction failed')
                with acquire_posix_lock_descriptor(descriptor):
                    self.assertTrue(True)
            finally:
                os.close(descriptor)


@unittest.skipUnless(os.name == 'nt', 'Windows LockFileEx contention test')
class BootstrapWindowsLockTests(unittest.TestCase):
    def test_windows_lock_serializes_concurrent_callers_and_releases(self):
        with tempfile.NamedTemporaryFile(delete=False) as lock_file:
            lock_path = lock_file.name
        first_handle = _windows_handle(lock_path)
        second_handle = _windows_handle(lock_path)
        first_holds_lock = threading.Event()
        release_first = threading.Event()
        second_acquired = threading.Event()

        def first_worker():
            with _acquire_windows_lock(first_handle):
                first_holds_lock.set()
                release_first.wait(timeout=5)

        def second_worker():
            with _acquire_windows_lock(second_handle):
                second_acquired.set()

        first_thread = threading.Thread(target=first_worker)
        second_thread = threading.Thread(target=second_worker)
        try:
            first_thread.start()
            self.assertTrue(first_holds_lock.wait(timeout=2))
            second_thread.start()
            self.assertFalse(second_acquired.wait(timeout=0.1))
            release_first.set()
            first_thread.join(timeout=2)
            second_thread.join(timeout=2)
            self.assertTrue(second_acquired.is_set())
        finally:
            release_first.set()
            first_thread.join(timeout=2)
            second_thread.join(timeout=2)
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle(first_handle)
            kernel32.CloseHandle(second_handle)
            os.unlink(lock_path)