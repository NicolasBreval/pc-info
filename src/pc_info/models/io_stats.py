from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class NetworkInterfaceStat:
    name: str
    is_up: bool = True
    bytes_sent: int | None = None
    bytes_recv: int | None = None
    tx_bytes_per_sec: float | None = None
    rx_bytes_per_sec: float | None = None
    errin: int | None = None
    errout: int | None = None


@dataclass(slots=True)
class DiskIoStat:
    name: str
    read_bytes: int | None = None
    write_bytes: int | None = None
    read_bytes_per_sec: float | None = None
    write_bytes_per_sec: float | None = None
    read_count: int | None = None
    write_count: int | None = None


@dataclass(slots=True)
class SystemIoSnapshot:
    total_tx_bytes_per_sec: float = 0.0
    total_rx_bytes_per_sec: float = 0.0
    total_read_bytes_per_sec: float = 0.0
    total_write_bytes_per_sec: float = 0.0
    interfaces: list[NetworkInterfaceStat] = field(default_factory=list)
    disks: list[DiskIoStat] = field(default_factory=list)