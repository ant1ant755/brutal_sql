"""Definition of done for ANT-14: the joins_shop fixture and its seeded cases.

Never skipped: start the database with `docker compose up -d`.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.exc import IntegrityError

from brutal_sql.db.connection_settings import ConnectionSettings
from brutal_sql.flow import fetch_schema_graph

pytestmark = pytest.mark.postgres

TABLES = ["complaints", "customer", "employee", "order_items", "orders", "products"]
FOREIGN_KEYS = {
    ("complaints", "customer_id", "customer", "id"),
    ("complaints", "order_id", "orders", "id"),
    ("employee", "manager_id", "employee", "id"),
    ("order_items", "order_id", "orders", "id"),
    ("order_items", "product_id", "products", "id"),
    ("orders", "customer_id", "customer", "id"),
}
FOREIGN_KEYS_SQL = """
    SELECT source.table_name, source.column_name, target.table_name,
           target.column_name
    FROM information_schema.referential_constraints AS ref
    JOIN information_schema.key_column_usage AS source
      ON source.constraint_schema = ref.constraint_schema
     AND source.constraint_name = ref.constraint_name
    JOIN information_schema.key_column_usage AS target
      ON target.constraint_schema = ref.unique_constraint_schema
     AND target.constraint_name = ref.unique_constraint_name
     AND target.ordinal_position = source.position_in_unique_constraint
    WHERE ref.constraint_schema = :schema
"""


@pytest.fixture(scope="module")
def connection(joins_shop_schema: ConnectionSettings) -> Iterator[Connection]:
    engine = create_engine(joins_shop_schema.to_sqlalchemy_url())
    try:
        with engine.connect() as open_connection:
            open_connection.exec_driver_sql("SET search_path TO joins_shop")
            yield open_connection
    finally:
        engine.dispose()


def ids(connection: Connection, sql: str) -> list[int]:
    return [row[0] for row in connection.execute(text(sql))]


def test_fixture_loads_and_builds_a_graph(
    joins_shop_schema: ConnectionSettings,
) -> None:
    graph = fetch_schema_graph(joins_shop_schema)
    assert joins_shop_schema.schema_name == "joins_shop"
    assert sorted(node.name for node in graph.nodes) == sorted([*TABLES, "managers"])


def test_schema_has_exactly_the_six_tables(connection: Connection) -> None:
    sql = """SELECT table_name FROM information_schema.tables
             WHERE table_schema = 'joins_shop' ORDER BY table_name"""
    assert [row[0] for row in connection.execute(text(sql))] == TABLES


def test_schema_has_exactly_the_six_foreign_keys(connection: Connection) -> None:
    rows = connection.execute(text(FOREIGN_KEYS_SQL), {"schema": "joins_shop"})
    found = [tuple(row) for row in rows]
    assert len(found) == 6
    assert set(found) == FOREIGN_KEYS


def test_nullability_of_foreign_key_columns(connection: Connection) -> None:
    sql = """SELECT table_name || '.' || column_name FROM information_schema.columns
             WHERE table_schema = 'joins_shop' AND is_nullable = 'YES'
               AND column_name IN ('customer_id', 'order_id', 'product_id',
                                   'manager_id')"""
    nullable = {row[0] for row in connection.execute(text(sql))}
    assert nullable == {"complaints.order_id", "employee.manager_id"}


def test_customer_with_no_orders(connection: Connection) -> None:
    sql = """SELECT c.id FROM customer c
             WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)"""
    assert ids(connection, sql) == [2]


def test_customer_with_several_orders(connection: Connection) -> None:
    sql = """SELECT customer_id FROM orders GROUP BY customer_id
             HAVING COUNT(*) > 1"""
    assert ids(connection, sql) == [1]


def test_order_with_no_items_is_its_customers_only_order(
    connection: Connection,
) -> None:
    sql = """SELECT o.id FROM orders o
             WHERE NOT EXISTS (SELECT 1 FROM order_items i WHERE i.order_id = o.id)
               AND (SELECT COUNT(*) FROM orders other
                    WHERE other.customer_id = o.customer_id) = 1"""
    assert ids(connection, sql) == [12]


def test_order_with_several_items(connection: Connection) -> None:
    sql = "SELECT order_id FROM order_items GROUP BY order_id HAVING COUNT(*) > 1"
    assert ids(connection, sql) == [10]


def test_order_with_no_complaints_and_order_with_a_complaint(
    connection: Connection,
) -> None:
    without = """SELECT o.id FROM orders o WHERE NOT EXISTS
                 (SELECT 1 FROM complaints c WHERE c.order_id = o.id) ORDER BY o.id"""
    with_complaint = (
        "SELECT DISTINCT order_id FROM complaints WHERE order_id IS NOT NULL"
    )
    assert 11 in ids(connection, without)
    assert ids(connection, with_complaint) == [10]


def test_complaint_with_no_order(connection: Connection) -> None:
    assert ids(connection, "SELECT id FROM complaints WHERE order_id IS NULL") == [1001]


def test_product_never_ordered(connection: Connection) -> None:
    sql = """SELECT p.id FROM products p
             WHERE NOT EXISTS (SELECT 1 FROM order_items i WHERE i.product_id = p.id)"""
    assert ids(connection, sql) == [3]


def test_top_level_employee(connection: Connection) -> None:
    assert ids(connection, "SELECT id FROM employee WHERE manager_id IS NULL") == [1]


def test_managers(connection: Connection) -> None:
    sql = """SELECT DISTINCT manager_id FROM employee
             WHERE manager_id IS NOT NULL ORDER BY manager_id"""
    assert ids(connection, sql) == [1, 2]


def test_employee_who_manages_no_one(connection: Connection) -> None:
    sql = """SELECT e.id FROM employee e
             WHERE NOT EXISTS (SELECT 1 FROM employee r WHERE r.manager_id = e.id)"""
    assert ids(connection, sql) == [3]


def test_missing_order_id_is_rejected_for_order_items(connection: Connection) -> None:
    with pytest.raises(IntegrityError, match="null value"):
        with connection.begin_nested():
            connection.execute(text("INSERT INTO order_items VALUES (999, NULL, 1, 1)"))
