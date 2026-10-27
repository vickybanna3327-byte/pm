import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.database import (
    PostgresConnection,
    _postgres_statement,
    database_integrity_errors,
    connect_database,
    database_timestamp,
    initialize_database,
)
from backend.app.main import create_app


class FakeCursor:
    rowcount = 1


class FakeConnection:
    def __init__(self) -> None:
        self.statements: list[tuple[str, tuple[object, ...]]] = []
        self.commits = 0
        self.rollbacks = 0

    def execute(
        self, statement: str, parameters: tuple[object, ...] = ()
    ) -> FakeCursor:
        self.statements.append((statement, parameters))
        return FakeCursor()

    def cursor(self) -> "FakeConnection":
        return self

    def executemany(
        self,
        statement: str,
        parameters: list[tuple[object, ...]],
    ) -> FakeCursor:
        self.statements.append((statement, tuple(parameters[0])))
        return FakeCursor()

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        pass


def test_postgres_sql_adapts_parameters_and_conflict_handling() -> None:
    statement = _postgres_statement(
        "INSERT OR IGNORE INTO users (id, created_at) VALUES (?, CURRENT_TIMESTAMP)"
    )

    assert statement == (
        "INSERT INTO users (id, created_at) "
        "VALUES (%s, (CURRENT_TIMESTAMP::text)) ON CONFLICT DO NOTHING"
    )


def test_postgres_connection_serializes_write_and_commits() -> None:
    raw_connection = FakeConnection()
    connection = PostgresConnection(raw_connection)

    with connection:
        connection.begin_immediate("rate-limit:key")

    assert raw_connection.statements == [
        ("SELECT pg_advisory_xact_lock(hashtext(%s))", ("rate-limit:key",))
    ]
    assert raw_connection.commits == 1
    assert raw_connection.rollbacks == 0


def test_postgres_connection_rolls_back_on_error() -> None:
    raw_connection = FakeConnection()

    try:
        with PostgresConnection(raw_connection):
            raise RuntimeError("fail transaction")
    except RuntimeError:
        pass

    assert raw_connection.commits == 0
    assert raw_connection.rollbacks == 1


def test_database_integrity_errors_include_postgres() -> None:
    import psycopg
    import sqlite3

    errors = database_integrity_errors()

    assert sqlite3.IntegrityError in errors
    assert psycopg.IntegrityError in errors


def test_postgres_bootstraps_legacy_users_and_supports_project_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("PM_TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip("Set PM_TEST_POSTGRES_URL to run PostgreSQL integration coverage.")

    monkeypatch.setenv("SESSION_SECRET", "test-session-secret-that-is-long-enough")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("FRONTEND_URL", "http://testserver")
    legacy_id = f"legacy-{uuid4().hex}"
    legacy_username = f"legacy{uuid4().hex[:12]}"
    username = f"test{uuid4().hex[:12]}"

    initialize_database(database_url)
    connection = connect_database(database_url)
    with connection:
        connection.execute(
            "INSERT INTO users (id, username, created_at) VALUES (?, ?, ?)",
            (legacy_id, legacy_username, database_timestamp()),
        )
    connection.close()

    try:
        initialize_database(database_url)
        connection = connect_database(database_url)
        legacy_workspace = connection.execute(
            "SELECT id FROM workspaces WHERE owner_id = ?", (legacy_id,)
        ).fetchone()
        legacy_project = connection.execute(
            "SELECT id FROM projects WHERE workspace_id = ?",
            (legacy_workspace["id"],),
        ).fetchone()
        seeded_cards = connection.execute(
            """
            SELECT COUNT(*) AS card_count FROM cards
            JOIN columns ON columns.id = cards.column_id
            JOIN boards ON boards.id = columns.board_id
            WHERE boards.project_id = ?
            """,
            (legacy_project["id"],),
        ).fetchone()["card_count"]
        connection.close()
        assert seeded_cards == 8

        with TestClient(
            create_app(database_url),
            headers={"Origin": "http://testserver"},
        ) as client:
            signup = client.post(
                "/api/auth/register",
                json={
                    "username": username,
                    "password": "SecurePassword123!",
                },
            )
            assert signup.status_code == 201

            workspaces = client.get("/api/workspaces")
            assert workspaces.status_code == 200
            workspace_id = workspaces.json()[0]["id"]
            dashboard = client.get("/api/dashboard")
            assert dashboard.status_code == 200
            assert dashboard.json()["metrics"]["total_projects"] == 1

            project = client.post(
                f"/api/workspaces/{workspace_id}/projects",
                json={"name": "PostgreSQL project"},
            )
            assert project.status_code == 201
            assert project.json()["board_id"]
            board = client.get(f"/api/projects/{project.json()['id']}/board")
            assert board.status_code == 200
            assert len(board.json()["columns"]) == 5
            assert len(board.json()["cards"]) == 8
            card_id = board.json()["columns"][0]["cardIds"][0]
            target_column_id = board.json()["columns"][3]["id"]
            moved = client.post(
                f"/api/projects/{project.json()['id']}/board/cards/{card_id}/move",
                json={"column_id": target_column_id},
            )
            assert moved.status_code == 200
            assert moved.json()["cards"][card_id]["status"] == "in_review"
            assert card_id in moved.json()["columns"][3]["cardIds"]
    finally:
        connection = connect_database(database_url)
        with connection:
            connection.execute(
                "DELETE FROM workspaces WHERE owner_id IN "
                "(SELECT id FROM users WHERE id = ? OR username = ?)",
                (legacy_id, username),
            )
            connection.execute("DELETE FROM users WHERE id = ?", (legacy_id,))
            connection.execute("DELETE FROM users WHERE username = ?", (username,))
        connection.close()
