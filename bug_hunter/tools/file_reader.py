"""Safe file reader tool for local text inspection."""

from pathlib import Path


def safe_read_text(path: str, root: str, max_chars: int = 12000) -> str:
    root_path = Path(root).resolve()
    target = Path(path).resolve()

    if root_path not in target.parents and target != root_path:
        raise ValueError(f"Refusing to read outside root: {target}")
    if not target.exists():
        raise FileNotFoundError(f"File does not exist: {target}")
    if target.is_dir():
        raise IsADirectoryError(f"Expected file, got directory: {target}")
    if target.suffix not in {".py", ".txt", ".md", ".toml", ".yaml", ".yml", ".json", ".ini", ".cfg"}:
        raise ValueError(f"Unsupported extension for safe text read: {target.suffix}")

    content = target.read_text(encoding="utf-8", errors="replace")
    if len(content) > max_chars:
        return content[:max_chars] + "\n...[truncated]..."
    return content
