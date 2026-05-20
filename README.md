# Bug Hunter Agent

Small local Python micro-agent that:
- runs local `pytest`,
- parses failures/tracebacks,
- builds a structured directory map with `os.walk`,
- reads candidate files safely,
- uses an LLM-oriented system prompt to localize likely code boundaries,
- and performs a conservative auto-fix phase (propose -> apply -> retest).

## Layout

- `main.py` runtime entry point
- `bug_hunter/agent.py` async orchestrator loop and state transitions
- `bug_hunter/tools/` native tool modules
- `sample_app/` dummy app code with an intentional bug
- `tests/` intentionally failing test

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python main.py
```

## Optional remote LLM endpoint

If you want real model calls instead of heuristic fallback, provide:

- `BUG_HUNTER_LLM_URL` (chat-completions compatible HTTP endpoint)
- `BUG_HUNTER_LLM_KEY`
- `BUG_HUNTER_LLM_MODEL` (optional)
