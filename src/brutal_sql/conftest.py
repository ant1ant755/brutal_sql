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


LINES_SCHEMA = "ant10_lines"
LINES_DDL = [
    f"DROP SCHEMA IF EXISTS {LINES_SCHEMA} CASCADE",
    f"CREATE SCHEMA {LINES_SCHEMA}",
    f"""CREATE TABLE {LINES_SCHEMA}.order_lines (
        order_id integer NOT NULL, line_no integer NOT NULL, sku text NOT NULL,
        PRIMARY KEY (order_id, line_no))""",
    f"""CREATE TABLE {LINES_SCHEMA}.shipments (
        id integer PRIMARY KEY, order_id integer NOT NULL, line_no integer NOT NULL,
        FOREIGN KEY (order_id, line_no)
            REFERENCES {LINES_SCHEMA}.order_lines (order_id, line_no))""",
    f"""INSERT INTO {LINES_SCHEMA}.order_lines (order_id, line_no, sku) VALUES
        (7, 1, 'pen'), (7, 2, 'ink'), (7, 3, 'pad'), (8, 2, 'cup')""",
    f"INSERT INTO {LINES_SCHEMA}.shipments (id, order_id, line_no) VALUES (1, 7, 2)",
]


@pytest.fixture(scope="session")
def lines_schema(postgres_settings: ConnectionSettings) -> Iterator[ConnectionSettings]:
    """Create the lines schema (shipments -> order_lines on two columns), then drop it.

    Runs only against the local Docker test container.
    """
    settings = dataclasses.replace(postgres_settings, schema_name=LINES_SCHEMA)
    engine = create_engine(settings.to_sqlalchemy_url())
    try:
        with engine.begin() as connection:
            for statement in LINES_DDL:
                connection.exec_driver_sql(statement)
        yield settings
        with engine.begin() as connection:
            connection.exec_driver_sql(LINES_DDL[0])
    finally:
        engine.dispose()


BILLING_SCHEMA = "ant11_billing"
BILLING_DDL = [
    f"DROP SCHEMA IF EXISTS {BILLING_SCHEMA} CASCADE",
    f"CREATE SCHEMA {BILLING_SCHEMA}",
    f"CREATE TABLE {BILLING_SCHEMA}.address (id integer PRIMARY KEY, city text)",
    f"""CREATE TABLE {BILLING_SCHEMA}.orders (
        id integer PRIMARY KEY,
        billing_address_id integer NOT NULL
            CONSTRAINT orders_billing_fkey REFERENCES {BILLING_SCHEMA}.address (id),
        shipping_address_id integer
            CONSTRAINT orders_shipping_fkey
            REFERENCES {BILLING_SCHEMA}.address (id))""",
    f"""CREATE TABLE {BILLING_SCHEMA}.complaints (
        id integer PRIMARY KEY,
        order_id integer REFERENCES {BILLING_SCHEMA}.orders (id))""",
]


@pytest.fixture(scope="session")
def billing_schema(
    postgres_settings: ConnectionSettings,
) -> Iterator[ConnectionSettings]:
    """Create the billing schema (orders -> address twice, complaints), then drop it.

    Runs only against the local Docker test container.
    """
    settings = dataclasses.replace(postgres_settings, schema_name=BILLING_SCHEMA)
    engine = create_engine(settings.to_sqlalchemy_url())
    try:
        with engine.begin() as connection:
            for statement in BILLING_DDL:
                connection.exec_driver_sql(statement)
        yield settings
        with engine.begin() as connection:
            connection.exec_driver_sql(BILLING_DDL[0])
    finally:
        engine.dispose()


JOINS_SHOP_SCHEMA = "joins_shop"
JOINS = JOINS_SHOP_SCHEMA
JOINS_SHOP_DDL = [
    f"DROP SCHEMA IF EXISTS {JOINS} CASCADE",
    f"CREATE SCHEMA {JOINS}",
    f"""CREATE TABLE {JOINS}.customer (
        id integer PRIMARY KEY, name text, country text)""",
    f"""CREATE TABLE {JOINS}.products (
        id integer PRIMARY KEY, title text, category text,
        unit_price numeric(10, 2))""",
    f"""CREATE TABLE {JOINS}.orders (
        id integer PRIMARY KEY,
        customer_id integer NOT NULL REFERENCES {JOINS}.customer (id),
        ordered_at timestamptz, total_amount numeric(10, 2))""",
    f"""CREATE TABLE {JOINS}.order_items (
        id integer PRIMARY KEY,
        order_id integer NOT NULL REFERENCES {JOINS}.orders (id),
        product_id integer NOT NULL REFERENCES {JOINS}.products (id),
        quantity integer)""",
    f"""CREATE TABLE {JOINS}.complaints (
        id integer PRIMARY KEY,
        customer_id integer NOT NULL REFERENCES {JOINS}.customer (id),
        order_id integer REFERENCES {JOINS}.orders (id), created_at timestamptz)""",
    f"""CREATE TABLE {JOINS}.employee (
        id integer PRIMARY KEY, name text,
        manager_id integer REFERENCES {JOINS}.employee (id))""",
    f"""INSERT INTO {JOINS}.customer VALUES
        (1, 'Alice', 'UK'), (2, 'Bob', 'FR'), (3, 'Carol', 'DE')""",
    f"""INSERT INTO {JOINS}.products VALUES (1, 'Pen', 'office', 1.50),
        (2, 'Notebook', 'office', 4.00), (3, 'Lamp', 'home', 25.00)""",
    f"""INSERT INTO {JOINS}.orders VALUES (10, 1, '2026-01-05', 7.00),
        (11, 1, '2026-02-10', 7.50), (12, 3, '2026-03-15', 0.00)""",
    f"""INSERT INTO {JOINS}.order_items VALUES
        (100, 10, 1, 2), (101, 10, 2, 1), (102, 11, 1, 5)""",
    f"""INSERT INTO {JOINS}.complaints VALUES
        (1000, 1, 10, '2026-01-07'), (1001, 2, NULL, '2026-02-01')""",
    f"""INSERT INTO {JOINS}.employee VALUES
        (1, 'Ada', NULL), (2, 'Grace', 1), (3, 'Linus', 2)""",
]


@pytest.fixture(scope="session")
def joins_shop_schema(
    postgres_settings: ConnectionSettings,
) -> Iterator[ConnectionSettings]:
    """Create the joins_shop schema with rows for every join case, then drop it.

    Which row covers which case:
    - customer with no orders: customer 2 (Bob)
    - customer with several orders: customer 1 (Alice), orders 10 and 11
    - order with no items, its customer's only order: order 12 (Carol, customer 3)
    - order with several items: order 10 (items 100 and 101)
    - order with no complaints: order 11; order with a complaint: order 10 (1000)
    - complaint with no order: complaint 1001 (Bob, order_id NULL)
    - product never ordered: product 3 (Lamp)
    - top-level employee: 1 (Ada); manager: 2 (Grace, manages Linus; Ada
      manages Grace); employee who manages no one: 3 (Linus)

    Runs only against the local Docker test container.
    """
    settings = dataclasses.replace(postgres_settings, schema_name=JOINS_SHOP_SCHEMA)
    engine = create_engine(settings.to_sqlalchemy_url())
    try:
        with engine.begin() as connection:
            for statement in JOINS_SHOP_DDL:
                connection.exec_driver_sql(statement)
        yield settings
        with engine.begin() as connection:
            connection.exec_driver_sql(JOINS_SHOP_DDL[0])
    finally:
        engine.dispose()
