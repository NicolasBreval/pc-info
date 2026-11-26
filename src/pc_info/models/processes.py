from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ProcessEntry:
    pid: int
    name: str
    username: str = "N/D"
    status: str = "N/D"
    cpu_percent: float | None = None
    memory_percent: float | None = None
    rss_bytes: int | None = None


@dataclass(slots=True)
class SystemProcessesSnapshot:
    total_cpu_percent: float | None = None
    per_core_cpu_percent: list[float] = field(default_factory=list)
    total_processes: int = 0
    running_processes: int = 0
    processes: list[ProcessEntry] = field(default_factory=list)