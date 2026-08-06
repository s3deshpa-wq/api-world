---

## description: Update project documentation (README, CLAUDE.md, docs/) to reflect uncommitted code changes allowed-tools: Bash(git diff:*), Bash(git status:*), Bash(git log:\*), Read, Edit, Glob, Grep

## Context

Current uncommitted changes: \!`git diff`

Files changed (including untracked): \!`git status --short`

## Task

Review the diff above and update the project's documentation to reflect these changes. Specifically:

1. **README.md** — update if the changes affect: setup/installation steps, usage instructions, CLI commands or flags, configuration options, dependencies, or the feature list. Do not touch unrelated sections.  
     
2. **CLAUDE.md** — update if the changes affect project conventions, architecture, key file locations, or anything a future Claude Code session would need to know to work in this codebase correctly. Skip if nothing here is affected.  
     
3. **docs/ folder** (if it exists) — update the specific file(s) relevant to what changed (e.g. `docs/api.md` for API changes, `docs/architecture.md` for structural changes). Create a new doc file only if there's a clear gap and no existing file covers it — ask me first before creating new files.

## Rules

- Only update documentation that is actually affected by this diff. Do not rewrite or reformat unrelated content.  
- Match the existing tone, structure, and formatting conventions of each file.  
- If the diff is purely internal (refactor, tests, formatting) with no user-facing or architectural impact, say so and make no changes.  
- After updating, give me a short summary of exactly what you changed and why, file by file.

