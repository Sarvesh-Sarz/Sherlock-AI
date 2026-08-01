# Sherlock AI — Backend

Backend foundation for Sherlock AI, an AI-powered Windows diagnostic
investigation tool. This is a scaffold: placeholder endpoints and a
service layer wired up for a future reasoning pipeline. No AI, no
Windows diagnostics, no database yet — see [Scope](#scope) below.

## Requirements

- Python 3.12+

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate      # .venv\Scripts\activate on Windows
pip install -e ".[dev]"
cp .env.example .env           # optional, defaults work out of the box
```

## Run

```bash
uvicorn app.main:app --reload
```

The API is then available at `http://127.0.0.1:8000`, with interactive
docs at `http://127.0.0.1:8000/docs`.

## Test

```bash
pytest
```

## Endpoints

| Method | Path                       | Description                                    |
|--------|----------------------------|-------------------------------------------------|
| GET    | `/health`                  | Service liveness check                          |
| POST   | `/investigation/start`     | Open a new investigation, runs diagnostic tools |
| GET    | `/investigation/{case_id}` | Get the current status of a case, incl. evidence |

## Diagnostic tools

`app/tools/` holds individual diagnostic tools. Each exposes a single
`run() -> ToolResult` function and never raises — failures come back as
an error `ToolResult` instead. `InvestigationService` runs every
registered tool synchronously when a case is opened and attaches each
result to the case as `evidence`.

Implemented so far:

- **`cpu.py`** — CPU usage percentage, physical/logical core counts, and
  current/max frequency, via `psutil`.

Planned (not yet implemented): `memory.py`, `disk.py`, `battery.py`,
`wifi.py`, `startup.py`. Adding one means writing the module and adding
one line to the `_DIAGNOSTIC_TOOLS` registry in
`app/services/investigation_service.py`.

## Scope

This foundation intentionally does **not** implement:

- AI / LLM reasoning (Ollama or otherwise)
- LangGraph or any agent orchestration framework
- Windows Event Log diagnostics, or any tool beyond `cpu.py`
- RAG / retrieval
- A real database (an in-memory repository stands in for now)

See `app/agents/` for the placeholder Planner, Tool Manager, Reasoner,
Memory, and Report Generator classes these will build on, and the main
project README for overall architecture and roadmap.
