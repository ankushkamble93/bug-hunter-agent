"""Async orchestrator loop for the localized bug hunter."""

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Optional

from bug_hunter.autofix import apply_patch, propose_patch
from bug_hunter.llm import BugHunterLLM
from bug_hunter.models import AgentState
from bug_hunter.tools.directory_map import build_directory_map, render_directory_map
from bug_hunter.tools.file_reader import safe_read_text
from bug_hunter.tools.pytest_runner import run_pytest


class BugHunterAgent:
    def __init__(self, project_root: str = ".", max_iterations: int = 3) -> None:
        self.project_root = str(Path(project_root).resolve())
        self.max_iterations = max_iterations
        self.state = AgentState()
        self.llm = BugHunterLLM()

    async def run(self) -> None:
        print("== Localized Bug Hunter Starting ==")
        print(f"Project root: {self.project_root}")

        for i in range(1, self.max_iterations + 1):
            self.state.iteration = i
            self.state.status = "running_pytest"
            self.state.touch()
            self._print_state()

            pytest_result = await asyncio.to_thread(run_pytest, "tests", self.project_root)
            self.state.last_command = pytest_result.command
            self.state.last_stdout = pytest_result.stdout
            self.state.last_stderr = pytest_result.stderr
            self.state.last_traceback = self._extract_traceback(pytest_result.combined_output)

            if pytest_result.return_code == 0:
                self.state.status = "healthy"
                self.state.hypothesis = "No failing tests detected."
                self.state.touch()
                self._print_state()
                print("No failures found. Exiting loop.")
                return

            self.state.status = "analyzing_failure"
            self.state.touch()
            self._print_state()

            directory_map = await asyncio.to_thread(build_directory_map, self.project_root)
            directory_map_text = render_directory_map(directory_map)

            analysis = await self.llm.analyze(
                traceback_text=self.state.last_traceback or pytest_result.combined_output,
                directory_map=directory_map_text,
            )

            self.state.hypothesis = analysis.summary
            self.state.suggested_file = analysis.target_file
            self.state.suggested_boundary = analysis.boundary_hint
            self.state.status = "inspection_ready"
            self.state.touch()

            print("\n--- Failure Analysis ---")
            print(json.dumps(analysis.__dict__, indent=2))

            if analysis.target_file:
                normalized_target = self._normalize_target_file(analysis.target_file)
                if normalized_target and os.path.exists(normalized_target):
                    try:
                        snippet = await asyncio.to_thread(
                            safe_read_text,
                            normalized_target,
                            self.project_root,
                            1200,
                        )
                        print("\n--- Candidate File Snippet ---")
                        print(snippet)
                    except (ValueError, OSError) as exc:
                        print(f"Could not read suggested file: {exc}")

            self.state.status = "autofix_proposing"
            self.state.touch()
            self._print_state()
            proposal = await asyncio.to_thread(
                propose_patch,
                self.project_root,
                analysis.target_file,
            )
            if proposal:
                print("\n--- Proposed Patch ---")
                print(
                    json.dumps(
                        {
                            "target_file": proposal.target_file,
                            "old_text": proposal.old_text,
                            "new_text": proposal.new_text,
                            "reason": proposal.reason,
                        },
                        indent=2,
                    )
                )

                self.state.status = "autofix_applying"
                self.state.touch()
                self._print_state()
                patch_applied = await asyncio.to_thread(
                    apply_patch,
                    self.project_root,
                    proposal,
                )
                if patch_applied:
                    print("Applied proposed patch. Re-running pytest now.")
                    verification = await asyncio.to_thread(run_pytest, "tests", self.project_root)
                    self.state.last_command = verification.command
                    self.state.last_stdout = verification.stdout
                    self.state.last_stderr = verification.stderr
                    self.state.last_traceback = self._extract_traceback(verification.combined_output)
                    if verification.return_code == 0:
                        self.state.status = "healthy"
                        self.state.hypothesis = "Auto-fix succeeded and tests are now passing."
                        self.state.touch()
                        self._print_state()
                        print("Auto-fix validated; stopping loop on green tests.")
                        return
                    print("Patch applied, but tests are still failing. Continuing loop.")
                else:
                    print("Proposed patch could not be safely applied.")
            else:
                print("No safe patch proposal available for this failure.")

            self._print_state()

        print("Reached max iterations; stopping for manual intervention.")

    def _normalize_target_file(self, target_file: str) -> Optional[str]:
        p = Path(target_file)
        if p.is_absolute():
            return str(p)
        candidate = Path(self.project_root) / p
        return str(candidate.resolve())

    @staticmethod
    def _extract_traceback(output: str) -> str:
        traceback_index = output.find("Traceback (most recent call last):")
        if traceback_index >= 0:
            return output[traceback_index:].strip()

        frame_matches = re.findall(
            r"(File \"[^\"]+\", line \d+, in [^\n]+(?:\n\s+.+)?)",
            output,
            flags=re.MULTILINE,
        )
        if frame_matches:
            return "\n".join(frame_matches[-8:])
        return output[-2000:]

    def _print_state(self) -> None:
        print(
            f"\n[state] iteration={self.state.iteration} "
            f"status={self.state.status} updated_at={self.state.updated_at.isoformat()} "
            f"boundary={self.state.suggested_boundary or 'n/a'}"
        )
