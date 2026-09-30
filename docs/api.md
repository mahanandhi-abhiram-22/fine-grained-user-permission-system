# API Reference

Local backend base URL: `http://127.0.0.1:8000`. API endpoints below are mounted under `/api`. Generated Swagger UI is available at `/api/docs/`; the OpenAPI schema is at `/api/schema/`. Both documentation routes are public.

Protected API requests use the JWT access token:

```http
Authorization: Bearer <access-token>
```

## Authentication

| Method | Endpoint | Authentication | Result |
|---|---|---|---|
| POST | `/api/accounts/login/` | Public | Access token, refresh token, and user details |
| POST | `/api/accounts/token/refresh/` | Public; requires a refresh token | New access token |

Login request:

```json
{
	"email": "<account-email>",
	"password": "<account-password>"
}
```

Successful login response shape:

```json
{
	"refresh": "<refresh-token>",
	"access": "<access-token>",
	"user": {
		"id": 12,
		"email": "<account-email>",
		"first_name": "<first-name>",
		"last_name": "<last-name>",
		"is_superuser": false,
		"permissions": ["VIEW_EMPLOYEE"]
	}
}
```

Refresh request and response:

```json
{"refresh": "<refresh-token>"}
```

```json
{"access": "<access-token>"}
```

Invalid login or refresh credentials return HTTP 401. Access tokens are configured for 60 minutes and refresh tokens for one day. There is no separate logout or token-revocation API route.

## Employees

| Method | Endpoint | Authentication and permission | Success |
|---|---|---|---|
| GET | `/api/employees/` | JWT and `VIEW_EMPLOYEE` | 200, paginated list |
| POST | `/api/employees/` | JWT and `CREATE_EMPLOYEE` | 201, created employee |
| GET | `/api/employees/{id}/` | JWT and `VIEW_EMPLOYEE` | 200, employee |
| PUT/PATCH | `/api/employees/{id}/` | JWT and `EDIT_EMPLOYEE` | 200, updated employee |
| DELETE | `/api/employees/{id}/` | JWT and `DELETE_EMPLOYEE` | 204, no response body |
| GET | `/api/employees/me/` | JWT and explicit `VIEW_SELF` | 200, caller's employee record |

Every employee CRUD action requires its mapped function code, including for superusers. `/api/employees/me/` requires explicit `VIEW_SELF` and returns only the authenticated user's employee record.

Employee create request (the `user` field is read-only and set to the authenticated caller):

```json
{
	"employee_code": "EMP-100",
	"first_name": "Example",
	"last_name": "Employee",
	"department": "Engineering"
}
```

Employee response shape:

```json
{
	"id": 42,
	"user": 12,
	"employee_code": "EMP-100",
	"first_name": "Example",
	"last_name": "Employee",
	"department": "Engineering",
	"created_at": "2026-09-30T12:00:00Z",
	"updated_at": "2026-09-30T12:00:00Z"
}
```

The employee values above illustrate serializer fields and are not claims about a particular database record.

### Employee List Pagination

The list endpoint uses DRF `PageNumberPagination` with a fixed page size of 20. Use `?page=2` to request page two. The page defaults to 1; there is no `page_size` query parameter.

```json
{
	"count": 21,
	"next": null,
	"previous": "http://127.0.0.1:8000/api/employees/?page=1",
	"results": [
		{
			"id": 42,
			"user": 12,
			"employee_code": "EMP-100",
			"first_name": "Example",
			"last_name": "Employee",
			"department": "Engineering",
			"created_at": "2026-09-30T12:00:00Z",
			"updated_at": "2026-09-30T12:00:00Z"
		}
	]
}
```

`count` is the total number of employees; `results` contains the current page. `next` and `previous` are absolute navigation URLs or `null`. Invalid and out-of-range page numbers return HTTP 404 with `{"detail":"Invalid page."}`.

### Self-Profile Behavior

The view filters by the authenticated user and does not accept a user ID for selecting another person's record. No associated employee returns HTTP 404 (`{"detail":"Employee profile not found."}`). Multiple associated employees return HTTP 409 (`{"detail":"Multiple employee records are associated with this user."}`) rather than an arbitrary record.

## Permissions

| Method | Endpoint | Authentication and permission | Result |
|---|---|---|---|
| GET | `/api/permissions/me/` | JWT only | 200, caller identity and permission codes |
| GET | `/api/permissions/manage/` | JWT and explicit `ASSIGN_PERMISSION` | 200, other users and registered functions |
| POST | `/api/permissions/assign/` | JWT and explicit `ASSIGN_PERMISSION` | 200, updated permission set |

Current-permissions response:

```json
{
	"id": 12,
	"email": "<account-email>",
	"is_superuser": false,
	"permissions": ["VIEW_EMPLOYEE", "VIEW_SELF"]
}
```

Permission assignment request:

```json
{
	"user_id": 34,
	"function_codes": ["VIEW_EMPLOYEE", "VIEW_SELF"]
}
```

The `GET /api/permissions/manage/` response supplies users other than the caller and registered permission choices to the UI:

```json
{
	"users": [
		{"id": 34, "email": "<account-email>", "permissions": ["VIEW_EMPLOYEE"]}
	],
	"functions": [
		{"code": "VIEW_EMPLOYEE", "name": "View Employee"}
	]
}
```

This endpoint requires explicit `ASSIGN_PERMISSION` and never returns the caller as an assignable target.

Codes must refer to existing `Function` records. Inputs are normalized to uppercase and duplicates are removed. Unknown or blank codes return HTTP 400; a nonexistent `user_id` returns HTTP 404. Self-assignment returns HTTP 403. Superusers also need explicit `ASSIGN_PERMISSION` for this endpoint.

Assignment replaces the target user's entire permission set. Omitted codes are revoked; an empty list revokes all permissions. There is no separate revoke endpoint. Successful response:

```json
{
	"detail": "Permissions updated successfully.",
	"user_id": 34,
	"permissions": ["VIEW_EMPLOYEE", "VIEW_SELF"]
}
```

## Common Status Codes

| Status | Meaning |
|---|---|
| 200 | Successful read, update, token refresh, or permission replacement |
| 201 | Employee created |
| 204 | Employee deleted; no response body |
| 400 | Invalid input, including unknown permission codes |
| 401 | Missing or invalid authentication credentials |
| 403 | Authenticated user lacks permission or attempts self-assignment |
| 404 | Resource/profile not found or invalid/out-of-range page number |
| 409 | Multiple employee records are associated with `/api/employees/me/` |

## Permission Seed

From the `backend` directory, run `python manage.py seed_permissions` to create the six permission definitions. This command does not create users or grant assignments.

## Initial Permission Administrator Bootstrap

There is no public bootstrap API. Run `python manage.py bootstrap_permission_admin` only from a trusted server shell after migrations and `seed_permissions` have completed. The command accepts only the canonical `config.settings` module and verifies its source path before mapping lookup or database access; alternate `DJANGO_SETTINGS_MODULE` and `--settings` selections are rejected. It does not accept operator identity or mapping/lock-path overrides as arguments.

The principal must map to an active Django operator account in protected host configuration. Windows identity is the process-token SID; thread impersonation is rejected. POSIX identity is the effective UID, and differing real/effective UID or GID values are rejected. `SUDO_USER` is not used. Password prompts require an interactive terminal and fail before input if getpass would echo.

- **Windows:** Use the `HKLM\SOFTWARE\FineGrainedPermissionSystem\BootstrapOperators` registry key. Each value name is a SID such as `sid:<SID>`; its `DWORD` value is the mapped Django user ID. The command validates DACLs on the key and ancestors, rejecting unsafe owners, untrusted write ACEs, and unsupported ACE types. Restrict key writes to administrators and `SYSTEM`.
- **POSIX:** Use `/etc/fine-grained-permissions/bootstrap-operators.json`, for example `{ "uid:1001": 7 }`. The file and every parent must be real, root-owned, and not group/world writable; the file must be a single-link regular file. It is opened without following symlinks and checked again after open.

The command uses a host-local lock at `C:\ProgramData\FineGrainedPermissionSystem\bootstrap.lock` on Windows or `/run/fine-grained-permissions/bootstrap.lock` on POSIX. It validates file/directory type, reparse/symlink status, ownership, and ACL/modes before locking the same verified handle/file descriptor. Pre-create the POSIX directory as root-owned and non-writable by group/other, with the lock file owned by the mapped operator and mode `0600`. POSIX flock does not coordinate multiple hosts sharing a database; the configured SQLite deployment is single-host. Provision the Windows directory with restrictive ACLs for the mapped operator, administrators, and `SYSTEM`.

The command prompts for a new administrator email and hidden password, creates a regular account, and grants only `ASSIGN_PERMISSION`. The target must differ from the mapped operator. The existing `PermissionAudit` row records the mapped Django operator as actor. User creation, assignment, and audit are transactional. Bootstrap is refused if the permission has ever been assigned, even if that assignment was later revoked. Subsequent grants/revocations use `POST /api/permissions/assign/` and its existing replacement semantics.
