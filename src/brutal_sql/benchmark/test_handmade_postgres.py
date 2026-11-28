"""Definition of done for ANT-48 against the Docker Compose Postgres.

Never skipped: start the database with `docker compose up -d`.
"""

import dataclasses
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine

from brutal_sql.benchmark.build_handmade import build_handmade_benchmark
from brutal_sql.benchmark.expected_rows import rows_match, run_expected_sql
from brutal_sql.benchmark.format import BenchmarkRecord
from brutal_sql.benchmark.handmade import (
    SCHEMA_PREFIX,
    handmade_schema_names,
    load_handmade_benchmark,
    load_handmade_schema,
    read_schema_annotations,
)
from brutal_sql.db.connection_settings import ConnectionSettings
from brutal_sql.errors import ProcessingError
from brutal_sql.flow.annotated_graph import build_annotated_graph

pytestmark = pytest.mark.postgres
RECORDS = load_handmade_benchmark()


@pytest.fixture(scope="session")
def handmade_engine(
    postgres_settings: ConnectionSettings,
) -> Iterator[Engine]:
    """Load every hand-made schema in one session, then drop them all.

    Runs only against the local Docker test container.
    """
    engine = create_engine(postgres_settings.to_sqlalchemy_url())
    try:
        with engine.begin() as connection:
            for name in handmade_schema_names():
                load_handmade_schema(connection, name)
        yield engine
        with engine.begin() as connection:
            for name in handmade_schema_names():
                connection.exec_driver_sql(
                    f"DROP SCHEMA IF EXISTS {SCHEMA_PREFIX}{name} CASCADE"
                )
    finally:
        engine.dispose()


@pytest.mark.parametrize("record", RECORDS, ids=[record.id for record in RECORDS])
def test_expected_sql_matches_stored_rows(
    handmade_engine: Engine, record: BenchmarkRecord
) -> None:
    with handmade_engine.connect() as connection:
        actual = run_expected_sql(connection, record.expected_sql)
    assert rows_match(record.expected_rows, actual, record.ordered), record.id


def test_changed_stored_rows_do_not_match(handmade_engine: Engine) -> None:
    record = next(r for r in RECORDS if r.id == "handmade/shop-never-ordered")
    with handmade_engine.connect() as connection:
        actual = run_expected_sql(connection, record.expected_sql)
    assert not rows_match((("Mira",),), actual, record.ordered)


@pytest.mark.parametrize("name", handmade_schema_names())
def test_schema_annotations_make_a_complete_ontology(
    handmade_engine: Engine, postgres_settings: ConnectionSettings, name: str
) -> None:
    settings = dataclasses.replace(
        postgres_settings, schema_name=f"{SCHEMA_PREFIX}{name}"
    )
    graph = build_annotated_graph(settings, read_schema_annotations(name))
    assert all(node.table_type is not None for node in graph.nodes)


def test_build_handmade_benchmark_reproduces_stored_records(
    handmade_engine: Engine, postgres_settings: ConnectionSettings
) -> None:
    assert build_handmade_benchmark(postgres_settings) == RECORDS


def test_build_handmade_benchmark_masks_credentials_on_failure(
    postgres_settings: ConnectionSettings,
) -> None:
    settings = dataclasses.replace(postgres_settings, password="wrong-password-123")
    with pytest.raises(ProcessingError) as raised:
        build_handmade_benchmark(settings)
    message = f"{raised.value} {raised.value.__cause__}"
    names_database = settings.database in message
    leaks_password = "wrong-password-123" in message
    leaks_username = f'"{settings.username}"' in message
    assert names_database, "error should name the database"
    assert not leaks_password, "error must not echo the password"
    assert not leaks_username, "error must not echo the username"
