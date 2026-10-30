# DevStride

**Track Your Day. Build Your Skills.** DevStride is a personal productivity and coding-practice app. The React frontend is published on GitHub Pages; a separate FastAPI service and persistent SQL database hold account data.

## Screenshots

Screenshots can be added here after the first deployment.

## Features

- Public landing page and account registration/login.
- Private dashboard with real activity counts and weekly completion chart.
- Activity creation, editing, deletion, categories, priorities, due dates, completion and reopen timestamps, search, and filters.
- 45 coding references (20 arrays, 15 strings, 10 linked lists) with per-user progress and notes support. External URLs are omitted unless verified.
- Personal monthly analytics, profile settings, theme, timezone, password changes, and account deletion.
- The first account on a fresh database becomes founder and can view aggregate registration counts; later accounts cannot access this page.
- Responsive dark and light themes; hash-based routing for GitHub Pages.
- Session cookies are HttpOnly. Every private query is scoped to the authenticated account.

## Technology and architecture

- **Frontend:** React, Vite, Tailwind CSS, React Router, Recharts, Lucide, Axios.
- **Backend:** FastAPI, Pydantic, SQLAlchemy, Alembic, Argon2 password hashing.
- **Database:** SQLite for local development; PostgreSQL for deployment.
- **Hosting:** GitHub Pages serves only the frontend. Deploy `backend/` as a separate Python web service and attach a persistent PostgreSQL database.

```text
frontend/       React application and GitHub Pages build
backend/app/    FastAPI routes, ORM models, security, configuration
backend/migrations/  Alembic schema history
backend/tests/  Authentication and account-isolation tests
.github/workflows/pages.yml  GitHub Pages build and deployment
migration-backup/  Original HTML, server, README, and ignore file
```

## Windows local development

Use Python 3.11 or newer and Node.js 20 or newer. These commands are examples for PowerShell; in Windows CMD, replace `py -m venv .venv` with `py -m venv .venv`, activate with `.venv\Scripts\activate.bat`, and use `set NAME=value` for environment variables.

### 1. Start the backend

```powershell
cd D:\devstride\DevStride\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

For SQLite development, edit `.env` and set:

```dotenv
DATABASE_URL=sqlite:///./devstride.db
SECRET_KEY=replace-this-with-a-long-random-local-secret
FRONTEND_URL=http://localhost:5173
ENVIRONMENT=development
COOKIE_SECURE=false
```

Then migrate and start the API:

```powershell
alembic upgrade head
python -m app
```

The API is at <http://localhost:8000>; interactive API documentation is at <http://localhost:8000/docs>, and the health check is <http://localhost:8000/health>.

### 2. Start the frontend

Open a second PowerShell window:

```powershell
cd D:\devstride\DevStride\frontend
npm install
$env:VITE_API_URL = 'http://localhost:8000'
npm run dev
```

Open <http://localhost:5173>. `VITE_API_URL` is a public API address, not a secret. Never put private keys or database credentials in frontend variables.

### CMD equivalents

```bat
cd /d D:\devstride\DevStride\backend
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements-dev.txt
copy .env.example .env
alembic upgrade head
python -m app
```

In another CMD window:

```bat
cd /d D:\devstride\DevStride\frontend
npm install
set VITE_API_URL=http://localhost:8000
npm run dev
```

## Database and migrations

`DATABASE_URL` selects the database. SQLite is the local default; production should use a managed PostgreSQL database with persistent storage and automated backups. Example PostgreSQL URL:

```text
postgresql+psycopg://username:password@hostname:5432/devstride
```

Apply schema changes before starting the API with `alembic upgrade head`. Inspect changes with `alembic current` and `alembic history`. Take a managed database snapshot before applying production migrations. Keep database credentials and `.env` out of Git. Restore from the provider’s tested backup/export; periodically verify a restore in a separate database.

The API seeds the shared 45-question reference list when it starts. It does not generate problem URLs. User activities, sessions, coding progress, notes, and preferences are stored in database rows associated with an account.

On an empty database, the first registered account becomes the founder and can see the aggregate account counts from **Founder overview**. A migration also promotes the oldest existing account when adding this role to a database with users. Create your founder account before opening public registration; later accounts have no founder access.

## Tests and production build

```powershell
cd D:\devstride\DevStride\backend
python -m pytest
cd ..\frontend
npm test
npm run build
```

## GitHub Pages frontend deployment

The Vite base path is `/DevStride/`; the app uses hash routing so refreshing a route works on Pages. The workflow in `.github/workflows/pages.yml` builds `frontend/` and publishes the artifact on pushes to `main`.

1. In GitHub, open **Vikal0712/DevStride → Settings → Pages** and select **GitHub Actions** as the build and deployment source.
2. Deploy the FastAPI backend and PostgreSQL database separately (instructions below).
3. Set the repository Actions variable `VITE_API_URL` to the backend HTTPS base URL, such as `https://api.example.com` (no trailing slash).
4. Push to `main` or run the Pages workflow manually. Check the Actions run before sharing the site at <https://vikal0712.github.io/DevStride/>.

GitHub Pages does not run Python or provide a database.

## Backend deployment

Create a Python 3.11+ web service rooted at `backend/`, install `requirements-production.txt`, and use this start command:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Set deployment environment variables in the host dashboard (do not commit them):

```dotenv
DATABASE_URL=postgresql+psycopg://...managed-postgres-url...
SECRET_KEY=<at least 32 random characters>
FRONTEND_URL=https://vikal0712.github.io
ENVIRONMENT=production
COOKIE_SECURE=true
```

Run `alembic upgrade head` as the host’s pre-deploy/release command. Configure its health probe to `/health`, enable TLS, restrict database network access to the app, and enable managed backups. Check that the host preserves PostgreSQL data across deploys and that backup restoration works. The configured CORS origin must match the exact browser origin `https://vikal0712.github.io`.

**Browser cookie constraint:** the Pages origin and a separately hosted API are different sites. Production cookies are `Secure; HttpOnly; SameSite=None` and CORS is credentialed, but browsers or privacy settings that block third-party cookies can prevent sessions from persisting across this cross-site boundary. For reliable cookie behavior across browsers, use a custom frontend domain and a same-site API subdomain (for example, `app.example.com` and `api.example.com`) and set `FRONTEND_URL` to the frontend origin. The default Pages URL has no shared custom domain configured in this repository.

## Security and data migration

Passwords use Argon2. Session identifiers are random, stored hashed on the server, and issued in HttpOnly cookies. Unsafe API calls check the allowlisted `Origin` and a custom request header; CORS only allows configured origins. Authentication attempts are throttled per process. Production requires a strong secret, HTTPS frontend, and secure cookies. Put rate limiting at the hosting edge as well when scaling to multiple API instances.

The original app kept tasks and coding completions in browser local storage and had a separate SQLite username/session schema. No user database file is present in the repository. Existing browser-local records cannot be imported by the server because browsers do not expose that data to this migration; the original files are backed up in `migration-backup/`. Existing PBKDF2 account rows are not automatically translated to the new Argon2 schema. Keep any private old database backup secure and arrange an explicit migration if one exists.

Email delivery is not configured, so password recovery email is not available. Account owners can change their password while logged in. Configure an email provider and a verified recovery flow before offering public self-service account recovery.
