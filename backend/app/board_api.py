import sqlite3
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.database import connect_database

router = APIRouter(prefix="/api/users/{user_id}/board", tags=["board"])
DatabaseConnection = Annotated[sqlite3.Connection, Depends(connect_database)]


class ColumnUpdate(BaseModel):
    title: str


class CardCreate(BaseModel):
    title: str
    details: str = ""


class CardMove(BaseModel):
    column_id: str
    position: int | None = Field(default=None, ge=0)


def get_board_row(connection: sqlite3.Connection, user_id: str) -> sqlite3.Row:
    board = connection.execute(
        "SELECT id FROM boards WHERE user_id = ?", (user_id,)
    ).fetchone()
    if board is None:
        raise HTTPException(status_code=404, detail="Board not found.")
    return board


def serialize_board(
    connection: sqlite3.Connection, board_id: str
) -> dict[str, object]:
    column_rows = connection.execute(
        "SELECT id, title FROM columns WHERE board_id = ? ORDER BY position",
        (board_id,),
    ).fetchall()
    card_rows = connection.execute(
        """
        SELECT cards.id, cards.title, cards.details, cards.column_id
        FROM cards
        JOIN columns ON columns.id = cards.column_id
        WHERE columns.board_id = ?
        ORDER BY cards.position
        """,
        (board_id,),
    ).fetchall()

    card_ids_by_column: dict[str, list[str]] = {
        row["id"]: [] for row in column_rows
    }
    cards: dict[str, dict[str, str]] = {}
    for row in card_rows:
        card_ids_by_column[row["column_id"]].append(row["id"])
        cards[row["id"]] = {
            "id": row["id"],
            "title": row["title"],
            "details": row["details"],
        }

    return {
        "columns": [
            {
                "id": row["id"],
                "title": row["title"],
                "cardIds": card_ids_by_column[row["id"]],
            }
            for row in column_rows
        ],
        "cards": cards,
    }


def get_user_column(
    connection: sqlite3.Connection, board_id: str, column_id: str
) -> sqlite3.Row:
    column = connection.execute(
        "SELECT id FROM columns WHERE board_id = ? AND id = ?",
        (board_id, column_id),
    ).fetchone()
    if column is None:
        raise HTTPException(status_code=404, detail="Column not found.")
    return column


def set_card_order(
    connection: sqlite3.Connection, column_id: str, ordered_ids: list[str]
) -> None:
    connection.execute(
        "UPDATE cards SET position = position + 1000000000 WHERE column_id = ?",
        (column_id,),
    )
    connection.executemany(
        "UPDATE cards SET position = ? WHERE id = ? AND column_id = ?",
        [
            (position, card_id, column_id)
            for position, card_id in enumerate(ordered_ids)
        ],
    )


@router.get("")
def read_board(user_id: str, connection: DatabaseConnection) -> dict[str, object]:
    board = get_board_row(connection, user_id)
    return serialize_board(connection, board["id"])


@router.patch("/columns/{column_id}")
def rename_column(
    user_id: str,
    column_id: str,
    update: ColumnUpdate,
    connection: DatabaseConnection,
) -> dict[str, object]:
    board = get_board_row(connection, user_id)
    get_user_column(connection, board["id"], column_id)
    with connection:
        connection.execute(
            "UPDATE columns SET title = ? WHERE id = ?",
            (update.title, column_id),
        )
    return serialize_board(connection, board["id"])


@router.post("/columns/{column_id}/cards", status_code=201)
def create_card(
    user_id: str,
    column_id: str,
    card: CardCreate,
    connection: DatabaseConnection,
) -> dict[str, object]:
    board = get_board_row(connection, user_id)
    get_user_column(connection, board["id"], column_id)
    card_id = f"card-{uuid4().hex}"
    with connection:
        position = connection.execute(
            "SELECT COUNT(*) FROM cards WHERE column_id = ?", (column_id,)
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO cards (id, column_id, title, details, position) "
            "VALUES (?, ?, ?, ?, ?)",
            (card_id, column_id, card.title, card.details, position),
        )
    return serialize_board(connection, board["id"])


@router.delete("/cards/{card_id}")
def delete_card(
    user_id: str, card_id: str, connection: DatabaseConnection
) -> dict[str, object]:
    board = get_board_row(connection, user_id)
    card = connection.execute(
        """
        SELECT cards.column_id
        FROM cards
        JOIN columns ON columns.id = cards.column_id
        WHERE cards.id = ? AND columns.board_id = ?
        """,
        (card_id, board["id"]),
    ).fetchone()
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found.")

    with connection:
        connection.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        remaining_ids = [
            row["id"]
            for row in connection.execute(
                "SELECT id FROM cards WHERE column_id = ? ORDER BY position",
                (card["column_id"],),
            ).fetchall()
        ]
        set_card_order(connection, card["column_id"], remaining_ids)
    return serialize_board(connection, board["id"])


@router.post("/cards/{card_id}/move")
def move_card(
    user_id: str,
    card_id: str,
    move: CardMove,
    connection: DatabaseConnection,
) -> dict[str, object]:
    board = get_board_row(connection, user_id)
    target = get_user_column(connection, board["id"], move.column_id)
    card = connection.execute(
        """
        SELECT cards.column_id
        FROM cards
        JOIN columns ON columns.id = cards.column_id
        WHERE cards.id = ? AND columns.board_id = ?
        """,
        (card_id, board["id"]),
    ).fetchone()
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found.")

    source_column_id = card["column_id"]
    target_column_id = target["id"]
    with connection:
        source_ids = [
            row["id"]
            for row in connection.execute(
                "SELECT id FROM cards WHERE column_id = ? ORDER BY position",
                (source_column_id,),
            ).fetchall()
        ]
        source_ids.remove(card_id)

        if source_column_id == target_column_id:
            target_ids = source_ids
        else:
            target_ids = [
                row["id"]
                for row in connection.execute(
                    "SELECT id FROM cards WHERE column_id = ? ORDER BY position",
                    (target_column_id,),
                ).fetchall()
            ]
            connection.execute(
                "UPDATE cards SET column_id = ?, position = 2000000000 WHERE id = ?",
                (target_column_id, card_id),
            )

        insert_position = (
            len(target_ids) if move.position is None else move.position
        )
        if insert_position > len(target_ids):
            raise HTTPException(
                status_code=422,
                detail="Position is outside the target column.",
            )
        target_ids.insert(insert_position, card_id)

        if source_column_id != target_column_id:
            set_card_order(connection, source_column_id, source_ids)
        set_card_order(connection, target_column_id, target_ids)

    return serialize_board(connection, board["id"])
