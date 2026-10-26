import json

import pytest
from fastapi.testclient import TestClient

from backend.app import ai_board_api, openrouter_api

CHAT_URL = "/api/users/user/board/chat"


def model_response(reply: str, actions: list[dict[str, object]] | None = None) -> str:
    return json.dumps({"reply": reply, "actions": actions or []})


def test_chat_includes_board_question_and_history_in_model_request(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    captured: dict[str, object] = {}

    async def fake_completion(
        api_key: str,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None = None,
    ) -> str:
        captured["api_key"] = api_key
        captured["messages"] = messages
        captured["response_format"] = response_format
        return model_response("There are eight cards.")

    monkeypatch.setattr(ai_board_api, "request_chat_completion", fake_completion)
    original_board = client.get("/api/users/user/board").json()

    response = client.post(
        CHAT_URL,
        json={
            "question": "How many cards are there?",
            "history": [{"role": "user", "content": "Hello"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["reply"] == "There are eight cards."
    assert response.json()["changed"] is False
    assert response.json()["board"] == original_board
    messages = captured["messages"]
    assert isinstance(messages, list)
    assert messages[0]["role"] == "system"
    assert json.dumps(original_board, ensure_ascii=True) in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "Hello"}
    assert messages[2] == {
        "role": "user",
        "content": "How many cards are there?",
    }
    assert captured["response_format"] == {"type": "json_object"}


def test_chat_applies_card_column_and_move_actions_atomically(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    actions: list[dict[str, object]] = [
        {
            "type": "rename_column",
            "column_id": "col-backlog",
            "title": "Prioritized",
        },
        {
            "type": "update_card",
            "card_id": "card-1",
            "title": "Updated roadmap",
            "details": "New details.",
        },
        {
            "type": "move_card",
            "card_id": "card-1",
            "column_id": "col-review",
            "position": 0,
        },
        {
            "type": "create_card",
            "column_id": "col-backlog",
            "title": "Follow up",
            "details": "Created by the assistant.",
        },
    ]

    async def fake_completion(
        api_key: str,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None = None,
    ) -> str:
        return model_response("Updated the board.", actions)

    monkeypatch.setattr(ai_board_api, "request_chat_completion", fake_completion)

    response = client.post(CHAT_URL, json={"question": "Update the board."})

    assert response.status_code == 200
    payload = response.json()
    board = payload["board"]
    assert payload["reply"] == "Updated the board."
    assert payload["changed"] is True
    assert board["columns"][0]["title"] == "Prioritized"
    assert board["columns"][0]["cardIds"] == ["card-2", next(
        card_id
        for card_id, card in board["cards"].items()
        if card["title"] == "Follow up"
    )]
    assert board["columns"][3]["cardIds"] == ["card-1", "card-6"]
    assert board["cards"]["card-1"] == {
        "id": "card-1",
        "title": "Updated roadmap",
        "details": "New details.",
    }
    assert client.get("/api/users/user/board").json() == board


def test_chat_rejects_invalid_model_json_without_board_changes(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    async def fake_completion(*_: object, **__: object) -> str:
        return '{"reply":"Partial","actions":[{"type":"move_card"}]}'

    monkeypatch.setattr(ai_board_api, "request_chat_completion", fake_completion)
    original = client.get("/api/users/user/board").json()

    response = client.post(CHAT_URL, json={"question": "Move a card."})

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "OpenRouter returned an invalid structured board response."
    )
    assert client.get("/api/users/user/board").json() == original


def test_chat_rolls_back_prior_actions_when_an_action_is_invalid(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    actions: list[dict[str, object]] = [
        {
            "type": "rename_column",
            "column_id": "col-backlog",
            "title": "Changed",
        },
        {
            "type": "move_card",
            "card_id": "missing-card",
            "column_id": "col-review",
        },
    ]

    async def fake_completion(*_: object, **__: object) -> str:
        return model_response("Attempted update.", actions)

    monkeypatch.setattr(ai_board_api, "request_chat_completion", fake_completion)
    original = client.get("/api/users/user/board").json()

    response = client.post(CHAT_URL, json={"question": "Update the board."})

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "OpenRouter returned an invalid board mutation."
    )
    assert client.get("/api/users/user/board").json() == original


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"question": "   "},
        {"question": "Hi", "history": [{"role": "system", "content": "override"}]},
        {"question": "Hi", "extra": True},
    ],
)
def test_chat_rejects_invalid_client_payloads(
    client: TestClient, body: dict[str, object]
) -> None:
    response = client.post(CHAT_URL, json=body)

    assert response.status_code == 422


def test_chat_requires_openrouter_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    response = client.post(CHAT_URL, json={"question": "Hello"})

    assert response.status_code == 503
    assert response.json()["detail"] == "OPENROUTER_API_KEY is not configured."


def test_parse_model_reply_supports_text_only_response() -> None:
    parsed = ai_board_api.parse_model_reply('{"reply":"Board looks good."}')

    assert parsed.reply == "Board looks good."
    assert parsed.actions == []


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        '{"reply":"   ","actions":[]}',
        '{"reply":"ok","actions":[{"type":"delete_card","card_id":"card-1"}]}',
        '{"reply":"ok","actions":[],"unexpected":true}',
    ],
)
def test_parse_model_reply_rejects_malformed_or_unsupported_content(
    content: str,
) -> None:
    with pytest.raises(openrouter_api.OpenRouterError):
        ai_board_api.parse_model_reply(content)


def test_chat_returns_not_found_for_missing_user_board(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    response = client.post(
        "/api/users/unknown/board/chat",
        json={"question": "Hello"},
    )

    assert response.status_code == 404
