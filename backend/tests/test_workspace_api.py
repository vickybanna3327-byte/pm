from pathlib import Path
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.app.database import connect_database


ORIGIN = {"Origin": "http://testserver"}


def test_personal_workspace_is_created_for_seeded_user(client: TestClient) -> None:
    response = client.get("/api/workspaces")

    assert response.status_code == 200
    workspaces = response.json()
    assert len(workspaces) == 1
    assert workspaces[0]["id"] == "personal-user"
    assert workspaces[0]["kind"] == "personal"
    assert workspaces[0]["role"] == "owner"
    assert workspaces[0]["project_count"] == 1


def test_workspace_owner_can_create_edit_archive_and_restore_project(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/workspaces/personal-user/projects",
        headers=ORIGIN,
        json={
            "name": "  Launch Plan ",
            "description": "First release",
            "start_date": "2026-10-01",
            "due_date": "2026-11-01",
            "priority": "high",
            "status": "planning",
            "color": "#753991",
        },
    )

    assert response.status_code == 201
    project = response.json()
    assert project["name"] == "Launch Plan"
    assert project["priority"] == "high"
    assert project["board_id"]

    update = client.patch(
        f"/api/projects/{project['id']}",
        headers=ORIGIN,
        json={"status": "active", "description": "Updated release plan"},
    )
    assert update.status_code == 200
    assert update.json()["status"] == "active"
    assert update.json()["description"] == "Updated release plan"

    archive = client.post(
        f"/api/projects/{project['id']}/archive",
        headers=ORIGIN,
    )
    assert archive.status_code == 200
    assert archive.json()["status"] == "archived"

    visible = client.get("/api/workspaces/personal-user/projects")
    assert project["id"] not in [item["id"] for item in visible.json()]

    restore = client.post(
        f"/api/projects/{project['id']}/restore",
        headers=ORIGIN,
    )
    assert restore.status_code == 200
    assert restore.json()["status"] == "active"


def test_project_search_and_invalid_dates_are_validated(client: TestClient) -> None:
    created = client.post(
        "/api/workspaces/personal-user/projects",
        headers=ORIGIN,
        json={"name": "Roadmap Q4", "description": "Quarterly planning"},
    )
    assert created.status_code == 201

    search = client.get(
        "/api/workspaces/personal-user/projects?search=roadmap",
    )
    assert len(search.json()) == 1
    assert search.json()[0]["id"] == created.json()["id"]

    invalid = client.post(
        "/api/workspaces/personal-user/projects",
        headers=ORIGIN,
        json={
            "name": "Invalid dates",
            "start_date": "2026-12-01",
            "due_date": "2026-11-01",
        },
    )
    assert invalid.status_code == 422


def test_project_board_routes_load_and_persist_board_changes(
    client: TestClient,
) -> None:
    project = client.post(
        "/api/workspaces/personal-user/projects",
        headers=ORIGIN,
        json={"name": "Board Project"},
    ).json()
    board_url = f"/api/projects/{project['id']}/board"

    loaded = client.get(board_url)
    assert loaded.status_code == 200
    assert len(loaded.json()["columns"]) == 5
    assert len(loaded.json()["cards"]) == 8
    column_id = loaded.json()["columns"][0]["id"]

    created = client.post(
        f"{board_url}/columns/{column_id}/cards",
        headers=ORIGIN,
        json={"title": "Project task", "details": "Persisted"},
    )
    assert created.status_code == 200
    assert any(
        card["title"] == "Project task"
        for card in created.json()["cards"].values()
    )


def test_task_fields_validate_assignments_and_track_completion(
    client: TestClient,
) -> None:
    project = client.post(
        "/api/workspaces/personal-user/projects",
        headers=ORIGIN,
        json={"name": "Task metadata"},
    ).json()
    board_url = f"/api/projects/{project['id']}/board"
    board = client.get(board_url).json()
    backlog = board["columns"][0]["id"]
    completed = board["columns"][-1]["id"]

    invalid_assignee = client.post(
        f"{board_url}/columns/{backlog}/cards",
        headers=ORIGIN,
        json={"title": "Invalid assignment", "assignee_id": "not-a-member"},
    )
    assert invalid_assignee.status_code == 422

    created = client.post(
        f"{board_url}/columns/{backlog}/cards",
        headers=ORIGIN,
        json={
            "title": "  Scheduled task ",
            "details": " Add a due date ",
            "priority": "high",
            "assignee_id": "user",
            "start_date": "2026-10-01",
            "due_date": "2026-10-15",
            "labels": [" release ", "review"],
        },
    )
    assert created.status_code == 200
    card = next(
        card
        for card in created.json()["cards"].values()
        if card["title"] == "Scheduled task"
    )
    assert card["details"] == "Add a due date"
    assert card["priority"] == "high"
    assert card["assignee_id"] == "user"
    assert card["labels"] == ["release", "review"]

    moved = client.post(
        f"{board_url}/cards/{card['id']}/move",
        headers=ORIGIN,
        json={"column_id": completed},
    )
    completed_card = moved.json()["cards"][card["id"]]
    assert completed_card["status"] == "completed"
    assert completed_card["completed_at"]

    moved_back = client.post(
        f"{board_url}/cards/{card['id']}/move",
        headers=ORIGIN,
        json={"column_id": backlog},
    )
    assert moved_back.json()["cards"][card["id"]]["completed_at"] is None


def test_dashboard_metrics_use_authorized_task_data(
    client: TestClient,
    database_path: Path,
) -> None:
    today = datetime.now(UTC).date()
    connection = connect_database(database_path)
    with connection:
        connection.execute(
            "UPDATE cards SET assignee_id = 'user', priority = 'high', due_date = ? "
            "WHERE id = 'card-1'",
            ((today - timedelta(days=1)).isoformat(),),
        )
        connection.execute(
            "UPDATE cards SET assignee_id = 'user', due_date = ? "
            "WHERE id = 'card-4'",
            ((today + timedelta(days=3)).isoformat(),),
        )
    connection.close()

    response = client.get("/api/dashboard")
    assert response.status_code == 200
    result = response.json()

    assert result["metrics"] == {
        "total_projects": 1,
        "active_projects": 1,
        "completed_projects": 0,
        "total_assigned_tasks": 2,
        "tasks_in_progress": 1,
        "completed_tasks": 0,
        "overdue_tasks": 1,
        "upcoming_deadlines": 1,
    }
    assert result["task_status_distribution"] == {
        "backlog": 2,
        "todo": 1,
        "in_progress": 2,
        "in_review": 1,
        "completed": 2,
    }
    assert result["high_priority_tasks"][0]["id"] == "card-1"
    assert result["upcoming_deadline_items"][0]["id"] == "card-4"
    assert result["project_progress"][0]["completed_tasks"] == 2


def test_only_workspace_owner_or_admin_can_create_projects(
    client: TestClient,
    database_path: Path,
) -> None:
    team = client.post(
        "/api/workspaces",
        headers=ORIGIN,
        json={"name": "Design team"},
    )
    workspace_id = team.json()["id"]
    connection = connect_database(database_path)
    with connection:
        connection.execute(
            "UPDATE workspace_members SET role = 'member' "
            "WHERE workspace_id = ? AND user_id = 'user'",
            (workspace_id,),
        )
    connection.close()

    response = client.post(
        f"/api/workspaces/{workspace_id}/projects",
        headers=ORIGIN,
        json={"name": "Not allowed"},
    )
    assert response.status_code == 403


def test_workspace_routes_hide_other_users_data(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app import auth_api

    sent: list[str] = []
    monkeypatch.setattr(
        auth_api,
        "send_code_email",
        lambda _email, code, _purpose: sent.append(code),
    )
    registered = client.post(
        "/api/auth/register",
        headers=ORIGIN,
        json={
            "full_name": "Second User",
            "username": "seconduser",
            "email": "second@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert registered.status_code == 202
    own_project_ids = {
        project["id"]
        for project in client.get(
            "/api/workspaces/personal-user/projects"
        ).json()
    }
    verified = client.post(
        "/api/auth/verify-email",
        headers=ORIGIN,
        json={"email": "second@example.com", "code": sent[0]},
    )
    assert verified.status_code == 200
    client.cookies.clear()
    login = client.post(
        "/api/auth/login",
        headers=ORIGIN,
        json={
            "identifier": "seconduser",
            "password": "SecurePassword123!",
        },
    )
    assert login.status_code == 200

    assert client.get("/api/workspaces/personal-user/projects").status_code == 404
    assert all(
        client.get(f"/api/projects/{project_id}").status_code == 404
        for project_id in own_project_ids
    )
    assert all(
        workspace["kind"] == "personal"
        for workspace in client.get("/api/workspaces").json()
    )


def test_project_viewer_can_read_but_not_mutate_project_board(
    client: TestClient,
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = client.post(
        "/api/workspaces/personal-user/projects",
        headers=ORIGIN,
        json={"name": "Viewer project"},
    ).json()
    board_url = f"/api/projects/{project['id']}/board"
    sent: list[str] = []
    from backend.app import auth_api

    monkeypatch.setattr(
        auth_api,
        "send_code_email",
        lambda _email, code, _purpose: sent.append(code),
    )
    registered = client.post(
        "/api/auth/register",
        headers=ORIGIN,
        json={
            "full_name": "Project Viewer",
            "username": "projectviewer",
            "email": "viewer@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert registered.status_code == 202
    verified = client.post(
        "/api/auth/verify-email",
        headers=ORIGIN,
        json={"email": "viewer@example.com", "code": sent[0]},
    )
    assert verified.status_code == 200

    connection = connect_database(database_path)
    viewer_id = connection.execute(
        "SELECT id FROM users WHERE username = 'projectviewer'"
    ).fetchone()["id"]
    with connection:
        connection.execute(
            """
            INSERT INTO project_members (project_id, user_id, role, joined_at)
            VALUES (?, ?, 'viewer', CURRENT_TIMESTAMP)
            """,
            (project["id"], viewer_id),
        )
    connection.close()

    client.cookies.clear()
    login = client.post(
        "/api/auth/login",
        headers=ORIGIN,
        json={
            "identifier": "projectviewer",
            "password": "SecurePassword123!",
        },
    )
    assert login.status_code == 200

    board = client.get(board_url)
    assert board.status_code == 200
    column_id = board.json()["columns"][0]["id"]
    mutation = client.post(
        f"{board_url}/columns/{column_id}/cards",
        headers=ORIGIN,
        json={"title": "Viewer cannot add"},
    )
    assert mutation.status_code == 403


def test_archived_project_board_remains_readable_but_is_read_only(
    client: TestClient,
) -> None:
    project = client.post(
        "/api/workspaces/personal-user/projects",
        headers=ORIGIN,
        json={"name": "Archived project"},
    ).json()
    board_url = f"/api/projects/{project['id']}/board"
    column_id = client.get(board_url).json()["columns"][0]["id"]

    archived = client.post(
        f"/api/projects/{project['id']}/archive",
        headers=ORIGIN,
    )
    assert archived.status_code == 200
    assert client.get(board_url).status_code == 200
    mutation = client.patch(
        f"{board_url}/columns/{column_id}",
        headers=ORIGIN,
        json={"title": "Should not change"},
    )
    assert mutation.status_code == 403
