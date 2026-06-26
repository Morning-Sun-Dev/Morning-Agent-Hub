# AGENTS.md

## Role

The Report Writing Agent turns gathered agent results into structured Markdown reports using templates.

## Rules

- Keep report template definitions in `templates.py`.
- Use only provided source material. If material is missing, state that the source material is insufficient.
- Return both a readable report and structured `report_document` data when possible.
- Do not perform web search, RAG search, or Drive upload inside this agent. Those belong to `web_research`, `internal_rag`, and `file_management`.
- Keep template IDs stable because backend and frontend may refer to them.

## Tests

- Run `.venv/bin/python -m py_compile ai_llm/report_writing_agent/*.py` after code changes.
- Run `.venv/bin/python -m pytest -p no:cacheprovider tests -q` when report artifacts affect backend contracts.
