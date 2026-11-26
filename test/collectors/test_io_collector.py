from __future__ import annotations

from types import SimpleNamespace

from pc_info.collectors.io_stats import IoCollector
from pc_info.models.io_stats import SystemIoSnapshot


def test_io_collector_calculates_rates_and_orders_by_activity(monkeypatch) -> None:
    current_time = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: current_time[0])

    net_states = [
        {
            "eth0": SimpleNamespace(bytes_sent=1_000, bytes_recv=2_000, errin=0, errout=0),
            "lo": SimpleNamespace(bytes_sent=100, bytes_recv=100, errin=0, errout=0),
        },
        {
            "eth0": SimpleNamespace(bytes_sent=3_000, bytes_recv=6_000, errin=1, errout=0),
            "lo": SimpleNamespace(bytes_sent=200, bytes_recv=200, errin=0, errout=0),
        },
    ]
    disk_states = [
        {
            "nvme0n1": SimpleNamespace(read_bytes=10_000, write_bytes=5_000, read_count=10, write_count=5),
            "sda": SimpleNamespace(read_bytes=1_000, write_bytes=1_000, read_count=2, write_count=2),
        },
        {
            "nvme0n1": SimpleNamespace(read_bytes=20_000, write_bytes=15_000, read_count=15, write_count=9),
            "sda": SimpleNamespace(read_bytes=1_500, write_bytes=1_000, read_count=3, write_count=2),
        },
    ]

    net_idx = [-1]
    disk_idx = [-1]

    def fake_net_io(*, pernic=False):
        net_idx[0] = min(net_idx[0] + 1, len(net_states) - 1)
        return net_states[net_idx[0]]

    def fake_disk_io(*, perdisk=False):
        disk_idx[0] = min(disk_idx[0] + 1, len(disk_states) - 1)
        return disk_states[disk_idx[0]]

    monkeypatch.setattr("psutil.net_io_counters", fake_net_io)
    monkeypatch.setattr("psutil.disk_io_counters", fake_disk_io)
    monkeypatch.setattr(
        "psutil.net_if_stats",
        lambda: {"eth0": SimpleNamespace(isup=True), "lo": SimpleNamespace(isup=False)},
    )

    collector = IoCollector()

    # Avanza 2.0 segundos para el primer snapshot real
    current_time[0] = 102.0
    snapshot = collector.collect_snapshot()

    assert isinstance(snapshot, SystemIoSnapshot)
    # eth0: tx delta 2000 / 2s = 1000 B/s, rx delta 4000 / 2s = 2000 B/s
    # lo: tx delta 100 / 2s = 50 B/s, rx delta 100 / 2s = 50 B/s
    assert snapshot.total_tx_bytes_per_sec == 1050.0
    assert snapshot.total_rx_bytes_per_sec == 2050.0
    assert snapshot.interfaces[0].name == "eth0"
    assert snapshot.interfaces[0].is_up is True
    assert snapshot.interfaces[0].tx_bytes_per_sec == 1000.0
    assert snapshot.interfaces[0].rx_bytes_per_sec == 2000.0
    assert snapshot.interfaces[1].name == "lo"
    assert snapshot.interfaces[1].is_up is False

    # nvme0n1: read delta 10000 / 2s = 5000 B/s, write delta 10000 / 2s = 5000 B/s
    # sda: read delta 500 / 2s = 250 B/s, write delta 0 / 2s = 0 B/s
    assert snapshot.total_read_bytes_per_sec == 5250.0
    assert snapshot.total_write_bytes_per_sec == 5000.0
    assert snapshot.disks[0].name == "nvme0n1"
    assert snapshot.disks[0].read_bytes_per_sec == 5000.0
    assert snapshot.disks[0].write_bytes_per_sec == 5000.0
    assert snapshot.disks[1].name == "sda"
    assert snapshot.disks[1].read_bytes_per_sec == 250.0


def test_io_collector_handles_psutil_errors_gracefully(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise OSError("counter unavailable")

    monkeypatch.setattr("psutil.net_io_counters", boom)
    monkeypatch.setattr("psutil.disk_io_counters", boom)
    monkeypatch.setattr("psutil.net_if_stats", boom)

    collector = IoCollector()
    snapshot = collector.collect_snapshot()

    assert snapshot.interfaces == []
    assert snapshot.disks == []
    assert snapshot.total_tx_bytes_per_sec == 0.0
    assert snapshot.total_read_bytes_per_sec == 0.0