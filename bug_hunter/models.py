"""Core dataclasses for orchestrator state tracking."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class AgentState:
    iteration: int = 0
    status: str = "idle"
    last_command: str = ""
    last_stdout: str = ""
    last_stderr: str = ""
    last_traceback: str = ""
    hypothesis: str = ""
    suggested_file: Optional[str] = None
    suggested_boundary: Optional[str] = None
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def touch(self) -> None:
        self.updated_at = datetime.utcnow()
