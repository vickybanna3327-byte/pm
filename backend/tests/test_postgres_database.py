from backend.app.database import (
    PostgresConnection,
    _postgres_statement,
    database_integrity_errors,
)


class FakeCursor:
    rowcount = 1


class FakeConnection:
    def __init__(self) -> None:
        self.statements: list[tuple[str, tuple[object, ...]]] = []
        self.commits = 0
        self.rollbacks = 0

    def execute(
        self, statement: str, parameters: tuple[object, ...] = ()
    ) -> FakeCursor:
        self.statements.append((statement, parameters))
        return FakeCursor()

    def cursor(self) -> "FakeConnection":
        return self

    def executemany(
        self,
        statement: str,
        parameters: list[tuple[object, ...]],
    ) -> FakeCursor:
        self.statements.append((statement, tuple(parameters[0])))
        return FakeCursor()

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        pass


def test_postgres_sql_adapts_parameters_and_conflict_handling() -> None:
    statement = _postgres_statement(
        "INSERT OR IGNORE INTO users (id, created_at) VALUES (?, CURRENT_TIMESTAMP)"
    )

    assert statement == (
        "INSERT INTO users (id, created_at) "
        "VALUES (%s, (CURRENT_TIMESTAMP::text)) ON CONFLICT DO NOTHING"
    )


def test_postgres_connection_serializes_write_and_commits() -> None:
    raw_connection = FakeConnection()
    connection = PostgresConnection(raw_connection)

    with connection:
        connection.begin_immediate("rate-limit:key")

    assert raw_connection.statements == [
        ("SELECT pg_advisory_xact_lock(hashtext(%s))", ("rate-limit:key",))
    ]
    assert raw_connection.commits == 1
    assert raw_connection.rollbacks == 0


def test_postgres_connection_rolls_back_on_error() -> None:
    raw_connection = FakeConnection()

    try:
        with PostgresConnection(raw_connection):
            raise RuntimeError("fail transaction")
    except RuntimeError:
        pass

    assert raw_connection.commits == 0
    assert raw_connection.rollbacks == 1


def test_database_integrity_errors_include_postgres() -> None:
    import psycopg
    import sqlite3

    errors = database_integrity_errors()

    assert sqlite3.IntegrityError in errors
    assert psycopg.IntegrityError in errors
