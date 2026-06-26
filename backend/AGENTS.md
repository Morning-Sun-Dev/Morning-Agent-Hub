# AGENTS.md

## Scope

This folder owns the FastAPI gateway, REST routes, SSE chat stream, Supabase access, and contract adaptation from A2A responses to UI responses.

## Route Ownership

- `backend/main.py` wires app middleware, lifespan, health, root metadata, and router inclusion.
- Chat behavior lives in `backend/api/routers/chat.py`.
- File upload/list behavior lives in `backend/api/routers/files.py`.
- Session behavior lives in `backend/api/routers/sessions.py`.
- Do not add a second app-level `/api/chat` route in `backend/main.py`.

## Contract Rules

- Use `backend/api/schemas.py` route models and `common/contracts.py` shared contracts.
- Keep `/api/chat` request shape compatible with `ChatRequestContract`: `message`, `session_id`, `attachments`, `requested_capabilities`.
- Keep SSE events parseable JSON with explicit `type` fields and a final `[DONE]` event.
- Preserve attachments and requested capabilities when building orchestrator prompts.
- Keep prior chat history out of RAG query prompts unless a task explicitly changes that behavior and updates tests.

## Verification

- Run `.venv/bin/python -m pytest -p no:cacheprovider tests -q` for backend route or contract changes.
- Run `.venv/bin/python -m py_compile backend/main.py backend/api/routers/*.py backend/api/*.py` after Python edits.
