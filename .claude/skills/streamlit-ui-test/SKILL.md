---
name: streamlit-ui-test
description: Test the Brutal_sql Streamlit app in a real browser with agent-browser, record every page, and upload the recordings to the Linear ticket. Use after the code for a ticket is complete, after any later change to UI code, before declaring a UI ticket done, or when asked to check, test, record or screenshot the app.
---

# Streamlit UI test with agent-browser

Uses the `agent-browser` CLI (vercel-labs/agent-browser). For exact syntax run
`agent-browser skills get core`. Recording needs `ffmpeg` (`brew install agent-browser ffmpeg`).

**Rule:** after the code is complete, re-run **every** Streamlit page (not only the changed ones),
record each one working, and upload the fresh recordings to the Linear ticket. Repeat after any
later code change so the recording always matches the final code.

## 1. Start the stack
```bash
docker compose up -d                       # local Postgres (skip if the app doesn't need it yet)
poetry run streamlit run src/brutal_sql/app.py \
  --server.headless true --server.port 8501 &   # run in background
curl -sf http://localhost:8501/_stcore/health   # repeat until it prints "ok"
```

## 2. Record and drive each page
List the pages first: the main page (`src/brutal_sql/app.py`) plus any files under
`src/brutal_sql/pages/` (each one is served at `/<page_name>`). For **each** page:
```bash
agent-browser record start screenshots/<ticket-id>-<page>-<commit>.webm http://localhost:8501/<page>
agent-browser wait "h1"            # wait for the page to render
agent-browser snapshot -i          # list interactive elements with refs (@e1, @e2…)
agent-browser fill @eN "<value>"   # type into an input
agent-browser click @eN            # press a button
agent-browser errors               # page JS errors (must be empty)
agent-browser screenshot screenshots/<ticket-id>-<page>-<commit>.png
agent-browser record stop
```
- `<commit>` is `git rev-parse --short HEAD`, so each recording names the code it shows.
- Streamlit reruns the script after every interaction. Re-run `snapshot -i` after each action,
  because refs change.
- Wait for the "Running…" indicator to disappear before reading results.

## 3. What to check
For each page, and each success criterion in the ticket that touches the UI:
- **Positive path**: the page loads, its title shows, and its main flow works (e.g. valid
  connection string → schema list loads → tables and relationships show → graph renders).
- **Negative path**: bad input (bad connection string, wrong password, empty schema) → a clear
  error message is shown. No stack trace, and no password echoed on screen.
- No Streamlit exception boxes anywhere on the page, and `agent-browser errors` is empty.

## 4. Upload to Linear
For each recording, then each screenshot, **one file at a time** (signed URLs expire in 60 s):
1. `prepare_attachment_upload` with the ticket ID, filename, content type
   (`video/webm` / `image/png`) and exact size (`stat -f %z <file>`). Put the page name and
   commit hash in the title.
2. `curl -X PUT --data-binary @<file>` to `uploadRequest.url`, sending every header in
   `uploadRequest.headers` exactly as given. Expect HTTP 200.
3. `create_attachment_from_upload` with the returned `assetUrl`.

## 5. Clean up and report
```bash
agent-browser close
```
Stop the Streamlit process. Report each page as pass/fail with its recording and screenshot path
and the Linear attachment titles. Use only the local test database and never paste real
credentials into the browser. `screenshots/` is gitignored.
