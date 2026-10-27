# Database model

The application uses direct SQL without an ORM. Local development uses SQLite through `sqlite3`; hosted deployments can use PostgreSQL through `psycopg`. Startup initializes the selected database and preserves existing SQLite board, column, and card IDs and content.

## Current entities

- `users` stores account identity and authentication fields.
- `workspaces` and `workspace_members` provide personal/team boundaries and workspace roles.
- `projects` belong to one workspace and owner; `project_members` grants project-scoped access.
- `boards` belong to projects and retain the creator in `user_id`. A user can own multiple project boards.
- `columns` and `cards` preserve the existing ordered Kanban representation.

Every existing user receives a private personal workspace. Existing boards are linked to a project in that workspace without changing their IDs or card data. Before the board relationship migration, startup creates a SQLite backup next to the database using the `.before-workspace-migration` suffix.

New users receive a personal workspace, a starter project, and a board preloaded with the sample Kanban template (five status columns and eight example cards). Existing empty personal starter boards are seeded once at startup; boards containing user data are left unchanged. Team workspaces are private until membership is explicitly added. Workspace and project APIs verify membership before returning records; identifiers alone do not grant access.

## Board and task data

Board reads return ordered `columns`, each with `id`, `title`, and ordered `cardIds`, plus a `cards` map keyed by card ID. The backend persists column/card ordering in integer positions. Project boards are available through `/api/projects/{project_id}/board`; the legacy user-board endpoint remains available for the user's first board.

Cards retain the original title/details fields and now include task metadata such as priority, assignee, reporter, labels, dates, status, and timestamps. Assignees must have access to the relevant workspace or project. Comment and checklist tables are present in the schema, but their APIs and UI are not yet implemented.

## Local database

`DATABASE_URL` selects PostgreSQL when it starts with `postgres://` or `postgresql://`. When it is unset, `PM_DATABASE_PATH` selects the SQLite file, which defaults to `data/pm.db` under the repository root. Local Docker Compose mounts `/app/data` as a persistent volume. Hosted Render services use Neon PostgreSQL because Render's free service filesystem is temporary.
