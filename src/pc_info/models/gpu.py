from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class GpuInfo:
    index: int
    name: str
    vendor: str = "N/D"
    utilization_percent: float | None = None
    memory_used_bytes: int | None = None
    memory_total_bytes: int | None = None
    temperature_c: float | None = None
    power_watts: float | None = None


@dataclass(slots=True)
class SystemGpuSnapshot:
    gpus: list[GpuInfo] = field(default_factory=list)
    source: str = "N/D"