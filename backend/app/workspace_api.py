from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.auth_api import AuthenticatedUser, check_origin
from backend.app.database import (
    DatabaseConnection as DatabaseSession,
    DatabaseRow,
    create_board,
    create_project,
    connect_database,
)

router = APIRouter(tags=["workspaces", "projects"])
DatabaseConnection = Annotated[DatabaseSession, Depends(connect_database)]
OriginCheck = Annotated[None, Depends(check_origin)]
ProjectStatus = Literal["planning", "active", "on_hold", "completed", "archived"]
ProjectLifecycle = Literal["planning", "active", "on_hold", "completed"]
ProjectPriority = Literal["low", "medium", "high"]
class WorkspaceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=1000)


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    start_date: date | None = None
    due_date: date | None = None
    priority: ProjectPriority = "medium"
    status: ProjectLifecycle = "planning"
    color: str = Field(default="#209dd7", pattern=r"^#[0-9a-fA-F]{6}$")

    @model_validator(mode="after")
    def dates_are_ordered(self) -> "ProjectCreate":
        if self.start_date and self.due_date and self.due_date < self.start_date:
            raise ValueError("Due date must be on or after the start date.")
        return self


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    start_date: date | None = None
    due_date: date | None = None
    priority: ProjectPriority | None = None
    status: ProjectLifecycle | None = None
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")

    @model_validator(mode="after")
    def dates_are_ordered(self) -> "ProjectUpdate":
        if self.start_date and self.due_date and self.due_date < self.start_date:
            raise ValueError("Due date must be on or after the start date.")
        return self


def workspace_membership(
    connection: DatabaseSession,
    workspace_id: str,
    user_id: str,
) -> DatabaseRow:
    row = connection.execute(
        """
        SELECT workspaces.id, workspaces.name, workspaces.description,
            workspaces.kind, workspaces.owner_id, workspace_members.role
        FROM workspaces
        JOIN workspace_members ON workspace_members.workspace_id = workspaces.id
        WHERE workspaces.id = ? AND workspace_members.user_id = ?
        """,
        (workspace_id, user_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return row


def project_access(
    connection: DatabaseSession,
    project_id: str,
    user_id: str,
) -> DatabaseRow:
    row = connection.execute(
        """
        SELECT projects.*, workspaces.kind AS workspace_kind,
            workspace_members.role AS workspace_role,
            project_members.role AS project_role
        FROM projects
        JOIN workspaces ON workspaces.id = projects.workspace_id
        LEFT JOIN workspace_members
            ON workspace_members.workspace_id = workspaces.id
            AND workspace_members.user_id = ?
        LEFT JOIN project_members
            ON project_members.project_id = projects.id
            AND project_members.user_id = ?
        WHERE projects.id = ?
            AND (workspace_members.user_id IS NOT NULL
                OR project_members.user_id IS NOT NULL)
        """,
        (user_id, user_id, project_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return row


def can_manage_project(project: DatabaseRow, user_id: str) -> bool:
    return (
        project["owner_id"] == user_id
        or project["workspace_role"] in {"owner", "admin"}
        or project["project_role"] == "project_manager"
    )


def serialize_project(
    connection: DatabaseSession,
    project: DatabaseRow,
) -> dict[str, object]:
    board = connection.execute(
        "SELECT id FROM boards WHERE project_id = ?", (project["id"],)
    ).fetchone()
    member_count = connection.execute(
        """
        SELECT COUNT(*) FROM project_members WHERE project_id = ?
        """,
        (project["id"],),
    ).fetchone()[0]
    return {
        "id": project["id"],
        "workspace_id": project["workspace_id"],
        "owner_id": project["owner_id"],
        "name": project["name"],
        "description": project["description"],
        "start_date": project["start_date"],
        "due_date": project["due_date"],
        "priority": project["priority"],
        "status": project["status"],
        "color": project["color"],
        "created_at": project["created_at"],
        "updated_at": project["updated_at"],
        "archived_at": project["archived_at"],
        "board_id": board["id"] if board else None,
        "member_count": member_count,
    }


@router.get("/api/workspaces")
def list_workspaces(
    user: AuthenticatedUser,
    connection: DatabaseConnection,
) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT workspaces.id, workspaces.name, workspaces.description,
            workspaces.kind, workspaces.owner_id, workspaces.created_at,
            workspace_members.role,
            COUNT(DISTINCT projects.id) AS project_count
        FROM workspace_members
        JOIN workspaces ON workspaces.id = workspace_members.workspace_id
        LEFT JOIN projects ON projects.workspace_id = workspaces.id
            AND projects.status != 'archived'
        WHERE workspace_members.user_id = ?
        GROUP BY workspaces.id
        ORDER BY workspaces.kind, workspaces.created_at
        """,
        (user["id"],),
    ).fetchall()
    return [dict(row) for row in rows]


@router.get("/api/projects")
def list_accessible_projects(
    user: AuthenticatedUser,
    connection: DatabaseConnection,
    search: str = Query(default="", max_length=120),
    status: ProjectStatus | None = None,
    include_archived: bool = False,
) -> list[dict[str, object]]:
    conditions = [
        """
        (EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_members.workspace_id = projects.workspace_id
                AND workspace_members.user_id = ?
        ) OR EXISTS (
            SELECT 1 FROM project_members
            WHERE project_members.project_id = projects.id
                AND project_members.user_id = ?
        ))
        """
    ]
    values: list[object] = [user["id"], user["id"]]
    if not include_archived:
        conditions.append("projects.status != 'archived'")
    if search.strip():
        conditions.append("(lower(projects.name) LIKE ? OR lower(projects.description) LIKE ?)")
        search_pattern = f"%{search.strip().casefold()}%"
        values.extend((search_pattern, search_pattern))
    if status:
        conditions.append("projects.status = ?")
        values.append(status)
    rows = connection.execute(
        f"SELECT projects.* FROM projects WHERE {' AND '.join(conditions)} "
        "ORDER BY projects.updated_at DESC",
        values,
    ).fetchall()
    return [serialize_project(connection, row) for row in rows]


@router.get("/api/dashboard")
def dashboard(
    user: AuthenticatedUser,
    connection: DatabaseConnection,
) -> dict[str, object]:
    project_rows = connection.execute(
        """
        SELECT projects.*
        FROM projects
        WHERE projects.status != 'archived'
            AND (
                EXISTS (
                    SELECT 1 FROM workspace_members
                    WHERE workspace_members.workspace_id = projects.workspace_id
                        AND workspace_members.user_id = ?
                ) OR EXISTS (
                    SELECT 1 FROM project_members
                    WHERE project_members.project_id = projects.id
                        AND project_members.user_id = ?
                )
            )
        ORDER BY projects.updated_at DESC
        """,
        (user["id"], user["id"]),
    ).fetchall()
    projects = [dict(project) for project in project_rows]
    project_ids = [project["id"] for project in projects]
    tasks: list[dict[str, object]] = []
    if project_ids:
        placeholders = ",".join("?" for _ in project_ids)
        task_rows = connection.execute(
            f"""
            SELECT cards.id, cards.title, cards.details, cards.priority,
                cards.assignee_id, cards.start_date, cards.due_date,
                cards.completed_at, columns.status_key, projects.id AS project_id,
                projects.name AS project_name, users.username AS assignee_username,
                users.full_name AS assignee_name
            FROM cards
            JOIN columns ON columns.id = cards.column_id
            JOIN boards ON boards.id = columns.board_id
            JOIN projects ON projects.id = boards.project_id
            LEFT JOIN users ON users.id = cards.assignee_id
            WHERE projects.id IN ({placeholders})
            """,
            project_ids,
        ).fetchall()
        tasks = [dict(task) for task in task_rows]

    today_date = datetime.now(UTC).date()
    today = today_date.isoformat()
    upcoming_limit = (today_date + timedelta(days=7)).isoformat()
    completion_window = (today_date - timedelta(days=29)).isoformat()
    assigned_tasks = [
        task for task in tasks if task["assignee_id"] == user["id"]
    ]
    completed_tasks = [
        task for task in assigned_tasks if task["status_key"] == "completed"
    ]
    overdue_tasks = [
        task
        for task in assigned_tasks
        if task["due_date"]
        and task["due_date"] < today
        and task["status_key"] != "completed"
    ]
    upcoming_tasks = [
        task
        for task in assigned_tasks
        if task["due_date"]
        and today <= task["due_date"] <= upcoming_limit
        and task["status_key"] != "completed"
    ]

    status_distribution = {
        status_name: sum(task["status_key"] == status_name for task in tasks)
        for status_name in ("backlog", "todo", "in_progress", "in_review", "completed")
    }
    completion_by_date: dict[str, int] = {}
    for task in tasks:
        completed_at = task["completed_at"]
        if completed_at and completion_window <= completed_at[:10] <= today:
            completion_day = completed_at[:10]
            completion_by_date[completion_day] = (
                completion_by_date.get(completion_day, 0) + 1
            )

    project_progress: list[dict[str, object]] = []
    for project in projects:
        project_tasks = [
            task for task in tasks if task["project_id"] == project["id"]
        ]
        completed = sum(task["status_key"] == "completed" for task in project_tasks)
        total = len(project_tasks)
        project_progress.append(
            {
                "project_id": project["id"],
                "project_name": project["name"],
                "status": project["status"],
                "total_tasks": total,
                "completed_tasks": completed,
                "progress_percent": round(completed * 100 / total) if total else 0,
            }
        )

    workload: dict[str, dict[str, object]] = {}
    for task in tasks:
        assignee_id = task["assignee_id"]
        if not assignee_id:
            continue
        member = workload.setdefault(
            assignee_id,
            {
                "user_id": assignee_id,
                "username": task["assignee_username"],
                "name": task["assignee_name"] or task["assignee_username"],
                "total_tasks": 0,
                "completed_tasks": 0,
            },
        )
        member["total_tasks"] = int(member["total_tasks"]) + 1
        if task["status_key"] == "completed":
            member["completed_tasks"] = int(member["completed_tasks"]) + 1

    upcoming_deadlines = sorted(
        [
            {
                "id": task["id"],
                "title": task["title"],
                "project_id": task["project_id"],
                "project_name": task["project_name"],
                "due_date": task["due_date"],
                "priority": task["priority"],
            }
            for task in tasks
            if task["due_date"]
            and today <= task["due_date"] <= upcoming_limit
            and task["status_key"] != "completed"
        ],
        key=lambda task: str(task["due_date"]),
    )
    high_priority_tasks = [
        {
            "id": task["id"],
            "title": task["title"],
            "project_id": task["project_id"],
            "project_name": task["project_name"],
            "status": task["status_key"],
            "due_date": task["due_date"],
        }
        for task in tasks
        if task["priority"] == "high" and task["status_key"] != "completed"
    ][:10]
    return {
        "user": {
            "id": user["id"],
            "name": user["full_name"] or user["username"],
            "username": user["username"],
        },
        "metrics": {
            "total_projects": len(projects),
            "active_projects": sum(
                project["status"] == "active" for project in projects
            ),
            "completed_projects": sum(
                project["status"] == "completed" for project in projects
            ),
            "total_assigned_tasks": len(assigned_tasks),
            "tasks_in_progress": sum(
                task["status_key"] == "in_progress" for task in assigned_tasks
            ),
            "completed_tasks": len(completed_tasks),
            "overdue_tasks": len(overdue_tasks),
            "upcoming_deadlines": len(upcoming_tasks),
        },
        "task_status_distribution": status_distribution,
        "completed_over_time": [
            {"date": key, "count": value}
            for key, value in sorted(completion_by_date.items())
        ],
        "project_progress": project_progress,
        "upcoming_deadline_items": upcoming_deadlines[:10],
        "workload_by_member": list(workload.values()),
        "high_priority_tasks": high_priority_tasks,
    }


@router.post("/api/workspaces", status_code=201)
def create_workspace(
    body: WorkspaceCreate,
    user: AuthenticatedUser,
    connection: DatabaseConnection,
    _: OriginCheck,
) -> dict[str, object]:
    workspace_id = f"workspace-{uuid4().hex}"
    created_at = datetime.now(UTC).isoformat()
    name = " ".join(body.name.split())
    if not name:
        raise HTTPException(status_code=422, detail="Workspace name is required.")
    with connection:
        connection.execute(
            """
            INSERT INTO workspaces
                (id, name, description, kind, owner_id, created_at)
            VALUES (?, ?, ?, 'team', ?, ?)
            """,
            (workspace_id, name, body.description.strip(), user["id"], created_at),
        )
        connection.execute(
            """
            INSERT INTO workspace_members (workspace_id, user_id, role, joined_at)
            VALUES (?, ?, 'owner', ?)
            """,
            (workspace_id, user["id"], created_at),
        )
    return {
        "id": workspace_id,
        "name": name,
        "description": body.description.strip(),
        "kind": "team",
        "owner_id": user["id"],
        "role": "owner",
        "project_count": 0,
        "created_at": created_at,
    }


@router.get("/api/workspaces/{workspace_id}/projects")
def list_projects(
    workspace_id: str,
    user: AuthenticatedUser,
    connection: DatabaseConnection,
    search: str = Query(default="", max_length=120),
    status: ProjectStatus | None = None,
) -> list[dict[str, object]]:
    workspace_membership(connection, workspace_id, user["id"])
    conditions = ["workspace_id = ?", "status != 'archived'"]
    values: list[object] = [workspace_id]
    if search.strip():
        conditions.append("(lower(name) LIKE ? OR lower(description) LIKE ?)")
        search_pattern = f"%{search.strip().casefold()}%"
        values.extend((search_pattern, search_pattern))
    if status:
        conditions.append("status = ?")
        values.append(status)
    rows = connection.execute(
        f"SELECT * FROM projects WHERE {' AND '.join(conditions)} "
        "ORDER BY updated_at DESC",
        values,
    ).fetchall()
    return [serialize_project(connection, row) for row in rows]


@router.post("/api/workspaces/{workspace_id}/projects", status_code=201)
def create_workspace_project(
    workspace_id: str,
    body: ProjectCreate,
    user: AuthenticatedUser,
    connection: DatabaseConnection,
    _: OriginCheck,
) -> dict[str, object]:
    member = workspace_membership(connection, workspace_id, user["id"])
    if member["role"] not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions.")
    name = " ".join(body.name.split())
    if not name:
        raise HTTPException(status_code=422, detail="Project name is required.")
    with connection:
        project_id = create_project(
            connection,
            workspace_id,
            user["id"],
            name,
            body.description.strip(),
        )
        connection.execute(
            """
            UPDATE projects SET start_date = ?, due_date = ?, priority = ?,
                status = ?, color = ? WHERE id = ?
            """,
            (
                body.start_date.isoformat() if body.start_date else None,
                body.due_date.isoformat() if body.due_date else None,
                body.priority,
                body.status,
                body.color.lower(),
                project_id,
            ),
        )
        created_at = connection.execute(
            "SELECT created_at FROM projects WHERE id = ?", (project_id,)
        ).fetchone()["created_at"]
        connection.execute(
            """
            INSERT INTO project_members (project_id, user_id, role, joined_at)
            VALUES (?, ?, 'project_manager', ?)
            """,
            (project_id, user["id"], created_at),
        )
        create_board(connection, user["id"], project_id, name)
    project = connection.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    return serialize_project(connection, project)


@router.get("/api/projects/{project_id}")
def get_project(
    project_id: str,
    user: AuthenticatedUser,
    connection: DatabaseConnection,
) -> dict[str, object]:
    project = project_access(connection, project_id, user["id"])
    return serialize_project(connection, project)


@router.patch("/api/projects/{project_id}")
def update_project(
    project_id: str,
    body: ProjectUpdate,
    user: AuthenticatedUser,
    connection: DatabaseConnection,
    _: OriginCheck,
) -> dict[str, object]:
    project = project_access(connection, project_id, user["id"])
    if not can_manage_project(project, user["id"]):
        raise HTTPException(status_code=403, detail="Insufficient permissions.")
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return serialize_project(connection, project)
    values: dict[str, object] = {}
    for field, value in updates.items():
        if isinstance(value, date):
            values[field] = value.isoformat()
        elif isinstance(value, str) and field in {"name", "description"}:
            values[field] = " ".join(value.split()) if field == "name" else value.strip()
        else:
            values[field] = value.lower() if field == "color" and value else value
    if "name" in values and not values["name"]:
        raise HTTPException(status_code=422, detail="Project name is required.")
    start_date = values.get("start_date", project["start_date"])
    due_date = values.get("due_date", project["due_date"])
    if start_date and due_date and due_date < start_date:
        raise HTTPException(
            status_code=422,
            detail="Due date must be on or after the start date.",
        )
    assignments = ", ".join(f"{field} = ?" for field in values)
    with connection:
        connection.execute(
            f"UPDATE projects SET {assignments}, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (*values.values(), project_id),
        )
    updated = connection.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    return serialize_project(connection, updated)


def change_archive_state(
    project_id: str,
    user: AuthenticatedUser,
    connection: DatabaseConnection,
    archived: bool,
) -> dict[str, object]:
    project = project_access(connection, project_id, user["id"])
    if not can_manage_project(project, user["id"]):
        raise HTTPException(status_code=403, detail="Insufficient permissions.")
    status = "archived" if archived else "active"
    archived_at = (
        "CURRENT_TIMESTAMP" if archived else "NULL"
    )
    with connection:
        connection.execute(
            f"UPDATE projects SET status = ?, archived_at = {archived_at}, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, project_id),
        )
    updated = connection.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    return serialize_project(connection, updated)


@router.post("/api/projects/{project_id}/archive")
def archive_project(
    project_id: str,
    user: AuthenticatedUser,
    connection: DatabaseConnection,
    _: OriginCheck,
) -> dict[str, object]:
    return change_archive_state(project_id, user, connection, True)


@router.post("/api/projects/{project_id}/restore")
def restore_project(
    project_id: str,
    user: AuthenticatedUser,
    connection: DatabaseConnection,
    _: OriginCheck,
) -> dict[str, object]:
    return change_archive_state(project_id, user, connection, False)
