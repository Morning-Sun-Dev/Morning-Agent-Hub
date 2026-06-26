# AGENTS.md

## Role

The Web Research Agent handles external web, news, and trend searches and returns source-backed summaries.

## Rules

- Use web search only for external or time-sensitive information. Internal policies and uploaded documents belong to `internal_rag`.
- Preserve source title, URL, snippet, and score when available.
- Return source artifacts in addition to the prose summary.
- Do not fabricate citations. If no reliable source is found, say so.

## Tests

- Run `.venv/bin/python -m pytest -p no:cacheprovider ai_llm/web_research_agent/tests -q` after model, source extraction, or artifact changes.
