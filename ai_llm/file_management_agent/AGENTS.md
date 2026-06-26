# AGENTS.md

## Role

The File Management Agent owns Google Drive file upload, listing, search, folder, and file metadata operations.

## Rules

- Keep Google Drive credential files local-only: `credentials.json` and `token.json` must not be committed.
- Return machine-readable file artifacts for file lists, uploads, downloads, and Drive references.
- Do not implement RAG indexing here. Hand off indexed document work to `internal_rag`.
- Do not expose raw file bytes or private file bodies in logs.
- Keep folder IDs and storage refs as data fields, not prose-only output.

## Tests

- Run `.venv/bin/python -m py_compile ai_llm/file_management_agent/*.py` after code changes.
- Run backend file route tests when file artifacts or upload behavior changes.
