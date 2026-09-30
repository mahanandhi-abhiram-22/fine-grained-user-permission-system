# Demonstration Walkthrough

This is a script and checklist, not a recorded video. Use a disposable local checkout/database for demonstrations. Do not record passwords, tokens, private keys, or production registry/mapping details.

## Preflight

- Review `README.md` setup instructions and confirm Django is using PostgreSQL.
- Set a private local `SECRET_KEY` in the project-root `.env`; keep that file out of recordings and version control.
- In a disposable environment, run migrations and `python manage.py seed_permissions`.
- Create the initial permission administrator with `python manage.py set_initial_permission_admin` (it reads `DEMO_ADMIN_EMAIL` / `DEMO_ADMIN_PASSWORD` from the project-root `.env`). Show that the new account is granted only `ASSIGN_PERMISSION` and receives no employee permissions; do not display the credentials.
- For a hardened trusted-shell demonstration, also provision the OS-principal mapping and lock path using the platform prerequisites in the README/API reference, then run `python manage.py bootstrap_permission_admin` interactively. Show that it creates a separate regular account with only `ASSIGN_PERMISSION`; do not show typed credentials.
- Create disposable regular users and employee records before recording. Never use actual project or production users.
- Start Django and Vite in separate terminals. Verify the configured API URL and CORS origin.

## Demo Script

1. **Architecture:** identify the React/Vite client, Django REST API, PostgreSQL database, and the direct user-to-function mapping.
2. **Login:** sign in with a disposable user. Explain access/refresh tokens and note they are currently stored in `localStorage`.
3. **Permission model:** show the six seeded codes and the `UserFunction` link; explain that function definitions and user assignments are separate.
4. **Employee authorization:** demonstrate list/create/update/delete controls only when the corresponding codes are assigned. Explain that the backend repeats every check, including for superusers.
5. **Self-profile:** sign in as a user holding `VIEW_SELF` and show the "My Profile" panel calling `/api/employees/me/`; show that it returns only the caller's record, and that missing/multiple records render 404/409 messages. Then show a user without `VIEW_SELF` does not see the control at all, and that calling the endpoint directly still returns 403.
6. **Permission administration:** use the bootstrapped permission administrator to assign a permission to a different disposable user. Show that omitted codes are revoked and the change is audited. Do not demonstrate against the operator's own account; self-targeting is rejected.
7. **Pagination:** show the employee count, page size 20, and previous/next navigation following the API links.
8. **Unauthorized behavior:** show a request without a function code receiving 403 and an unauthenticated request receiving 401.
9. **Tests:** run `python -B tests/run_isolated.py` from `backend`; describe that it runs against PostgreSQL using a separate throwaway test database, which is dropped afterwards, and never touches your development data.
10. **Bootstrap safeguards:** explain that bootstrap is trusted-shell-only, rejects alternate Django settings, verifies OS identity/mapping/ACLs, requires an interactive hidden password prompt, locks host-locally, and refuses repeat grants even after revocation.
11. **API documentation:** open `/api/docs/` while signed in, use **Authorize** to paste an access token, and show a documented request. Note that the docs and schema routes require authentication like every other endpoint except login.

## Closing Checklist

- Do not display the `.env`, tokens, passwords, or private OS mapping contents.
- Confirm the visible account and employee data are disposable.
- State any unverified platform or assignment requirements; do not claim a video exists until it has actually been recorded.