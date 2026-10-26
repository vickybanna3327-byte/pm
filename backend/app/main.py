import os
from contextlib import asynccontextmanager
from pathlib import Path
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.app.board_api import router as board_router
from backend.app.database import connect_database, initialize_database

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_EXPORT = REPOSITORY_ROOT / "frontend" / "out"
DEFAULT_DATABASE = REPOSITORY_ROOT / "data" / "pm.db"


def database_path() -> Path:
    return Path(os.environ.get("PM_DATABASE_PATH", DEFAULT_DATABASE))


def create_app(database: Path | None = None) -> FastAPI:
    selected_database = database or database_path()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        initialize_database(selected_database)
        yield

    app = FastAPI(title="PM MVP Backend", lifespan=lifespan)
    app.state.database_path = selected_database
    app.include_router(board_router)

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
