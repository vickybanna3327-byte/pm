import json
from datetime import date
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.auth_api import AuthenticatedUser, check_origin
from backend.app.database import (
    DatabaseConnection as DatabaseSession,
    DatabaseRow,
    connect_database,
)

router = APIRouter(prefix="/api/users/{user_id}/board", tags=["board"])
project_router = APIRouter(prefix="/api/projects/{project_id}/board", tags=["board"])
DatabaseConnection = Annotated[DatabaseSession, Depends(connect_database)]


class ColumnUpdate(BaseModel):
    title: str


class CardCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    details: str = Field(default="", max_length=4000)
    priority: Literal["low", "medium", "high"] = "medium"
    assignee_id: str | None = None
    start_date: date | None = None
    due_date: date | None = None
    labels: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Title must not be blank.")
        return normalized

    @field_validator("labels")
    @classmethod
    def validate_labels(cls, labels: list[str]) -> list[str]:
        normalized = [label.strip() for label in labels]
        if any(not label or len(label) > 32 for label in normalized):
            raise ValueError("Labels must contain 1-32 characters.")
        return normalized

    @model_validator(mode="after")
    def validate_dates(self) -> "CardCreate":
        if self.start_date and self.due_date and self.due_date < self.start_date:
            raise ValueError("Due date must be on or after the start date.")
        return self

class CardUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    details: str | None = Field(default=None, max_length=4000)
    priority: Literal["low", "medium", "high"] | None = None
    assignee_id: str | None = None
    start_date: date | None = None
    due_date: date | None = None
    labels: list[str] | None = Field(default=None, max_length=20)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Title must not be blank.")
        return normalized

    @field_validator("labels")
    @classmethod
    def validate_labels(cls, labels: list[str] | None) -> list[str] | None:
        if labels is None:
            return None
        normalized = [label.strip() for label in labels]
        if any(not label or len(label) > 32 for label in normalized):
            raise ValueError("Labels must contain 1-32 characters.")
        return normalized

    @model_validator(mode="after")
    def validate_update(self) -> "CardUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one task field must be provided.")
        if self.start_date and self.due_date and self.due_date < self.start_date:
            raise ValueError("Due date must be on or after the start date.")
        return self


class CardMove(BaseModel):
    column_id: str
    position: int | None = Field(default=None, ge=0)


def get_board_row(connection: DatabaseSession, user_id: str) -> DatabaseRow:
    board = connection.execute(
        """
        SELECT boards.id FROM boards
        JOIN projects ON projects.id = boards.project_id
        WHERE boards.user_id = ? AND projects.status != 'archived'
        ORDER BY projects.created_at, boards.id LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    if board is None:
        raise HTTPException(status_code=404, detail="Board not found.")
    return board


def authorized_user_id(user_id: str, current_user: dict[str, str]) -> str:
    if user_id not in {"me", current_user["id"]}:
        raise HTTPException(status_code=404, detail="Board not found.")
    return current_user["id"]


def resolve_board_owner(
    user_id: str,
    current_user: AuthenticatedUser,
) -> str:
    return authorized_user_id(user_id, current_user)


BoardOwner = Annotated[str, Depends(resolve_board_owner)]
OriginCheck = Annotated[None, Depends(check_origin)]


def serialize_board(
    connection: DatabaseSession, board_id: str
) -> dict[str, object]:
    column_rows = connection.execute(
        "SELECT id, title FROM columns WHERE board_id = ? ORDER BY position",
        (board_id,),
    ).fetchall()
    card_rows = connection.execute(
        """
        SELECT cards.id, cards.title, cards.details, cards.column_id,
            cards.priority, cards.assignee_id, cards.reporter_id,
            cards.start_date, cards.due_date, cards.completed_at, cards.labels_json,
            cards.created_at, cards.updated_at, columns.status_key
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
    cards: dict[str, dict[str, object]] = {}
    for row in card_rows:
        card_ids_by_column[row["column_id"]].append(row["id"])
        cards[row["id"]] = {
            "id": row["id"],
            "title": row["title"],
            "details": row["details"],
            "priority": row["priority"],
            "assignee_id": row["assignee_id"],
            "reporter_id": row["reporter_id"],
            "start_date": row["start_date"],
            "due_date": row["due_date"],
            "completed_at": row["completed_at"],
            "labels": json.loads(row["labels_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "status": row["status_key"],
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
    connection: DatabaseSession, board_id: str, column_id: str
) -> DatabaseRow:
    column = connection.execute(
        "SELECT id FROM columns WHERE board_id = ? AND id = ?",
        (board_id, column_id),
    ).fetchone()
    if column is None:
        raise HTTPException(status_code=404, detail="Column not found.")
    return column


def validate_assignee(
    connection: DatabaseSession,
    board_id: str,
    assignee_id: str | None,
) -> None:
    if assignee_id is None:
        return
    member = connection.execute(
        """
        SELECT 1
        FROM boards
        JOIN projects ON projects.id = boards.project_id
        LEFT JOIN workspace_members
            ON workspace_members.workspace_id = projects.workspace_id
            AND workspace_members.user_id = ?
        LEFT JOIN project_members
            ON project_members.project_id = projects.id
            AND project_members.user_id = ?
        WHERE boards.id = ?
            AND (workspace_members.user_id IS NOT NULL
                OR project_members.user_id IS NOT NULL)
        """,
        (assignee_id, assignee_id, board_id),
    ).fetchone()
    if member is None:
        raise HTTPException(
            status_code=422,
            detail="Assignee must belong to this workspace or project.",
        )


def set_card_order(
    connection: DatabaseSession, column_id: str, ordered_ids: list[str]
) -> None:
    connection.execute(
        "UPDATE cards SET position = position + 1000000000 "
        "WHERE column_id = ? AND position < 1000000000",
        (column_id,),
    )
    connection.executemany(
        "UPDATE cards SET position = ? WHERE id = ? AND column_id = ?",
        [
            (position, card_id, column_id)
            for position, card_id in enumerate(ordered_ids)
        ],
    )


def get_project_board_row(
    connection: DatabaseSession,
    project_id: str,
    current_user: dict[str, str],
    *,
    write: bool = False,
) -> DatabaseRow:
    project = connection.execute(
        """
        SELECT projects.id, projects.owner_id, projects.status,
            workspace_members.role AS workspace_role,
            project_members.role AS project_role
        FROM projects
        LEFT JOIN workspace_members
            ON workspace_members.workspace_id = projects.workspace_id
            AND workspace_members.user_id = ?
        LEFT JOIN project_members
            ON project_members.project_id = projects.id
            AND project_members.user_id = ?
        WHERE projects.id = ?
            AND (workspace_members.user_id IS NOT NULL
                OR project_members.user_id IS NOT NULL)
        """,
        (current_user["id"], current_user["id"], project_id),
    ).fetchone()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    if write and (
        project["status"] == "archived"
        or (
            project["owner_id"] != current_user["id"]
            and project["workspace_role"] not in {"owner", "admin"}
            and project["project_role"] not in {"project_manager", "member"}
        )
    ):
        raise HTTPException(status_code=403, detail="Insufficient permissions.")
    board = connection.execute(
        "SELECT id FROM boards WHERE project_id = ?", (project_id,)
    ).fetchone()
    if board is None:
        raise HTTPException(status_code=404, detail="Board not found.")
    return board


def rename_column_on_board(
    connection: DatabaseSession,
    board_id: str,
    column_id: str,
    title: str,
) -> dict[str, object]:
    get_user_column(connection, board_id, column_id)
    with connection:
        connection.execute(
            "UPDATE columns SET title = ? WHERE id = ?",
            (title, column_id),
        )
    return serialize_board(connection, board_id)


def create_card_on_board(
    connection: DatabaseSession,
    board_id: str,
    column_id: str,
    card: CardCreate,
    reporter_id: str,
) -> dict[str, object]:
    get_user_column(connection, board_id, column_id)
    validate_assignee(connection, board_id, card.assignee_id)
    card_id = f"card-{uuid4().hex}"
    with connection:
        position = connection.execute(
            "SELECT COUNT(*) AS card_count FROM cards WHERE column_id = ?",
            (column_id,),
        ).fetchone()["card_count"]
        connection.execute(
            """
            INSERT INTO cards
                (id, column_id, title, details, position, priority, assignee_id,
                    reporter_id, start_date, due_date, labels_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                card_id,
                column_id,
                card.title.strip(),
                card.details.strip(),
                position,
                card.priority,
                card.assignee_id,
                reporter_id,
                card.start_date.isoformat() if card.start_date else None,
                card.due_date.isoformat() if card.due_date else None,
                json.dumps(card.labels),
            ),
        )
    return serialize_board(connection, board_id)


def delete_card_on_board(
    connection: DatabaseSession,
    board_id: str,
    card_id: str,
) -> dict[str, object]:
    card = connection.execute(
        """
        SELECT cards.column_id
        FROM cards
        JOIN columns ON columns.id = cards.column_id
        WHERE cards.id = ? AND columns.board_id = ?
        """,
        (card_id, board_id),
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
    return serialize_board(connection, board_id)


def update_card_on_board(
    connection: DatabaseSession,
    board_id: str,
    card_id: str,
    update: CardUpdate,
    user_id: str,
) -> dict[str, object]:
    card = connection.execute(
        """
        SELECT cards.id, cards.assignee_id, cards.start_date, cards.due_date
        FROM cards
        JOIN columns ON columns.id = cards.column_id
        WHERE cards.id = ? AND columns.board_id = ?
        """,
        (card_id, board_id),
    ).fetchone()
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found.")
    updates = update.model_dump(exclude_unset=True)
    if "assignee_id" in updates:
        validate_assignee(connection, board_id, updates["assignee_id"])
    start_date = updates.get("start_date", card["start_date"])
    due_date = updates.get("due_date", card["due_date"])
    if isinstance(start_date, date):
        start_date = start_date.isoformat()
    if isinstance(due_date, date):
        due_date = due_date.isoformat()
    if start_date and due_date and due_date < start_date:
        raise HTTPException(
            status_code=422,
            detail="Due date must be on or after the start date.",
        )
    serialized = {
        "labels": "labels_json",
        "start_date": "start_date",
        "due_date": "due_date",
        "assignee_id": "assignee_id",
        "title": "title",
        "details": "details",
        "priority": "priority",
    }
    values: list[object] = []
    assignments: list[str] = []
    for field, value in updates.items():
        column = serialized[field]
        if field == "labels":
            value = json.dumps(value)
        elif isinstance(value, date):
            value = value.isoformat()
        elif isinstance(value, str) and field in {"title", "details"}:
            value = value.strip()
        assignments.append(f"{column} = ?")
        values.append(value)
    if not assignments:
        return serialize_board(connection, board_id)
    assignments.append("updated_at = CURRENT_TIMESTAMP")
    values.append(card_id)
    with connection:
        connection.execute(
            f"UPDATE cards SET {', '.join(assignments)} WHERE id = ?",
            values,
        )
    return serialize_board(connection, board_id)


def move_card_on_board(
    connection: DatabaseSession,
    board_id: str,
    card_id: str,
    move: CardMove,
) -> dict[str, object]:
    target = get_user_column(connection, board_id, move.column_id)
    card = connection.execute(
        """
        SELECT cards.column_id
        FROM cards
        JOIN columns ON columns.id = cards.column_id
        WHERE cards.id = ? AND columns.board_id = ?
        """,
        (card_id, board_id),
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

        insert_position = len(target_ids) if move.position is None else move.position
        if insert_position > len(target_ids):
            raise HTTPException(
                status_code=422,
                detail="Position is outside the target column.",
            )
        target_ids.insert(insert_position, card_id)

        if source_column_id != target_column_id:
            set_card_order(connection, source_column_id, source_ids)
        set_card_order(connection, target_column_id, target_ids)
        connection.execute(
            """
            UPDATE cards
            SET updated_at = CURRENT_TIMESTAMP,
                completed_at = CASE
                    WHEN (SELECT status_key FROM columns WHERE id = ?) = 'completed'
                        THEN COALESCE(completed_at, CURRENT_TIMESTAMP)
                    ELSE NULL
                END
            WHERE id = ?
            """,
            (target_column_id, card_id),
        )

    return serialize_board(connection, board_id)


@router.get("")
def read_board(user_id: BoardOwner, connection: DatabaseConnection) -> dict[str, object]:
    board = get_board_row(connection, user_id)
    return serialize_board(connection, board["id"])


@router.patch("/columns/{column_id}")
def rename_column(
    user_id: BoardOwner,
    column_id: str,
    update: ColumnUpdate,
    connection: DatabaseConnection,
    _: OriginCheck,
) -> dict[str, object]:
    board = get_board_row(connection, user_id)
    return rename_column_on_board(connection, board["id"], column_id, update.title)


@router.post("/columns/{column_id}/cards", status_code=201)
def create_card(
    user_id: BoardOwner,
    column_id: str,
    card: CardCreate,
    connection: DatabaseConnection,
    _: OriginCheck,
) -> dict[str, object]:
    board = get_board_row(connection, user_id)
    return create_card_on_board(
        connection, board["id"], column_id, card, user_id
    )


@router.delete("/cards/{card_id}")
def delete_card(
    user_id: BoardOwner,
    card_id: str,
    connection: DatabaseConnection,
    _: OriginCheck,
) -> dict[str, object]:
    board = get_board_row(connection, user_id)
    return delete_card_on_board(connection, board["id"], card_id)


@router.patch("/cards/{card_id}")
def update_card(
    user_id: BoardOwner,
    card_id: str,
    update: CardUpdate,
    connection: DatabaseConnection,
    _: OriginCheck,
) -> dict[str, object]:
    board = get_board_row(connection, user_id)
    return update_card_on_board(connection, board["id"], card_id, update, user_id)


@router.post("/cards/{card_id}/move")
def move_card(
    user_id: BoardOwner,
    card_id: str,
    move: CardMove,
    connection: DatabaseConnection,
    _: OriginCheck,
) -> dict[str, object]:
    board = get_board_row(connection, user_id)
    return move_card_on_board(connection, board["id"], card_id, move)


@project_router.get("")
def read_project_board(
    project_id: str,
    user: AuthenticatedUser,
    connection: DatabaseConnection,
) -> dict[str, object]:
    board = get_project_board_row(connection, project_id, user)
    return serialize_board(connection, board["id"])


@project_router.patch("/columns/{column_id}")
def rename_project_column(
    project_id: str,
    column_id: str,
    update: ColumnUpdate,
    user: AuthenticatedUser,
    connection: DatabaseConnection,
    _: OriginCheck,
) -> dict[str, object]:
    board = get_project_board_row(connection, project_id, user, write=True)
    return rename_column_on_board(connection, board["id"], column_id, update.title)


@project_router.post("/columns/{column_id}/cards")
def create_project_card(
    project_id: str,
    column_id: str,
    card: CardCreate,
    user: AuthenticatedUser,
    connection: DatabaseConnection,
    _: OriginCheck,
) -> dict[str, object]:
    board = get_project_board_row(connection, project_id, user, write=True)
    return create_card_on_board(
        connection, board["id"], column_id, card, user["id"]
    )


@project_router.delete("/cards/{card_id}")
def delete_project_card(
    project_id: str,
    card_id: str,
    user: AuthenticatedUser,
    connection: DatabaseConnection,
    _: OriginCheck,
) -> dict[str, object]:
    board = get_project_board_row(connection, project_id, user, write=True)
    return delete_card_on_board(connection, board["id"], card_id)


@project_router.patch("/cards/{card_id}")
def update_project_card(
    project_id: str,
    card_id: str,
    update: CardUpdate,
    user: AuthenticatedUser,
    connection: DatabaseConnection,
    _: OriginCheck,
) -> dict[str, object]:
    board = get_project_board_row(connection, project_id, user, write=True)
    return update_card_on_board(connection, board["id"], card_id, update, user["id"])


@project_router.post("/cards/{card_id}/move")
def move_project_card(
    project_id: str,
    card_id: str,
    move: CardMove,
    user: AuthenticatedUser,
    connection: DatabaseConnection,
    _: OriginCheck,
) -> dict[str, object]:
    board = get_project_board_row(connection, project_id, user, write=True)
    return move_card_on_board(connection, board["id"], card_id, move)
