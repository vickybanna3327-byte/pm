# Authentication setup

The app owns account credentials and sessions in FastAPI. Passwords are hashed with Argon2id through `pwdlib`; browser sessions are opaque, random values stored only as SHA-256 digests in the configured database and sent in HttpOnly, SameSite=Strict cookies. The static Next.js frontend never stores an authentication token.

The public showcase signup uses a username and password only. There is no email verification or password recovery; if a tester forgets their password, they can register a different username. Do not use this recovery model for an app storing personal or business-critical data.

## Local setup

1. Copy `.env.example` to `.env`.
2. Set `SESSION_SECRET` to a unique random value of at least 32 characters. For example, generate one with `openssl rand -hex 32`.
3. Keep `AUTH_COOKIE_SECURE=false` for local HTTP only. Set it to `true` behind HTTPS in every deployed environment.
4. Start the development services with `docker compose up --build`.
5. Open the app at `http://127.0.0.1:8000`. Normal demo signup uses only a username and password; it does not send email.

For running FastAPI directly on the host, configure `SMTP_HOST=localhost`, `SMTP_PORT=1025`, `SMTP_USE_TLS=false`, and `EMAIL_FROM_ADDRESS` in `.env`, then run Mailpit separately or configure a real SMTP provider. Never use Mailpit or insecure cookies in production.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `SESSION_SECRET` | Required HMAC key for session-related digests; use a random secret of at least 32 characters. |
| `AUTH_COOKIE_SECURE` | Set `true` for HTTPS deployments; local HTTP development uses `false`. |
| `FRONTEND_URL` | Exact public origin used to validate `Origin`; Render deployments fall back to `RENDER_EXTERNAL_URL` if this is unset. |
| `BOOTSTRAP_ADMIN_EMAIL` | Optional one-time promotion of a matching verified account when no administrator exists. Remove after setup. |
| `DATABASE_URL` | Optional PostgreSQL connection URL; when set, it takes precedence over SQLite. |
| `PM_DATABASE_PATH` | Local SQLite database location when `DATABASE_URL` is unset; defaults to `data/pm.db`. |
| `OPENROUTER_API_KEY` | Existing optional AI provider credential. |

## Account and data behavior

- Public signup normalizes and checks the username, hashes the password, creates a `member`, and creates an independent board with the sample template. Email is not requested or used by the public signup screen.
- The legacy seeded `user` and its board are preserved by migration. It has no password or verified email, so it cannot sign in. No new account inherits this board.
- Passwords must be at least 12 characters and use three character classes, or be a passphrase of at least 20 characters. Common weak passwords are rejected.
- There is no public password reset. Testers who forget a password can make a new account with another username; their previous account and board remain stored.
- Changing a password revokes other sessions while retaining the current session.
- Sessions expire after seven days. Logout deletes the server-side session row as well as clearing the cookie.
- Login and registration have IP- and/or identifier-based rate limits. Mutation APIs verify the request origin, and board IDs in URLs must belong to the authenticated user.
- All new users start as `member`. Set `BOOTSTRAP_ADMIN_EMAIL` only for an operator-controlled, verified account; the first matching account is promoted only if there is no administrator. Admin-only APIs enforce the stored role.
- Bootstrap promotion runs at application startup. If the account does not exist or is not verified yet, restart the app after verification; remove `BOOTSTRAP_ADMIN_EMAIL` once promotion is complete.

## Testing

Backend tests cover username-only registration, password hashing, duplicate handling, session creation, per-user board ownership, role checks, and origin validation. Email-code endpoints remain for legacy email-backed accounts and are not part of the public showcase signup flow. Playwright mocks the authentication API; no automated test sends email or uses real credentials.
