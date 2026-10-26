from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    return tmp_path / "pm-test.db"


@pytest.fixture
def client(database_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(database_path)) as test_client:
        yield test_client
