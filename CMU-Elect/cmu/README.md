# CMU-ELECT — React + Django Login & Forgot Password

This version keeps the React + Django architecture but adds a real database-backed authentication flow for **Login** and **Forgot Password** while keeping the existing Dashboard, Voting, and Analytics pages connected to the same Django API.

## What is actually working?

### Login
- Student / Alumni / Faculty role selection.
- Login uses the user's **CMU email + password**.
- Django checks the account and role against the database.
- A Django REST Framework token is returned and stored by React.
- Protected pages redirect back to Login when there is no token.
- Logout invalidates the token.

### Forgot Password
The flow matches the supplied screens:

1. Forgot Password → enter CMU email.
2. Django finds the account and creates a short-lived 6-digit verification code.
3. In local development, the email is printed in the Django terminal and the code is also shown in the React UI as a **Development code**.
4. Verification → enter the code.
5. Django verifies it and issues a short-lived reset token.
6. New Password → enter and confirm the new password.
7. Django changes the user's password and invalidates existing login tokens.
8. Return to Login and sign in with the new password.

For a real deployment, configure Django SMTP so the verification code is actually sent to the CMU email address. Do not expose `dev_code` in production.

## Do I need real CMU data right now?

**No.** You need database records for authentication to work, but you should not put real student/faculty/alumni information into the development project just to test it.

The included `seed_demo` command creates safe fake records:

| Role | CMU Email | Password |
|---|---|---|
| Student | `student@cmu.edu` | `DemoPass123!` |
| Alumni | `alumni@cmu.edu` | `DemoPass123!` |
| Faculty | `faculty@cmu.edu` | `DemoPass123!` |

It also creates demo elections, positions, and candidates so Login → Dashboard → Voting is connected to actual database data.

The project paper describes the intended system as using a verified university voter registry as the baseline for eligible users, so real CMU data can be imported later through an approved process rather than hard-coded into React. See the project's description of the voter database and authentication flow. fileciteturn0file1L57-L61 fileciteturn0file0L16-L19

## Architecture

```text
React (localhost:5173)
        |
        | JSON API
        v
Django REST API (127.0.0.1:8000/api/)
        |
        v
Django ORM
        |
        v
SQLite (development)
```

The existing project specification describes Django/Python as the backend, HTML/CSS/JavaScript for the frontend, MySQL as the intended centralized database, Chart.js for visualization, and session-based authentication. This React version keeps the same separation of responsibilities while using React for the UI and DRF tokens for the local prototype. fileciteturn0file2L94-L107

## Setup on Windows PowerShell

### 1. Backend

Open a terminal:

```powershell
cd path\to\cmu-elect-react-django\backend
py -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py seed_demo
.\venv\Scripts\python.exe manage.py runserver
```

You do **not** need to activate `Activate.ps1`. The commands above directly use `backend\venv` and avoid the PowerShell execution-policy problem.

### 2. Frontend

Open a second terminal:

```powershell
cd path\to\cmu-elect-react-django\frontend
npm.cmd install
npm.cmd run dev
```

Open the Vite URL, normally:

```text
http://localhost:5173/
```

Keep the Django terminal running at the same time.

## Important: database data

The database is not created just by writing models. The normal development flow is:

```text
models.py
   ↓
migrations
   ↓
migrate
   ↓
SQLite database tables
   ↓
seed_demo
   ↓
fake users + elections + candidates
```

So yes, **Login needs user records to authenticate against**, but those records can be fake development records. Later, the approved CMU voter registry can populate the user table.

## Main API endpoints

```text
POST /api/auth/login/
POST /api/auth/logout/
GET  /api/auth/me/

POST /api/auth/forgot-password/
POST /api/auth/resend-code/
POST /api/auth/verify-code/
POST /api/auth/reset-password/

GET  /api/elections/
POST /api/votes/
GET  /api/elections/<id>/results/
```

## Security notes

This is a capstone prototype, not a production election-security deployment. Before a real CMU deployment, add institution-controlled authentication/SSO, HTTPS, environment-based secrets, proper email delivery, rate limiting, audit logging, backups, stronger authorization rules, careful separation/anonymization of voter identity and ballots, and a production database such as MySQL/PostgreSQL.

The project documentation specifically describes separating voter identity from final selections and validating duplicate votes before storing validated ballots. fileciteturn0file3L120-L123

## GitHub: Preserve the Existing Database and Media

This project intentionally keeps `backend/db.sqlite3` and `backend/media/` out of `.gitignore` so they can be committed to GitHub when the complete working system needs to be shared.

If you want GitHub downloads to contain the current database and candidate media, make sure these files are included in the commit:

```text
backend/db.sqlite3
backend/media/
```

After cloning or downloading the repository, these files should remain in the same locations. The database and candidate photos will therefore be preserved without running `seed_demo`.

Do not commit real voter personal information to a public repository. Use a private GitHub repository or sanitized/demo data when appropriate.
