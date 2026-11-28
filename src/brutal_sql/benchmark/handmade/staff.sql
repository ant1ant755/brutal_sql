-- handmade_staff: departments and employees, each employee with an optional manager.
-- Original schema and rows written for this project (MIT).
-- Edge cases: Ana has no manager; Dee and Eli earn the same; Bo and Ivy tie in
-- Research; Jo reports to Cy, who reports to Bo (a three-level chain).
DROP SCHEMA IF EXISTS handmade_staff CASCADE;
CREATE SCHEMA handmade_staff;
CREATE TABLE handmade_staff.department (
    id integer PRIMARY KEY,
    name text NOT NULL
);
CREATE TABLE handmade_staff.employee (
    id integer PRIMARY KEY,
    name text NOT NULL,
    department_id integer NOT NULL REFERENCES handmade_staff.department (id),
    manager_id integer REFERENCES handmade_staff.employee (id),
    salary integer NOT NULL
);
INSERT INTO handmade_staff.department VALUES (1, 'Research'), (2, 'Sales'), (3, 'Support');
INSERT INTO handmade_staff.employee VALUES
    (1, 'Ana', 1, NULL, 9000), (2, 'Bo', 1, 1, 7000), (3, 'Cy', 1, 2, 7500),
    (4, 'Dee', 2, 1, 6000), (5, 'Eli', 2, 4, 6000), (6, 'Fay', 2, 4, 6500),
    (7, 'Gus', 3, 1, 4000), (8, 'Hal', 3, 7, 3500), (9, 'Ivy', 1, 2, 7000),
    (10, 'Jo', 1, 3, 5000);
