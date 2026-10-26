from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="PM MVP Backend")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/hello")
def api_hello() -> dict[str, str]:
    return {"message": "Hello from the PM backend API"}


frontend_export = Path(__file__).resolve().parents[2] / "frontend" / "out"
app.mount(
    "/",
    StaticFiles(directory=frontend_export, html=True, check_dir=False),
    name="frontend",
)
