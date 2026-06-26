# AGENTS.md

## Scope

This folder owns shared contracts, configuration helpers, schemas, and A2A client wrappers used across backend, frontend-facing adapters, and agents.

## Contract Rules

- Treat `common/contracts.py` as the source of shared frontend/backend/orchestrator data shapes.
- Update backend schemas, contract adapter tests, and frontend model tests when changing a shared contract field.
- Keep enum values stable. If an enum must change, update every producer and consumer in the same PR.
- Treat `ChatResponseContract.answer` as Markdown-formatted user-facing content.
- Keep machine-readable sources, files, progress, and artifacts outside the Markdown answer so UI rendering and evidence panels remain separately testable.
- Avoid importing FastAPI or Vue-specific concepts into common contract models.

## Verification

- Run `.venv/bin/python -m pytest -p no:cacheprovider tests/test_contracts.py tests/test_backend_chat_contract.py -q` after contract changes.
- Run `.venv/bin/python -m py_compile common/*.py` after Python edits.
