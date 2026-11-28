"""Rebuild handmade.jsonl: load every hand-made schema and store its result rows.

Run against the local Docker test database only (the schema scripts drop and
recreate their schemas)::

    set -a; source .env; set +a
    poetry run python -m brutal_sql.benchmark.build_handmade
"""

import json
import logging
import os
from collections.abc import Mapping
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from brutal_sql.benchmark.expected_rows import fill_expected_rows
from brutal_sql.benchmark.format import BenchmarkRecord, record_to_dict
from brutal_sql.benchmark.handmade import (
    HANDMADE_BENCHMARK_FILE,
    handmade_schema_names,
    load_handmade_benchmark,
    load_handmade_schema,
)
from brutal_sql.db.connection_settings import ConnectionSettings
from brutal_sql.db.credential_masking import mask_credentials
from brutal_sql.errors import ProcessingError, SanitizedDriverError
from brutal_sql.logging_config import configure_logging

logger = logging.getLogger(__name__)
REQUIRED_KEYS = ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")


def settings_from_environment(environment: Mapping[str, str]) -> ConnectionSettings:
    """Build settings for the local Postgres from POSTGRES_* variables.

    Raises ProcessingError naming each missing key (never any value).
    """
    missing = [key for key in REQUIRED_KEYS if not environment.get(key)]
    if missing:
        raise ProcessingError(f"set {', '.join(missing)} in the environment")
    return ConnectionSettings(
        host=environment.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(environment.get("POSTGRES_PORT", "5432")),
        database=environment["POSTGRES_DB"],
        schema_name="public",
        username=environment["POSTGRES_USER"],
        password=environment["POSTGRES_PASSWORD"],
    )


def write_benchmark(path: Path, records: list[BenchmarkRecord]) -> None:
    """Write records to path as JSON Lines, one record per line."""
    lines = [json.dumps(record_to_dict(record)) for record in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_handmade_benchmark(settings: ConnectionSettings) -> list[BenchmarkRecord]:
    """Load every hand-made schema, then return the records with fresh rows."""
    engine = create_engine(settings.to_sqlalchemy_url())
    try:
        with engine.begin() as connection:
            for name in handmade_schema_names():
                load_handmade_schema(connection, name)
            return fill_expected_rows(connection, load_handmade_benchmark())
    except SQLAlchemyError as error:
        detail = mask_credentials(str(error), settings)
        message = (
            f"building the hand-made benchmark on {settings.describe_database()} failed"
        )
        cause = SanitizedDriverError(f"{type(error).__name__}: {detail}")
        raise ProcessingError(f"{message}: {detail}") from cause
    finally:
        engine.dispose()


def main() -> None:
    """Rebuild handmade.jsonl with rows from the local Postgres."""
    configure_logging()
    settings = settings_from_environment(os.environ)
    records = build_handmade_benchmark(settings)
    write_benchmark(HANDMADE_BENCHMARK_FILE, records)
    logger.info("Wrote %d records to %s", len(records), HANDMADE_BENCHMARK_FILE.name)


if __name__ == "__main__":
    main()
