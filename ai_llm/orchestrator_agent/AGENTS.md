# AGENTS.md

## Role

The orchestrator analyzes user intent, creates a plan, calls remote agents, and returns answer, trace, and child artifacts.

## Routing Rules

- Keep the valid child agents aligned with `AgentName` in `models.py` and `AgentId` in `common/contracts.py`.
- Use `DIRECT` only for greetings, simple acknowledgements, and feature explanations. Factual, policy, document, web, file, or report requests must route to an agent.
- Preserve user constraints such as count, scope, target folder, output format, and language in each `PlanStep.query`.
- Use `depends_on` when a later agent needs a prior result; leave it `None` only for truly independent work.

## Artifact Rules

- Forward child agent artifacts as named A2A artifacts so backend adapters can normalize them.
- Do not collapse structured child data into only natural language when the frontend may need files, sources, or progress.
- Regardless of the child agents' raw response formats, produce the final user-facing `answer` as Markdown.
- Use Markdown for meaningful emphasis and structure: headings, bold text, lists, tables, links, and code fences when they improve readability.
- Keep structured artifacts separate from the Markdown answer so the frontend can render both rich text and machine-readable evidence.

## Tests

- Run `.venv/bin/python -m pytest -p no:cacheprovider ai_llm/orchestrator_agent/tests tests/test_contracts.py -q` after routing, model, or artifact changes.
