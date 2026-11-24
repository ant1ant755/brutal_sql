"""Tests for fetching and saving a Postgres schema snapshot.

Tests marked ``integration`` need the Docker Compose Postgres
(``docker compose up -d``).
The rest run without a database.
"""

from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from brutal_sql.db.conftest import (
    TEST_DATABASE_NAME,
    TEST_SCHEMA_NAME,
    PostgresSettings,
)
from brutal_sql.db.schema_fetcher import (
    DatabaseConnectionError,
    SchemaNotFoundError,
    fetch_and_save_schema,
    fetch_schema_details,
)
from brutal_sql.db.schema_model import PostgresSchemaObject


def credentials_free_url(settings: PostgresSettings, database: str) -> str:
    """Return the test database URL as a string, without credentials."""
    return settings.url_for(database, with_credentials=False).render_as_string()


# fetch_and_save_schema: bad URLs caught before connecting


@pytest.mark.parametrize(
    "bad_url",
    [
        "not a url",
        "",
        "mysql+pymysql://localhost/test",
        "sqlite:///x.db",
        "postgresql+nosuchdriver://localhost/test",
    ],
)
def test_unusable_url_raises_connection_error(bad_url: str, tmp_path: Path) -> None:
    with pytest.raises(DatabaseConnectionError):
        fetch_and_save_schema(bad_url, "user", "s3cret-pw", "shop", tmp_path)
    assert list(tmp_path.iterdir()) == []


# Integration: positive


@pytest.mark.integration
def test_fetch_and_save_captures_whole_shop_schema(
    shop_database: Engine, postgres_settings: PostgresSettings, tmp_path: Path
) -> None:
    file_path = fetch_and_save_schema(
        credentials_free_url(postgres_settings, TEST_DATABASE_NAME),
        postgres_settings.username,
        postgres_settings.password,
        TEST_SCHEMA_NAME,
        tmp_path,
    )
    assert file_path.is_file() and file_path.parent == tmp_path.resolve()
    snapshot = PostgresSchemaObject.load_from_file(file_path)
    assert snapshot.database_name == TEST_DATABASE_NAME
    assert snapshot.schema_name == TEST_SCHEMA_NAME
    assert [table.name for table in snapshot.tables] == [
        "customers",
        "order_items",
        "orders",
        "products",
    ]
    assert postgres_settings.password not in file_path.read_text()


@pytest.mark.integration
def test_snapshot_has_primary_and_unique_keys(
    shop_database: Engine, postgres_settings: PostgresSettings
) -> None:
    snapshot = fetch_schema_details(shop_database, TEST_SCHEMA_NAME)
    customers = snapshot.find_table("customers")
    assert customers.primary_key is not None
    assert customers.primary_key.column_names == ["id"]
    assert [key.column_names for key in customers.unique_constraints] == [["email"]]
    order_items = snapshot.find_table("order_items")
    assert order_items.primary_key is not None
    assert order_items.primary_key.column_names == ["order_id", "product_id"]
    assert snapshot.find_table("products").unique_constraints[0].name == (
        "products_sku_key"
    )


@pytest.mark.integration
def test_snapshot_has_foreign_keys(shop_database: Engine) -> None:
    snapshot = fetch_schema_details(shop_database, TEST_SCHEMA_NAME)
    (order_to_customer,) = snapshot.find_table("orders").foreign_keys
    assert order_to_customer.column_names == ["customer_id"]
    assert order_to_customer.referred_table == "customers"
    assert order_to_customer.referred_column_names == ["id"]
    assert order_to_customer.on_delete == "CASCADE"
    item_keys = snapshot.find_table("order_items").foreign_keys
    assert sorted(key.referred_table for key in item_keys) == ["orders", "products"]


@pytest.mark.integration
def test_snapshot_has_indexes_and_columns(shop_database: Engine) -> None:
    orders = fetch_schema_details(shop_database, TEST_SCHEMA_NAME).find_table("orders")
    indexes = {index.name: index for index in orders.indexes}
    assert indexes["orders_placed_at_idx"].column_names == ["placed_at"]
    assert indexes["orders_customer_status_idx"].column_names == [
        "customer_id",
        "status",
    ]
    assert not indexes["orders_placed_at_idx"].is_unique
    columns = {column.name: column for column in orders.columns}
    assert "order_status" in columns["status"].data_type
    assert columns["paid_with"].is_nullable and not columns["status"].is_nullable
    assert columns["status"].default is not None


@pytest.mark.integration
def test_expression_index_keeps_its_expression(shop_database: Engine) -> None:
    customers = fetch_schema_details(shop_database, TEST_SCHEMA_NAME).find_table(
        "customers"
    )
    indexes = {index.name: index for index in customers.indexes}
    (expression,) = indexes["customers_lower_name_idx"].column_names
    assert "lower" in expression and "full_name" in expression


@pytest.mark.integration
def test_snapshot_has_enums_in_order(shop_database: Engine) -> None:
    snapshot = fetch_schema_details(shop_database, TEST_SCHEMA_NAME)
    assert [enum.name for enum in snapshot.enums] == ["order_status", "payment_method"]
    assert snapshot.find_enum("order_status").values == [
        "pending",
        "shipped",
        "delivered",
    ]


@pytest.mark.integration
def test_self_referencing_foreign_key(shop_database: Engine) -> None:
    customers = fetch_schema_details(shop_database, TEST_SCHEMA_NAME).find_table(
        "customers"
    )
    (referral,) = customers.foreign_keys
    assert referral.column_names == ["referred_by"]
    assert referral.referred_table == "customers"


@pytest.mark.integration
def test_empty_schema_gives_empty_snapshot(shop_database: Engine) -> None:
    with shop_database.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS empty_shop"))
    try:
        snapshot = fetch_schema_details(shop_database, "empty_shop")
    finally:
        with shop_database.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS empty_shop CASCADE"))
    assert snapshot.tables == [] and snapshot.enums == []


# Integration: negative


def assert_fails_cleanly(
    error_class: type[Exception],
    url: str,
    username: str,
    password: str,
    schema_name: str,
    staging_folder: Path,
) -> None:
    """Assert the fetch raises ``error_class``, hides the password, saves nothing."""
    with pytest.raises(error_class) as raised:
        fetch_and_save_schema(url, username, password, schema_name, staging_folder)
    assert password not in str(raised.value)
    assert list(staging_folder.iterdir()) == []


@pytest.mark.integration
def test_wrong_password_raises_connection_error(
    shop_database: Engine, postgres_settings: PostgresSettings, tmp_path: Path
) -> None:
    url = credentials_free_url(postgres_settings, TEST_DATABASE_NAME)
    assert_fails_cleanly(
        DatabaseConnectionError,
        url,
        postgres_settings.username,
        "definitely-wrong-password",
        TEST_SCHEMA_NAME,
        tmp_path,
    )


@pytest.mark.integration
def test_wrong_username_raises_connection_error(
    shop_database: Engine, postgres_settings: PostgresSettings, tmp_path: Path
) -> None:
    url = credentials_free_url(postgres_settings, TEST_DATABASE_NAME)
    assert_fails_cleanly(
        DatabaseConnectionError,
        url,
        "no_such_user",
        postgres_settings.password,
        TEST_SCHEMA_NAME,
        tmp_path,
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    "bad_url",
    [
        "postgresql+psycopg://127.0.0.1:1/test",  # nothing listens on port 1
        "postgresql+psycopg://no-such-host.invalid:5432/test",
    ],
)
def test_wrong_host_or_port_raises_connection_error(
    bad_url: str, postgres_settings: PostgresSettings, tmp_path: Path
) -> None:
    assert_fails_cleanly(
        DatabaseConnectionError,
        bad_url,
        postgres_settings.username,
        postgres_settings.password,
        TEST_SCHEMA_NAME,
        tmp_path,
    )


@pytest.mark.integration
def test_wrong_database_name_raises_connection_error(
    shop_database: Engine, postgres_settings: PostgresSettings, tmp_path: Path
) -> None:
    assert_fails_cleanly(
        DatabaseConnectionError,
        credentials_free_url(postgres_settings, "no_such_database"),
        postgres_settings.username,
        postgres_settings.password,
        TEST_SCHEMA_NAME,
        tmp_path,
    )


@pytest.mark.integration
def test_wrong_schema_raises_schema_not_found(
    shop_database: Engine, postgres_settings: PostgresSettings, tmp_path: Path
) -> None:
    assert_fails_cleanly(
        SchemaNotFoundError,
        credentials_free_url(postgres_settings, TEST_DATABASE_NAME),
        postgres_settings.username,
        postgres_settings.password,
        "no_such_schema",
        tmp_path,
    )


@pytest.mark.integration
def test_fetch_schema_details_raises_for_missing_schema(
    shop_database: Engine,
) -> None:
    with pytest.raises(SchemaNotFoundError, match="no_such_schema"):
        fetch_schema_details(shop_database, "no_such_schema")
