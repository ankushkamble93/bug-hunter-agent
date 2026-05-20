"""Pytest execution tool using subprocess.run."""

import subprocess
import sys
from dataclasses import dataclass


@dataclass
class PytestResult:
    command: str
    return_code: int
    stdout: str
    stderr: str

    @property
    def combined_output(self) -> str:
        return f"{self.stdout}\n{self.stderr}".strip()


def run_pytest(test_target: str = "tests", cwd: str = ".") -> PytestResult:
    command_parts = [sys.executable, "-m", "pytest", test_target, "-q"]
    command = " ".join(command_parts)
    completed = subprocess.run(
        command_parts,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    return PytestResult(
        command=command,
        return_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
