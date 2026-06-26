# AGENTS.md

## Scope

This folder owns the Vue 3 frontend, API adapter, chat UI components, and frontend tests.

## UI Rules

- Keep the main chat experience in Vue components under `frontend/src/components/chat/`.
- Normalize backend responses in `frontend/src/api.js` and `frontend/src/models/chatModels.js`; avoid ad hoc response parsing inside components.
- Do not duplicate backend or agent business logic in the UI.
- The UI must expose message input, file attachment state, answer rendering, sources, generated/downloadable files, progress, and error recovery when backend data is available.
- Render assistant answers as Markdown because the orchestrator uses Markdown to convey hierarchy, emphasis, links, tables, lists, and code.
- Markdown rendering must be safe: do not execute raw HTML or script content, and keep external links/file links controlled by the normalized model.
- Keep test-only placeholder components out of production routes once a real component exists.

## Design Rules

- Follow existing M-001 tokens in `frontend/src/styles/m001-tokens.css` unless a design task explicitly changes them.
- Use stable dimensions for toolbars, message rows, evidence panels, and file chips so dynamic content does not shift layout.
- Keep text readable in Korean and English. Do not rely on viewport-scaled font sizes.

## Verification

- Run `npm --prefix frontend run test:run` after component, model, or API adapter changes.
- Run `npm --prefix frontend run build` before frontend PR closeout.
