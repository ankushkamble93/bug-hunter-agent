"""LLM prompting layer with standard-library fallback behavior."""

import asyncio
import json
import os
import re
from dataclasses import dataclass
from typing import List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SYSTEM_PROMPT = """
You are a localized Python bug hunter.
Given a traceback and repository context, do the following:
1) Identify the likely root-cause failure signal.
2) Locate likely code boundaries: module, class, function, and approximate line span.
3) Suggest the minimal next inspection steps.
4) Return concise JSON with keys:
   summary, root_cause, target_file, target_symbol, boundary_hint, next_steps.
Avoid broad refactors. Stay scoped to the traceback.
""".strip()


@dataclass
class LLMAnalysis:
    summary: str
    root_cause: str
    target_file: Optional[str]
    target_symbol: Optional[str]
    boundary_hint: str
    next_steps: List[str]


class BugHunterLLM:
    """Small LLM adapter.

    If BUG_HUNTER_LLM_URL and BUG_HUNTER_LLM_KEY are present, it calls a
    chat-completions-compatible endpoint via urllib.
    Otherwise, it falls back to deterministic traceback heuristics.
    """

    def __init__(self) -> None:
        self.base_url = os.getenv("BUG_HUNTER_LLM_URL", "").strip()
        self.api_key = os.getenv("BUG_HUNTER_LLM_KEY", "").strip()
        self.model = os.getenv("BUG_HUNTER_LLM_MODEL", "gpt-4o-mini")

    async def analyze(
        self,
        traceback_text: str,
        directory_map: str,
    ) -> LLMAnalysis:
        if self.base_url and self.api_key:
            return await asyncio.to_thread(
                self._remote_analyze,
                traceback_text,
                directory_map,
            )
        return self._heuristic_analyze(traceback_text)

    def _remote_analyze(self, traceback_text: str, directory_map: str) -> LLMAnalysis:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Directory map:\n"
                        f"{directory_map}\n\n"
                        "Traceback:\n"
                        f"{traceback_text}\n"
                    ),
                },
            ],
            "temperature": 0.1,
        }
        payload = json.dumps(body).encode("utf-8")
        request = Request(
            self.base_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, ValueError):
            return self._heuristic_analyze(traceback_text)

        content = self._extract_content(data)
        parsed = self._parse_jsonish(content)
        if not parsed:
            return self._heuristic_analyze(traceback_text)
        return LLMAnalysis(
            summary=parsed.get("summary", "LLM analysis parsed."),
            root_cause=parsed.get("root_cause", "Unknown"),
            target_file=parsed.get("target_file"),
            target_symbol=parsed.get("target_symbol"),
            boundary_hint=parsed.get("boundary_hint", "inspect traceback frame"),
            next_steps=parsed.get("next_steps", ["Open the target file and inspect failing function."]),
        )

    @staticmethod
    def _extract_content(response_json: dict) -> str:
        choices = response_json.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        return str(message.get("content", ""))

    @staticmethod
    def _parse_jsonish(text: str) -> Optional[dict]:
        text = text.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except ValueError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                return None
            try:
                return json.loads(match.group(0))
            except ValueError:
                return None

    @staticmethod
    def _heuristic_analyze(traceback_text: str) -> LLMAnalysis:
        file_match = re.findall(r'File "([^"]+)", line (\d+), in ([^\n]+)', traceback_text)
        if file_match:
            target_file, line_no, symbol = file_match[-1]
            boundary = f"around line {line_no} in {symbol.strip()}"
            summary = f"Failure likely occurs in {symbol.strip()} ({target_file}:{line_no})."
            root_cause = "Derived from final traceback frame."
        else:
            pytest_match = re.search(r"([^\s]+\.py):(\d+):\s+([^\n]+)", traceback_text)
            if pytest_match:
                target_file = pytest_match.group(1)
                symbol = "pytest assertion context"
                line_no = pytest_match.group(2)
                assertion_text = pytest_match.group(3).strip()
                boundary = f"around line {line_no} in failing assertion"
                summary = f"Pytest failure localized to {target_file}:{line_no}."
                root_cause = f"Assertion failure: {assertion_text}"
            else:
                target_file = None
                symbol = None
                boundary = "no frame parsed; inspect full traceback output"
                summary = "Could not parse traceback frames."
                root_cause = "Traceback format may be incomplete."

        return LLMAnalysis(
            summary=summary,
            root_cause=root_cause,
            target_file=target_file,
            target_symbol=symbol.strip() if symbol else None,
            boundary_hint=boundary,
            next_steps=[
                "Open the target file and inspect the failing symbol.",
                "Confirm assertion inputs in the failing test.",
                "Run pytest again after a focused fix.",
            ],
        )
