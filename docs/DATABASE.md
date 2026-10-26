# Database design proposal

This proposal is for approval before SQLite persistence is implemented. The board API representation is defined in [DB_SCHEMA.json](./DB_SCHEMA.json) and follows the current frontend `BoardData` shape.

## SQLite model

Use four normalized tables:

- `users`: one row per user, with a stable text primary key and a unique username. The MVP has one seeded user named `user`; the hardcoded demo password is not stored in the database.
- `boards`: one row per board, with a text primary key and a `user_id` foreign key. A unique constraint on `user_id` enforces one board per user.
- `columns`: board columns with a text primary key, `board_id`, editable title, and integer `position`. A unique `(board_id, position)` constraint preserves the board's fixed column order.
- `cards`: cards with a text primary key, `column_id`, title, details, and integer `position`. A unique `(column_id, position)` constraint preserves card order within a column.

Enable SQLite foreign-key enforcement for each connection. Deleting a board cascades to its columns and cards; deleting a column cascades to its cards. Do not add a separate `cardIds` table: card ordering is represented by each card's `position`, and the API maps the normalized rows to the `columns[].cardIds` and `cards` JSON shape.

Example DDL for the proposed model:

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE
);

CREATE TABLE boards (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL
);

CREATE TABLE columns (
    id TEXT PRIMARY KEY,
    board_id TEXT NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    UNIQUE (board_id, position)
);

CREATE TABLE cards (
    id TEXT PRIMARY KEY,
    column_id TEXT NOT NULL REFERENCES columns(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    details TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    UNIQUE (column_id, position)
);
```

## Board contract and consistency

The JSON contract deliberately mirrors the existing frontend:

- `columns` is ordered; its array order maps to the SQLite column `position`.
- Each column has `id`, editable `title`, and ordered `cardIds`.
- `cards` is keyed by card ID; each value has `id`, `title`, and `details`.
- Every card must appear exactly once in a column's `cardIds`, and the map key must match the card's `id`. These cross-reference rules are enforced by backend validation because JSON Schema cannot express the full relational consistency requirement.
- Empty strings remain permitted for titles/details at this persistence boundary; input validation can apply the UX rules when API routes are implemented.

User IDs are separate from usernames so usernames can change without re-keying boards. The one-board-per-user constraint is enforced by `boards.user_id`; adding users later requires no schema redesign. Password handling is outside this proposal: the current frontend-only credential gate is a demo, not backend authentication.

## Implemented API contract

The approved schema is implemented by the Part 6 backend. The MVP seeds user ID `user` and its initial board, and exposes:

- `GET /api/users/{user_id}/board`
- `PATCH /api/users/{user_id}/board/columns/{column_id}` with `{ "title": "..." }`
- `POST /api/users/{user_id}/board/columns/{column_id}/cards` with `{ "title": "...", "details": "..." }`
- `DELETE /api/users/{user_id}/board/cards/{card_id}`
- `POST /api/users/{user_id}/board/cards/{card_id}/move` with `{ "column_id": "...", "position": 0 }`; omit `position` to append.

Each successful mutation returns the full board in the JSON contract. Unknown users, columns, and cards return 404; a move position beyond the target column's end returns 422. The SQLite database path is configured through `PM_DATABASE_PATH`, defaulting to `data/pm.db` under the repository root.
