---
description: Fetch the next open Linear ticket in brutal_sql_project and draft a workflow plan
---

Using the Linear MCP tools:

1. List open issues (not Done/Canceled) in the Linear project **brutal_sql_project**, ordered by priority, then oldest first. If $ARGUMENTS names a ticket ID, use that ticket instead.
2. If there are none, say "No open tickets in brutal_sql_project" and stop.
3. Show the selected ticket: ID, title, spec, and success criteria.
4. If the success criteria are missing or vague, list what is unclear and stop. Do not guess.
5. Otherwise draft a workflow plan:
   - Modules to create or change (keep each under 300 lines)
   - Functions/classes with English-readable names and one-line purposes (each under 20 lines)
   - Positive and negative tests for every public function
   - How each success criterion will be verified
6. Wait for approval before writing any code. Follow the workflow in CLAUDE.md.
