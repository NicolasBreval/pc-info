from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ProcessDetail:
    pid: int
    name: str
    username: str = "N/D"
    status: str = "N/D"
    exe: str = "N/D"
    cmdline: list[str] = field(default_factory=list)
    num_threads: int | None = None
    cpu_percent: float | None = None
    memory_percent: float | None = None
    rss_bytes: int | None = None
    vms_bytes: int | None = None
    created_at: str = "N/D"