# Frontend

The frontend is a React application built with Vite. It uses Axios to call the Django API and currently stores JWT access and refresh tokens in browser `localStorage`. Protected requests retry once after a 401 by refreshing the access token; if refresh fails, both tokens are cleared and the app returns to login. Logout clears local tokens; there is no server-side logout/revocation endpoint.

Because tokens are readable by same-origin JavaScript, an XSS flaw could expose them. Moving to HttpOnly cookies requires coordinated backend, CSRF, and API contract changes; this implementation preserves the existing token response contract.

Users with explicit `ASSIGN_PERMISSION` see the permission-management panel. It loads non-self target users and registered function codes from `GET /api/permissions/manage/`, then submits the full replacement set to `POST /api/permissions/assign/`.

## Backend API URL

The API base URL is read from the `VITE_API_URL` environment variable, with a development fallback:

```js
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';
```

To point the frontend at a different backend, copy `frontend/.env.example` to `frontend/.env` and
set `VITE_API_URL`. Vite only exposes variables prefixed with `VITE_`, and only from a `.env` file
inside this `frontend/` directory — the project-root `.env` is read by Django, not by Vite. Do not
commit `frontend/.env`.

Note that everything in a Vite `VITE_*` variable is shipped to the browser, so never place a secret
in it.

## Install and Run

From this directory:

```powershell
npm install
npm run dev
```

The Vite development server normally runs at `http://localhost:5173/`. Start Django separately at `http://127.0.0.1:8000/` and ensure its CORS allowlist contains the frontend origin.

## Checks and Production Build

```powershell
npm run lint
npm run build
```

The production bundle is written to `dist/`. Use `npm run preview` to serve the build locally.
