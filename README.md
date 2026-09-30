# Fine-Grained User Permission System

An employee management application that demonstrates **fine-grained, per-user authorization** built with React, Django REST Framework, PostgreSQL, and JWT authentication. Instead of assigning broad static roles (Admin / Manager / Employee), this system assigns **individual permission codes directly to specific users**, enforces every one of those permissions **on the backend**, and reflects them **dynamically in the React frontend**.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Key Features](#key-features)
3. [Technology Stack](#technology-stack)
4. [Architecture](#architecture)
5. [Permission Model](#permission-model)
6. [API Overview](#api-overview)
7. [Authentication Flow](#authentication-flow)
8. [Permission Assignment Flow](#permission-assignment-flow)
9. [Frontend Behavior](#frontend-behavior)
10. [Security Design](#security-design)
11. [Testing](#testing)
12. [Project Structure](#project-structure)
13. [Setup Instructions](#setup-instructions)
14. [Bootstrapping the Permission Administrator](#bootstrapping-the-permission-administrator)
15. [Documentation](#documentation)
16. [Design Decisions](#design-decisions)
17. [Limitations and Repository Notes](#limitations-and-repository-notes)

---

## Project Overview

Most applications gate functionality using coarse roles: a user is either an "admin" or a "user", and authorization becomes an `if is_admin:` scattered through the codebase. That model is inflexible and hard to audit, because the actual capabilities of a person are rarely all-or-nothing. Someone may legitimately need to **view** the employee directory and **edit** records without being able to **delete** them or **grant permissions to others**.

This project replaces roles with a direct, data-driven mapping between users and **functions** (permission codes). Six specific permissions — `CREATE_EMPLOYEE`, `EDIT_EMPLOYEE`, `DELETE_EMPLOYEE`, `VIEW_EMPLOYEE`, `VIEW_SELF`, and `ASSIGN_PERMISSION` — are stored as rows in a `Function` table and assigned to individual users through a `UserFunction` join table. Authorization is then resolved at request time from that mapping.

Every protected API endpoint declares **which function code it requires**, and a single reusable permission class enforces that declaration. The result is that permission logic lives in exactly one place, adding a new capability means adding a data row rather than editing scattered conditionals, and a superuser has **no implicit bypass** — privileges are always explicit and auditable.

---

## Key Features

**Authentication & sessions**

- JWT authentication using Django SimpleJWT (stateless access + refresh tokens)
- Passwords stored using Django's secure password hashers, never in plain text
- Django password validators enforced at account creation
- Protected API routes that reject unauthenticated requests with `401`
- Automatic access-token refresh and single request retry
- Session clearing and return to login when the session becomes unrecoverable

**Fine-grained authorization**

- Function-based permission model (`User` <-> `Function` via `UserFunction`)
- Six required permission codes seeded through a management command
- A single reusable permission class (`HasFunctionPermission`) drives all authorization
- Per-action permission mapping for the full employee CRUD surface
- Dedicated `VIEW_SELF` endpoint that returns only the caller's own employee record
- Permission replacement semantics: omitted codes are revoked
- Validation of submitted permission codes against the registered catalog
- Protection against self-targeting when assigning permissions

**User interface**

- Dynamic permission-management panel rendered only for `ASSIGN_PERMISSION` holders
- Target users and function codes are loaded from the backend - never hardcoded in the frontend
- Checkbox-based permission selection with success and validation error feedback
- Paginated employee directory with previous/next navigation

**Operations & security**

- Auditing of every permission assignment and revocation, recording the acting user
- Transactional permission changes so partial writes cannot occur
- Secure, trusted-server-shell bootstrap command for creating the first permission administrator
- Interactive-terminal requirement for credential entry during bootstrap

---

## Technology Stack

### Frontend

| Technology | Purpose |
|---|---|
| React 19 | User interface |
| Vite | Development server and production bundler |
| Axios | HTTP client with request/response interceptors |
| Vitest | Unit and component test runner |
| React Testing Library | DOM-based component testing |
| jsdom | Browser-like environment for Vitest |
| ESLint | Static analysis |

> The frontend uses a single authenticated `Dashboard` view toggled by session state in `App.jsx`; a client-side router library is not used.

### Backend

| Technology | Purpose |
|---|---|
| Python | Language |
| Django 5 | Web framework |
| Django REST Framework | REST API layer |
| SimpleJWT | Access/refresh token issuance and validation |
| django-cors-headers | CORS for the local Vite dev server |
| drf-spectacular | OpenAPI schema and Swagger UI |
| PostgreSQL 14+ | Relational database (required by the assignment) |

### Version control

Git and GitHub for source control.

---

## Architecture

### Request flow

```text
        +------------------------------+
        |        React UI              |
        |  (Dashboard / Login)         |
        +--------------+---------------+
                       |  Authorization: Bearer <access token>
                       v
        +------------------------------+
        |   Django REST Framework      |
        |  JWTAuthentication           |
        |  (validates token or -> 401) |
        +--------------+---------------+
                       v
        +------------------------------+
        |    HasFunctionPermission     |  <- single, reusable gate
        |  (the only authorization     |
        |   decision point)            |
        +--------------+---------------+
                       |  required_function
                       v
        +------------------------------+
        |  action_permissions mapping  |  (EmployeeViewSet)
        |  e.g. 'destroy' ->           |
        |  DELETE_EMPLOYEE             |
        +--------------+---------------+
                       v
        +------------------------------+
        |   UserFunction join table    |  (user <-> function)
        |   "does this user hold it?"  |
        +--------------+---------------+
                       v
              +--------+--------+
              |                 |
        permission held    not held / not
                           authenticated
              v                 v
        +-----------+    +--------------+
        |  200 /    |    | 403 Forbidden |
        |  201 / 204|    |  401 if no    |
        +-----------+    |  credentials  |
                         +--------------+
```

### Why authorization is centralized

All authorization decisions flow through **one** class, `HasFunctionPermission`, in `backend/permissions/permissions.py`. Each protected view only has to *declare* the permission code it needs — it never re-implements the check:

```python
class HasFunctionPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        required_function = getattr(view, 'required_function', None)
        if not required_function:
            return False
        return request.user.user_functions.filter(
            function__code=required_function
        ).exists()
```

This design means:

- **One place to audit.** There is a single, greppable definition of "what counts as authorized."
- **No duplicated logic.** Hardcoded email checks, `is_staff` checks, and role `if/else` chains are absent from the codebase.
- **Data-driven.** Granting a new capability is a database change (`Function` row + `UserFunction` assignment), not a code change.
- **Safe default.** If a view forgets to declare `required_function`, the permission class returns `False` and the request is denied rather than allowed.

---

## Permission Model

### Entities

```text
   +----------------+                +----------------+
   |      User      |                |    Function    |
   |                |                |                |
   | id             |                | id             |
   | email (unique) |                | code (unique)  |
   | password hash  |                | name           |
   | is_active      |                | description    |
   | is_superuser   |                | module --------+
   +-------+--------+                +----------------+
           |
           |            +-------------------+
           +---------->|   UserFunction    |<--+
                        |                   |
                        | user      (FK)    |
                        | function  (FK)    |
                        | granted_at        |
                        | granted_by (FK)   |  <-- who performed the grant
                        |                   |
                        | UNIQUE(user,      |  <-- no duplicate grants
                        |       function)   |
                        +-------------------+

   +----------------+
   |     Module     |  (groups functions into a feature area)
   | id, code, name |
   +-------+--------+
           | 1
           |
           | N
      +----+-----+
      | Function |
      +----------+

   +----------------+
   | PermissionAudit|  (immutable history)
   | actor      FK  |  <-- who did it
   | target_user FK |  <-- whose permissions changed
   | function   FK  |
   | action         |  <-- ASSIGNED | REVOKED
   | created_at     |
   +----------------+
```

Key points:

- A `Function` is a **permission definition**, not a role. It carries a stable `code` and belongs to a `Module`.
- A `UserFunction` row is an **individual grant**. Its composite unique constraint `(user, function)` prevents duplicates.
- `granted_by` records which user performed the grant.
- `PermissionAudit` rows are written for every `ASSIGNED` and `REVOKED` change, giving a full history.
- `Module` groups functions for organization; it is not used for authorization decisions.

### The six required permission codes

| Permission code | Controls | Enforced at |
|---|---|---|
| `CREATE_EMPLOYEE` | Creating a new employee record via `POST /api/employees/` | `EmployeeViewSet.create` |
| `EDIT_EMPLOYEE` | Updating an existing employee via `PUT`/`PATCH /api/employees/{id}/` | `EmployeeViewSet.update`, `partial_update` |
| `DELETE_EMPLOYEE` | Deleting an employee via `DELETE /api/employees/{id}/` | `EmployeeViewSet.destroy` |
| `VIEW_EMPLOYEE` | Listing the employee directory and retrieving individual records | `EmployeeViewSet.list`, `retrieve` |
| `VIEW_SELF` | Reading **only** the caller's own linked employee record | `EmployeeViewSet.me` (`GET /api/employees/me/`) |
| `ASSIGN_PERMISSION` | Listing permission-management options and assigning/revoking permissions for **other** users | `PermissionAdminOptionsView`, `ManagePermissionsView` |

Seed these with:

```bash
python manage.py seed_permissions
```

The command creates the `EMPLOYEE_MGMT` module and the six `Function` rows. It creates no users and grants nothing.

---

## API Overview

All endpoints are mounted under `/api`. Full request/response detail is in [`docs/api.md`](docs/api.md).

| Method | Endpoint | Purpose | Required permission |
|---|---|---|---|
| `POST` | `/api/accounts/login/` | Authenticate and obtain access + refresh tokens | Public |
| `POST` | `/api/accounts/token/refresh/` | Exchange a refresh token for a new access token | Public (refresh token) |
| `GET` | `/api/employees/` | Paginated employee list | `VIEW_EMPLOYEE` |
| `POST` | `/api/employees/` | Create an employee record | `CREATE_EMPLOYEE` |
| `GET` | `/api/employees/{id}/` | Retrieve one employee record | `VIEW_EMPLOYEE` |
| `PUT` / `PATCH` | `/api/employees/{id}/` | Update an employee record | `EDIT_EMPLOYEE` |
| `DELETE` | `/api/employees/{id}/` | Delete an employee record | `DELETE_EMPLOYEE` |
| `GET` | `/api/employees/me/` | Retrieve the caller's own employee record | `VIEW_SELF` |
| `GET` | `/api/permissions/me/` | Return the caller's id, email, and permission codes | Any authenticated user |
| `GET` | `/api/permissions/manage/` | List target users (excluding self) and registered functions | `ASSIGN_PERMISSION` |
| `POST` | `/api/permissions/assign/` | Replace a target user's permission set | `ASSIGN_PERMISSION` |
| `GET` | `/api/schema/` | OpenAPI schema | Any authenticated user |
| `GET` | `/api/docs/` | Swagger UI | Any authenticated user |

**Status codes**

| Status | Meaning |
|---|---|
| `200` | Successful read, update, token refresh, or permission replacement |
| `201` | Employee created |
| `204` | Employee deleted (no response body) |
| `400` | Invalid input, including unknown permission codes |
| `401` | Missing, invalid, or expired authentication credentials |
| `403` | Authenticated but lacking the required permission, or self-assignment attempted |
| `404` | Resource or self-profile not found, or invalid page number |
| `409` | Multiple employee records linked to `/api/employees/me/` |

---

## Authentication Flow

### 1. Login

```http
POST /api/accounts/login/
Content-Type: application/json

{ "email": "user@example.com", "password": "your-password" }
```

A successful response returns a refresh token, an access token, and a profile block containing the user's permission codes:

```json
{
  "refresh": "<refresh-token>",
  "access": "<access-token>",
  "user": {
    "id": 12,
    "email": "user@example.com",
    "first_name": "Example",
    "last_name": "Employee",
    "is_superuser": false,
    "permissions": ["VIEW_EMPLOYEE"]
  }
}
```

Credentials are verified against Django's password hashers. Invalid credentials return `401`.

### 2. Protected API requests

Every subsequent request carries the access token in the `Authorization` header:

```http
Authorization: Bearer <access-token>
```

This header is attached automatically by an Axios request interceptor.

### 3. Refresh-and-retry

Access tokens are configured for a **60-minute** lifetime and refresh tokens for **1 day**. When a protected request returns `401`, an Axios response interceptor:

1. Checks that the request is retryable (not already retried, not the public login/refresh endpoints).
2. Calls `/api/accounts/token/refresh/` with the stored refresh token.
3. Stores the new access token and replays the original request once.
4. De-duplicates concurrent refreshes so simultaneous `401`s share a single refresh call.

### 4. Session expiry

If refresh fails, the interceptor clears both tokens from storage and dispatches an `auth:expired` browser event. `App.jsx` listens for that event and returns the user to the login screen, discarding the authenticated view.

### 5. Logout

Logout clears `access_token` and `refresh_token` from storage and resets the session. There is **no server-side logout or token-revocation endpoint**.

### Token storage — important detail

Tokens are stored in the browser's **`localStorage`**, which is readable by same-origin JavaScript. This means an XSS vulnerability could expose them. The alternative — `HttpOnly` cookies — would require coordinated backend, CSRF, and API contract changes; this implementation deliberately preserves the existing localStorage-based token contract. Deployments with strict token-theft risk should treat this as a known limitation.

---

## Permission Assignment Flow

Only a user holding `ASSIGN_PERMISSION` can manage other users' permissions.

1. **Access the panel.** The dashboard renders the *Manage user permissions* button only when the caller's permission list includes `ASSIGN_PERMISSION`. Hiding the control is a usability measure only — the backend independently rejects unauthorized calls.

2. **Load options.** Opening the panel issues `GET /api/permissions/manage/`. The backend returns:
   - `users` — every user **except the caller**, each with their current permission codes.
   - `functions` — the registered permission catalog read from the `Function` table.

   Because both lists come from the database, adding a new `Function` row makes it available in the UI automatically. No permission code is hardcoded in the frontend.

3. **Select a target and functions.** The user picks a target account from a dropdown. Selecting a target pre-checks that user's current permissions. Function permissions are toggled with checkboxes.

4. **Submit the full set.** Saving sends the complete desired set to `POST /api/permissions/assign/`:

   ```json
   { "user_id": 34, "function_codes": ["VIEW_EMPLOYEE", "VIEW_SELF"] }
   ```

5. **Replacement semantics.** The endpoint performs an atomic **replacement**: any code present before but omitted from the request is revoked. Submitting an empty list revokes every permission for that user. There is no separate revoke endpoint.

### Restrictions actually enforced by the backend

| Restriction | Behavior |
|---|---|
| Caller must hold `ASSIGN_PERMISSION` | Otherwise `403` |
| Codes validated against registered `Function` rows | Unknown codes return `400`; arbitrary `Module`/`Function` records are never created by this endpoint |
| Codes normalized and de-duplicated | Trimmed, upper-cased, duplicates collapsed |
| **Self-targeting rejected** | A request targeting the caller returns `403` |
| Unknown target user | Returns `404` |
| Atomicity | Assignment and audit rows commit in a single transaction |

### Audit behavior

Each code that is newly added produces a `PermissionAudit` row with action `ASSIGNED`; each code that is removed produces one with action `REVOKED`. Both record the acting user (`actor`), the affected user (`target_user`), and the `function`.

---

## Frontend Behavior

### Authentication state

`App.jsx` initializes the session from `localStorage` and swaps between the `Login` and `Dashboard` components. It subscribes to the `auth:expired` event so an unrecoverable session expiry anywhere in the app returns the user to the login screen.

### Obtaining permission information

On mount, the dashboard calls `GET /api/permissions/me/` to load the caller's identity and permission codes into component state. It then conditionally requests the employee directory **only** if the user holds `VIEW_EMPLOYEE`, avoiding a guaranteed `403` for users without it.

### Dynamically reflecting permissions

The UI derives all controls from the returned permission list via a `hasPermission(code)` helper:

| Condition | Rendered UI |
|---|---|
| Holds `VIEW_EMPLOYEE` | Employee directory table with pagination controls |
| Holds `CREATE_EMPLOYEE` | "Add Employee" button and create form |
| Holds `EDIT_EMPLOYEE` | Per-row "Edit" button and edit form |
| Holds `DELETE_EMPLOYEE` | Per-row "Delete" button with confirmation |
| Holds `ASSIGN_PERMISSION` | "Manage user permissions" button and management panel |
| Holds `VIEW_SELF` | The caller's own profile is reachable through `/api/employees/me/` |
| Superuser without function codes | A notice that function permissions still apply; no employee or permission controls are shown |

A superuser is deliberately shown **no** additional employee controls unless those permissions are explicitly assigned to them.

### Error and expiry handling

- API errors surface the backend `detail` message in an alert region; a failed employee fetch does not discard the rest of the dashboard.
- Permission-management errors (for example, an invalid code or a rejected self-assignment) are displayed separately from the success notice.
- A successful save shows the backend confirmation message.
- Session expiry is handled centrally by the Axios interceptor and the `auth:expired` event described above.

---

## Security Design

Only controls that are actually implemented are listed here.

### Backend authorization is authoritative

The frontend hides controls the user cannot use, but this is **not** a security boundary. Every protected endpoint re-checks the caller's permission server-side. Hiding a button while leaving the API open would be a vulnerability, and the implementation does not do that.

### No superuser bypass

`HasFunctionPermission` never inspects `is_superuser`, `is_staff`, or any email address. A superuser holding no `UserFunction` rows receives `403` on every protected endpoint. This is enforced by tests that assert exactly this behavior.

### JWT authentication

Stateless bearer tokens validated by SimpleJWT. Missing, malformed, or expired credentials return `401` before any permission logic executes.

### Password handling

- Passwords are hashed with Django's default secure password hashers; plaintext is never stored or returned.
- Django's password validators (user-attribute similarity, minimum length, common-password, numeric-only) are enforced through `validate_password`.
- Responses never include password material.

### Input validation

Submitted permission codes are validated against the registered `Function` table. Unknown codes produce a `400` and no `Module` or `Function` rows are created from user input.

### Status code discipline

Unauthenticated requests receive `401`; authenticated-but-unauthorized requests receive `403`. The two conditions are distinguished consistently by DRF's authentication and permission classes.

### Transactional permission changes

Permission replacement and its audit rows execute inside `transaction.atomic()`. If any part fails, nothing is persisted, and the bootstrap user-creation flow rolls back user, assignment, and audit together.

### Auditing

Every permission grant and revocation is recorded with the acting user, target user, function, action, and timestamp.

### Bootstrap security controls

The one-time permission-administrator bootstrap command is deliberately hardened and is intended to run only from a trusted server shell. It enforces:

- **Canonical settings verification** — only the project's `config.settings` module is accepted, and its source path is verified, so alternate `DJANGO_SETTINGS_MODULE` / `--settings` selections are rejected.
- **Trusted OS principal mapping** — the operator must map to an active Django account through protected host configuration (Windows registry on Windows, a root-owned JSON mapping file on POSIX). There is no command-line override for identity or paths.
- **Strong identity checks** — Windows resolves the process-token SID and rejects thread impersonation; POSIX uses the effective UID and rejects differing real/effective UID or GID values.
- **Explicit ACL / ownership validation** — lock directory and file ACLs, ownership, and link counts are validated before use; untrusted write ACEs and unsafe owners are rejected.
- **Restricted operator rights** — the operator may own the lock file where explicitly permitted but must not gain delete or ACL-management rights, and directory-level write/delete rights such as `FILE_DELETE_CHILD` are treated as relevant risks.
- **Interactive terminal required** — the command refuses non-interactive execution before any password prompt, and rejects a prompt that would echo the password.
- **Validated locking** — a host-local lock is taken on the same verified handle, with the lock path re-verified immediately before acquisition.
- **One-time semantics** — bootstrap is refused if `ASSIGN_PERMISSION` has ever been granted, even if that assignment was later revoked.

---

## Testing

### Verified results

All figures below were produced by running the commands in this repository.

| Suite | Command | Result |
|---|---|---|
| Bootstrap security | `python -B tests/run_isolated.py tests.test_bootstrap_security` | **19 passed**, 4 platform skips |
| Full backend suite | `python -B tests/run_isolated.py` | **64 passed**, 4 platform skips |
| Frontend | `npm test` | **13 / 13 passed** (2 test files) |
| Lint | `npm run lint` | **Clean**, no errors or warnings |
| Production build | `npm run build` | **Successful** |

### About the 4 platform-specific skips

The four skipped tests are **POSIX-only** security tests that are correctly skipped when the suite runs on Windows:

- two tests asserting real/effective/saved UID and GID handling for POSIX principals;
- two tests verifying `flock` mutual exclusion and guaranteed release on POSIX lock descriptors.

They are guarded by `@unittest.skipUnless(os.name == 'posix', ...)`. This is intentional, not a suppressed failure: the POSIX code paths cannot execute on a Windows host. The Windows equivalents — including the `LockFileEx` contention test — do run and pass.

### Test coverage highlights

- Unauthenticated requests are rejected with `401`; authenticated-but-unauthorized requests receive `403`.
- The OpenAPI schema and Swagger UI require authentication, and remain reachable for a signed-in user.
- Each employee action is denied without its specific permission and allowed with it.
- A superuser **without** explicit function codes is denied on protected endpoints.
- `VIEW_SELF` returns only the caller's record, and returns `404` / `409` for missing / multiple records.
- Function codes are validated as uppercase at the model layer, and `seed_permissions` is idempotent.
- Pagination returns 20 records per page and rejects invalid page numbers.
- Permission assignment validates codes, rejects unknown codes, revokes omitted codes, rejects self-assignment, and writes audit rows.
- Bootstrap refuses an unsafe lock path **before** any operator lookup, database access, or prompt, and re-verifies the lock path immediately before acquisition.
- Bootstrap rolls back user, assignment, and audit together if any step fails.
- Frontend tests cover permission-driven rendering, dynamic loading, pagination navigation, API error display, token refresh/retry, and session expiry.

### Isolated test runner

`backend/tests/run_isolated.py` runs the Django suite against **PostgreSQL**. It pins the canonical `config.settings` module, rejects redirection to arbitrary settings modules, generates an ephemeral per-process `SECRET_KEY`, disables bytecode writes, and asserts that the configured database engine is the project's PostgreSQL engine before running. Django creates a separate throwaway test database (`test_<DB_NAME>`) for the run and drops it afterwards, so your development data in `DB_NAME` is never read or modified by the test suite.

---

## Project Structure

```text
fine-grained-permissions/
├── .env.example                  # Environment variable template (no secrets)
├── .gitignore
├── README.md
│
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   │
│   ├── config/                   # Django project configuration
│   │   ├── settings.py           # Apps, DRF, SimpleJWT, CORS, PostgreSQL
│   │   ├── urls.py               # Root URL conf and API router mounts
│   │   ├── asgi.py
│   │   └── wsgi.py
│   │
│   ├── accounts/                 # Custom user model and JWT login
│   │   ├── models.py             # User (email as USERNAME_FIELD)
│   │   ├── serializers.py        # Login response incl. permission codes
│   │   ├── views.py
│   │   └── urls.py               # login/, token/refresh/
│   │
│   ├── permissions/              # Core of the authorization model
│   │   ├── models.py             # Module, Function, UserFunction
│   │   ├── permissions.py        # HasFunctionPermission (reusable gate)
│   │   ├── serializers.py        # Permission code validation
│   │   ├── views.py              # me/, manage/, assign/
│   │   ├── urls.py
│   │   ├── bootstrap_security.py # OS identity, ACL and lock-path validation
│   │   └── management/commands/
│   │       ├── seed_permissions.py
│   │       ├── set_initial_permission_admin.py
│   │       └── bootstrap_permission_admin.py
│   │
│   ├── employees/                # Employee CRUD with per-action permissions
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py              # action_permissions map + me/ action
│   │   └── urls.py
│   │
│   ├── audit/                    # PermissionAudit history
│   │   └── models.py
│   │
│   └── tests/
│       ├── run_isolated.py       # PostgreSQL-isolated test runner
│       ├── test_accounts.py
│       ├── test_employees.py
│       ├── test_permissions.py
│       └── test_bootstrap_security.py
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js            # Dev server + Vitest config
│   ├── eslint.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx               # Session state, Login/Dashboard switch
│       ├── components/
│       │   ├── Login.jsx
│       │   ├── Dashboard.jsx     # Permission-driven UI + manager panel
│       │   └── Dashboard.test.jsx
│       ├── services/
│       │   ├── api.js            # Axios instance + refresh/retry interceptors
│       │   └── api.test.js
│       └── test/
│           └── setup.js
│
└── docs/
    ├── api.md                    # Detailed endpoint reference
    └── walkthrough.md            # Demonstration script and checklist
```

---

## Setup Instructions

### Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- **PostgreSQL 14 or newer**, running locally. PostgreSQL is required by the assignment and the
  Django settings have no SQLite fallback; `settings.py` raises `ImproperlyConfigured` unless the
  database is configured.

### 1. Backend environment

```bash
cd backend
python -m venv venv
```

Activate it:

```powershell
# Windows PowerShell
.\venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source venv/bin/activate
```

### 2. Install backend dependencies

```bash
pip install -r requirements.txt
```

`requirements.txt` installs `psycopg2-binary`, the PostgreSQL driver Django uses to connect.

### 3. Create the PostgreSQL database and role

`backend/config/settings.py` configures `django.db.backends.postgresql`, so a PostgreSQL database
and a login role must exist before Django will start:

```bash
# using the PostgreSQL client tools
psql -U postgres -c "CREATE ROLE fine_grained WITH LOGIN PASSWORD 'choose-a-strong-password' CREATEDB;"
psql -U postgres -c "CREATE DATABASE fine_grained_permissions OWNER fine_grained;"
```

The role name and database name are up to you — they only have to match the `DB_USER` and `DB_NAME`
values you set in the next step. `CREATEDB` is the privilege that allows the test runner to create
and then drop the throwaway `test_fine_grained_permissions` database.

### 4. Configure environment variables

The project reads a `.env` file from the **repository root** (the parent of `backend/`). Copy the template:

```bash
# from the repository root
copy .env.example .env      # Windows
cp .env.example .env        # macOS / Linux
```

Then fill in the values. The complete set of variables the project reads is:

| Variable | Required | Purpose |
|---|---|---|
| `SECRET_KEY` | Yes | Django signing key. `settings.py` raises `ImproperlyConfigured` when it is missing. |
| `DEBUG` | Yes | `True` for local development, `False` in production. |
| `ALLOWED_HOSTS` | Yes | Comma-separated host list, e.g. `localhost,127.0.0.1`. |
| `DB_NAME` | Yes | PostgreSQL database name, e.g. `fine_grained_permissions`. |
| `DB_USER` | Yes | PostgreSQL role that owns the database. |
| `DB_PASSWORD` | Yes | Password for that PostgreSQL role. |
| `DB_HOST` | Yes | PostgreSQL host, e.g. `localhost`. |
| `DB_PORT` | Yes | PostgreSQL port, e.g. `5432`. |
| `DEMO_ADMIN_EMAIL` | No | Email for `set_initial_permission_admin`. |
| `DEMO_ADMIN_PASSWORD` | No | Password for that account. Never printed or logged. |

A development example:

```
SECRET_KEY=<your-unique-random-value>
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_NAME=fine_grained_permissions
DB_USER=fine_grained
DB_PASSWORD=<the-password-you-chose-for-the-role>
DB_HOST=localhost
DB_PORT=5432
```

Generate one with:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

`settings.py` raises `ImproperlyConfigured` if `SECRET_KEY` is not set, and again if `DB_NAME` or
`DB_USER` is not set. **Never commit your `.env` file** — it is listed in `.gitignore`, and it
contains your `SECRET_KEY`, your PostgreSQL password, and your administrator password.

### 5. Apply database migrations

```bash
cd backend
python manage.py migrate
```

This creates every table in your PostgreSQL database.

### 6. Seed the permission definitions

```bash
python manage.py seed_permissions
```

This creates the `EMPLOYEE_MGMT` module and the six `Function` rows: `CREATE_EMPLOYEE`,
`EDIT_EMPLOYEE`, `DELETE_EMPLOYEE`, `VIEW_EMPLOYEE`, `VIEW_SELF`, and `ASSIGN_PERMISSION`. It is
idempotent, so re-running it never duplicates a code. It does not create users and grants nothing.

### 7. Create the first permission administrator

A permission system needs at least one user holding `ASSIGN_PERMISSION`, but no such permission
exists yet to authorize creating that user through the API. This step breaks that circular
dependency by creating the initial administrator from the server shell.

Read the credentials from the environment by setting these two variables in your project-root
`.env` **before** running the command:

| Variable | Meaning |
|---|---|
| `DEMO_ADMIN_EMAIL` | Email address for the new administrator account. |
| `DEMO_ADMIN_PASSWORD` | Password for that account. It is validated against Django's password validators, hashed immediately, and is never printed, logged, or echoed. |

Choose a strong password — Django's validators will reject weak ones. Do not commit `.env`, and
do not paste real credentials into version control or a screen recording.

```bash
cd backend
python manage.py set_initial_permission_admin
```

What the command does:

- creates a **regular** (non-staff, non-superuser) account using `DEMO_ADMIN_EMAIL` /
  `DEMO_ADMIN_PASSWORD`;
- grants that account **only `ASSIGN_PERMISSION`** and nothing else;
- writes a `PermissionAudit` row so the grant is attributable;
- does all of the above in a single transaction, so a failure leaves nothing behind;
- is **one-time only** — it refuses to run again once `ASSIGN_PERMISSION` has been granted or
  audited, even if that grant was later revoked.

On success it prints only the new user id, for example:

```text
Created initial permission administrator (user id 1) with ASSIGN_PERMISSION.
```

**The new administrator does not receive any other permission.** They can sign in and use the
permission-management panel, but they see no employee list, no add/edit/delete buttons, and no
profile panel. Every additional permission — `VIEW_EMPLOYEE`, `CREATE_EMPLOYEE`, `EDIT_EMPLOYEE`,
`DELETE_EMPLOYEE`, and `VIEW_SELF` — must be **explicitly assigned to that user**, by signing in
as them and using the "Manage user permissions" panel (or `POST /api/permissions/assign/`), before
those controls appear. This is deliberate: privileges are always explicit and never inherited.

A second, hardened bootstrap command also exists — `python manage.py bootstrap_permission_admin` —
for trusted production shells. It requires host-level identity mapping, ACL, and lock-path
configuration, so use `set_initial_permission_admin` for local development, containers, and CI.
See [Bootstrapping the Permission Administrator](#bootstrapping-the-permission-administrator).

### 8. Run the backend

```bash
python manage.py runserver
```

The API is then available at `http://127.0.0.1:8000/`. Interactive Swagger documentation is at
`http://127.0.0.1:8000/api/docs/`. Because the assignment requires authentication on every endpoint
except login, both `/api/docs/` and `/api/schema/` are protected: sign in first, then open the
Swagger page, then use the **Authorize** button in the top-right and paste a valid access token to
make requests from the page. See [API documentation](#api-documentation).

### 9. Run the frontend

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173/`.

The API base URL is read from the `VITE_API_URL` environment variable, with a development fallback
to the default Django address:

```js
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';
```

`npm run dev` therefore works against `http://127.0.0.1:8000` with no extra configuration. To point
the frontend at a different backend, copy `frontend/.env.example` to `frontend/.env` and set
`VITE_API_URL` — Vite reads that file from the `frontend/` directory, not from the project root, and
only exposes variables prefixed with `VITE_`. The backend CORS allowlist in
`backend/config/settings.py` must include the frontend origin.

### 10. Run the tests

```bash
# Backend (runs against PostgreSQL in a throwaway test database)
cd backend
python -B tests/run_isolated.py

# Focused backend suites
python -B tests/run_isolated.py tests.test_bootstrap_security
python -B tests/run_isolated.py tests.test_employees tests.test_permissions
```

```bash
# Frontend
cd frontend
npm test
npm run lint
npm run build
```

---

## Bootstrapping the Permission Administrator

### Why it exists

A permission system needs at least one user holding `ASSIGN_PERMISSION`, but there is no permission yet that could authorize creating that first user through the API — a circular dependency. This command breaks the cycle by creating the initial administrator directly on the server, under a set of conditions stricter than ordinary API access.

### What it does

1. Verifies the canonical Django settings module and its source path.
2. Resolves the current OS principal (Windows SID or POSIX UID) and refuses identity transitions that could regain privilege.
3. Maps that principal to an active Django operator account through protected host configuration.
4. Validates the lock path's ACLs, ownership, and non-writability **before** any database access or prompt, and re-verifies them immediately before locking.
5. Rejects the run if `ASSIGN_PERMISSION` has ever been granted, even if it was later revoked.
6. Prompts interactively for a **new, distinct** account email and a hidden password, validating it against Django's password validators.
7. Creates the user, grants only `ASSIGN_PERMISSION`, and writes an audit row — all in a single transaction.
8. Creates a **regular** account: never a staff or superuser account.

### Security prerequisites

| Platform | Requirement |
|---|---|
| Windows | Operator SID mapping in the `HKLM\SOFTWARE\FineGrainedPermissionSystem\BootstrapOperators` registry key; restricted ACLs on that key and its ancestors; a lock directory under `C:\ProgramData\FineGrainedPermissionSystem\` with restrictive ACLs for the mapped operator, Administrators, and `SYSTEM` |
| POSIX | Root-owned, non-group/world-writable mapping file at `/etc/fine-grained-permissions/bootstrap-operators.json` (for example `{ "uid:1001": 7 }`); a pre-created root-owned, non-writable lock directory `/run/fine-grained-permissions/`; lock file owned by the mapped operator with mode `0600` |

The command accepts no arguments for operator identity, mapping location, or lock path — those are fixed and host-configured. It must be run from an interactive trusted shell.

### Running it

```bash
cd backend
python manage.py bootstrap_permission_admin
```

```text
Initial permission administrator email: new.admin@example.com
New administrator password: ********
Confirm password: ********
Created permission administrator account with user ID 42.
```

After the first successful run, use the UI or `POST /api/permissions/assign/` for all subsequent grants and revocations.

> Reference material only — do not place real credentials, tokens, or host mapping contents in version control or recordings.

---

## Documentation

| Document | Contents |
|---|---|
| [`docs/api.md`](docs/api.md) | Detailed endpoint reference: request bodies, response shapes, status codes, pagination format, and bootstrap prerequisites |
| [`docs/walkthrough.md`](docs/walkthrough.md) | Demonstration script and preflight checklist for presenting the system |
| [`frontend/README.md`](frontend/README.md) | Frontend setup, token storage, and session behavior notes |
| Swagger UI | Served at `/api/docs/` while the backend is running (authentication required — see [API documentation](#api-documentation)) |

### API documentation

The backend generates an OpenAPI 3 schema with `drf-spectacular` and renders it as interactive
Swagger UI:

| Route | Contents |
|---|---|
| `GET /api/docs/` | Swagger UI |
| `GET /api/schema/` | Raw OpenAPI schema (also downloadable as YAML) |

Both routes are **authenticated**, because the assignment requires authentication on every
endpoint except login. `backend/config/urls.py` no longer grants `AllowAny` to them, so they fall
through to `SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"]`, which is `IsAuthenticated`. The generated
schema is unaffected — only access to it is gated.

To browse the API:

1. `POST /api/accounts/login/` to obtain an access token.
2. Open `http://127.0.0.1:8000/api/docs/` while signed in.
3. Click **Authorize**, paste the access token, and save.
4. Requests sent from the Swagger page are then made as that user, and the same per-permission
   authorization rules apply — a 403 here means the user lacks the required function code.

---

## Design Decisions

**Why a reusable permission class instead of inline checks.**
Authorization implemented as scattered `if` statements cannot be reviewed reliably. Centralizing the decision in `HasFunctionPermission` means a single definition governs access, each view only declares its requirement, and audits reduce to reading one file.

**Why permissions are data-driven.**
Roles become a bottleneck as soon as two people need different capabilities. Storing permissions as `Function` rows joined to users through `UserFunction` means capabilities are configuration, not code. Granting or revoking access is a database operation, and new permissions appear in the management UI automatically because the UI reads the catalog from the backend.

**Why backend enforcement is mandatory.**
The frontend is an untrusted client — requests can be replayed with `curl` regardless of what the UI hides. Every authorization decision is therefore re-made on the server, and the frontend's conditional rendering is treated purely as a usability feature.

**Why there is no superuser bypass.**
An implicit bypass hides the real privilege structure and undermines auditing: if superusers implicitly pass every check, the permission records stop describing what the system actually does. Requiring explicit grants keeps the permission set a truthful description of access, and is verified by tests.

**Why permission assignment is restricted and self-targeting is blocked.**
`ASSIGN_PERMISSION` is the most powerful capability in the system because it controls all others. It is gated behind an explicit grant, and self-assignment is rejected so a user cannot escalate their own permissions or silently interfere with their own access — every change must be attributable to a distinct acting user.

**Why permissions are replaced rather than appended.**
An append-only model cannot express revocation, and users accumulate privileges indefinitely. Treating the submitted list as the complete desired state means omitted codes are revoked, which makes the UI's checkbox model a faithful representation of the backend's replacement semantics.

**Why the employee list is paginated.**
An unbounded directory degrades quickly as records grow. DRF's `PageNumberPagination` with a fixed page size of 20 keeps responses small and consistent, and the frontend follows the provided `next`/`previous` links rather than constructing page numbers itself.

**Why the bootstrap command is separate from the API.**
The first `ASSIGN_PERMISSION` grant cannot be authorized through the API because the permission that would authorize it does not yet exist. Isolating that one exceptional operation in a command — under explicit OS-level identity, ACL, locking, and transaction controls — keeps the API surface free of any self-service privilege-escalation path.

---

## Limitations and Repository Notes

- **Tokens are stored in `localStorage`.** Readable by same-origin JavaScript, so an XSS flaw could expose them. Moving to `HttpOnly` cookies would require coordinated backend, CSRF, and API contract changes. Deployments with strict token-theft risk should account for this.
- **There is no server-side logout or token revocation.** Logging out clears client-side storage only; an access token remains valid until it expires (60 minutes).
- **The API base URL falls back to a hardcoded development address** (`http://127.0.0.1:8000/api`) when `VITE_API_URL` is unset. That is a convenience default for `npm run dev`; set `VITE_API_URL` in `frontend/.env` for any other target.
- **The bootstrap lock is host-local.** The POSIX `flock` used for bootstrap locking coordinates callers on a single host only; it does not coordinate multiple hosts sharing one database.
- **CORS origins are development defaults** (`localhost:5173`–`5175`) and `DEBUG` is enabled by the template environment. Production deployment would require hardened settings, a production secret, and a production database — none of which are configured here.
- **No walkthrough video has been recorded.** [`docs/walkthrough.md`](docs/walkthrough.md) is a script and checklist prepared for a demonstration; it is not a recording.

---

## Author

**Mahanandhi Abhiram**

- GitHub: [mahanandhi-abhiram-22](https://github.com/mahanandhi-abhiram-22)
- LinkedIn: [Mahanandhi Abhiram](https://www.linkedin.com/in/m-abhiram/)

---

## License

This project is intended for educational and demonstration purposes. No license file is currently included; add one before distributing or reusing the code under specific terms.
