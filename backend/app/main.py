import os
from contextlib import asynccontextmanager
from pathlib import Path
from collections.abc import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.app.auth_api import router as auth_router
from backend.app.board_api import project_router as project_board_router
from backend.app.board_api import router as board_router
from backend.app.ai_board_api import project_router as project_ai_board_router
from backend.app.ai_board_api import router as ai_board_router
from backend.app.database import connect_database, initialize_database
from backend.app.openrouter_api import router as openrouter_router
from backend.app.workspace_api import router as workspace_router

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_EXPORT = REPOSITORY_ROOT / "frontend" / "out"
DEFAULT_DATABASE = REPOSITORY_ROOT / "data" / "pm.db"
load_dotenv(REPOSITORY_ROOT / ".env")


def database_path() -> Path | str:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        return database_url
    return Path(os.environ.get("PM_DATABASE_PATH", DEFAULT_DATABASE))


def create_app(database: Path | str | None = None) -> FastAPI:
    selected_database = database if database is not None else database_path()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        initialize_database(selected_database)
        yield

    app = FastAPI(title="PM MVP Backend", lifespan=lifespan)
    app.state.database_path = selected_database
    app.include_router(auth_router)
    app.include_router(board_router)
    app.include_router(project_board_router)
    app.include_router(ai_board_router)
    app.include_router(project_ai_board_router)
    app.include_router(openrouter_router)
    app.include_router(workspace_router)

    def database_connection():
        connection = connect_database(selected_database)
        try:
            yield connection
        finally:
            connection.close()

    app.dependency_overrides[connect_database] = database_connection

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/hello")
    def api_hello() -> dict[str, str]:
        return {"message": "Hello from the PM backend API"}

    app.mount(
        "/",
        StaticFiles(directory=FRONTEND_EXPORT, html=True, check_dir=False),
        name="frontend",
    )
    return app


app = create_app()
