# CivicCare AI

CivicCare AI is a FastAPI application that serves its web frontend and API
from the same process. It requires a reachable MySQL database.

## Deploy on Render

1. Push this repository to GitHub.
2. In Render, choose **New → Blueprint**, connect the GitHub repository, and
   apply the `render.yaml` blueprint.
3. Create a MySQL database with a provider that allows connections from
   Render. Render's blueprint does not create a MySQL database.
4. In the Render service's environment settings, set `DATABASE_URL` to the
   provider's MySQL connection URI. It must use the `mysql+pymysql://` driver
   format. Keep database credentials and other secrets in Render's environment
   settings, never in the repository.
5. On a new, empty database, run `python setup_departments.py` once from the
   project root after setting `DATABASE_URL`. This creates the current tables
   and seeds the departments. For an existing database, apply the required
   migration scripts before deploying; `create_all` does not update existing
   table schemas.
6. Wait for the service health check at `/api/health` to pass. The frontend is
   served by the same service as the API.

The blueprint generates `JWT_SECRET_KEY` and sets `APP_ENV=production`.
Email verification requires SMTP settings (`SMTP_HOST`, `SMTP_PORT`,
`SMTP_USERNAME`, `SMTP_PASSWORD`, and optionally `SMTP_FROM_EMAIL`) in the
Render service environment.

The SLA scheduler is currently only started when `APP_ENV=development`, so
scheduled SLA escalations will not run in this production configuration.
