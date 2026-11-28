# Benchmark format

Every benchmark question, whatever its source, is stored in the same format so
that all reports (join coverage, structure coverage, retrieval, execution
accuracy) read the same files.

## File format

A benchmark file is **JSON Lines**: one UTF-8 JSON object per line, one question
per object. Blank lines are ignored. Ids must be unique within a file.

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | stable id, e.g. `spider/dev/0042`, `handmade/lc183` |
| `source` | yes | `spider`, `handmade` or `merged` |
| `licence` | yes | licence of the question, e.g. `CC BY-SA 4.0` for Spider-derived items |
| `schema` | yes | Postgres schema the question runs on |
| `question` | yes | the natural-language question |
| `expected_sql` | yes | Postgres SQL that answers it |
| `ordered` | yes | `true` when row order matters (the question asks for an order) |
| `patterns` | yes | list of distinct pattern numbers 1–16; may be `[]` until classified |
| `expected_rows` | no | result of `expected_sql` on the loaded data, as a list of rows (lists) |
| `expected_tree` | no | object, filled later by the build tickets that need it |
| `expected_shape` | no | object, filled later by the build tickets that need it |

Unknown fields are rejected, so typos surface as errors.

Example line:

```json
{"id": "handmade/sample-001", "source": "handmade", "licence": "MIT", "schema": "joins_shop", "question": "How many customers are there?", "expected_sql": "SELECT count(*) FROM joins_shop.customer", "ordered": false, "patterns": [1], "expected_rows": [[5]]}
```

## Loading

```python
from brutal_sql.benchmark import filter_by, load_benchmark

records = load_benchmark("data/benchmark/spider_dev.jsonl")
joins = filter_by(records, source="spider", patterns=[2, 5])
```

`load_benchmark` raises `BenchmarkFormatError` naming the file and line of the
first bad record. `filter_by` keeps records matching every filter given;
`patterns` keeps records using **any** of the listed numbers.

## Licences

- **Spider-derived items** (`source: spider`, and `merged` items built from
  them) come from the [Spider dataset](https://yale-lily.github.io/spider) and
  are licensed **CC BY-SA 4.0**. The Spider data itself is not committed: it is
  downloaded into the gitignored `data/` folder.
- **Hand-made items** (`source: handmade`) are original questions written for
  this project and are licensed under the repository's **MIT** licence. They are
  written in the style of common SQL interview questions but never copy
  LeetCode (or any other site's) text, schemas or solutions.
- `sample_benchmark.jsonl` holds a few invented records for tests only.

## Hand-made question set

`handmade/` holds about 20 interview-style questions with our own schemas, rows
and wording (`source: handmade`, MIT). They cover well-known pattern cases that
Spider has few of: anti and semi joins, self-joins, top-N per group, comparing
with an aggregate or a manager's value, ratios, previous-row and recursive
queries.

- `<name>.sql` drops and recreates schema `handmade_<name>` (foreign keys
  declared) and fills it with a few rows chosen to hit the edge cases.
- `<name>.annotations.json` gives the schema's table types and verbs (ontology
  annotation format).
- `handmade.jsonl` holds the records. Patterns are tagged by hand for now and
  re-checked by the pattern tagger (B.05).

`expected_rows` comes from running each `expected_sql`. Numeric values are stored
as JSON numbers and dates as ISO strings. To rebuild them against the **local
Docker test database** (the scripts drop and recreate their schemas):

```bash
set -a; source .env; set +a
poetry run python -m brutal_sql.benchmark.build_handmade
```

`test_handmade_postgres.py` loads every schema in one session and checks that
each expected SQL still returns its stored rows.
