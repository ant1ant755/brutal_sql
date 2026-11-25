"""Fetcher tests against the Docker Compose Postgres (never skipped)."""

import pytest

from brutal_sql.db.connection_settings import ConnectionSettings
from brutal_sql.db.postgres_fetcher import fetch_schema_tables

pytestmark = pytest.mark.postgres


def test_fetch_schema_tables_reads_shop_metadata(
    shop_schema: ConnectionSettings,
) -> None:
    tables = {table.name: table for table in fetch_schema_tables(shop_schema)}
    assert sorted(tables) == ["customer", "order_items", "orders", "products"]
    orders = tables["orders"]
    assert [column.name for column in orders.columns] == [
        "id",
        "customer_id",
        "ordered_at",
    ]
    assert orders.primary_key == ("id",)
    assert ("customer_id",) in [index.column_names for index in orders.indexes]
    (key,) = orders.foreign_keys
    assert (key.referred_schema, key.referred_table) == ("ant8_shop", "customer")
    assert key.referred_column_names == ("id",)
    customer = tables["customer"]
    assert customer.columns[1].comment == "customer name"
    assert any(index.unique for index in customer.indexes)
    assert len(tables["order_items"].foreign_keys) == 2
