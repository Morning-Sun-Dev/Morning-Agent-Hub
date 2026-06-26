# AGENTS.md

## Scope

This folder owns repository-level backend and contract regression tests.

## Test Rules

- Prefer focused regression tests for the contract or behavior being changed.
- Keep tests deterministic and independent from live external services unless the task is explicitly an integration smoke.
- Mock A2A clients, Supabase, and Google Drive boundaries when testing backend route dispatch.
- Add tests near the contract boundary when a bug involved frontend/backend/orchestrator shape mismatch.
- When changing `common/capabilities.py`, cover both the shared contract registry and the `/api/capabilities` route when the UI status affects frontend behavior.
- Live smoke tests may use real local agent processes only when the task explicitly calls for integration verification. Stop any servers started for smoke after recording the result.

## Commands

- Full backend/contract suite: `.venv/bin/python -m pytest -p no:cacheprovider tests -q`.
- Targeted route tests: `.venv/bin/python -m pytest -p no:cacheprovider tests/test_backend_main_routes.py tests/test_backend_chat_contract.py -q`.
- Local integration smoke: `.venv/bin/python scripts/smoke_system.py --skip-chat --json`; full chat stream smoke: `.venv/bin/python scripts/smoke_system.py --json`.
