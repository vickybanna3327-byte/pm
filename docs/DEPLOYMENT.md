# Free hosted test deployment

The app can run as one Docker web service on Render, with Neon PostgreSQL for persistent hosted data. Local development continues to use SQLite when `DATABASE_URL` is unset.

## What to expect

- This is a free-tier test deployment, not a production hosting recommendation.
- Render's free web service spins down after inactivity and can take about a minute to wake. Its local filesystem is temporary, so the app must use Neon rather than SQLite for hosted accounts and boards.
- Neon Free provides a managed PostgreSQL database and suspends compute after inactivity. Check both providers' current usage limits before inviting testers.
- The hosted Neon database starts empty. Existing local accounts and boards remain in the local SQLite file and are not copied.
- Portfolio-demo signup asks only for a username and password, so no email service is needed. There is no password recovery; users who forget a password need to register another username.
- OpenRouter calls require an `OPENROUTER_API_KEY`; without one, the app and board still load, but AI requests cannot be completed.
- Render supplies its public origin through `RENDER_EXTERNAL_URL`; set `FRONTEND_URL` only if you use a custom domain.

## Deploy

1. Push this repository to a Git provider connected to your Render account.
2. Create a Neon project and copy its PostgreSQL connection string. Use the pooled connection string when offered, and keep the password private.
3. In Render, create a Blueprint from the repository and review `render.yaml`.
4. Enter the Neon connection string for `DATABASE_URL`. Render generates `SESSION_SECRET`; leave that value private.
5. Add `OPENROUTER_API_KEY` if AI chat should be available. Set usage limits at OpenRouter because public demo accounts can make AI requests.
6. Deploy and wait for the `/health` check to pass. Open the Render URL and create a username/password account.
7. Test login/logout, creating and moving cards, assistant calls, and a second account's data isolation. Revisit the app after it has gone idle to confirm the free service wakes correctly and the Neon data remains.

The application selects PostgreSQL when `DATABASE_URL` begins with `postgres://` or `postgresql://`. Otherwise, `PM_DATABASE_PATH` selects the local SQLite file.

## Security and operations

- Keep all database, session, SMTP, and OpenRouter values in the hosting provider's secret environment-variable settings. Never commit populated `.env` files.
- Use a unique `SESSION_SECRET` per deployment and keep `AUTH_COOKIE_SECURE=true` on the public HTTPS service.
- Restrict access to the Neon project and rotate credentials if they are exposed.
- The backend creates its schema at startup. Neon must be reachable from the Render service.
- The free web service's sleep behavior and included resource limits can change; consult the providers' current documentation before relying on this setup.

Provider references: [Render free services](https://render.com/docs/free), [Render persistent disks](https://render.com/docs/disks), and [Neon pricing](https://neon.com/pricing).
