from __future__ import annotations

import pytest

from pc_info.models.processes import ProcessEntry
from pc_info.ui.screens.processes_tab import _matches_filter, _sort_processes


@pytest.fixture
def sample_processes() -> list[ProcessEntry]:
    return [
        ProcessEntry(
            pid=1050,
            name="python3",
            username="alice",
            status="running",
            cpu_percent=35.0,
            memory_percent=4.5,
            rss_bytes=256 * 1024 * 1024,
        ),
        ProcessEntry(
            pid=420,
            name="Chrome",
            username="Alice",
            status="sleeping",
            cpu_percent=68.5,
            memory_percent=18.2,
            rss_bytes=1024 * 1024 * 1024,
        ),
        ProcessEntry(
            pid=99,
            name="systemd-journald",
            username="root",
            status="running",
            cpu_percent=None,
            memory_percent=None,
            rss_bytes=None,
        ),
        ProcessEntry(
            pid=2300,
            name="Code",
            username="bob",
            status="stopped",
            cpu_percent=12.0,
            memory_percent=9.1,
            rss_bytes=512 * 1024 * 1024,
        ),
    ]


def test_matches_filter_empty_or_whitespace(sample_processes: list[ProcessEntry]) -> None:
    assert all(_matches_filter(proc, "") for proc in sample_processes)
    assert all(_matches_filter(proc, "   ") for proc in sample_processes)


def test_matches_filter_case_insensitive_fields(sample_processes: list[ProcessEntry]) -> None:
    by_pid = {proc.pid: proc for proc in sample_processes}

    assert _matches_filter(by_pid[420], "chrome") is True
    assert _matches_filter(by_pid[1050], "ALICE") is True
    assert _matches_filter(by_pid[2300], "STOPPED") is True
    assert _matches_filter(by_pid[99], "99") is True

    assert _matches_filter(by_pid[420], "python") is False
    assert _matches_filter(by_pid[2300], "root") is False


def test_sort_processes_by_cpu_descending_and_ascending(sample_processes: list[ProcessEntry]) -> None:
    desc = _sort_processes(sample_processes, sort_by="cpu", descending=True)
    assert [p.pid for p in desc] == [420, 1050, 2300, 99]

    asc = _sort_processes(sample_processes, sort_by="cpu", descending=False)
    assert [p.pid for p in asc] == [99, 2300, 1050, 420]


def test_sort_processes_by_mem_and_rss(sample_processes: list[ProcessEntry]) -> None:
    by_mem_desc = _sort_processes(sample_processes, sort_by="mem", descending=True)
    assert [p.pid for p in by_mem_desc] == [420, 2300, 1050, 99]

    by_mem_asc = _sort_processes(sample_processes, sort_by="mem", descending=False)
    assert [p.pid for p in by_mem_asc] == [99, 1050, 2300, 420]

    by_rss_desc = _sort_processes(sample_processes, sort_by="rss", descending=True)
    assert [p.pid for p in by_rss_desc] == [420, 2300, 1050, 99]

    by_rss_asc = _sort_processes(sample_processes, sort_by="rss", descending=False)
    assert [p.pid for p in by_rss_asc] == [99, 1050, 2300, 420]


def test_sort_processes_by_name_and_pid(sample_processes: list[ProcessEntry]) -> None:
    by_name_asc = _sort_processes(sample_processes, sort_by="name", descending=False)
    assert [p.name.lower() for p in by_name_asc] == [
        "chrome",
        "code",
        "python3",
        "systemd-journald",
    ]

    by_name_desc = _sort_processes(sample_processes, sort_by="name", descending=True)
    assert [p.name.lower() for p in by_name_desc] == [
        "systemd-journald",
        "python3",
        "code",
        "chrome",
    ]

    by_pid_asc = _sort_processes(sample_processes, sort_by="pid", descending=False)
    assert [p.pid for p in by_pid_asc] == [99, 420, 1050, 2300]

    by_pid_desc = _sort_processes(sample_processes, sort_by="pid", descending=True)
    assert [p.pid for p in by_pid_desc] == [2300, 1050, 420, 99]


def test_sort_processes_unknown_criterion_defaults_to_cpu(sample_processes: list[ProcessEntry]) -> None:
    desc = _sort_processes(sample_processes, sort_by="unknown", descending=True)
    assert [p.pid for p in desc] == [420, 1050, 2300, 99]

    asc = _sort_processes(sample_processes, sort_by="unknown", descending=False)
    assert [p.pid for p in asc] == [99, 2300, 1050, 420]