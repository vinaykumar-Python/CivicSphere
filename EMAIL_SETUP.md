# Email verification setup

Citizen registration now requires a six-digit email code before sign-in. Codes
expire after 10 minutes and are limited to five guesses. A new code can be
requested once per minute.

## Configure Gmail SMTP

1. Enable 2-Step Verification for the Gmail account used to send CivicCare
   messages.
2. Create a Google App Password for the application. Do not use the account's
   normal Gmail password.
3. Add these values to the local `.env` file or the deployment's secret
   environment configuration:

   ```dotenv
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your-sender@gmail.com
   SMTP_PASSWORD=your-16-character-app-password
   SMTP_FROM_EMAIL=your-sender@gmail.com
   ```

4. Restart the application so it loads the new settings.

Keep SMTP credentials private and never commit them or paste them into chat.
The verification code is not stored in plain text.

## Create the database table

Development startup creates the new table automatically. For an existing
deployment, run this once using the deployment's configured `DATABASE_URL`:

```powershell
.\.venv\Scripts\python.exe setup_email_verification.py
```

The script only creates `email_verifications`; it does not modify existing
users or tables. Existing accounts continue to work without re-verification.
