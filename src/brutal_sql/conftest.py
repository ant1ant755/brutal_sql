"""Shared fixtures for tests that use the Docker Compose Postgres.

These tests are never skipped: if the container is down they fail.
Start it with `docker compose up -d`.
"""

import dataclasses
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from brutal_sql.db.connection_settings import ConnectionSettings

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
SHOP_SCHEMA = "ant8_shop"
SHOP_DDL = [
    f"DROP SCHEMA IF EXISTS {SHOP_SCHEMA} CASCADE",
    f"CREATE SCHEMA {SHOP_SCHEMA}",
    f"""CREATE TABLE {SHOP_SCHEMA}.customer (
        id serial PRIMARY KEY, full_name text NOT NULL, email text UNIQUE)""",
    f"COMMENT ON COLUMN {SHOP_SCHEMA}.customer.full_name IS 'customer name'",
    f"""CREATE TABLE {SHOP_SCHEMA}.products (
        id serial PRIMARY KEY, title text NOT NULL, unit_price numeric(10, 2))""",
    f"COMMENT ON COLUMN {SHOP_SCHEMA}.products.unit_price IS 'price per unit'",
    f"""CREATE TABLE {SHOP_SCHEMA}.orders (
        id serial PRIMARY KEY,
        customer_id integer NOT NULL REFERENCES {SHOP_SCHEMA}.customer (id),
        ordered_at timestamptz)""",
    f"CREATE INDEX orders_customer_id_idx ON {SHOP_SCHEMA}.orders (customer_id)",
    f"""CREATE TABLE {SHOP_SCHEMA}.order_items (
        id serial PRIMARY KEY,
        order_id integer NOT NULL REFERENCES {SHOP_SCHEMA}.orders (id),
        product_id integer NOT NULL REFERENCES {SHOP_SCHEMA}.products (id),
        quantity integer NOT NULL)""",
    f"COMMENT ON COLUMN {SHOP_SCHEMA}.order_items.quantity IS 'number of units'",
]


def read_env_file(path: Path) -> dict[str, str]:
    """Return KEY=VALUE pairs from a .env file, ignoring blanks and comments."""
    if not path.is_file():
        return {}
    pairs = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            pairs[key.strip()] = value.strip().strip("'\"")
    return pairs


def postgres_value(key: str, file_values: dict[str, str]) -> str:
    """Return a POSTGRES_* value from the environment, else from .env."""
    value = os.environ.get(key) or file_values.get(key)
    if not value:
        pytest.fail(f"{key} is not set in the environment or .env", pytrace=False)
    return value


@pytest.fixture(scope="session")
def postgres_settings() -> ConnectionSettings:
    """Settings for the Docker Compose Postgres, pointing at the shop schema."""
    file_values = read_env_file(ENV_FILE)
    return ConnectionSettings(
        host="127.0.0.1",
        port=int(
            os.environ.get("POSTGRES_PORT") or file_values.get("POSTGRES_PORT") or 5432
        ),
        database=postgres_value("POSTGRES_DB", file_values),
        schema_name=SHOP_SCHEMA,
        username=postgres_value("POSTGRES_USER", file_values),
        password=postgres_value("POSTGRES_PASSWORD", file_values),
    )


@pytest.fixture(scope="session")
def shop_schema(postgres_settings: ConnectionSettings) -> Iterator[ConnectionSettings]:
    """Create the shop schema (customer, products, orders, order_items), then drop it.

    Runs only against the local Docker test container.
    """
    engine = create_engine(postgres_settings.to_sqlalchemy_url())
    try:
        with engine.begin() as connection:
            for statement in SHOP_DDL:
                connection.exec_driver_sql(statement)
        yield postgres_settings
        with engine.begin() as connection:
            connection.exec_driver_sql(SHOP_DDL[0])
    finally:
        engine.dispose()


STAFF_SCHEMA = "ant9_staff"
STAFF_DDL = [
    f"DROP SCHEMA IF EXISTS {STAFF_SCHEMA} CASCADE",
    f"CREATE SCHEMA {STAFF_SCHEMA}",
    f"""CREATE TABLE {STAFF_SCHEMA}.department (
        id serial PRIMARY KEY, title text NOT NULL)""",
    f"""CREATE TABLE {STAFF_SCHEMA}.employee (
        id integer PRIMARY KEY,
        manager_id integer REFERENCES {STAFF_SCHEMA}.employee (id),
        name text NOT NULL,
        department_id integer REFERENCES {STAFF_SCHEMA}.department (id))""",
    f"COMMENT ON COLUMN {STAFF_SCHEMA}.employee.name IS 'employee name'",
    f"""INSERT INTO {STAFF_SCHEMA}.employee (id, manager_id, name) VALUES
        (1, NULL, 'alice'), (2, 1, 'bob'), (3, 2, 'rom'), (4, 2, 'rogue')""",
]


@pytest.fixture(scope="session")
def staff_schema(postgres_settings: ConnectionSettings) -> Iterator[ConnectionSettings]:
    """Create the staff schema (department, self-referencing employee), then drop it.

    Runs only against the local Docker test container.
    """
    settings = dataclasses.replace(postgres_settings, schema_name=STAFF_SCHEMA)
    engine = create_engine(settings.to_sqlalchemy_url())
    try:
        with engine.begin() as connection:
            for statement in STAFF_DDL:
                connection.exec_driver_sql(statement)
        yield settings
        with engine.begin() as connection:
            connection.exec_driver_sql(STAFF_DDL[0])
    finally:
        engine.dispose()
