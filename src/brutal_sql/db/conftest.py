"""Fixtures for integration tests against the local Docker Compose Postgres.

Connection settings come from ``POSTGRES_*`` environment variables, falling back to
the repo's ``.env`` file. The fixtures create a ``test`` database holding a ``shop``
schema, and drop the schema afterwards. Only ever point these at the local test
container: the teardown runs ``DROP SCHEMA ... CASCADE``.
"""

import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import URL, Engine, create_engine, text
from sqlalchemy.exc import OperationalError

REPO_ROOT = Path(__file__).resolve().parents[3]
TEST_DATABASE_NAME = "test"
TEST_SCHEMA_NAME = "shop"

SHOP_SCHEMA_STATEMENTS = [
    f"DROP SCHEMA IF EXISTS {TEST_SCHEMA_NAME} CASCADE",
    f"CREATE SCHEMA {TEST_SCHEMA_NAME}",
    "CREATE TYPE shop.order_status AS ENUM ('pending', 'shipped', 'delivered')",
    "CREATE TYPE shop.payment_method AS ENUM ('card', 'cash')",
    """CREATE TABLE shop.customers (
        id SERIAL PRIMARY KEY,
        email VARCHAR(200) NOT NULL UNIQUE,
        full_name TEXT NOT NULL,
        referred_by INTEGER REFERENCES shop.customers (id))""",
    """CREATE TABLE shop.products (
        id SERIAL PRIMARY KEY,
        sku VARCHAR(40) NOT NULL,
        price NUMERIC(10, 2) NOT NULL DEFAULT 0,
        CONSTRAINT products_sku_key UNIQUE (sku))""",
    """CREATE TABLE shop.orders (
        id SERIAL PRIMARY KEY,
        customer_id INTEGER NOT NULL
            REFERENCES shop.customers (id) ON DELETE CASCADE,
        status shop.order_status NOT NULL DEFAULT 'pending',
        paid_with shop.payment_method,
        placed_at TIMESTAMPTZ NOT NULL DEFAULT now())""",
    "CREATE INDEX orders_placed_at_idx ON shop.orders (placed_at)",
    "CREATE INDEX customers_lower_name_idx ON shop.customers (lower(full_name))",
    "CREATE INDEX orders_customer_status_idx ON shop.orders (customer_id, status)",
    """CREATE TABLE shop.order_items (
        order_id INTEGER NOT NULL REFERENCES shop.orders (id),
        product_id INTEGER NOT NULL REFERENCES shop.products (id),
        quantity INTEGER NOT NULL,
        PRIMARY KEY (order_id, product_id))""",
]


@dataclass(frozen=True)
class PostgresSettings:
    """Connection settings for the local Postgres container."""

    host: str
    port: int
    username: str
    password: str
    admin_database: str

    def url_for(self, database: str, with_credentials: bool = True) -> URL:
        """Return a psycopg URL for ``database``, with or without credentials."""
        return URL.create(
            "postgresql+psycopg",
            username=self.username if with_credentials else None,
            password=self.password if with_credentials else None,
            host=self.host,
            port=self.port,
            database=database,
        )


def read_env_file(path: Path) -> dict[str, str]:
    """Parse simple ``KEY=value`` lines from a .env file; missing file → empty."""
    if not path.is_file():
        return {}
    settings = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            settings[key.strip()] = value.strip().strip("'\"")
    return settings


def _setting(name: str, env_file: dict[str, str], default: str | None = None) -> str:
    """Return a setting from the environment, then .env, then the default."""
    value = os.environ.get(name) or env_file.get(name) or default
    if value is None:
        pytest.fail(f"{name} is not set. Copy .env.example to .env and fill it in.")
    return value


@pytest.fixture(scope="session")
def postgres_settings() -> PostgresSettings:
    """Settings for the Docker Compose Postgres, from the environment or .env."""
    env_file = read_env_file(REPO_ROOT / ".env")
    return PostgresSettings(
        host=_setting("POSTGRES_HOST", env_file, "127.0.0.1"),
        port=int(_setting("POSTGRES_PORT", env_file, "5432")),
        username=_setting("POSTGRES_USER", env_file),
        password=_setting("POSTGRES_PASSWORD", env_file),
        admin_database=_setting("POSTGRES_DB", env_file),
    )


def _create_test_database(settings: PostgresSettings) -> None:
    """Create the ``test`` database if it does not exist yet."""
    engine = create_engine(
        settings.url_for(settings.admin_database), isolation_level="AUTOCOMMIT"
    )
    try:
        with engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": TEST_DATABASE_NAME},
            ).scalar()
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{TEST_DATABASE_NAME}"'))
    except OperationalError as error:
        pytest.fail(
            f"Local Postgres is not reachable; run `docker compose up -d`.\n{error}"
        )
    finally:
        engine.dispose()


@pytest.fixture(scope="module")
def shop_database(postgres_settings: PostgresSettings) -> Iterator[Engine]:
    """Create the ``test`` database and a fresh ``shop`` schema; drop it afterwards."""
    _create_test_database(postgres_settings)
    engine = create_engine(postgres_settings.url_for(TEST_DATABASE_NAME))
    with engine.begin() as connection:
        for statement in SHOP_SCHEMA_STATEMENTS:
            connection.execute(text(statement))
    yield engine
    with engine.begin() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA_NAME} CASCADE"))
    engine.dispose()
