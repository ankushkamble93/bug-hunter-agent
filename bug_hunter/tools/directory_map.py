"""Directory mapping tool powered by os.walk."""

import os
from pathlib import Path
from typing import Any


def build_directory_map(root: str, max_depth: int = 4) -> dict[str, Any]:
    root_path = Path(root).resolve()
    mapping: dict[str, Any] = {"root": str(root_path), "entries": []}

    for current_root, dirs, files in os.walk(root_path):
        current_path = Path(current_root)
        depth = len(current_path.relative_to(root_path).parts)
        if depth > max_depth:
            dirs[:] = []
            continue

        dirs[:] = sorted([d for d in dirs if not d.startswith(".") and d != "__pycache__"])
        filtered_files = sorted(
            [
                f
                for f in files
                if not f.startswith(".")
                and not f.endswith((".pyc", ".pyo"))
                and f != ".DS_Store"
            ]
        )

        mapping["entries"].append(
            {
                "path": str(current_path),
                "depth": depth,
                "dirs": dirs.copy(),
                "files": filtered_files,
            }
        )
    return mapping


def render_directory_map(structured_map: dict[str, Any]) -> str:
    lines = [f"ROOT {structured_map['root']}"]
    for entry in structured_map.get("entries", []):
        indent = "  " * entry["depth"]
        relative = Path(entry["path"]).name if entry["depth"] else "."
        lines.append(f"{indent}- {relative}/")
        for filename in entry.get("files", []):
            lines.append(f"{indent}    - {filename}")
    return "\n".join(lines)
