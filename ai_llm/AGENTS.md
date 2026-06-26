# AGENTS.md

## Scope

This folder contains the A2A orchestrator and specialist remote agents.

## Shared Agent Contract

- Each agent should expose `agent.py`, `agent_executor.py`, and `agent_server.py` unless there is a documented reason not to.
- Executors translate agent stream output into A2A task status and artifacts. Keep business logic in `agent.py`.
- Emit structured artifacts whenever downstream modules or the UI need machine-readable data. Do not rely only on prose.
- Keep user intent intact when delegating between agents. Add context; do not rewrite constraints away.

## Error And Trace Rules

- Return clear failure messages through A2A status updates instead of swallowing exceptions.
- Preserve enough trace information for the orchestrator and frontend progress UI to show what happened.
- Do not log raw document contents, credentials, tokens, or private file bodies.

## Verification

- Run agent-specific tests when present: `.venv/bin/python -m pytest -p no:cacheprovider ai_llm/<agent>/tests -q`.
- Run shared backend tests when an agent artifact shape changes: `.venv/bin/python -m pytest -p no:cacheprovider tests -q`.
