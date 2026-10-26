import os
import re

import pytest
from fastapi.testclient import TestClient

CONNECTIVITY_URL = "/api/ai/connectivity"

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_OPENROUTER_INTEGRATION") != "1"
    or not os.getenv("OPENROUTER_API_KEY"),
    reason="Set RUN_OPENROUTER_INTEGRATION=1 and OPENROUTER_API_KEY to call OpenRouter.",
)


def test_openrouter_connectivity_with_live_provider(client: TestClient) -> None:
    response = client.post(CONNECTIVITY_URL)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["model"] == "openai/gpt-oss-120b"
    assert isinstance(payload["response"], str)
    assert payload["response"].strip()
    assert re.search(r"\b4\b", payload["response"])
