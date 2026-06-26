# AGENTS.md

## Scope

This folder owns repository-level backend and contract regression tests.

## Test Rules

- Prefer focused regression tests for the contract or behavior being changed.
- Keep tests deterministic and independent from live external services unless the task is explicitly an integration smoke.
- Mock A2A clients, Supabase, and Google Drive boundaries when testing backend route dispatch.
- Add tests near the contract boundary when a bug involved frontend/backend/orchestrator shape mismatch.

## Commands

- Full backend/contract suite: `.venv/bin/python -m pytest -p no:cacheprovider tests -q`.
- Targeted route tests: `.venv/bin/python -m pytest -p no:cacheprovider tests/test_backend_main_routes.py tests/test_backend_chat_contract.py -q`.
