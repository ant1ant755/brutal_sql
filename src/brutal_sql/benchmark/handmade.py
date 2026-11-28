"""The hand-made question set: its schema scripts, annotations and records.

Each schema ``handmade_<name>`` has ``handmade/<name>.sql`` (drops and recreates
the schema with its rows) and ``handmade/<name>.annotations.json`` (table types
and verbs). The questions are in ``handmade/handmade.jsonl``. Everything in the
folder is original work under the repository's MIT licence.
"""

import json
from pathlib import Path
from typing import Any

from sqlalchemy import Connection

from brutal_sql.benchmark.format import BenchmarkFormatError, BenchmarkRecord
from brutal_sql.benchmark.loader import load_benchmark

HANDMADE_DIRECTORY = Path(__file__).with_name("handmade")
HANDMADE_BENCHMARK_FILE = HANDMADE_DIRECTORY / "handmade.jsonl"
SCHEMA_PREFIX = "handmade_"


def handmade_schema_names() -> list[str]:
    """Return the short name of every hand-made schema, e.g. ["school", "shop"]."""
    return sorted(path.stem for path in HANDMADE_DIRECTORY.glob("*.sql"))


def _schema_file(name: str, suffix: str) -> Path:
    """Return handmade/<name><suffix>; raise BenchmarkFormatError if unknown."""
    if name not in handmade_schema_names():
        raise BenchmarkFormatError(
            f"unknown hand-made schema {name!r}, "
            f"expected one of {', '.join(handmade_schema_names())}"
        )
    return HANDMADE_DIRECTORY / f"{name}{suffix}"


def read_schema_script(name: str) -> str:
    """Return the SQL that drops, recreates and fills schema handmade_<name>."""
    return _schema_file(name, ".sql").read_text(encoding="utf-8")


def read_schema_annotations(name: str) -> dict[str, Any]:
    """Return the ontology annotations of schema handmade_<name>."""
    text = _schema_file(name, ".annotations.json").read_text(encoding="utf-8")
    return json.loads(text)


def load_handmade_schema(connection: Connection, name: str) -> None:
    """Drop and recreate schema handmade_<name> with its rows.

    Destructive: run it only against the local Docker test database.
    """
    connection.exec_driver_sql(read_schema_script(name))


def load_handmade_benchmark() -> list[BenchmarkRecord]:
    """Return the hand-made benchmark records."""
    return load_benchmark(HANDMADE_BENCHMARK_FILE)
