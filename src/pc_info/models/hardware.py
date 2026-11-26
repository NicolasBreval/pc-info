from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CpuStaticInfo:
    model_name: str = "N/D"
    architecture: str = "N/D"
    physical_cores: int | None = None
    logical_cores: int | None = None
    max_freq_mhz: float | None = None
    min_freq_mhz: float | None = None


@dataclass(slots=True)
class CpuDynamicInfo:
    current_freq_mhz: float | None = None
    per_core_freq_mhz: list[float] = field(default_factory=list)


@dataclass(slots=True)
class MemoryInfo:
    total_bytes: int | None = None
    available_bytes: int | None = None
    used_bytes: int | None = None
    percent: float | None = None
    swap_total_bytes: int | None = None
    swap_used_bytes: int | None = None
    swap_percent: float | None = None


@dataclass(slots=True)
class DiskPartitionInfo:
    device: str
    mountpoint: str
    fstype: str
    total_bytes: int | None = None
    used_bytes: int | None = None
    free_bytes: int | None = None
    percent: float | None = None


@dataclass(slots=True)
class TemperatureSensorInfo:
    label: str
    current_c: float | None = None
    high_c: float | None = None
    critical_c: float | None = None


@dataclass(slots=True)
class SystemHardwareSnapshot:
    os_name: str = "N/D"
    os_version: str = "N/D"
    hostname: str = "N/D"
    cpu_static: CpuStaticInfo = field(default_factory=CpuStaticInfo)
    cpu_dynamic: CpuDynamicInfo = field(default_factory=CpuDynamicInfo)
    memory: MemoryInfo = field(default_factory=MemoryInfo)
    disks: list[DiskPartitionInfo] = field(default_factory=list)
    temperatures: list[TemperatureSensorInfo] = field(default_factory=list)
    battery_percent: float | None = None
    battery_plugged: bool | None = None