from __future__ import annotations

from types import SimpleNamespace

import psutil

from pc_info.collectors.processes import ProcessCollector
from pc_info.models.processes import SystemProcessesSnapshot


class _FakeProc:
    def __init__(self, info: dict) -> None:
        self.pid = info["pid"]
        self.info = info


def test_process_collector_collects_sorts_and_limits(monkeypatch) -> None:
    monkeypatch.setattr("psutil.cpu_percent", lambda interval=None, percpu=False: [25.0, 75.0] if percpu else 50.0)
    monkeypatch.setattr("psutil.STATUS_RUNNING", "running", raising=False)

    procs = [
        _FakeProc(
            {
                "pid": 101,
                "name": "python3",
                "username": "alice",
                "status": "running",
                "cpu_percent": 42.5,
                "memory_percent": 5.2,
                "memory_info": SimpleNamespace(rss=200 * 1024 * 1024),
            }
        ),
        _FakeProc(
            {
                "pid": 202,
                "name": "chrome",
                "username": "alice",
                "status": "sleeping",
                "cpu_percent": 85.0,
                "memory_percent": 14.8,
                "memory_info": SimpleNamespace(rss=600 * 1024 * 1024),
            }
        ),
        _FakeProc(
            {
                "pid": 303,
                "name": "systemd",
                "username": "root",
                "status": "running",
                "cpu_percent": 1.0,
                "memory_percent": 0.5,
                "memory_info": SimpleNamespace(rss=20 * 1024 * 1024),
            }
        ),
    ]

    monkeypatch.setattr("psutil.process_iter", lambda attrs=None: iter(procs))

    collector = ProcessCollector(max_processes=2)
    snapshot = collector.collect_snapshot()

    assert isinstance(snapshot, SystemProcessesSnapshot)
    assert snapshot.total_cpu_percent == 50.0
    assert snapshot.per_core_cpu_percent == [25.0, 75.0]
    assert snapshot.total_processes == 3
    assert snapshot.running_processes == 2
    assert len(snapshot.processes) == 2
    assert [p.pid for p in snapshot.processes] == [202, 101]


def test_process_collector_skips_inaccessible_processes(monkeypatch) -> None:
    monkeypatch.setattr("psutil.cpu_percent", lambda interval=None, percpu=False: [] if percpu else 10.0)
    monkeypatch.setattr("psutil.STATUS_RUNNING", "running", raising=False)

    class _BrokenProc:
        pid = 999

        @property
        def info(self):
            raise psutil.AccessDenied(pid=999)

    valid_proc = _FakeProc(
        {
            "pid": 404,
            "name": "worker",
            "username": "bob",
            "status": "sleeping",
            "cpu_percent": 15.0,
            "memory_percent": 2.0,
            "memory_info": SimpleNamespace(rss=64 * 1024 * 1024),
        }
    )

    monkeypatch.setattr("psutil.process_iter", lambda attrs=None: iter([_BrokenProc(), valid_proc]))

    collector = ProcessCollector()
    snapshot = collector.collect_snapshot()

    assert snapshot.total_processes == 1
    assert len(snapshot.processes) == 1
    assert snapshot.processes[0].pid == 404