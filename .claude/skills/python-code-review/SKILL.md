---
name: python-code-review
description: Review Python changes in this repo against project standards. Use before committing, after finishing a ticket, or when asked to review Python code.
---

# Python code review

Review the current diff (`git diff main...HEAD` plus uncommitted changes). Report findings as a list:
`file:line — severity (blocker / should-fix / nit) — issue — suggested fix`.

## Checks
1. **Size limits**: any module over 300 lines or function body over 20 lines is a blocker. Use
   `wc -l` and inspect function lengths.
2. **Readability**: names read like English, with no cryptic abbreviations. Each function does one thing.
   Avoid deep nesting (more than 3 levels) by using early returns.
3. **Types and docs**: type hints on every signature. Docstrings on public functions and classes.
4. **Tests**: every new or changed public function has at least one positive and one negative test.
   Existing tests are unmodified. Flag any edit to an existing `test_*.py` file that changes existing test functions.
5. **Correctness**: edge cases (empty schema, no foreign keys, self-referencing FKs, composite keys,
   circular relationships), error handling, resource cleanup (connections closed via context managers).
6. **SQL safety**: no string-formatted SQL with user input. Use parameters or SQLAlchemy constructs.
7. **Tooling**: run `poetry run black --check .`, `poetry run isort --check .`, `poetry run flake8`,
   `poetry run pytest` and include the results.

End with a verdict: **Ready to commit** or **Changes needed** (list the blockers).
