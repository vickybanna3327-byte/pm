from collections.abc import Callable

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app import openrouter_api

CONNECTIVITY_URL = "/api/ai/connectivity"


class MockAsyncClient:
    def __init__(
        self,
        response: httpx.Response | None = None,
        error: Exception | None = None,
        on_post: Callable[..., None] | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.on_post = on_post

    async def __aenter__(self) -> "MockAsyncClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def post(self, url: str, **kwargs: object) -> httpx.Response:
        if self.on_post:
            self.on_post(url, kwargs)
        if self.error:
            raise self.error
        assert self.response is not None
        return self.response


def install_mock_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    response: httpx.Response | None = None,
    error: Exception | None = None,
    on_post: Callable[..., None] | None = None,
) -> None:
    monkeypatch.setattr(
        openrouter_api.httpx,
        "AsyncClient",
        lambda **_: MockAsyncClient(response, error, on_post),  # type: ignore[arg-type]
    )


def completion_response(content: object) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}]},
        request=httpx.Request("POST", openrouter_api.OPENROUTER_URL),
    )


def test_connectivity_uses_configured_model_and_validates_response(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    response = completion_response("4")
    captured: dict[str, object] = {}

    def capture_request(url: str, kwargs: dict[str, object]) -> None:
        captured["url"] = url
        captured.update(kwargs)

    install_mock_client(
        monkeypatch, response=response, on_post=capture_request
    )
    result = client.post(CONNECTIVITY_URL)

    assert result.status_code == 200
    assert result.json() == {
        "model": "openai/gpt-oss-120b",
        "response": "4",
    }
    assert captured["url"] == openrouter_api.OPENROUTER_URL
    assert captured["headers"] == {"Authorization": "Bearer test-key"}
    assert captured["json"] == {
        "model": "openai/gpt-oss-120b",
        "messages": [
            {"role": "user", "content": openrouter_api.CONNECTIVITY_PROMPT}
        ],
    }


def test_connectivity_requires_api_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    response = client.post(CONNECTIVITY_URL)

    assert response.status_code == 503
    assert response.json()["detail"] == "OPENROUTER_API_KEY is not configured."


@pytest.mark.parametrize("status_code", [401, 403])
def test_connectivity_reports_invalid_api_key(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "invalid-key")
    install_mock_client(
        monkeypatch,
        response=httpx.Response(
            status_code,
            request=httpx.Request("POST", openrouter_api.OPENROUTER_URL),
        ),
    )

    response = client.post(CONNECTIVITY_URL)

    assert response.status_code == 502
    assert response.json()["detail"] == "OpenRouter rejected the API key."


def test_connectivity_reports_network_errors(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    install_mock_client(
        monkeypatch,
        error=httpx.ConnectError("network unavailable"),
    )

    response = client.post(CONNECTIVITY_URL)

    assert response.status_code == 502
    assert response.json()["detail"] == "Could not connect to OpenRouter."


def test_connectivity_reports_timeouts(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    install_mock_client(
        monkeypatch,
        error=httpx.ReadTimeout("provider timed out"),
    )

    response = client.post(CONNECTIVITY_URL)

    assert response.status_code == 502
    assert response.json()["detail"] == "The OpenRouter request timed out."


def test_connectivity_reports_provider_errors(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    install_mock_client(
        monkeypatch,
        response=httpx.Response(
            429,
            request=httpx.Request("POST", openrouter_api.OPENROUTER_URL),
        ),
    )

    response = client.post(CONNECTIVITY_URL)

    assert response.status_code == 502
    assert response.json()["detail"] == "OpenRouter returned HTTP 429."


def test_connectivity_rejects_invalid_provider_response(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    install_mock_client(monkeypatch, response=completion_response(None))

    response = client.post(CONNECTIVITY_URL)

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "OpenRouter returned an invalid chat completion response."
    )
