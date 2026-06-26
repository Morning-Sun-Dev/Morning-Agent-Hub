# AGENTS.md

## Project Purpose

Morning Agent Hub is an A2A-based multi-agent application. The frontend sends a chat/file request to the FastAPI backend, the backend forwards work to the orchestrator, and the orchestrator delegates to specialist agents under `ai_llm/`.

## Work Boundaries

- Keep README human-facing. Put agent/tool operating rules in `AGENTS.md` files close to the code they govern.
- Do not store or print raw secrets, tokens, credentials, environment values, private document body text, or session transcripts.
- Do not stage or edit `docs/` and `data/` unless the current task explicitly asks for those paths.
- Do not duplicate another module's responsibility. Call the existing module interface or update the owning module first.
- Prefer small PRs with one clear ownership boundary: frontend UI, backend contract, common schema, one A2A agent, or tests.

## Branch And PR Workflow

- Work from `dev` unless the user or maintainers choose another base.
- Use a focused branch name such as `docs/agent-guidelines`, `feature/m001-chat-ui`, or `fix/backend-chat-route-owner`.
- Stage only explicit pathspecs for files changed by the task.
- In PRs, include changed module IDs when applicable, the contract surface changed, and the verification commands run.

## Verification

- Backend and contract changes: `.venv/bin/python -m pytest -p no:cacheprovider tests -q`.
- Python syntax check when touching backend, common, or agent files: `.venv/bin/python -m py_compile <changed python files>`.
- Frontend changes: `npm --prefix frontend run test:run` and `npm --prefix frontend run build`.
- Before committing: `git diff --check` and, after staging, `git diff --cached --check`.

## Contract Rules

- Shared frontend/backend/orchestrator shapes live in `common/contracts.py`.
- Backend route models should extend or adapt the common contract instead of inventing incompatible shapes.
- `/api/chat` uses `message`, `session_id`, `attachments`, and `requested_capabilities`. Do not reintroduce legacy `query` requests.
- Preserve artifact metadata that the UI needs: `sources`, `files`, `progress`, `artifacts`, `run_id`, `status`, and `error`.

## Local File Guidance

- `credentials.json`, `token.json`, `.env`, `.venv/`, `node_modules/`, logs, and generated caches are local-only.
- Treat uploaded documents and seed PDFs as data inputs. Confirm before tracking them.
- Keep generated build output out of source commits unless the repository explicitly tracks it.
