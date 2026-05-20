# Bug Hunter Agent

`bug-hunter-agent` is an autonomous Python micro-agent for localized failure triage in real codebases.  
It navigates repository structure, executes test suites via subprocess orchestration, parses traceback and assertion failure signals, and identifies high-confidence code boundaries where defects likely originate.

The runtime is optimized for tight, iterative debugging loops: run tests, analyze failure context, propose scoped corrections, apply safe patches, and validate on re-execution.

## Architecture / How It Works

The agent operates as a bounded async cycle:

1. **Orchestration Loop**
   - The runtime entrypoint initializes agent state and starts an async control loop.
   - Each iteration tracks execution metadata (status, command output, traceback fragments, boundary hypotheses).
2. **Tool Selection**
   - **Directory Map Tool** (`os.walk`): builds a structured view of modules and files.
   - **File Reader Tool**: reads text safely from within project boundaries.
   - **Test Runner Tool** (`subprocess.run`): executes `pytest`, capturing stdout/stderr and return code.
3. **LLM Analysis & Self-Correction**
   - A structured system prompt instructs the model to reason over traceback evidence and infer module/function boundaries.
   - The auto-fix phase proposes conservative text-level patches, applies them safely, reruns tests, and exits on green.

## Project Structure

```text
.
├── main.py
├── pyproject.toml
├── bug_hunter/
│   ├── agent.py
│   ├── autofix.py
│   ├── llm.py
│   ├── models.py
│   └── tools/
│       ├── directory_map.py
│       ├── file_reader.py
│       └── pytest_runner.py
├── sample_app/
└── tests/
```

## Quick Installation & Setup

```bash
git clone git@github.com:ankushkamble93/bug-hunter-agent.git
cd bug-hunter-agent

python3 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
```

### LLM Configuration (OpenAI-Compatible Endpoint)

Set your API key and endpoint before running:

```bash
export OPENAI_API_KEY="your_api_key_here"
export BUG_HUNTER_LLM_KEY="$OPENAI_API_KEY"
export BUG_HUNTER_LLM_URL="https://api.openai.com/v1/chat/completions"
export BUG_HUNTER_LLM_MODEL="gpt-4o-mini"
```

If these variables are omitted, the agent falls back to deterministic heuristic traceback analysis.

## Usage

```bash
python main.py
```

## Usage Example

```text
== Localized Bug Hunter Starting ==
Project root: /path/to/bug-hunter-agent

[state] iteration=1 status=running_pytest updated_at=2026-05-20T19:09:01.235656 boundary=n/a
[state] iteration=1 status=analyzing_failure updated_at=2026-05-20T19:09:02.326515 boundary=n/a

--- Failure Analysis ---
{
  "summary": "Pytest failure localized to tests/test_bug_demo.py:5.",
  "root_cause": "Assertion failure: AssertionError",
  "target_file": "tests/test_bug_demo.py",
  "target_symbol": "pytest assertion context",
  "boundary_hint": "around line 5 in failing assertion",
  "next_steps": [
    "Open the target file and inspect the failing symbol.",
    "Confirm assertion inputs in the failing test.",
    "Run pytest again after a focused fix."
  ]
}

--- Proposed Patch ---
{
  "target_file": "/path/to/bug-hunter-agent/sample_app/math_ops.py",
  "old_text": "return a - b",
  "new_text": "return a + b",
  "reason": "Function `add` subtracts values; failing test expects addition."
}

Applied proposed patch. Re-running pytest now.
[state] iteration=1 status=healthy updated_at=2026-05-20T19:09:02.725488 boundary=around line 5 in failing assertion
Auto-fix validated; stopping loop on green tests.
```
