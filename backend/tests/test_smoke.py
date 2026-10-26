import re

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_root_serves_exported_frontend() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Kanban Studio" in response.text
    assert "Single Board Kanban" in response.text


def test_health_route() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_hello_route() -> None:
    response = client.get("/api/hello")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello from the PM backend API"}


def test_frontend_assets_are_served() -> None:
    page = client.get("/")
    stylesheet = re.search(r'href="([^"]+\.css[^"]*)"', page.text)
    assert stylesheet is not None

    response = client.get(stylesheet.group(1))
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]
