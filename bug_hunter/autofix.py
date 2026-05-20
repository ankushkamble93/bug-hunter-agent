"""Auto-fix helpers: propose and apply safe local patches."""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class PatchProposal:
    target_file: str
    old_text: str
    new_text: str
    reason: str


def propose_patch(project_root: str, suggested_file: Optional[str]) -> Optional[PatchProposal]:
    """Return a conservative patch proposal when a known failure pattern is detected."""
    if not suggested_file:
        return None

    test_file = Path(project_root) / suggested_file
    if not test_file.exists() or "tests" not in test_file.parts:
        return None

    try:
        test_text = test_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    # Demo heuristic: parse `assert add(2, 3) == 5` and patch add's implementation.
    assert_match = re.search(
        r"assert\s+([a-zA-Z_]\w*)\(([^)]*)\)\s*==\s*([^\n#]+)",
        test_text,
    )
    if not assert_match:
        return None

    function_name = assert_match.group(1)
    source_path = _find_function_definition(project_root, function_name)
    if not source_path:
        return None

    try:
        source_text = source_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    # Conservative replacement for the intentional demo defect.
    if "return a - b" in source_text and function_name == "add":
        return PatchProposal(
            target_file=str(source_path),
            old_text="return a - b",
            new_text="return a + b",
            reason="Function `add` subtracts values; failing test expects addition.",
        )

    return None


def apply_patch(project_root: str, proposal: PatchProposal) -> bool:
    """Apply a proposal using a safe in-file exact replacement."""
    root = Path(project_root).resolve()
    target = Path(proposal.target_file).resolve()

    if root not in target.parents:
        return False
    if not target.exists() or target.is_dir():
        return False

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False

    if proposal.old_text not in content:
        return False

    updated = content.replace(proposal.old_text, proposal.new_text, 1)
    try:
        target.write_text(updated, encoding="utf-8")
    except OSError:
        return False
    return True


def _find_function_definition(project_root: str, function_name: str) -> Optional[Path]:
    root = Path(project_root)
    pattern = re.compile(rf"^\s*def\s+{re.escape(function_name)}\s*\(", re.MULTILINE)

    for current_root, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
        for filename in files:
            if not filename.endswith(".py"):
                continue
            candidate = Path(current_root) / filename
            if "tests" in candidate.parts:
                continue
            try:
                text = candidate.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if pattern.search(text):
                return candidate
    return None
