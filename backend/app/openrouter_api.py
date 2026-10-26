import os

import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/ai", tags=["ai"])

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-oss-120b"
CONNECTIVITY_PROMPT = "What is 2 + 2? Reply with the answer only."


class OpenRouterError(Exception):
    pass


async def request_completion(api_key: str, prompt: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENROUTER_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": OPENROUTER_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
    except httpx.TimeoutException as error:
        raise OpenRouterError("The OpenRouter request timed out.") from error
    except httpx.RequestError as error:
        raise OpenRouterError("Could not connect to OpenRouter.") from error

    if response.status_code in (401, 403):
        raise OpenRouterError("OpenRouter rejected the API key.")
    if response.is_error:
        raise OpenRouterError(
            f"OpenRouter returned HTTP {response.status_code}."
        )

    try:
        payload = response.json()
        choices = payload["choices"]
        message = choices[0]["message"]
        content = message["content"]
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise OpenRouterError(
            "OpenRouter returned an invalid chat completion response."
        ) from error

    if not isinstance(content, str) or not content.strip():
        raise OpenRouterError(
            "OpenRouter returned an invalid chat completion response."
        )
    return content.strip()


@router.post("/connectivity")
async def check_connectivity() -> dict[str, str]:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENROUTER_API_KEY is not configured.",
        )

    try:
        answer = await request_completion(api_key, CONNECTIVITY_PROMPT)
    except OpenRouterError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    return {"model": OPENROUTER_MODEL, "response": answer}
