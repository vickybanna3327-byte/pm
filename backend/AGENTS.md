# Backend AGENTS.md

## Purpose

This directory contains the FastAPI backend for the project management MVP. The backend is intentionally minimal at this stage: it provides a small hello-world app and health endpoints, and it is set up so the app can later serve the static frontend, persist board data in SQLite, and integrate with OpenRouter.

## Current architecture

- `app/main.py` is the FastAPI application entry point.
- The app serves the statically exported Next.js frontend from `frontend/out/` at `/`.
- `/health` returns a JSON success payload for health checks.
- `/api/hello` returns a sample JSON response confirming that the API is responding.

## Local runtime expectations

The backend is designed to run with Uvicorn and should be started from the repository root with a command similar to:

```bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Build the frontend first with `npm run build` from `frontend/`; the static export is required for the root route and frontend assets. The Docker build performs this step automatically. The project uses Python 3.15 and will later support SQLite-backed Kanban persistence and AI endpoints.

## Development conventions

- Keep the backend simple and easy to reason about.
- Prefer clear, minimal endpoints over overly abstract service layers.
- Add tests for new routes and behavior as they are introduced.
- Do not add unnecessary complexity or preemptive abstraction before the current phase requirements are implemented.
