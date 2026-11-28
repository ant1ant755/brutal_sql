-- handmade_weather: weather stations and their daily readings.
-- Original schema and rows written for this project (MIT).
-- Edge cases: each station's first day has no previous day; Hill is equally warm
-- on 3 and 4 March.
DROP SCHEMA IF EXISTS handmade_weather CASCADE;
CREATE SCHEMA handmade_weather;
CREATE TABLE handmade_weather.station (
    id integer PRIMARY KEY,
    name text NOT NULL
);
CREATE TABLE handmade_weather.reading (
    station_id integer NOT NULL REFERENCES handmade_weather.station (id),
    day date NOT NULL,
    temperature numeric(4, 1) NOT NULL,
    rainfall_mm numeric(5, 1) NOT NULL,
    PRIMARY KEY (station_id, day)
);
INSERT INTO handmade_weather.station VALUES (1, 'Hill'), (2, 'Coast');
INSERT INTO handmade_weather.reading VALUES
    (1, '2026-03-01', 10.0, 2.0), (1, '2026-03-02', 12.5, 0.0),
    (1, '2026-03-03', 11.0, 5.5), (1, '2026-03-04', 11.0, 1.0),
    (1, '2026-03-05', 13.0, 0.0),
    (2, '2026-03-01', 15.0, 0.0), (2, '2026-03-02', 14.0, 3.0),
    (2, '2026-03-03', 16.5, 0.5);
