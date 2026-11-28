-- handmade_school: teachers, the courses they teach, students and enrollments.
-- Original schema and rows written for this project (MIT).
-- Edge cases: Omar takes no course; Lea takes two; Ms Wren teaches two courses.
DROP SCHEMA IF EXISTS handmade_school CASCADE;
CREATE SCHEMA handmade_school;
CREATE TABLE handmade_school.teacher (
    id integer PRIMARY KEY,
    name text NOT NULL
);
CREATE TABLE handmade_school.course (
    id integer PRIMARY KEY,
    title text NOT NULL,
    teacher_id integer NOT NULL REFERENCES handmade_school.teacher (id)
);
CREATE TABLE handmade_school.student (
    id integer PRIMARY KEY,
    name text NOT NULL
);
CREATE TABLE handmade_school.enrollment (
    student_id integer NOT NULL REFERENCES handmade_school.student (id),
    course_id integer NOT NULL REFERENCES handmade_school.course (id),
    PRIMARY KEY (student_id, course_id)
);
INSERT INTO handmade_school.teacher VALUES (1, 'Ms Wren'), (2, 'Mr Holt');
INSERT INTO handmade_school.course VALUES
    (1, 'Algebra', 1), (2, 'Biology', 2), (3, 'Chemistry', 1);
INSERT INTO handmade_school.student VALUES
    (1, 'Lea'), (2, 'Max'), (3, 'Noor'), (4, 'Omar');
INSERT INTO handmade_school.enrollment VALUES (1, 1), (1, 2), (2, 2), (3, 3);
