# AGENTS.md

## Scope

This folder owns GitHub issue templates, PR templates, and CI workflows.

## Rules

- Keep templates aligned with the repository module IDs and completion criteria.
- CI must target `dev` unless the team changes the branch strategy.
- Do not add secrets or environment values to workflow files. Use GitHub Secrets references only.
- When changing CI commands, update the root `AGENTS.md` verification section in the same PR.
