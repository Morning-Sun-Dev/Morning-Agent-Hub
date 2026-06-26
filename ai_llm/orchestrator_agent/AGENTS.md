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

## Tests

- Run `.venv/bin/python -m pytest -p no:cacheprovider ai_llm/orchestrator_agent/tests tests/test_contracts.py -q` after routing, model, or artifact changes.
