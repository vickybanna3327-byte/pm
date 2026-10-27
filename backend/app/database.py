import os
import re
import sqlite3
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

DEMO_COLUMNS = [
    ("col-backlog", "Backlog", ["card-1", "card-2"]),
    ("col-discovery", "Discovery", ["card-3"]),
    ("col-progress", "In Progress", ["card-4", "card-5"]),
    ("col-review", "Review", ["card-6"]),
    ("col-done", "Done", ["card-7", "card-8"]),
]

DEMO_CARDS = {
    "card-1": (
        "Align roadmap themes",
        "Draft quarterly themes with impact statements and metrics.",
    ),
    "card-2": (
        "Gather customer signals",
        "Review support tags, sales notes, and churn feedback.",
    ),
    "card-3": (
        "Prototype analytics view",
        "Sketch initial dashboard layout and key drill-downs.",
    ),
    "card-4": (
        "Refine status language",
        "Standardize column labels and tone across the board.",
    ),
    "card-5": (
        "Design card layout",
        "Add hierarchy and spacing for scanning dense lists.",
    ),
    "card-6": (
        "QA micro-interactions",
        "Verify hover, focus, and loading states.",
    ),
    "card-7": (
        "Ship marketing page",
        "Final copy approved and asset pack delivered.",
    ),
    "card-8": (
        "Close onboarding sprint",
        "Document release notes and share internally.",
    ),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL CHECK (kind IN ('personal', 'team')),
    owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS one_personal_workspace_per_owner
    ON workspaces(owner_id) WHERE kind = 'personal';

CREATE TABLE IF NOT EXISTS workspace_members (
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
    joined_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, user_id)
);

CREATE INDEX IF NOT EXISTS workspace_members_user_idx
    ON workspace_members(user_id, workspace_id);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    start_date TEXT,
    due_date TEXT,
    priority TEXT NOT NULL DEFAULT 'medium'
        CHECK (priority IN ('low', 'medium', 'high')),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('planning', 'active', 'on_hold', 'completed', 'archived')),
    color TEXT NOT NULL DEFAULT '#209dd7',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT
);

CREATE INDEX IF NOT EXISTS projects_workspace_updated_idx
    ON projects(workspace_id, updated_at);

CREATE TABLE IF NOT EXISTS project_members (
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('project_manager', 'member', 'viewer')),
    joined_at TEXT NOT NULL,
    PRIMARY KEY (project_id, user_id)
);

CREATE INDEX IF NOT EXISTS project_members_user_idx
    ON project_members(user_id, project_id);

CREATE TABLE IF NOT EXISTS boards (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id TEXT NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS boards_user_id_idx ON boards(user_id);

CREATE TABLE IF NOT EXISTS columns (
    id TEXT PRIMARY KEY,
    board_id TEXT NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    status_key TEXT NOT NULL DEFAULT 'backlog'
        CHECK (status_key IN ('backlog', 'todo', 'in_progress', 'in_review', 'completed')),
    UNIQUE (board_id, position)
);

CREATE TABLE IF NOT EXISTS cards (
    id TEXT PRIMARY KEY,
    column_id TEXT NOT NULL REFERENCES columns(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    details TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    priority TEXT NOT NULL DEFAULT 'medium'
        CHECK (priority IN ('low', 'medium', 'high')),
    assignee_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    reporter_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    start_date TEXT,
    due_date TEXT,
    completed_at TEXT,
    labels_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (column_id, position)
);

CREATE TABLE IF NOT EXISTS task_comments (
    id TEXT PRIMARY KEY,
    card_id TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS task_comments_card_idx
    ON task_comments(card_id, created_at);

CREATE TABLE IF NOT EXISTS task_checklists (
    id TEXT PRIMARY KEY,
    card_id TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    completed_at TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS task_checklists_card_idx
    ON task_checklists(card_id, position);
"""

AUTH_TABLES = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS sessions_user_id_idx ON sessions(user_id);

CREATE TABLE IF NOT EXISTS email_codes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose TEXT NOT NULL CHECK (purpose IN ('verify_email', 'reset_password')),
    code_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    consumed_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (user_id, purpose)
);

CREATE TABLE IF NOT EXISTS reset_challenges (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    consumed_at TEXT
);

CREATE TABLE IF NOT EXISTS rate_limits (
    key TEXT PRIMARY KEY,
    count INTEGER NOT NULL,
    window_started_at TEXT NOT NULL
);
"""

USER_AUTH_COLUMNS = {
    "full_name": "TEXT NOT NULL DEFAULT ''",
    "email": "TEXT",
    "password_hash": "TEXT",
    "role": "TEXT NOT NULL DEFAULT 'member'",
    "email_verified_at": "TEXT",
    "created_at": "TEXT NOT NULL DEFAULT ''",
}

CARD_COLUMNS = {
    "priority": "TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high'))",
    "assignee_id": "TEXT REFERENCES users(id) ON DELETE SET NULL",
    "reporter_id": "TEXT REFERENCES users(id) ON DELETE SET NULL",
    "start_date": "TEXT",
    "due_date": "TEXT",
    "completed_at": "TEXT",
    "labels_json": "TEXT NOT NULL DEFAULT '[]'",
    "created_at": "TEXT NOT NULL DEFAULT ''",
    "updated_at": "TEXT NOT NULL DEFAULT ''",
}


class DatabaseRow(Protocol):
    def __getitem__(self, key: str, /) -> Any: ...


class DatabaseCursor(Protocol):
    rowcount: int

    def fetchone(self) -> DatabaseRow | None: ...

    def fetchall(self) -> list[DatabaseRow]: ...


class DatabaseConnection(Protocol):
    def execute(
        self, statement: str, parameters: Sequence[object] = ()
    ) -> DatabaseCursor: ...

    def executemany(
        self, statement: str, parameters: Iterable[Sequence[object]]
    ) -> DatabaseCursor: ...

    def executescript(self, script: str) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...

    def __enter__(self) -> "DatabaseConnection": ...

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool: ...


def _postgres_statement(statement: str) -> str:
    ignores_conflicts = statement.lstrip().upper().startswith("INSERT OR IGNORE")
    statement = re.sub(
        r"^\s*INSERT\s+OR\s+IGNORE\s+INTO\b",
        "INSERT INTO",
        statement,
        flags=re.IGNORECASE,
    )
    statement = re.sub(
        r"\bCURRENT_TIMESTAMP\b",
        "(CURRENT_TIMESTAMP::text)",
        statement,
        flags=re.IGNORECASE,
    )
    statement = statement.replace("?", "%s")
    if ignores_conflicts:
        statement = statement.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return statement


class PostgresConnection:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def execute(
        self, statement: str, parameters: Sequence[object] = ()
    ) -> Any:
        return self._connection.execute(
            _postgres_statement(statement), tuple(parameters)
        )

    def executemany(
        self, statement: str, parameters: Iterable[Sequence[object]]
    ) -> Any:
        return self._connection.cursor().executemany(
            _postgres_statement(statement), parameters
        )

    def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)

    def begin_immediate(self, lock_key: str) -> None:
        self.execute("SELECT pg_advisory_xact_lock(hashtext(?))", (lock_key,))

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "PostgresConnection":
        return self

    def __exit__(
        self, exc_type: object, exc: object, traceback: object
    ) -> bool:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False


def connect_database(database_path: Path | str) -> DatabaseConnection:
    if isinstance(database_path, str) and database_path.startswith(
        ("postgres://", "postgresql://")
    ):
        import psycopg
        from psycopg.rows import dict_row

        database_url = database_path.replace("postgres://", "postgresql://", 1)
        return PostgresConnection(
            psycopg.connect(database_url, row_factory=dict_row)
        )

    connection = sqlite3.connect(database_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def begin_immediate(connection: DatabaseConnection, lock_key: str) -> None:
    if isinstance(connection, PostgresConnection):
        connection.begin_immediate(lock_key)
    else:
        connection.execute("BEGIN IMMEDIATE")


def database_integrity_errors() -> tuple[type[BaseException], ...]:
    try:
        import psycopg
    except ImportError:
        return (sqlite3.IntegrityError,)
    return (sqlite3.IntegrityError, psycopg.IntegrityError)


def database_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def create_personal_workspace(
    connection: DatabaseConnection,
    user_id: str,
) -> str:
    workspace_id = f"personal-{user_id}"
    user = connection.execute(
        "SELECT username, full_name FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if user is None:
        raise ValueError("Workspace owner does not exist.")
    created_at = database_timestamp()
    name = f"{user['full_name'] or user['username']}'s Workspace"
    connection.execute(
        """
        INSERT OR IGNORE INTO workspaces
            (id, name, kind, owner_id, created_at)
        VALUES (?, ?, 'personal', ?, ?)
        """,
        (workspace_id, name, user_id, created_at),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO workspace_members
            (workspace_id, user_id, role, joined_at)
        VALUES (?, ?, 'owner', ?)
        """,
        (workspace_id, user_id, created_at),
    )
    return workspace_id


def create_project(
    connection: DatabaseConnection,
    workspace_id: str,
    owner_id: str,
    name: str,
    description: str = "",
) -> str:
    project_id = f"project-{uuid4().hex}"
    created_at = database_timestamp()
    connection.execute(
        """
        INSERT INTO projects
            (id, workspace_id, owner_id, name, description, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            workspace_id,
            owner_id,
            name,
            description,
            created_at,
            created_at,
        ),
    )
    return project_id


def seed_default_board_cards(
    connection: DatabaseConnection,
    board_id: str,
    user_id: str,
) -> bool:
    columns = connection.execute(
        "SELECT id, status_key FROM columns WHERE board_id = ? ORDER BY position",
        (board_id,),
    ).fetchall()
    if len(columns) != len(DEMO_COLUMNS):
        return False
    existing_cards = connection.execute(
        """
        SELECT 1 FROM cards
        JOIN columns ON columns.id = cards.column_id
        WHERE columns.board_id = ? LIMIT 1
        """,
        (board_id,),
    ).fetchone()
    if existing_cards is not None:
        return False

    created_at = database_timestamp()
    for column, (_, _, demo_card_ids) in zip(columns, DEMO_COLUMNS):
        for position, demo_card_id in enumerate(demo_card_ids):
            title, details = DEMO_CARDS[demo_card_id]
            completed_at = (
                created_at if column["status_key"] == "completed" else None
            )
            connection.execute(
                """
                INSERT INTO cards
                    (id, column_id, title, details, position, reporter_id,
                        completed_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"card-{uuid4().hex}",
                    column["id"],
                    title,
                    details,
                    position,
                    user_id,
                    completed_at,
                    created_at,
                    created_at,
                ),
            )
    return True


def create_board(
    connection: DatabaseConnection,
    user_id: str,
    project_id: str,
    title: str = "Kanban Studio",
) -> str:
    board_id = f"board-{uuid4().hex}"
    connection.execute(
        "INSERT INTO boards (id, user_id, project_id, title) VALUES (?, ?, ?, ?)",
        (board_id, user_id, project_id, title),
    )
    status_by_column = {
        "col-backlog": "backlog",
        "col-discovery": "todo",
        "col-progress": "in_progress",
        "col-review": "in_review",
        "col-done": "completed",
    }
    for position, (column_id, column_title, _) in enumerate(DEMO_COLUMNS):
        connection.execute(
            "INSERT INTO columns (id, board_id, title, position, status_key) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                f"{column_id}-{uuid4().hex}",
                board_id,
                column_title,
                position,
                status_by_column[column_id],
            ),
        )
    seed_default_board_cards(connection, board_id, user_id)
    return board_id


def backup_before_workspace_migration(
    connection: sqlite3.Connection,
    database_path: Path,
) -> None:
    suffix = ".before-workspace-migration"
    backup_path = database_path.with_name(database_path.name + suffix)
    index = 1
    while backup_path.exists():
        backup_path = database_path.with_name(
            f"{database_path.name}{suffix}-{index}"
        )
        index += 1
    with sqlite3.connect(backup_path) as backup:
        connection.backup(backup)


def migrate_boards_to_projects(connection: sqlite3.Connection) -> None:
    connection.commit()
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.execute("PRAGMA legacy_alter_table = ON")
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            CREATE TABLE boards_new (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                project_id TEXT NOT NULL UNIQUE
                    REFERENCES projects(id) ON DELETE CASCADE,
                title TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO boards_new (id, user_id, project_id, title)
            SELECT boards.id, boards.user_id, projects.id, boards.title
            FROM boards
            JOIN projects ON projects.id = 'project-' || boards.id
            """
        )
        connection.execute("DROP TABLE boards")
        connection.execute("ALTER TABLE boards_new RENAME TO boards")
        connection.execute("CREATE INDEX boards_user_id_idx ON boards(user_id)")
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise sqlite3.IntegrityError("Workspace migration broke foreign keys.")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA legacy_alter_table = OFF")
        connection.execute("PRAGMA foreign_keys = ON")


def initialize_postgres_database(database_url: str) -> None:
    with connect_database(database_url) as connection:
        postgres_schema = SCHEMA.replace(
            "DEFAULT CURRENT_TIMESTAMP",
            "DEFAULT (CURRENT_TIMESTAMP::text)",
        )
        connection.executescript(postgres_schema)
        for column, definition in USER_AUTH_COLUMNS.items():
            connection.execute(
                f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {column} {definition}"
            )
        for column, definition in CARD_COLUMNS.items():
            connection.execute(
                f"ALTER TABLE cards ADD COLUMN IF NOT EXISTS {column} {definition}"
            )
        connection.executescript(AUTH_TABLES)
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS users_username_normalized_idx "
            "ON users(lower(username))"
        )
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS users_email_normalized_idx "
            "ON users(lower(email)) WHERE email IS NOT NULL"
        )

        bootstrap_admin_email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
        if bootstrap_admin_email:
            connection.execute(
                """
                UPDATE users SET role = 'admin'
                WHERE lower(email) = ? AND email_verified_at IS NOT NULL
                    AND NOT EXISTS (SELECT 1 FROM users WHERE role = 'admin')
                """,
                (bootstrap_admin_email,),
            )

        connection.execute(
            "INSERT OR IGNORE INTO users (id, username, created_at) VALUES (?, ?, ?)",
            ("user", "user", database_timestamp()),
        )
        users = connection.execute("SELECT id FROM users").fetchall()
        for user in users:
            create_personal_workspace(connection, user["id"])

        workspace_id = "personal-user"
        default_project = connection.execute(
            "SELECT id FROM projects WHERE workspace_id = ? "
            "ORDER BY created_at LIMIT 1",
            (workspace_id,),
        ).fetchone()
        if default_project is None:
            project_id = create_project(
                connection,
                workspace_id,
                "user",
                "Kanban Studio",
            )
        else:
            project_id = default_project["id"]

        board = connection.execute(
            "SELECT id FROM boards WHERE project_id = ?", (project_id,)
        ).fetchone()
        if board is None:
            board_id = create_board(connection, "user", project_id)
        else:
            board_id = board["id"]
        seed_default_board_cards(connection, board_id, "user")


def initialize_database(database_path: Path | str) -> None:
    if isinstance(database_path, str):
        if database_path.startswith(("postgres://", "postgresql://")):
            initialize_postgres_database(database_path)
            return
        database_path = Path(database_path)

    database_path.parent.mkdir(parents=True, exist_ok=True)
    with connect_database(database_path) as connection:
        existing_tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        existing_board_columns = (
            {
                row["name"]
                for row in connection.execute("PRAGMA table_info(boards)").fetchall()
            }
            if "boards" in existing_tables
            else set()
        )
        needs_workspace_migration = (
            "boards" in existing_tables and "project_id" not in existing_board_columns
        )
        if needs_workspace_migration:
            backup_before_workspace_migration(connection, database_path)

        connection.executescript(SCHEMA)
        existing_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(users)").fetchall()
        }
        for column, definition in USER_AUTH_COLUMNS.items():
            if column not in existing_columns:
                connection.execute(
                    f"ALTER TABLE users ADD COLUMN {column} {definition}"
                )
        existing_column_fields = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(columns)").fetchall()
        }
        if "status_key" not in existing_column_fields:
            connection.execute(
                "ALTER TABLE columns ADD COLUMN status_key TEXT NOT NULL DEFAULT 'backlog' "
                "CHECK (status_key IN ('backlog', 'todo', 'in_progress', 'in_review', 'completed'))"
            )
            connection.execute(
                """
                UPDATE columns SET status_key = CASE lower(trim(title))
                    WHEN 'backlog' THEN 'backlog'
                    WHEN 'discovery' THEN 'todo'
                    WHEN 'to do' THEN 'todo'
                    WHEN 'todo' THEN 'todo'
                    WHEN 'in progress' THEN 'in_progress'
                    WHEN 'in review' THEN 'in_review'
                    WHEN 'review' THEN 'in_review'
                    WHEN 'done' THEN 'completed'
                    WHEN 'completed' THEN 'completed'
                    ELSE 'backlog'
                END
                """
            )
        existing_card_fields = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(cards)").fetchall()
        }
        for column, definition in CARD_COLUMNS.items():
            if column not in existing_card_fields:
                connection.execute(f"ALTER TABLE cards ADD COLUMN {column} {definition}")
        connection.execute(
            "UPDATE cards SET created_at = CURRENT_TIMESTAMP WHERE created_at = ''"
        )
        connection.execute(
            "UPDATE cards SET updated_at = created_at WHERE updated_at = ''"
        )
        connection.execute(
            "UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at = ''"
        )
        connection.executescript(AUTH_TABLES)
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS users_username_normalized_idx "
            "ON users(lower(username))"
        )
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS users_email_normalized_idx "
            "ON users(lower(email)) WHERE email IS NOT NULL"
        )
        bootstrap_admin_email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
        if bootstrap_admin_email:
            connection.execute(
                """
                UPDATE users SET role = 'admin'
                WHERE lower(email) = ? AND email_verified_at IS NOT NULL
                    AND NOT EXISTS (SELECT 1 FROM users WHERE role = 'admin')
                """,
                (bootstrap_admin_email,),
            )
        connection.execute(
            "INSERT OR IGNORE INTO users (id, username, created_at) "
            "VALUES (?, ?, CURRENT_TIMESTAMP)",
            ("user", "user"),
        )

        users = connection.execute("SELECT id FROM users").fetchall()
        for user in users:
            create_personal_workspace(connection, user["id"])

        legacy_boards = (
            connection.execute("SELECT id, user_id, title FROM boards").fetchall()
            if needs_workspace_migration
            else []
        )
        for board in legacy_boards:
            workspace_id = f"personal-{board['user_id']}"
            project_id = f"project-{board['id']}"
            created_at = database_timestamp()
            connection.execute(
                """
                INSERT OR IGNORE INTO projects
                    (id, workspace_id, owner_id, name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    workspace_id,
                    board["user_id"],
                    board["title"],
                    created_at,
                    created_at,
                ),
            )

        if needs_workspace_migration:
            migrate_boards_to_projects(connection)

        default_workspace = f"personal-user"
        default_project = connection.execute(
            "SELECT id FROM projects WHERE workspace_id = ? ORDER BY created_at LIMIT 1",
            (default_workspace,),
        ).fetchone()
        if default_project is None:
            project_id = create_project(
                connection,
                default_workspace,
                "user",
                "Kanban Studio",
            )
        else:
            project_id = default_project["id"]
        connection.execute(
            """
            INSERT OR IGNORE INTO boards (id, user_id, project_id, title)
            VALUES (?, ?, ?, ?)
            """,
            ("board-user", "user", project_id, "Kanban Studio"),
        )
        board_exists = connection.execute(
            "SELECT 1 FROM columns WHERE board_id = ? LIMIT 1",
            ("board-user",),
        ).fetchone()
        if board_exists is None:
            for column_position, (column_id, title, card_ids) in enumerate(
                DEMO_COLUMNS
            ):
                connection.execute(
                    "INSERT INTO columns (id, board_id, title, position, status_key) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        column_id,
                        "board-user",
                        title,
                        column_position,
                        {
                            "col-backlog": "backlog",
                            "col-discovery": "todo",
                            "col-progress": "in_progress",
                            "col-review": "in_review",
                            "col-done": "completed",
                        }[column_id],
                    ),
                )
                for card_position, card_id in enumerate(card_ids):
                    card_title, details = DEMO_CARDS[card_id]
                    connection.execute(
                        "INSERT INTO cards "
                        "(id, column_id, title, details, position, reporter_id, completed_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            card_id,
                            column_id,
                            card_title,
                            details,
                            card_position,
                            "user",
                            database_timestamp()
                            if column_id == "col-done"
                            else None,
                        ),
                    )

        personal_boards = connection.execute(
            """
            SELECT boards.id, boards.user_id
            FROM boards
            JOIN projects ON projects.id = boards.project_id
            JOIN workspaces ON workspaces.id = projects.workspace_id
            WHERE workspaces.kind = 'personal'
                AND projects.id = (
                SELECT first_project.id
                FROM projects AS first_project
                WHERE first_project.workspace_id = workspaces.id
                ORDER BY first_project.created_at, first_project.id
                LIMIT 1
                )
            """
        ).fetchall()
        for board in personal_boards:
            seed_default_board_cards(connection, board["id"], board["user_id"])
