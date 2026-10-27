from concurrent.futures import ThreadPoolExecutor
import sqlite3
from datetime import timedelta
from pathlib import Path
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from pwdlib import PasswordHash

from backend.app import auth_api
from backend.app.database import connect_database, initialize_database


ORIGIN = {"Origin": "http://testserver"}
REGISTER_URL = "/api/auth/register"


def register_user(
    client: TestClient,
    email: str = "new@example.com",
    username: str = "newuser",
) -> dict[str, str]:
    response = client.post(
        REGISTER_URL,
        headers=ORIGIN,
        json={
            "full_name": "New User",
            "username": username,
            "email": email,
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 202
    return {"email": email, "username": username}


def test_registration_normalizes_and_hashes_new_account(
    client: TestClient,
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        auth_api,
        "send_code_email",
        lambda email, code, purpose: sent.append((email, code, purpose)),
    )
    response = client.post(
        REGISTER_URL,
        headers=ORIGIN,
        json={
            "full_name": "  New   User ",
            "username": "New_User",
            "email": "New.User@Example.com",
            "password": "SecurePassword123!",
        },
    )

    assert response.status_code == 202
    assert sent[0][0] == "new.user@example.com"
    assert sent[0][2] == "verify_email"
    assert len(sent[0][1]) == 6
    connection = connect_database(database_path)
    user = connection.execute(
        "SELECT * FROM users WHERE username = 'new_user'"
    ).fetchone()
    stored_code = connection.execute(
        "SELECT code_hash FROM email_codes WHERE user_id = ?", (user["id"],)
    ).fetchone()
    board = connection.execute(
        "SELECT id FROM boards WHERE user_id = ?", (user["id"],)
    ).fetchone()
    board_cards = connection.execute(
        """
        SELECT COUNT(*) FROM cards
        JOIN columns ON columns.id = cards.column_id
        WHERE columns.board_id = ?
        """,
        (board["id"],),
    ).fetchone()[0]
    connection.close()

    assert user["full_name"] == "New User"
    assert user["email"] == "new.user@example.com"
    assert user["role"] == "member"
    assert user["email_verified_at"] is None
    assert user["created_at"]
    assert user["password_hash"] != "SecurePassword123!"
    assert PasswordHash.recommended().verify(
        "SecurePassword123!", user["password_hash"]
    )
    assert sent[0][1] not in stored_code["code_hash"]
    assert board is not None
    assert board_cards == 8


def test_username_only_registration_creates_a_session_without_email(
    client: TestClient,
    database_path: Path,
) -> None:
    response = client.post(
        REGISTER_URL,
        headers=ORIGIN,
        json={"username": "showcaseuser", "password": "SecurePassword123!"},
    )
    current_user_response = client.get("/api/auth/me")
    board_response = client.get("/api/users/me/board")
    connection = connect_database(database_path)
    user = connection.execute(
        "SELECT email, email_verified_at, password_hash FROM users "
        "WHERE username = 'showcaseuser'"
    ).fetchone()
    connection.close()

    assert response.status_code == 201
    assert response.json() == {"message": "Account created."}
    assert current_user_response.status_code == 200
    assert current_user_response.json()["user"]["username"] == "showcaseuser"
    assert board_response.status_code == 200
    assert user["email"] is None
    assert user["email_verified_at"]
    assert PasswordHash.recommended().verify(
        "SecurePassword123!", user["password_hash"]
    )


def test_username_only_registration_rejects_duplicate_usernames(
    client: TestClient,
) -> None:
    first = client.post(
        REGISTER_URL,
        headers=ORIGIN,
        json={"username": "showcaseuser", "password": "SecurePassword123!"},
    )
    second = client.post(
        REGISTER_URL,
        headers=ORIGIN,
        json={"username": "SHOWCASEUSER", "password": "SecurePassword123!"},
    )

    assert first.status_code == 201
    assert second.status_code == 409


@pytest.mark.parametrize(
    ("username", "email"),
    [
        ("user", "another@example.com"),
        ("another", "legacy-test@example.com"),
    ],
)
def test_registration_rejects_duplicate_username_or_email(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    username: str,
    email: str,
) -> None:
    monkeypatch.setattr(auth_api, "send_code_email", lambda *_: None)
    response = client.post(
        REGISTER_URL,
        headers=ORIGIN,
        json={
            "full_name": "Another User",
            "username": username,
            "email": email,
            "password": "SecurePassword123!",
        },
    )

    assert response.status_code == 409


def test_registration_rejects_case_normalized_duplicates(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_api, "send_code_email", lambda *_: None)
    register_user(client, email="Mixed@example.com", username="SomeUser")

    response = client.post(
        REGISTER_URL,
        headers=ORIGIN,
        json={
            "full_name": "Another User",
            "username": "someuser",
            "email": "MIXED@EXAMPLE.COM",
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 409


def test_registration_validates_password_and_username(client: TestClient) -> None:
    short_password = client.post(
        REGISTER_URL,
        headers=ORIGIN,
        json={
            "full_name": "New User",
            "username": "newuser",
            "email": "new@example.com",
            "password": "short",
        },
    )
    invalid_username = client.post(
        REGISTER_URL,
        headers=ORIGIN,
        json={
            "full_name": "New User",
            "username": "bad username",
            "email": "new@example.com",
            "password": "SecurePassword123!",
        },
    )

    assert short_password.status_code == 422
    assert invalid_username.status_code == 422


def test_email_verification_is_one_time_and_sets_verified_timestamp(
    client: TestClient,
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[str] = []
    monkeypatch.setattr(
        auth_api,
        "send_code_email",
        lambda _email, code, _purpose: sent.append(code),
    )
    account = register_user(client)

    verified = client.post(
        "/api/auth/verify-email",
        headers=ORIGIN,
        json={"email": account["email"], "code": sent[0]},
    )
    repeated = client.post(
        "/api/auth/verify-email",
        headers=ORIGIN,
        json={"email": account["email"], "code": sent[0]},
    )
    connection = connect_database(database_path)
    row = connection.execute(
        "SELECT email_verified_at FROM users WHERE email = ?",
        (account["email"],),
    ).fetchone()
    connection.close()

    assert verified.status_code == 200
    assert row["email_verified_at"]
    assert repeated.status_code == 400


def test_email_code_can_only_be_consumed_once_under_concurrent_requests(
    client: TestClient,
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[str] = []
    monkeypatch.setattr(
        auth_api,
        "send_code_email",
        lambda _email, code, _purpose: sent.append(code),
    )
    account = register_user(client)
    connection = connect_database(database_path)
    user_id = connection.execute(
        "SELECT id FROM users WHERE email = ?", (account["email"],)
    ).fetchone()["id"]
    connection.close()

    barrier = Barrier(8)

    def consume_code() -> bool:
        connection = connect_database(database_path)
        try:
            barrier.wait()
            return auth_api.verify_code(
                connection,
                user_id,
                "verify_email",
                sent[0],
            )
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: consume_code(), range(8)))

    assert results.count(True) == 1


def test_rate_limit_is_atomic_under_concurrent_requests(
    database_path: Path,
) -> None:
    initialize_database(database_path)
    barrier = Barrier(8)

    def record_attempt() -> bool:
        connection = connect_database(database_path)
        try:
            barrier.wait()
            auth_api.rate_limit(connection, "concurrent-test", 3, 3600)
            return True
        except auth_api.HTTPException as error:
            assert error.status_code == 429
            return False
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: record_attempt(), range(8)))

    assert results.count(True) == 3


def test_expired_code_is_rejected(
    client: TestClient,
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[str] = []
    monkeypatch.setattr(
        auth_api,
        "send_code_email",
        lambda _email, code, _purpose: sent.append(code),
    )
    account = register_user(client)
    connection = connect_database(database_path)
    with connection:
        connection.execute(
            "UPDATE email_codes SET expires_at = ? WHERE purpose = 'verify_email'",
            (auth_api.timestamp(auth_api.now() - timedelta(seconds=1)),),
        )
    connection.close()

    response = client.post(
        "/api/auth/verify-email",
        headers=ORIGIN,
        json={"email": account["email"], "code": sent[0]},
    )
    assert response.status_code == 400


def test_verification_resend_observes_cooldown_without_account_disclosure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_api, "send_code_email", lambda *_: None)
    account = register_user(client)

    known = client.post(
        "/api/auth/resend-verification",
        headers=ORIGIN,
        json={"email": account["email"]},
    )
    unknown = client.post(
        "/api/auth/resend-verification",
        headers=ORIGIN,
        json={"email": "missing@example.com"},
    )

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()


def test_verification_code_attempts_are_limited(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[str] = []
    monkeypatch.setattr(
        auth_api,
        "send_code_email",
        lambda _email, code, _purpose: sent.append(code),
    )
    account = register_user(client)

    for _ in range(auth_api.MAX_CODE_ATTEMPTS):
        response = client.post(
            "/api/auth/verify-email",
            headers=ORIGIN,
            json={"email": account["email"], "code": "999999"},
        )
        assert response.status_code == 400

    valid_code = client.post(
        "/api/auth/verify-email",
        headers=ORIGIN,
        json={"email": account["email"], "code": sent[0]},
    )
    assert valid_code.status_code == 400


def test_login_supports_username_and_email_and_sets_secure_cookie(
    client: TestClient,
) -> None:
    client.cookies.clear()
    response = client.post(
        "/api/auth/login",
        headers=ORIGIN,
        json={
            "identifier": "legacy-test@example.com",
            "password": "TestOnly-Password-123!",
        },
    )

    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert response.json()["user"]["username"] == "user"


def test_production_session_cookie_sets_secure_flag(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")
    client.cookies.clear()
    response = client.post(
        "/api/auth/login",
        headers=ORIGIN,
        json={"identifier": "user", "password": "TestOnly-Password-123!"},
    )

    assert response.status_code == 200
    assert "secure" in response.headers["set-cookie"].lower()


def test_login_rejects_unverified_accounts_without_account_detail(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_api, "send_code_email", lambda *_: None)
    register_user(client)
    client.cookies.clear()

    response = client.post(
        "/api/auth/login",
        headers=ORIGIN,
        json={"identifier": "newuser", "password": "SecurePassword123!"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid username/email or password."}


def test_forgot_password_response_does_not_disclose_account_existence(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        auth_api,
        "send_code_email",
        lambda email, _code, purpose: sent.append((email, purpose)),
    )
    known = client.post(
        "/api/auth/forgot-password",
        headers=ORIGIN,
        json={"email": "legacy-test@example.com"},
    )
    unknown = client.post(
        "/api/auth/forgot-password",
        headers=ORIGIN,
        json={"email": "missing@example.com"},
    )

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert sent == [("legacy-test@example.com", "reset_password")]


def test_password_reset_consumes_code_and_revokes_sessions(
    client: TestClient,
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[str] = []
    monkeypatch.setattr(
        auth_api,
        "send_code_email",
        lambda _email, code, _purpose: sent.append(code),
    )
    client.post(
        "/api/auth/forgot-password",
        headers=ORIGIN,
        json={"email": "legacy-test@example.com"},
    )
    client.post(
        "/api/auth/login",
        headers=ORIGIN,
        json={
            "identifier": "user",
            "password": "TestOnly-Password-123!",
        },
    )
    verified = client.post(
        "/api/auth/verify-reset-code",
        headers=ORIGIN,
        json={"email": "legacy-test@example.com", "code": sent[0]},
    )
    token = verified.json()["reset_token"]
    reset = client.post(
        "/api/auth/reset-password",
        headers=ORIGIN,
        json={"reset_token": token, "password": "NewSecurePassword123!"},
    )
    me = client.get("/api/auth/me")
    connection = connect_database(database_path)
    sessions = connection.execute(
        "SELECT COUNT(*) FROM sessions WHERE user_id = 'user'"
    ).fetchone()[0]
    connection.close()

    assert verified.status_code == 200
    assert reset.status_code == 200
    assert sessions == 0
    assert me.status_code == 401
    bad_reuse = client.post(
        "/api/auth/reset-password",
        headers=ORIGIN,
        json={"reset_token": token, "password": "OtherSecurePassword123!"},
    )
    assert bad_reuse.status_code == 400


def test_change_password_keeps_current_session_and_revokes_others(
    client: TestClient,
    database_path: Path,
) -> None:
    client.post(
        "/api/auth/login",
        headers=ORIGIN,
        json={"identifier": "user", "password": "TestOnly-Password-123!"},
    )
    response = client.post(
        "/api/auth/change-password",
        headers=ORIGIN,
        json={
            "current_password": "TestOnly-Password-123!",
            "new_password": "NewSecurePassword123!",
        },
    )
    connection = connect_database(database_path)
    remaining = connection.execute(
        "SELECT COUNT(*) FROM sessions WHERE user_id = 'user'"
    ).fetchone()[0]
    connection.close()

    assert response.status_code == 200
    assert remaining == 1
    assert client.get("/api/auth/me").status_code == 200


def test_logout_invalidates_database_session(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 200
    response = client.post("/api/auth/logout", headers=ORIGIN)

    assert response.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_login_is_rate_limited_by_ip_and_identifier(
    client: TestClient,
    database_path: Path,
) -> None:
    client.cookies.clear()
    connection = connect_database(database_path)
    with connection:
        connection.execute("DELETE FROM rate_limits")
    connection.close()

    responses = [
        client.post(
            "/api/auth/login",
            headers=ORIGIN,
            json={"identifier": "user", "password": "wrong-password"},
        )
        for _ in range(9)
    ]

    assert [response.status_code for response in responses[:8]] == [401] * 8
    assert responses[8].status_code == 429


def test_expired_session_is_rejected(
    client: TestClient,
    database_path: Path,
) -> None:
    connection = connect_database(database_path)
    with connection:
        connection.execute(
            "UPDATE sessions SET expires_at = ?",
            (auth_api.timestamp(auth_api.now() - timedelta(seconds=1)),),
        )
    connection.close()

    assert client.get("/api/auth/me").status_code == 401


def test_board_api_requires_session_and_rejects_other_users_board(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_api, "send_code_email", lambda *_: None)
    account = register_user(client)
    connection = connect_database(client.app.state.database_path)
    account_id = connection.execute(
        "SELECT id FROM users WHERE email = ?", (account["email"],)
    ).fetchone()["id"]
    connection.close()

    assert client.get(f"/api/users/{account_id}/board").status_code == 404
    foreign_write = client.patch(
        f"/api/users/{account_id}/board/columns/col-backlog-{account_id}",
        headers=ORIGIN,
        json={"title": "Access attempt"},
    )
    assert foreign_write.status_code == 404
    client.cookies.clear()
    assert client.get("/api/users/me/board").status_code == 401


def test_legacy_board_survives_authentication_migration(
    client: TestClient,
    database_path: Path,
) -> None:
    connection = connect_database(database_path)
    legacy = connection.execute(
        """
        SELECT users.password_hash, users.email_verified_at,
            boards.id AS board_id, COUNT(cards.id) AS card_count
        FROM users
        JOIN boards ON boards.user_id = users.id
        JOIN columns ON columns.board_id = boards.id
        LEFT JOIN cards ON cards.column_id = columns.id
        WHERE users.id = 'user'
        GROUP BY users.id, boards.id
        """
    ).fetchone()
    connection.close()

    assert legacy["password_hash"]
    assert legacy["email_verified_at"]
    assert legacy["board_id"] == "board-user"
    assert legacy["card_count"] == 8


def test_admin_endpoint_enforces_role(
    client: TestClient,
    database_path: Path,
) -> None:
    assert client.get("/api/auth/admin/users").status_code == 403
    connection = connect_database(database_path)
    with connection:
        connection.execute("UPDATE users SET role = 'admin' WHERE id = 'user'")
    connection.close()

    response = client.get("/api/auth/admin/users")
    assert response.status_code == 200


def test_mutating_auth_route_requires_same_origin(client: TestClient) -> None:
    response = client.post(
        "/api/auth/logout",
        headers={"Origin": "https://attacker.example"},
    )

    assert response.status_code == 403


def test_origin_uses_render_external_url_when_frontend_url_is_unset(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://pm-app.onrender.com")

    response = client.post(
        "/api/auth/logout",
        headers={"Origin": "https://pm-app.onrender.com"},
    )

    assert response.status_code == 204


def test_migration_preserves_existing_board_rows(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(database_path)
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE);
        CREATE TABLE boards (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL UNIQUE REFERENCES users(id),
            title TEXT NOT NULL
        );
        CREATE TABLE columns (
            id TEXT PRIMARY KEY,
            board_id TEXT NOT NULL REFERENCES boards(id),
            title TEXT NOT NULL,
            position INTEGER NOT NULL,
            UNIQUE (board_id, position)
        );
        CREATE TABLE cards (
            id TEXT PRIMARY KEY,
            column_id TEXT NOT NULL REFERENCES columns(id),
            title TEXT NOT NULL,
            details TEXT NOT NULL,
            position INTEGER NOT NULL,
            UNIQUE (column_id, position)
        );
        INSERT INTO users VALUES ('user', 'user');
        INSERT INTO boards VALUES ('board-user', 'user', 'Existing Project');
        INSERT INTO columns VALUES ('custom-column', 'board-user', 'Doing', 0);
        INSERT INTO cards VALUES ('existing-card', 'custom-column', 'Task', 'Keep me', 0);
        """
    )
    connection.close()

    initialize_database(database_path)

    connection = connect_database(database_path)
    user = connection.execute(
        "SELECT username, email, password_hash, role FROM users WHERE id = 'user'"
    ).fetchone()
    board = connection.execute(
        """
        SELECT boards.title, projects.name AS project_name,
            workspaces.kind AS workspace_kind
        FROM boards
        JOIN projects ON projects.id = boards.project_id
        JOIN workspaces ON workspaces.id = projects.workspace_id
        WHERE boards.id = 'board-user'
        """
    ).fetchone()
    card = connection.execute(
        "SELECT title, details FROM cards WHERE id = 'existing-card'"
    ).fetchone()
    connection.close()

    assert user["username"] == "user"
    assert user["email"] is None
    assert user["password_hash"] is None
    assert user["role"] == "member"
    assert board["title"] == "Existing Project"
    assert board["project_name"] == "Existing Project"
    assert board["workspace_kind"] == "personal"
    assert dict(card) == {"title": "Task", "details": "Keep me"}
    assert database_path.with_name(
        "legacy.db.before-workspace-migration"
    ).exists()
