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
