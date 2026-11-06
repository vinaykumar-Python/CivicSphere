# CivicCare AI

CivicCare AI is a FastAPI application that serves its web frontend and API
from the same process. It requires a reachable MySQL database.

## Deploy on Render

1. Push this repository to GitHub.
2. Create a MySQL database with a provider that allows connections from Render.
   Render's blueprint does not create a MySQL database.
3. Before deploying, initialize a new empty database by running
   `python setup_departments.py` from the project root with `DATABASE_URL` set
   to that database. This creates the current tables and seeds departments.
   For an existing database, back it up first, then apply the applicable
   existing migration scripts before deploying:
   `fix_users_updated_at.py`, `migrate_users_department.py`,
   `migrate_complaints_department.py`, `migrate_complaint_coordinates.py`,
   `migrate_sla_columns.py`, `add_emergency_columns.py`,
   `setup_status_history.py`, and `setup_email_verification.py`. Run
   `setup_departments.py` first so the departments table exists. These scripts
   are for upgrading older schemas; `create_all` does not update existing table
   schemas.
4. In Render, choose **New → Blueprint**, connect the GitHub repository, and
   apply the `render.yaml` blueprint. Set `DATABASE_URL` for **both** the web
   service and `civiccare-sla-escalations` cron job to the same MySQL URI in
   `mysql+pymysql://` format. Keep database credentials and other secrets in
   Render's environment settings, never in the repository.
5. Add SMTP settings if email verification is required:
   `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and optionally
   `SMTP_FROM_EMAIL`.
6. Wait for the web service health check at `/api/health/database` to pass.
   This check verifies the database connection. The frontend is served by the
   same service as the API.

The blueprint generates `JWT_SECRET_KEY` and sets `APP_ENV=production`.

The blueprint runs SLA escalation as a separate Render cron job every five
minutes. The cron job uses the `starter` plan and requires its own `DATABASE_URL`
setting pointing to the same database as the web service. Render cron jobs
have a minimum monthly charge. Local development continues to run the
in-process scheduler when `APP_ENV=development`.
