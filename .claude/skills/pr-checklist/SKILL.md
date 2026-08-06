---
name: pr-checklist
description: Runs a pre-commit/pre-PR checklist against the current changes — tests, lint, docs, secrets, commit message quality. Use when the user says "run the PR checklist," "am I ready to commit," "check before I push," or before opening a pull request.
---

# PR / Commit Checklist

Use this skill before committing or opening a pull request. Work through the checklist against the current uncommitted changes (`git diff` and `git status --short`), and report results as a pass/fail list — do not silently fix things unless asked.

## Checklist

**1. Tests**
Run the project's test suite. All tests must pass. If tests weren't added for new logic, flag it.

**2. Lint / formatting**
Run the project's linter/formatter check (e.g. `npm run lint`, `ruff check`, `flake8`, whatever this project uses — check `CLAUDE.md` or config files if unsure). Report any violations.

**3. No debug artifacts**
Scan the diff for leftover debug code: `console.log`, `print()` debugging statements, commented-out blocks, `TODO`/`FIXME` markers added in this diff, or debugger breakpoints (`pdb.set_trace()`, `debugger;`).

**4. No secrets or credentials**
Scan the diff for anything that looks like an API key, password, token, or `.env` value being committed. Flag even if it looks like a placeholder — better to double check.

**5. Documentation**
Check whether this diff should trigger a documentation update (new features, changed CLI flags, changed config, changed setup steps). If yes and docs weren't updated, flag it and suggest running `/update-docs`.

**6. Commit message quality** (if a commit message is provided or being drafted)
Should be concise, in imperative mood ("Add X" not "Added X" or "Adds X"), and describe *why* not just *what*, when the reason isn't obvious from the diff alone.

**7. Scope**
Flag if the diff mixes unrelated changes (e.g. a bug fix bundled with an unrelated refactor) that would be better as separate commits/PRs.

## Output format

Report each item as PASS, FAIL, or N/A, with a one-line reason for any FAIL. End with a single overall verdict: ready to commit / needs fixes before committing.
