from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pwdlib import PasswordHash

from backend.app.database import connect_database
from backend.app.main import create_app


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    return tmp_path / "pm-test.db"


@pytest.fixture
def client(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret-that-is-long-enough")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("FRONTEND_URL", "http://testserver")
    with TestClient(
        create_app(database_path),
        headers={"Origin": "http://testserver"},
    ) as test_client:
        connection = connect_database(database_path)
        with connection:
            connection.execute(
                """
                UPDATE users
                SET full_name = ?, email = ?, password_hash = ?, role = ?,
                    email_verified_at = CURRENT_TIMESTAMP
                WHERE id = 'user'
                """,
                (
                    "Legacy Test User",
                    "legacy-test@example.com",
                    PasswordHash.recommended().hash("TestOnly-Password-123!"),
                    "member",
                ),
            )
        connection.close()
        login = test_client.post(
            "/api/auth/login",
            json={
                "identifier": "user",
                "password": "TestOnly-Password-123!",
            },
            headers={"Origin": "http://testserver"},
        )
        assert login.status_code == 200
        yield test_client
