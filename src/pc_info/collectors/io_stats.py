from __future__ import annotations

import time

import psutil

from pc_info.models.io_stats import DiskIoStat, NetworkInterfaceStat, SystemIoSnapshot

_IO_SAFE_EXCEPTIONS = (
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
)


class IoCollector:
    """Recolector multiplataforma de tráfico de red e I/O de disco con tasas delta."""

    def __init__(self) -> None:
        self._last_timestamp: float | None = None
        self._last_net_pernic: dict[str, tuple[int, int]] = {}
        self._last_disk_io: dict[str, tuple[int, int]] = {}
        self._prime_counters()

    def _prime_counters(self) -> None:
        now = time.monotonic()
        self._last_timestamp = now

        try:
            pernic = psutil.net_io_counters(pernic=True) or {}
            for name, counter in pernic.items():
                self._last_net_pernic[str(name)] = (
                    int(getattr(counter, "bytes_sent", 0)),
                    int(getattr(counter, "bytes_recv", 0)),
                )
        except _IO_SAFE_EXCEPTIONS:
            self._last_net_pernic = {}

        try:
            disks = psutil.disk_io_counters(perdisk=True) or {}
            for name, counter in disks.items():
                self._last_disk_io[str(name)] = (
                    int(getattr(counter, "read_bytes", 0)),
                    int(getattr(counter, "write_bytes", 0)),
                )
        except _IO_SAFE_EXCEPTIONS:
            self._last_disk_io = {}

    def collect_snapshot(self) -> SystemIoSnapshot:
        now = time.monotonic()
        elapsed = (
            now - self._last_timestamp
            if self._last_timestamp is not None and now > self._last_timestamp
            else None
        )
        self._last_timestamp = now

        if_stats: dict[str, bool] = {}
        try:
            raw_if_stats = psutil.net_if_stats() or {}
            for if_name, st in raw_if_stats.items():
                if_stats[str(if_name)] = bool(getattr(st, "isup", True))
        except _IO_SAFE_EXCEPTIONS:
            if_stats = {}

        interfaces: list[NetworkInterfaceStat] = []
        next_net_cache: dict[str, tuple[int, int]] = {}
        total_tx_rate = 0.0
        total_rx_rate = 0.0

        try:
            pernic = psutil.net_io_counters(pernic=True) or {}
        except _IO_SAFE_EXCEPTIONS:
            pernic = {}

        for raw_name, counter in pernic.items():
            name = str(raw_name)
            sent = int(getattr(counter, "bytes_sent", 0))
            recv = int(getattr(counter, "bytes_recv", 0))
            errin = getattr(counter, "errin", None)
            errout = getattr(counter, "errout", None)

            next_net_cache[name] = (sent, recv)

            tx_rate: float | None = None
            rx_rate: float | None = None
            if elapsed is not None and elapsed > 0 and name in self._last_net_pernic:
                prev_sent, prev_recv = self._last_net_pernic[name]
                tx_rate = max(0.0, (sent - prev_sent) / elapsed)
                rx_rate = max(0.0, (recv - prev_recv) / elapsed)
                total_tx_rate += tx_rate
                total_rx_rate += rx_rate

            interfaces.append(
                NetworkInterfaceStat(
                    name=name,
                    is_up=if_stats.get(name, True),
                    bytes_sent=sent,
                    bytes_recv=recv,
                    tx_bytes_per_sec=tx_rate,
                    rx_bytes_per_sec=rx_rate,
                    errin=int(errin) if errin is not None else None,
                    errout=int(errout) if errout is not None else None,
                )
            )

        self._last_net_pernic = next_net_cache
        interfaces.sort(
            key=lambda item: (
                (item.tx_bytes_per_sec or 0.0) + (item.rx_bytes_per_sec or 0.0),
                (item.bytes_sent or 0) + (item.bytes_recv or 0),
                item.name,
            ),
            reverse=True,
        )

        disks: list[DiskIoStat] = []
        next_disk_cache: dict[str, tuple[int, int]] = {}
        total_read_rate = 0.0
        total_write_rate = 0.0

        try:
            perdisk = psutil.disk_io_counters(perdisk=True) or {}
        except _IO_SAFE_EXCEPTIONS:
            perdisk = {}

        for raw_name, counter in perdisk.items():
            name = str(raw_name)
            read_b = int(getattr(counter, "read_bytes", 0))
            write_b = int(getattr(counter, "write_bytes", 0))
            read_c = getattr(counter, "read_count", None)
            write_c = getattr(counter, "write_count", None)

            next_disk_cache[name] = (read_b, write_b)

            read_rate: float | None = None
            write_rate: float | None = None
            if elapsed is not None and elapsed > 0 and name in self._last_disk_io:
                prev_read, prev_write = self._last_disk_io[name]
                read_rate = max(0.0, (read_b - prev_read) / elapsed)
                write_rate = max(0.0, (write_b - prev_write) / elapsed)
                total_read_rate += read_rate
                total_write_rate += write_rate

            disks.append(
                DiskIoStat(
                    name=name,
                    read_bytes=read_b,
                    write_bytes=write_b,
                    read_bytes_per_sec=read_rate,
                    write_bytes_per_sec=write_rate,
                    read_count=int(read_c) if read_c is not None else None,
                    write_count=int(write_c) if write_c is not None else None,
                )
            )

        self._last_disk_io = next_disk_cache
        disks.sort(
            key=lambda item: (
                (item.read_bytes_per_sec or 0.0) + (item.write_bytes_per_sec or 0.0),
                (item.read_bytes or 0) + (item.write_bytes or 0),
                item.name,
            ),
            reverse=True,
        )

        return SystemIoSnapshot(
            total_tx_bytes_per_sec=total_tx_rate,
            total_rx_bytes_per_sec=total_rx_rate,
            total_read_bytes_per_sec=total_read_rate,
            total_write_bytes_per_sec=total_write_rate,
            interfaces=interfaces,
            disks=disks,
        )