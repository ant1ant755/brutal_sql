# Brutal_sql

Text-to-SQL by brute-force generation of SQL, guided by a graph ontology of the database schema.

## Stack
- Python 3.12, environment managed with **mamba**, dependencies with **poetry**
- UI: **Streamlit**
- Database: **PostgreSQL** (local instance via Docker Compose)
- Schema introspection: SQLAlchemy `inspect()` over psycopg 3
- Graph ontology: in-memory `networkx` graph (no graph database). Rebuilt from the schema on demand.
- Tests: `pytest`, Streamlit `AppTest` (`streamlit.testing.v1`) for UI logic
- Browser UI checks: `agent-browser` CLI (see the `streamlit-ui-test` skill)

## Commands
```bash
mamba activate brutal_sql            # activate env
poetry install                       # install deps
docker compose up -d                 # start local Postgres
poetry run pytest                    # run all tests
poetry run black . && poetry run isort .   # format
poetry run flake8                    # lint
poetry run streamlit run src/brutal_sql/app.py   # run the app
```

### Browser checks (agent-browser)
One-time setup: `brew install agent-browser ffmpeg && agent-browser install`
(ffmpeg is needed for video recording). For full syntax: `agent-browser skills get core`.
```bash
poetry run streamlit run src/brutal_sql/app.py --server.headless true --server.port 8501 &
curl -sf http://localhost:8501/_stcore/health          # wait until it prints "ok"
agent-browser record start screenshots/<ticket-id>-<name>.webm http://localhost:8501
agent-browser wait "h1"                                # wait for the page to render
agent-browser snapshot -i                              # interactive elements with refs (@e1…)
agent-browser fill @eN "<value>" / agent-browser click @eN
agent-browser get text h1                              # read an element's text
agent-browser errors                                   # page JS errors (should be empty)
agent-browser screenshot screenshots/<ticket-id>-<step>.png
agent-browser record stop                              # save the video
agent-browser close                                    # then stop the Streamlit process
```
Screenshots and videos go in `screenshots/` (gitignored).

## Project layout
- `src/brutal_sql/` — application code
- Tests live **next to the code they test**, in the same folder: `src/brutal_sql/<module>.py` →
  `src/brutal_sql/test_<module>.py`. There is no `tests/` folder. Project-level tests (e.g. on
  `pyproject.toml`) sit at the repo root. Test files are excluded from the built package.
- Secrets come from environment variables / `.env` (never committed). `.env.example` documents the keys.

## Workflow (every task)
1. Run `/next-ticket` to fetch the next open ticket from Linear project **brutal_sql_project**.
2. If there is no ticket, stop and say so. Do not invent work.
3. Read the ticket's spec and success criteria. Write a **workflow plan** (files to touch, functions, tests) and wait for my approval before coding.
4. Implement on a branch named `<ticket-id>-short-description`. Every commit message starts with the
   ticket ID, e.g. `BRU-12: extract foreign keys from schema`.
5. Before declaring done: run format, lint, and the full test suite. Check every success criterion in the ticket and report on each one.
6. If the ticket touches the Streamlit app, run the `streamlit-ui-test` skill and report pass/fail
   with screenshots.
7. Run the `python-code-review` and `secrets-review` skills on the diff before committing.

## Code rules
- Max **300 lines per module**, max **20 lines per function** (body, excluding docstring). Split if over.
- Names read like English: `fetch_foreign_keys(schema)`, `build_relationship_graph(tables)`, `is_join_path_valid(...)`. No abbreviations like `tbl`, `fk_lst`, `proc()`.
- Type hints on all function signatures. Docstrings on public functions and classes.
- black (line length 88), isort (profile `black`), flake8 must pass with no warnings.
- No new dependencies without asking first.
- Never bump, upgrade or change the version of an existing dependency (including `poetry update`
  or editing version constraints in `pyproject.toml`) without asking first.

## Testing rules
- Every public function gets **positive and negative tests** (valid input → expected result; invalid input → expected error or behaviour).
- **Never modify existing tests while building a feature.** Add new tests only.
- If an existing test fails: explain why it broke, then propose a fix to the **code**. If you believe the test itself is wrong, stop and ask me. Do not edit it yourself.
- UI behaviour gets repeatable tests with Streamlit `AppTest` in the `test_<module>.py` next to the
  UI module (e.g. `src/brutal_sql/test_app.py`). agent-browser checks are
  extra verification and don't replace these tests.
- Tests that need Postgres use the Docker Compose instance. Unit tests must not require a live database.

## Never
- Never commit `.env`, credentials, connection strings with passwords, or tokens.
- Never run destructive SQL (`DROP`, `TRUNCATE`, `DELETE`) against any database other than the local test container.
- Never push to `main` directly.
