# Backend AGENTS.md

## Purpose

This directory contains the FastAPI backend for the project management MVP. It serves the static frontend, exposes health and sample routes, and persists a per-user Kanban board in SQLite.

## Current architecture

- `app/main.py` is the FastAPI application entry point.
- The app serves the statically exported Next.js frontend from `frontend/out/` at `/`.
- `/health` returns a JSON success payload for health checks.
- `/api/hello` returns a sample JSON response confirming that the API is responding.
- `app/database.py` creates and seeds the SQLite schema on startup.
- `app/board_api.py` implements board read, column rename, card create/edit/delete, and card move routes.
- `app/ai_board_api.py` provides board-aware chat with validated structured card/column mutations applied atomically.
- `app/openrouter_api.py` makes a minimal OpenRouter chat-completion request for connectivity verification.
- The SQLite path is configured with `PM_DATABASE_PATH`; by default it is `data/pm.db` at the repository root.
- `OPENROUTER_API_KEY` is loaded from the repository-root `.env` file when present or from the process environment. It is never returned by an API route.
- The MVP seeds user ID `user` with one board. This is data initialization, not authentication; the frontend demo login does not protect backend routes.

## Local runtime expectations

The backend is designed to run with Uvicorn and should be started from the repository root with a command similar to:

```bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Build the frontend first with `npm run build` from `frontend/`; the static export is required for the root route and frontend assets. The Docker build performs this step automatically. The project uses Python 3.15 and will later add frontend API integration and AI endpoints.

## Board API

- `GET /api/users/{user_id}/board`
- `PATCH /api/users/{user_id}/board/columns/{column_id}`
- `POST /api/users/{user_id}/board/columns/{column_id}/cards`
- `PATCH /api/users/{user_id}/board/cards/{card_id}`
- `DELETE /api/users/{user_id}/board/cards/{card_id}`
- `POST /api/users/{user_id}/board/cards/{card_id}/move`

Mutation responses return the complete board in the frontend `BoardData` shape.

## OpenRouter connectivity

- `POST /api/ai/connectivity` sends a fixed `2 + 2` prompt to `openai/gpt-oss-120b`.
- Missing configuration returns HTTP 503; invalid credentials, provider failures, network errors, and malformed responses return HTTP 502 with a safe explanation.
- The request has a 30-second timeout.
- Unit/API tests mock the provider. To make a real provider request, set `RUN_OPENROUTER_INTEGRATION=1` and `OPENROUTER_API_KEY`, then run `python -m pytest backend/tests/test_openrouter_integration.py` from the repository root. Do not commit `.env`.
- `POST /api/users/{user_id}/board/chat` accepts `{"question": "...", "history": [{"role": "user|assistant", "content": "..."}]}`; history is optional.
- The backend adds the current SQLite board to the model context and returns `{"model": "...", "reply": "...", "board": {...}, "changed": true|false}`.
- Model `actions` may be empty, or contain `create_card`, `update_card`, `move_card`, and `rename_column` operations. The full action list is validated before being applied in one SQLite transaction; invalid model output or board references do not persist changes.

## Development conventions

- Keep the backend simple and easy to reason about.
- Prefer clear, minimal endpoints over overly abstract service layers.
- Add tests for new routes and behavior as they are introduced.
- Use a temporary SQLite file for backend tests; do not use the default local database in tests.
- Do not add unnecessary complexity or preemptive abstraction before the current phase requirements are implemented.
