import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.database import connect_database, initialize_database

BOARD_URL = "/api/users/user/board"


def test_database_bootstrap_creates_schema_and_seed(
    database_path: Path,
) -> None:
    assert not database_path.exists()
    initialize_database(database_path)

    with connect_database(database_path) as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM boards").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM columns").fetchone()[0] == 5
        assert connection.execute("SELECT COUNT(*) FROM cards").fetchone()[0] == 8


def test_database_bootstrap_is_idempotent(database_path: Path) -> None:
    initialize_database(database_path)
    initialize_database(database_path)

    with connect_database(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM boards").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM columns").fetchone()[0] == 5
        assert connection.execute("SELECT COUNT(*) FROM cards").fetchone()[0] == 8


def test_board_read_matches_frontend_contract(client: TestClient) -> None:
    response = client.get(BOARD_URL)
    assert response.status_code == 200
    board = response.json()
    assert [column["id"] for column in board["columns"]] == [
        "col-backlog",
        "col-discovery",
        "col-progress",
        "col-review",
        "col-done",
    ]
    assert board["columns"][0]["cardIds"] == ["card-1", "card-2"]
    assert board["cards"]["card-1"] == {
        "id": "card-1",
        "title": "Align roadmap themes",
        "details": "Draft quarterly themes with impact statements and metrics.",
    }


def test_missing_user_board_returns_not_found(client: TestClient) -> None:
    response = client.get("/api/users/unknown/board")
    assert response.status_code == 404
    assert response.json()["detail"] == "Board not found."


def test_rename_column_persists(client: TestClient) -> None:
    response = client.patch(
        f"{BOARD_URL}/columns/col-backlog",
        json={"title": "Prioritized"},
    )

    assert response.status_code == 200
    assert response.json()["columns"][0]["title"] == "Prioritized"
    assert client.get(BOARD_URL).json()["columns"][0]["title"] == "Prioritized"


def test_cannot_rename_a_column_on_another_board(client: TestClient) -> None:
    response = client.patch(
        f"{BOARD_URL}/columns/not-a-column",
        json={"title": "Changed"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Column not found."


def test_create_card_appends_to_column(client: TestClient) -> None:
    response = client.post(
        f"{BOARD_URL}/columns/col-backlog/cards",
        json={"title": "New task", "details": "Task details"},
    )

    assert response.status_code == 201
    board = response.json()
    new_card_id = board["columns"][0]["cardIds"][-1]
    assert board["cards"][new_card_id] == {
        "id": new_card_id,
        "title": "New task",
        "details": "Task details",
    }
    assert client.get(BOARD_URL).json() == board


def test_create_card_rejects_unknown_column(client: TestClient) -> None:
    response = client.post(
        f"{BOARD_URL}/columns/missing/cards",
        json={"title": "New task", "details": ""},
    )
    assert response.status_code == 404


def test_delete_card_removes_it_and_compacts_positions(
    client: TestClient, database_path: Path
) -> None:
    response = client.delete(f"{BOARD_URL}/cards/card-1")

    assert response.status_code == 200
    assert response.json()["columns"][0]["cardIds"] == ["card-2"]
    assert "card-1" not in response.json()["cards"]
    with connect_database(database_path) as connection:
        positions = connection.execute(
            "SELECT position FROM cards WHERE column_id = ? ORDER BY position",
            ("col-backlog",),
        ).fetchall()
    assert [row["position"] for row in positions] == [0]


def test_delete_unknown_card_returns_not_found(client: TestClient) -> None:
    response = client.delete(f"{BOARD_URL}/cards/missing")
    assert response.status_code == 404
    assert response.json()["detail"] == "Card not found."


def test_move_card_between_columns_and_persist_order(
    client: TestClient, database_path: Path
) -> None:
    response = client.post(
        f"{BOARD_URL}/cards/card-1/move",
        json={"column_id": "col-review"},
    )

    assert response.status_code == 200
    board = response.json()
    assert board["columns"][0]["cardIds"] == ["card-2"]
    assert board["columns"][3]["cardIds"] == ["card-6", "card-1"]
    assert client.get(BOARD_URL).json() == board
    with connect_database(database_path) as connection:
        moved = connection.execute(
            "SELECT column_id, position FROM cards WHERE id = ?",
            ("card-1",),
        ).fetchone()
    assert (moved["column_id"], moved["position"]) == ("col-review", 1)


def test_move_card_to_specific_position(client: TestClient) -> None:
    response = client.post(
        f"{BOARD_URL}/cards/card-2/move",
        json={"column_id": "col-backlog", "position": 0},
    )
    assert response.status_code == 200
    assert response.json()["columns"][0]["cardIds"] == ["card-2", "card-1"]


def test_move_card_rejects_invalid_position_without_changing_board(
    client: TestClient,
) -> None:
    original = client.get(BOARD_URL).json()
    response = client.post(
        f"{BOARD_URL}/cards/card-1/move",
        json={"column_id": "col-review", "position": 10},
    )

    assert response.status_code == 422
    assert client.get(BOARD_URL).json() == original


def test_move_card_rejects_unknown_card_or_column(client: TestClient) -> None:
    unknown_card = client.post(
        f"{BOARD_URL}/cards/missing/move",
        json={"column_id": "col-review"},
    )
    unknown_column = client.post(
        f"{BOARD_URL}/cards/card-1/move",
        json={"column_id": "missing"},
    )

    assert unknown_card.status_code == 404
    assert unknown_column.status_code == 404


def test_database_enforces_one_board_per_user_and_foreign_keys(
    database_path: Path,
) -> None:
    initialize_database(database_path)

    with connect_database(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO boards (id, user_id, title) VALUES (?, ?, ?)",
                ("another-board", "user", "Second board"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO boards (id, user_id, title) "
                "VALUES (?, ?, ?)",
                ("orphan-board", "missing-user", "Orphan"),
            )
