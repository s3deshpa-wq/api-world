# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

APIWorld is a personal sandbox for learning the Anthropic Python SDK (`anthropic`), built around two unrelated pieces:

- `todo.py` at the repo root — a standalone, stdlib-only CLI to-do app (unrelated to the API scripts below).
- A series of small, standalone scripts that each demonstrate one aspect of the Claude Messages API: plain completions, streaming, tool use, multi-tool agent loops, async tool execution, and multimodal (image/PDF) input. Every script is independently runnable (`python <script>.py`) and mostly duplicates its own tool/schema definitions rather than sharing code.

**Important quirk:** the actual example scripts live inside `venv/` (`venv/agentCall.py`, `venv/taskManager.py`, `venv/ex12.py`, etc.), mixed in alongside the real virtualenv internals (`venv/bin`, `venv/lib`, `venv/include`, `venv/pyvenv.cfg`). This is not intentional project layout — `venv/.gitignore` is the standard auto-generated `*` ignore-everything file — so these scripts are effectively untracked. When asked to find "the code," look inside `venv/`, not just the repo root.

## Setup & running

```bash
source venv/bin/activate        # the venv already has anthropic, python-dotenv, pydantic installed
cd venv                         # scripts use relative paths (data.json, taskManager.log) from here
python agentCall.py             # or api.py, taskManager.py, ex12.py, etc.
```

- Auth: scripts call `load_dotenv()` then `anthropic.Anthropic()`, which reads `ANTHROPIC_API_KEY` from `venv/.env`.
- There is no `requirements.txt`/`pyproject.toml` — the venv itself is the dependency record (`anthropic`, `python-dotenv`, `pydantic`, `httpx`, `pytest`).
- `pytest` is installed (the repo's only test dependency) with one test file, `venv/test_tool_agent.py`, covering `tool_agent.py`'s `get_time`. Run with `pytest -v test_tool_agent.py` from inside `venv/`. No other script has test coverage, and no linter exists anywhere in this repo.
- `todo.py`'s to-do CLI is documented separately below; it does not depend on the venv/API scripts.

## Architecture of the API scripts (`venv/*.py`)

Most scripts share the same shape, exploring one variation of the Claude tool-use loop:

1. A plain Python `tools` dict mapping tool name → function.
2. A hand-written `tool_schema` (or per-tool dict) list of Anthropic tool definitions (`name`/`description`/`input_schema`) — kept in sync with the `tools` dict *by hand*, not generated from it.
3. A loop that calls `client.messages.create(..., tools=tool_schema, messages=history)`, checks `resp.stop_reason`:
   - if `"tool_use"`: run the requested tool(s), append a `tool_result` block per call to `history` as a `role: "user"` message, and loop again.
   - otherwise: extract and print the `text` blocks — done.
4. `history` is the full conversation sent on every call (the API is stateless); an `Agent`/`TaskManager`-type class typically owns `self.history` and the loop.

Progression across files, roughly simplest to most complete:
- `api.py` — one-shot `messages.create`, no tools.
- `api-chatbot.py` / `api-chatbot-stream.py` — multi-turn chat loop over stdin, with/without `messages.stream`.
- `ex12.py` — multimodal input: base64-encodes `KCHS Logo.jpg` and `Financial_Advisor_Interview_QA.pdf` (both at repo root, one level above `venv/`) into an image+document message.
- `ex13.py` / `ex14.py` — single/multi tool-call round trip (manual, not looped); `ex14.py` has known bugs (references `weather_tool`/`calculate_tool` names that don't exist — the list is actually `tools`, and `calculate`/`search_notes` share copy-pasted fake weather data).
- `agentCall.py` — generalizes the loop into an `Agent` class; tools may be sync or async and are awaited via `asyncio.gather` for parallel tool calls.
- `agent_traced.py` — same `Agent` pattern as `agentCall.py` but instrumented with verbose step-by-step printing of `history` mutations (`show_history`/`describe_block`); useful as a reference for how `history` evolves turn by turn.
- `taskManager.py` — the most complete example: Pydantic `Task`/`AddTaskArgs` models, task state persisted to `venv/data.json`, logging to `venv/taskManager.log`, and a `TaskManager` class wired to real task-management tools (`add_task`, `list_tasks`, `complete_tasks`, `get_task_count`).
- `tool_agent.py` — a materially different pattern from the rest: instead of the hand-written tool-call loop + hand-written schema, it uses the SDK's `client.beta.messages.tool_runner(...)`, which drives the call/run-tool/feed-result loop for you. Tools are plain functions decorated with `@beta_tool`, and their schemas are generated from the function signature and docstring rather than written by hand. Its `get_time` tool resolves any city worldwide via the free Open-Meteo geocoding API (`httpx`, used directly here rather than only as a transitive `anthropic` SDK dependency) — unlike `agentCall.py`/`agent_traced.py`, whose `get_time` stubs still return fake fixed data for any city.
- `ex17.py` — Files API example (`client.beta.files.upload`, `betas=["files-api-2025-04-14"]`) that uploads PDFs and asks the model to summarize them. Not portable as-is: the file paths are hardcoded absolute paths outside the repo.
- `ex18.py` — prompt-templating demo: fills one prompt template with several tone/length/audience variable combinations and compares the resulting summaries.
- `ex19.py` — structured-output demo: prompts the model to return JSON matching a Pydantic `Invoice` model's shape, for extraction/validation use cases.
- `async.py` / `async2.py` — plain `asyncio.gather` vs. sequential `await` timing demo, not Anthropic-API-related.

All of the chat/agent loop scripts run an interactive `input()` loop and exit on typing `quit`.

## `meeting_app/` (repo root)

Prototype of a Zoom-like meeting app's control plane plus a Claude-powered Hindi/English meeting note taker. `meetings.py` (stdlib only: create/join/leave/end, 50-participant cap, no duration limit, transcript + end-of-meeting hooks), `note_taker.py` (rolling live notes per transcript chunk and a final `MeetingNotes` summary via `client.beta.messages.parse` with Pydantic models), `demo.py` (replays `sample_transcript.json`; needs an API key). `meeting_app/README.md` is the design doc. Offline tests: `pytest -v tests/test_meeting_app.py` from the repo root.

## `todo.py` (repo root)

Standalone CLI to-do app, stdlib only (`json`, `sys`, `pathlib`):

```bash
python todo.py add <description>    # add a task
python todo.py list                 # list tasks with [x]/[ ] status
python todo.py done <task number>   # mark a task complete (1-indexed)
python todo.py delete <task number> # delete a task (1-indexed)
```

Tasks persist as a JSON array of `{"description": str, "done": bool}` in `tasks.json` next to the script. Each command loads the full list, mutates it, and rewrites the file in full — no incremental updates, no stable IDs (indices are 1-based positions in the current list).
