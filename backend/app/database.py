import sqlite3
from pathlib import Path

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

CREATE TABLE IF NOT EXISTS boards (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS columns (
    id TEXT PRIMARY KEY,
    board_id TEXT NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    UNIQUE (board_id, position)
);

CREATE TABLE IF NOT EXISTS cards (
    id TEXT PRIMARY KEY,
    column_id TEXT NOT NULL REFERENCES columns(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    details TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    UNIQUE (column_id, position)
);
"""


def connect_database(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with connect_database(database_path) as connection:
        connection.executescript(SCHEMA)
        connection.execute(
            "INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)",
            ("user", "user"),
        )
        connection.execute(
            "INSERT OR IGNORE INTO boards (id, user_id, title) VALUES (?, ?, ?)",
            ("board-user", "user", "Kanban Studio"),
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
                    "INSERT INTO columns (id, board_id, title, position) "
                    "VALUES (?, ?, ?, ?)",
                    (column_id, "board-user", title, column_position),
                )
                for card_position, card_id in enumerate(card_ids):
                    card_title, details = DEMO_CARDS[card_id]
                    connection.execute(
                        "INSERT INTO cards "
                        "(id, column_id, title, details, position) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            card_id,
                            column_id,
                            card_title,
                            details,
                            card_position,
                        ),
                    )
