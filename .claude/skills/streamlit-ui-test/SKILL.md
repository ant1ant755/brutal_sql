---
name: streamlit-ui-test
description: Test the Brutal_sql Streamlit app in a real browser with agent-browser. Use after any change to UI code, before declaring a UI ticket done, or when asked to check, test or screenshot the app.
---

# Streamlit UI test with agent-browser

Uses the `agent-browser` CLI (vercel-labs/agent-browser). If the `agent-browser` skill is installed,
follow it for exact command syntax. The commands below are the core flow.

## 1. Start the stack
```bash
docker compose up -d                       # local Postgres with the test schema
poetry run streamlit run src/brutal_sql/app.py \
  --server.headless true --server.port 8501 &   # run in background
```
Wait until `http://localhost:8501` responds before continuing.

## 2. Drive the app
```bash
agent-browser open http://localhost:8501
agent-browser snapshot -i          # list interactive elements with refs (@e1, @e2…)
agent-browser fill @eN "<value>"   # type into an input
agent-browser click @eN            # press a button
agent-browser screenshot screenshots/<ticket-id>-<step>.png
```
- Streamlit reruns the script after every interaction. Re-run `snapshot -i` after each action,
  because refs change.
- Wait for the "Running…" indicator to disappear before reading results.

## 3. What to check
For each success criterion in the ticket that touches the UI:
- **Positive path**: valid connection string → schema list loads → tables and relationships show →
  graph renders.
- **Negative path**: bad connection string, wrong password, empty schema → a clear error message is
  shown. No stack trace, and no password echoed on screen.
- No Streamlit exception boxes anywhere on the page.

## 4. Clean up and report
```bash
agent-browser close
```
Stop the Streamlit process. Report each check as pass/fail with its screenshot path.
Use only the local test database and never paste real credentials into the browser.
`screenshots/` is gitignored.
