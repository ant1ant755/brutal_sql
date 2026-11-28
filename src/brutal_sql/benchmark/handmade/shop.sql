-- handmade_shop: customers, products in categories, orders and their items.
-- Original schema and rows written for this project (MIT).
-- Edge cases: Kofi never orders; Stapler is never sold; Hose and Rake share a price.
DROP SCHEMA IF EXISTS handmade_shop CASCADE;
CREATE SCHEMA handmade_shop;
CREATE TABLE handmade_shop.customer (
    id integer PRIMARY KEY,
    name text NOT NULL,
    city text NOT NULL
);
CREATE TABLE handmade_shop.category (
    id integer PRIMARY KEY,
    name text NOT NULL
);
CREATE TABLE handmade_shop.product (
    id integer PRIMARY KEY,
    name text NOT NULL,
    category_id integer NOT NULL REFERENCES handmade_shop.category (id),
    price numeric(10, 2) NOT NULL
);
CREATE TABLE handmade_shop.orders (
    id integer PRIMARY KEY,
    customer_id integer NOT NULL REFERENCES handmade_shop.customer (id),
    ordered_on date NOT NULL
);
CREATE TABLE handmade_shop.order_item (
    order_id integer NOT NULL REFERENCES handmade_shop.orders (id),
    product_id integer NOT NULL REFERENCES handmade_shop.product (id),
    quantity integer NOT NULL,
    PRIMARY KEY (order_id, product_id)
);
INSERT INTO handmade_shop.customer VALUES
    (1, 'Mira', 'Oslo'), (2, 'Tomas', 'Lisbon'), (3, 'Ines', 'Oslo'), (4, 'Kofi', 'Accra');
INSERT INTO handmade_shop.category VALUES (1, 'Kitchen'), (2, 'Garden'), (3, 'Office');
INSERT INTO handmade_shop.product VALUES
    (1, 'Kettle', 1, 40.00), (2, 'Toaster', 1, 60.00), (3, 'Pan', 1, 25.00),
    (4, 'Hose', 2, 30.00), (5, 'Rake', 2, 30.00), (6, 'Stapler', 3, 12.00);
INSERT INTO handmade_shop.orders VALUES
    (10, 1, '2026-03-01'), (11, 1, '2026-03-05'), (12, 2, '2026-03-02'),
    (13, 3, '2026-03-07'), (14, 3, '2026-03-09');
INSERT INTO handmade_shop.order_item VALUES
    (10, 1, 1), (10, 3, 2), (11, 2, 1), (12, 4, 2), (12, 5, 1), (13, 1, 2), (14, 3, 1);
