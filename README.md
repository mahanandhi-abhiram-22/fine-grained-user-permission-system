# Fine-Grained User Permission System

A secure Employee Management System built with **React, Django REST Framework, PostgreSQL, and JWT authentication**.

This project allows administrators to assign specific permissions to individual users. Each user can perform only the actions they are authorized to perform.

---

## 1. Project Overview

The Fine-Grained User Permission System is a web application designed to manage employee records with individual, action-based permissions.

Instead of assigning predefined roles such as Admin, Manager, or Employee, the system assigns permissions directly to users.

For example:

* One user can view employee records.
* Another user can create and edit employee records.
* A user with permission to view their own profile can access only their own employee information.

The backend independently checks permissions before allowing protected operations.

## 2. Project Objectives

* Implement secure user authentication.
* Manage employee records through REST APIs.
* Assign and revoke permissions for individual users.
* Restrict access to unauthorized operations.
* Display interface elements based on user permissions.
* Maintain a structured and scalable application architecture.

## 3. Technology Stack

| Technology            | Purpose                                 |
| --------------------- | --------------------------------------- |
| Python                | Backend programming language            |
| Django                | Backend web framework                   |
| Django REST Framework | REST API development                    |
| React                 | Frontend user interface                 |
| JavaScript            | Frontend programming language           |
| PostgreSQL            | Relational database                     |
| JWT                   | Token-based authentication              |
| HTML5                 | Web page structure                      |
| CSS3                  | Styling and responsive layouts          |
| Git & GitHub          | Version control and source code hosting |

## 4. Core Features

### Authentication

* Login using email and password.
* Secure password hashing.
* JWT-based authentication.
* Protected API endpoints.
* Unauthorized requests return HTTP 401.

### Employee Management

* Create employee records.
* View employee records.
* Update employee information.
* Delete employee records.
* View the logged-in user's own employee profile.
* Paginated employee listing.

### Permission Management

* Assign permissions directly to users.
* Revoke permissions from users.
* Restrict permission assignment to authorized users.
* Enforce permissions on protected backend endpoints.
* Show or hide frontend features based on permissions.

## 5. Permission System

The application uses six individual permission codes.

| Permission Code     | Description                                   |
| ------------------- | --------------------------------------------- |
| `CREATE_EMPLOYEE`   | Create employee records                       |
| `EDIT_EMPLOYEE`     | Update employee records                       |
| `DELETE_EMPLOYEE`   | Delete employee records                       |
| `VIEW_EMPLOYEE`     | View the employee directory                   |
| `VIEW_SELF`         | View the logged-in user's own employee record |
| `ASSIGN_PERMISSION` | Assign or revoke user permissions             |

### How permissions work

1. A user logs in with valid credentials.
2. The backend authenticates the user and issues a JWT.
3. The frontend retrieves the user's permission codes.
4. The frontend displays features based on those permissions.
5. The backend checks the user's permission for each protected request.
6. Requests without the required permission are rejected.

**Important:** Hiding a button in React does not provide security by itself. The backend must enforce authorization for every protected operation.

## 6. System Architecture

```text
                    User
                     |
                     v
              React Frontend
                     |
              JWT Authentication
                     |
                     v
         Django REST Framework
                     |
           Permission Validation
                     |
                     v
             Django Backend
                     |
                     v
                PostgreSQL
```

### Architecture components

* **Frontend:** React handles login, employee screens, and permission-aware UI.
* **API Layer:** Django REST Framework handles HTTP requests and responses.
* **Authentication:** JWT identifies authenticated users.
* **Authorization:** Reusable permission checks validate access to protected operations.
* **Database:** PostgreSQL stores users, employees, permissions, and user-permission relationships.

## 7. API Endpoints

The following endpoints describe the intended API structure.

### Authentication

| Method | Endpoint           | Purpose                                             |
| ------ | ------------------ | --------------------------------------------------- |
| POST   | `/api/auth/login/` | Authenticate a user                                 |
| GET    | `/api/auth/me/`    | Retrieve the current user's details and permissions |

### Employee Management

| Method    | Endpoint               | Required Permission |
| --------- | ---------------------- | ------------------- |
| GET       | `/api/employees/`      | `VIEW_EMPLOYEE`     |
| POST      | `/api/employees/`      | `CREATE_EMPLOYEE`   |
| GET       | `/api/employees/me/`   | `VIEW_SELF`         |
| PUT/PATCH | `/api/employees/{id}/` | `EDIT_EMPLOYEE`     |
| DELETE    | `/api/employees/{id}/` | `DELETE_EMPLOYEE`   |

### Permission Management

| Method | Endpoint                   | Required Permission  |
| ------ | -------------------------- | -------------------- |
| GET    | `/api/permissions/`        | Authenticated access |
| POST   | `/api/permissions/assign/` | `ASSIGN_PERMISSION`  |
| POST   | `/api/permissions/revoke/` | `ASSIGN_PERMISSION`  |

*Note: Confirm the exact endpoint paths and request formats against the implemented backend.*

## 8. Project Structure

```text
fine-grained-permissions/
│
├── backend/
│   ├── accounts/
│   ├── employees/
│   ├── permissions/
│   ├── tests/
│   ├── manage.py
│   └── requirements.txt
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   ├── services/
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
│
├── docs/
│   └── api.md
│
├── .gitignore
└── README.md
```

## 9. Installation and Setup

### Prerequisites

Install the following tools:

* Python 3.10 or a compatible version supported by the project dependencies.
* Node.js and npm.
* PostgreSQL.
* Git.

### Step 1: Clone the repository

```bash
git clone https://github.com/mahanandhi-abhiram-22/fine-grained-user-permission-system.git

cd fine-grained-user-permission-system
```

### Step 2: Set up the backend

Open a terminal in the project root.

```powershell
cd backend

python -m venv venv

.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

If PowerShell blocks virtual environment activation, use Command Prompt or adjust your local PowerShell execution policy appropriately.

### Step 3: Configure environment variables

Create a `.env` file inside the backend directory.

Example:

```env
SECRET_KEY=replace-with-a-secure-secret-key
DEBUG=True

DB_NAME=employee_permissions
DB_USER=postgres
DB_PASSWORD=your_database_password
DB_HOST=localhost
DB_PORT=5432
```

Use the variable names expected by the backend settings. Do not commit real secrets to GitHub.

### Step 4: Create the PostgreSQL database

Create a database named:

```text
employee_permissions
```

Make sure the database credentials match your backend environment configuration.

### Step 5: Apply database migrations

```powershell
python manage.py makemigrations

python manage.py migrate
```

### Step 6: Seed initial permissions

Run the project's permission-seeding command if available.

For example:

```powershell
python manage.py seed_permissions
```

*The exact command depends on the management command implemented in the project.*

### Step 7: Start the backend server

```powershell
python manage.py runserver
```

Backend development server:

```text
http://127.0.0.1:8000/
```

### Step 8: Set up the frontend

Open a new terminal.

```powershell
cd frontend

npm install

npm run dev
```

Frontend development server:

```text
http://localhost:5173/
```

Open the frontend URL in your browser.

## 10. Testing

The backend includes tests for authentication, employee operations, and permission-related behavior.

Run the Django test suite:

```powershell
cd backend

python manage.py test
```

### Important test scenarios

* Unauthenticated requests are rejected.
* Users without the required permission cannot perform protected operations.
* Users with the correct permission can perform authorized operations.
* Users can access their own employee profile when authorized.
* Permission assignment and revocation are restricted to authorized users.

## 11. Security Considerations

* Passwords must be stored using secure password hashing.
* JWT tokens must have appropriate expiration settings.
* Sensitive environment variables must not be committed.
* Backend authorization must be enforced independently of the frontend.
* Employee information should be limited to authorized users.
* Database access should use secure credentials.
* Permission checks should be reusable and consistently applied.

## 12. Future Improvements

* Audit logs for permission changes and employee operations.
* Permission caching for improved performance.
* Enhanced automated test coverage.
* Deployment with production-grade configuration.
* Improved monitoring and error reporting.
* More detailed API documentation.

## 13. Documentation

API documentation:

[`docs/api.md`](docs/api.md)

## 14. Author

**Mahanandhi Abhiram**

* GitHub: [mahanandhi-abhiram-22](https://github.com/mahanandhi-abhiram-22)
* LinkedIn: [Mahanandhi Abhiram](https://www.linkedin.com/in/m-abhiram/)

---

## 15. License

This project is intended for educational and demonstration purposes. Add a license file if you plan to distribute or reuse the code under specific terms.
