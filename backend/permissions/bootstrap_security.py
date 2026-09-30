import ctypes
import json
import os
import stat
import sys
from contextlib import contextmanager
from ctypes import wintypes
from importlib import import_module
from pathlib import Path

from django.conf import settings
from django.core.management.base import CommandError

CANONICAL_SETTINGS_MODULE = 'config.settings'
BACKEND_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SETTINGS_FILE = BACKEND_ROOT / 'config' / 'settings.py'
WINDOWS_MAPPING_KEY = r'SOFTWARE\FineGrainedPermissionSystem\BootstrapOperators'
WINDOWS_LOCK_PATH = Path(r'C:\ProgramData\FineGrainedPermissionSystem\bootstrap.lock')
POSIX_MAPPING_PATH = Path('/etc/fine-grained-permissions/bootstrap-operators.json')
POSIX_LOCK_PATH = Path('/run/fine-grained-permissions/bootstrap.lock')

SYSTEM_SID = 'S-1-5-18'
ADMINISTRATORS_SID = 'S-1-5-32-544'
TRUSTED_INSTALLER_SID = 'S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464'
TRUSTED_OWNERS = {SYSTEM_SID, ADMINISTRATORS_SID, TRUSTED_INSTALLER_SID}

REGISTRY_WRITE_MASK = 0x00000002 | 0x00000004 | 0x00010000 | 0x00040000 | 0x00080000 | 0x40000000 | 0x10000000
FILE_WRITE_MASK = 0x00000002 | 0x00000004 | 0x00000010 | 0x00000040 | 0x00000100 | 0x00010000 | 0x00040000 | 0x00080000 | 0x40000000 | 0x10000000
FILE_DELETE_MASK = 0x00010000 | 0x00000040 | 0x00040000 | 0x00080000 | 0x40000000 | 0x10000000
FILE_OPERATOR_LOCK_MASK = 0x00000001 | 0x00000002 | 0x00000080 | 0x00020000 | 0x00100000


def _close_windows_handle(handle):
    close_handle = ctypes.WinDLL('kernel32', use_last_error=True).CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    native_handle = handle if isinstance(handle, ctypes.c_void_p) else wintypes.HANDLE(handle)
    if not close_handle(native_handle):
        raise CommandError('Unable to release a verified Windows handle.')


def ensure_trusted_settings():
    if getattr(settings, 'SETTINGS_MODULE', None) != CANONICAL_SETTINGS_MODULE:
        raise CommandError('Bootstrap requires the canonical config.settings module.')
    module = sys.modules.get(CANONICAL_SETTINGS_MODULE)
    if module is None:
        try:
            module = import_module(CANONICAL_SETTINGS_MODULE)
        except ImportError as error:
            raise CommandError('Unable to verify canonical Django settings.') from error
    module_path = getattr(module, '__file__', None)
    if not module_path or Path(module_path).resolve() != CANONICAL_SETTINGS_FILE.resolve():
        raise CommandError('Bootstrap rejected an unexpected settings module path.')


def get_os_principal():
    if os.name == 'nt':
        return _get_windows_principal()
    if os.name == 'posix' and hasattr(os, 'geteuid'):
        user_ids = os.getresuid() if hasattr(os, 'getresuid') else (os.getuid(), os.geteuid())
        group_ids = os.getresgid() if hasattr(os, 'getresgid') else (os.getgid(), os.getegid())
        if len(set(user_ids)) != 1 or len(set(group_ids)) != 1:
            raise CommandError('Bootstrap refuses processes with differing real and effective identities.')
        return f'uid:{user_ids[1]}'
    raise CommandError('This platform does not provide a supported OS principal API.')


def _get_windows_principal():
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    advapi32 = ctypes.WinDLL('advapi32', use_last_error=True)
    current_thread = kernel32.GetCurrentThread
    current_thread.restype = wintypes.HANDLE
    thread_token = wintypes.HANDLE()
    open_thread_token = advapi32.OpenThreadToken
    open_thread_token.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, ctypes.POINTER(wintypes.HANDLE)]
    open_thread_token.restype = wintypes.BOOL
    if open_thread_token(current_thread(), 0x0008, True, ctypes.byref(thread_token)):
        _close_windows_handle(thread_token)
        raise CommandError('Bootstrap refuses an impersonated Windows thread.')
    if ctypes.get_last_error() != 1008:
        raise CommandError('Unable to verify the Windows thread identity.')

    class SidAndAttributes(ctypes.Structure):
        _fields_ = [('sid', wintypes.LPVOID), ('attributes', wintypes.DWORD)]

    class TokenUser(ctypes.Structure):
        _fields_ = [('user', SidAndAttributes)]

    process_token = wintypes.HANDLE()
    open_process_token = advapi32.OpenProcessToken
    open_process_token.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    open_process_token.restype = wintypes.BOOL
    get_current_process = kernel32.GetCurrentProcess
    get_current_process.restype = wintypes.HANDLE
    get_token_information = advapi32.GetTokenInformation
    get_token_information.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    get_token_information.restype = wintypes.BOOL

    if not open_process_token(get_current_process(), 0x0008, ctypes.byref(process_token)):
        raise CommandError('Unable to verify the Windows process identity.')
    try:
        required_size = wintypes.DWORD()
        get_token_information(process_token, 1, None, 0, ctypes.byref(required_size))
        if not required_size.value:
            raise CommandError('Unable to read the Windows process identity.')
        token_buffer = ctypes.create_string_buffer(required_size.value)
        if not get_token_information(process_token, 1, token_buffer, required_size, ctypes.byref(required_size)):
            raise CommandError('Unable to read the Windows process identity.')
        token_user = ctypes.cast(token_buffer, ctypes.POINTER(TokenUser)).contents
        return f'sid:{_sid_to_string(token_user.user.sid)}'
    finally:
        _close_windows_handle(process_token)


def _sid_to_string(sid):
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    advapi32 = ctypes.WinDLL('advapi32', use_last_error=True)
    sid_string = wintypes.LPWSTR()
    convert_sid = advapi32.ConvertSidToStringSidW
    convert_sid.argtypes = [wintypes.LPVOID, ctypes.POINTER(wintypes.LPWSTR)]
    convert_sid.restype = wintypes.BOOL
    if not convert_sid(sid, ctypes.byref(sid_string)):
        raise CommandError('Unable to canonicalize the Windows process identity.')
    try:
        return sid_string.value
    finally:
        local_free = kernel32.LocalFree
        local_free.argtypes = [wintypes.HLOCAL]
        local_free.restype = wintypes.HLOCAL
        local_free(ctypes.cast(sid_string, wintypes.HLOCAL))


def _unique_json_keys(pairs):
    mapping = {}
    for key, value in pairs:
        if key in mapping:
            raise ValueError('Duplicate mapping key.')
        mapping[key] = value
    return mapping


def _validate_mapping(mapping):
    if not isinstance(mapping, dict) or not mapping:
        raise CommandError('The bootstrap operator mapping must be a non-empty object.')
    if any(not isinstance(principal, str) or type(user_id) is not int or user_id <= 0
           for principal, user_id in mapping.items()):
        raise CommandError('Every bootstrap mapping must map an OS principal to a positive Django user ID.')
    return mapping


def _load_posix_mapping():
    mapping_path = POSIX_MAPPING_PATH
    try:
        _validate_posix_directory_chain(mapping_path.parent)
        directory_stat = mapping_path.parent.lstat()
        file_stat = mapping_path.lstat()
        validate_posix_mapping_stats(file_stat, directory_stat)

        descriptor = os.open(mapping_path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0))
        with os.fdopen(descriptor, encoding='utf-8') as mapping_file:
            opened_stat = os.fstat(mapping_file.fileno())
            if (opened_stat.st_dev, opened_stat.st_ino) != (file_stat.st_dev, file_stat.st_ino):
                raise CommandError('The POSIX mapping changed while it was being opened.')
            mapping = json.load(mapping_file, object_pairs_hook=_unique_json_keys)
    except CommandError:
        raise
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise CommandError('Unable to safely read the protected POSIX operator mapping.') from error
    return _validate_mapping(mapping)


def _load_windows_mapping():
    import winreg

    mapping = {}
    parts = WINDOWS_MAPPING_KEY.split('\\')
    try:
        for index in range(1, len(parts) + 1):
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                '\\'.join(parts[:index]),
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY | 0x00020000,
            )
            try:
                _validate_windows_acl(int(key), 4, TRUSTED_OWNERS, TRUSTED_OWNERS, 'registry mapping')
                if index == len(parts):
                    value_index = 0
                    while True:
                        try:
                            principal, operator_id, value_type = winreg.EnumValue(key, value_index)
                        except OSError:
                            break
                        if value_type != winreg.REG_DWORD or type(operator_id) is not int or operator_id <= 0:
                            raise CommandError('Registry mapping entries must be positive DWORD user IDs.')
                        mapping[principal] = operator_id
                        value_index += 1
            finally:
                key.Close()
    except CommandError:
        raise
    except OSError as error:
        raise CommandError('Unable to read or verify the protected Windows operator registry key.') from error
    return _validate_mapping(mapping)


def load_operator_mapping():
    return _load_windows_mapping() if os.name == 'nt' else _load_posix_mapping()


def resolve_operator_id(principal):
    mapping = load_operator_mapping()
    operator_id = mapping.get(principal)
    if type(operator_id) is not int or operator_id <= 0:
        raise CommandError('The verified OS principal is not mapped to a bootstrap operator.')
    return operator_id


def load_operator_account(operator_id):
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    try:
        return user_model.objects.get(pk=operator_id, is_active=True)
    except user_model.DoesNotExist as error:
        raise CommandError('The mapped bootstrap operator account is unavailable.') from error


class _AceHeader(ctypes.Structure):
    _fields_ = [('ace_type', ctypes.c_ubyte), ('ace_flags', ctypes.c_ubyte), ('ace_size', wintypes.WORD)]


def _validate_windows_acl(handle, object_type, allowed_owners, trusted_writers, label, operator_sid=None):
    advapi32 = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    owner = ctypes.c_void_p()
    dacl = ctypes.c_void_p()
    descriptor = ctypes.c_void_p()
    get_security_info = advapi32.GetSecurityInfo
    get_security_info.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    get_security_info.restype = wintypes.DWORD
    result = get_security_info(
        wintypes.HANDLE(handle), object_type, 0x00000001 | 0x00000004,
        ctypes.byref(owner), None, ctypes.byref(dacl), None, ctypes.byref(descriptor),
    )
    if result != 0 or not owner.value or not descriptor.value:
        raise CommandError(f'Unable to inspect the {label} security descriptor.')
    try:
        present = wintypes.BOOL()
        defaulted = wintypes.BOOL()
        get_dacl = advapi32.GetSecurityDescriptorDacl
        get_dacl.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL), ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.BOOL)]
        get_dacl.restype = wintypes.BOOL
        if not get_dacl(descriptor, ctypes.byref(present), ctypes.byref(dacl), ctypes.byref(defaulted)) or not present.value or not dacl.value:
            raise CommandError(f'The {label} must have an explicit, non-null DACL.')

        class AclSizeInformation(ctypes.Structure):
            _fields_ = [('ace_count', wintypes.DWORD), ('acl_bytes_in_use', wintypes.DWORD), ('acl_bytes_free', wintypes.DWORD)]

        acl_info = AclSizeInformation()
        if not advapi32.GetAclInformation(dacl, ctypes.byref(acl_info), ctypes.sizeof(acl_info), 2):
            raise CommandError(f'Unable to inspect the {label} DACL.')
        get_ace = advapi32.GetAce
        get_ace.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)]
        get_ace.restype = wintypes.BOOL
        ace_entries = []
        for index in range(acl_info.ace_count):
            ace = ctypes.c_void_p()
            if not get_ace(dacl, index, ctypes.byref(ace)) or not ace.value:
                raise CommandError(f'Unable to inspect an ACE in the {label} DACL.')
            header = ctypes.cast(ace, ctypes.POINTER(_AceHeader)).contents
            access_mask = ctypes.c_uint32.from_address(ace.value + ctypes.sizeof(_AceHeader)).value
            ace_sid = _sid_to_string(ctypes.c_void_p(ace.value + 8))
            ace_entries.append((header.ace_type, access_mask, ace_sid))
        write_mask = REGISTRY_WRITE_MASK if object_type == 4 else FILE_WRITE_MASK
        validate_windows_acl_policy(
            _sid_to_string(owner), ace_entries, allowed_owners, trusted_writers,
            label, write_mask, operator_sid,
        )
    finally:
        local_free = kernel32.LocalFree
        local_free.argtypes = [wintypes.HLOCAL]
        local_free.restype = wintypes.HLOCAL
        local_free(ctypes.cast(descriptor, wintypes.HLOCAL))


def _windows_handle(path, directory=False):
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create_file.restype = wintypes.HANDLE
    access = 0x00020000 | (0x00000080 if directory else FILE_OPERATOR_LOCK_MASK)
    flags = 0x00200000 | (0x02000000 if directory else 0)
    handle = create_file(str(path), access, 0x00000001 | 0x00000002, None, 3, flags, None)
    if handle == wintypes.HANDLE(-1).value:
        raise CommandError(f'Unable to securely open bootstrap path: {path}')

    class FileAttributeTagInfo(ctypes.Structure):
        _fields_ = [('attributes', wintypes.DWORD), ('reparse_tag', wintypes.DWORD)]

    info = FileAttributeTagInfo()
    get_info = kernel32.GetFileInformationByHandleEx
    get_info.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    get_info.restype = wintypes.BOOL
    if not get_info(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
        _close_windows_handle(handle)
        raise CommandError(f'Unable to inspect bootstrap path: {path}')
    if info.attributes & 0x00000400 or bool(info.attributes & 0x00000010) != directory:
        _close_windows_handle(handle)
        raise CommandError(f'Bootstrap path has an unexpected reparse-point or file type: {path}')
    return handle


def _validate_windows_path_acl(path, operator_sid, is_lock_file=False):
    path = Path(path)
    directories = []
    current = Path(path.anchor)
    components = path.parts[1:-1] if is_lock_file else path.parts[1:]
    for component in components:
        current = current / component
        directories.append(current)
    for directory in directories:
        handle = _windows_handle(directory, directory=True)
        try:
            _validate_windows_acl(handle, 1, TRUSTED_OWNERS, TRUSTED_OWNERS, 'bootstrap directory')
        finally:
            _close_windows_handle(handle)
    if is_lock_file:
        return _open_verified_windows_lock(path, operator_sid)


def validate_bootstrap_lock_path(operator_principal):
    if os.name == 'nt':
        operator_sid = operator_principal.removeprefix('sid:')
        lock_handle = _validate_windows_path_acl(WINDOWS_LOCK_PATH, operator_sid, is_lock_file=True)
        _close_windows_handle(lock_handle)
        return
    _validate_posix_lock_path(POSIX_LOCK_PATH, int(operator_principal.removeprefix('uid:')))


def _open_verified_windows_lock(path, operator_sid):
    handle = _windows_handle(path, directory=False)
    try:
        _validate_windows_acl(handle, 1, TRUSTED_OWNERS, TRUSTED_OWNERS, 'bootstrap lock', operator_sid=operator_sid)
        return handle
    except Exception:
        _close_windows_handle(handle)
        raise


def _validate_posix_directory_chain(directory):
    current = Path(directory.anchor)
    for component in directory.parts[1:]:
        current = current / component
        try:
            directory_stat = current.lstat()
        except OSError as error:
            raise CommandError(f'Unable to verify protected directory: {current}') from error
        if (
            not stat.S_ISDIR(directory_stat.st_mode)
            or directory_stat.st_uid != 0
            or directory_stat.st_mode & 0o022
        ):
            raise CommandError(f'Protected directory is unsafe: {current}')


def _validate_posix_lock_path(path, operator_uid):
    lock_path = Path(path)
    try:
        _validate_posix_directory_chain(lock_path.parent)
        directory_stat = lock_path.parent.lstat()
        lock_stat = lock_path.lstat()
        validate_posix_lock_stats(directory_stat, lock_stat, operator_uid)
    except CommandError:
        raise
    except OSError as error:
        raise CommandError('Unable to verify the protected POSIX lock path.') from error


def validate_posix_mapping_stats(file_stat, directory_stat, root_uid=0):
    if not stat.S_ISDIR(directory_stat.st_mode) or directory_stat.st_uid != root_uid or directory_stat.st_mode & 0o022:
        raise CommandError('The POSIX mapping directory must be real, root-owned, and not group/world writable.')
    if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_uid != root_uid or file_stat.st_mode & 0o022:
        raise CommandError('The POSIX mapping must be a root-owned, non-writable regular file.')
    if file_stat.st_nlink != 1:
        raise CommandError('The POSIX mapping file must not have additional hard links.')


def validate_posix_lock_stats(directory_stat, lock_stat, operator_uid):
    if not stat.S_ISDIR(directory_stat.st_mode) or directory_stat.st_uid != 0 or directory_stat.st_mode & 0o022:
        raise CommandError('The POSIX lock directory must be real, root-owned, and not group/world writable.')
    if not stat.S_ISREG(lock_stat.st_mode) or lock_stat.st_uid != operator_uid or lock_stat.st_nlink != 1:
        raise CommandError('The POSIX lock must be a single-link regular file owned by the operator.')
    if lock_stat.st_mode & 0o077:
        raise CommandError('The POSIX lock file must not grant group/world access.')


def validate_windows_acl_policy(owner_sid, ace_entries, allowed_owners, trusted_writers, label, write_mask, operator_sid=None):
    owner_allowlist = set(allowed_owners)
    if operator_sid:
        owner_allowlist.add(operator_sid)
    if owner_sid not in owner_allowlist:
        raise CommandError(f'The {label} has an untrusted owner.')
    trusted = set(trusted_writers)
    for ace_type, access_mask, ace_sid in ace_entries:
        if ace_type == 1:
            continue
        if ace_type != 0:
            raise CommandError(f'The {label} DACL contains an unsupported ACE type.')
        if operator_sid and ace_sid == operator_sid:
            forbidden = access_mask & (FILE_WRITE_MASK & ~FILE_OPERATOR_LOCK_MASK)
            if forbidden:
                raise CommandError(f'The {label} grants the operator excessive write or ACL-management rights.')
            continue
        if access_mask & write_mask and ace_sid not in trusted:
            raise CommandError(f'The {label} grants write access to an untrusted principal.')


@contextmanager
def acquire_posix_lock_descriptor(descriptor):
    import fcntl

    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    except OSError as error:
        raise CommandError('Unable to acquire or release the protected POSIX bootstrap lock.') from error


@contextmanager
def _acquire_windows_lock(handle):
    class Overlapped(ctypes.Structure):
        _fields_ = [
            ('internal', ctypes.c_void_p), ('internal_high', ctypes.c_void_p),
            ('offset', wintypes.DWORD), ('offset_high', wintypes.DWORD), ('event', wintypes.HANDLE),
        ]

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    lock_file = kernel32.LockFileEx
    lock_file.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(Overlapped)]
    lock_file.restype = wintypes.BOOL
    unlock_file = kernel32.UnlockFileEx
    unlock_file.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(Overlapped)]
    unlock_file.restype = wintypes.BOOL
    overlapped = Overlapped()
    if not lock_file(handle, 0x00000002, 0, 1, 0, ctypes.byref(overlapped)):
        raise CommandError('Unable to acquire the protected Windows bootstrap lock.')
    try:
        yield
    finally:
        unlock_file(handle, 0, 1, 0, ctypes.byref(overlapped))


@contextmanager
def acquire_bootstrap_lock(operator_principal):
    if os.name == 'nt':
        operator_sid = operator_principal.removeprefix('sid:')
        lock_handle = _validate_windows_path_acl(WINDOWS_LOCK_PATH, operator_sid, is_lock_file=True)
        try:
            with _acquire_windows_lock(lock_handle):
                yield
        finally:
            _close_windows_handle(lock_handle)
        return

    operator_uid = int(operator_principal.removeprefix('uid:'))
    _validate_posix_lock_path(POSIX_LOCK_PATH, operator_uid)
    try:
        descriptor = os.open(POSIX_LOCK_PATH, os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0))
    except OSError as error:
        raise CommandError('Unable to open the protected POSIX bootstrap lock.') from error
    try:
        opened_stat = os.fstat(descriptor)
        if not stat.S_ISREG(opened_stat.st_mode) or opened_stat.st_uid != operator_uid or opened_stat.st_mode & 0o077:
            raise CommandError('The opened POSIX lock file failed security validation.')
        with acquire_posix_lock_descriptor(descriptor):
            yield
    except OSError as error:
        raise CommandError('Unable to acquire the protected POSIX bootstrap lock.') from error
    finally:
        os.close(descriptor)