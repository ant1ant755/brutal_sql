# brutal_sql
Brute force generation for sql for text 2 sql

## Setup

Requires [mamba](https://mamba.readthedocs.io/) (e.g. via Miniforge). Docker is needed for the
local Postgres database.

```bash
mamba create -n brutal_sql python=3.12 poetry   # env with Python 3.12 + poetry
mamba activate brutal_sql                       # always activate before poetry commands
poetry install                                  # installs into this env (poetry.toml: no separate venv)
cp .env.example .env                            # then set real values in .env
```

> **Note:** `poetry.toml` sets `virtualenvs.create = false`, so poetry installs into whichever
> Python is active. Always run `mamba activate brutal_sql` first, or dependencies land in the
> base environment.

## Run

```bash
mamba activate brutal_sql
docker compose up -d                              # start local Postgres
poetry run streamlit run src/brutal_sql/app.py    # open http://localhost:8501
```

## Test

```bash
poetry run pytest                                 # tests live next to the code (test_*.py)
poetry run black . && poetry run isort .          # format
poetry run flake8                                 # lint
```
