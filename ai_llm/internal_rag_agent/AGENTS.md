# AGENTS.md

## Role

The Internal RAG Agent indexes and searches internal documents through Supabase and vector search.

## Rules

- Use this agent for internal documents, policies, regulations, uploaded files, and indexed knowledge.
- Keep indexing, parsing, search, and answer synthesis separated across the existing service files.
- Do not log or commit raw private document body text.
- Preserve source metadata needed by backend/UI citations.
- Use service role access only through the existing Supabase helper boundaries.

## Tests

- Run `.venv/bin/python -m pytest -p no:cacheprovider ai_llm/internal_rag_agent/tests tests/test_contracts.py -q` after parser, indexing, search, or source artifact changes.
