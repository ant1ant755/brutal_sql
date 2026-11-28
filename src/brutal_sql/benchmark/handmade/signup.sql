-- handmade_signup: members and the confirmation messages sent to them.
-- Original schema and rows written for this project (MIT).
-- Edge cases: Quinn was never sent a confirmation; Rui only timed out.
DROP SCHEMA IF EXISTS handmade_signup CASCADE;
CREATE SCHEMA handmade_signup;
CREATE TABLE handmade_signup.member (
    id integer PRIMARY KEY,
    name text NOT NULL,
    joined_on date NOT NULL
);
CREATE TABLE handmade_signup.confirmation (
    id integer PRIMARY KEY,
    member_id integer NOT NULL REFERENCES handmade_signup.member (id),
    action text NOT NULL CHECK (action IN ('confirmed', 'timeout'))
);
INSERT INTO handmade_signup.member VALUES
    (1, 'Ola', '2026-01-10'), (2, 'Pia', '2026-01-12'),
    (3, 'Quinn', '2026-02-01'), (4, 'Rui', '2026-02-03');
INSERT INTO handmade_signup.confirmation VALUES
    (1, 1, 'confirmed'), (2, 1, 'timeout'), (3, 2, 'confirmed'),
    (4, 2, 'confirmed'), (5, 4, 'timeout');
