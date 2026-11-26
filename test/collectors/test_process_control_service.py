from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime
from types import SimpleNamespace

import psutil
import pytest

from pc_info.collectors.process_control import ProcessControlService
from pc_info.models.process_detail import ProcessDetail


class _FakePsutilProcess:
    def __init__(
        self,
        pid: int,
        *,
        name: str = "worker",
        username: str = "alice",
        status: str = "running",
        exe: str = "/usr/bin/worker",
        cmdline: list[str] | None = None,
        num_threads: int = 4,
        cpu_percent: float = 12.5,
        memory_percent: float = 3.4,
        rss: int = 128 * 1024 * 1024,
        vms: int = 512 * 1024 * 1024,
        create_time: float = 1_700_000_000.0,
        raise_on: dict[str, Exception] | None = None,
    ) -> None:
        self.pid = pid
        self._name = name
        self._username = username
        self._status = status
        self._exe = exe
        self._cmdline = cmdline if cmdline is not None else ["/usr/bin/worker", "--port", "8080"]
        self._num_threads = num_threads
        self._cpu_percent = cpu_percent
        self._memory_percent = memory_percent
        self._rss = rss
        self._vms = vms
        self._create_time = create_time
        self._raise_on = raise_on or {}
        self.actions_called: list[str] = []

    def oneshot(self):
        return nullcontext()

    def name(self) -> str:
        if "name" in self._raise_on:
            raise self._raise_on["name"]
        return self._name

    def username(self) -> str:
        if "username" in self._raise_on:
            raise self._raise_on["username"]
        return self._username

    def status(self) -> str:
        if "status" in self._raise_on:
            raise self._raise_on["status"]
        return self._status

    def exe(self) -> str:
        if "exe" in self._raise_on:
            raise self._raise_on["exe"]
        return self._exe

    def cmdline(self) -> list[str]:
        if "cmdline" in self._raise_on:
            raise self._raise_on["cmdline"]
        return self._cmdline

    def num_threads(self) -> int:
        if "num_threads" in self._raise_on:
            raise self._raise_on["num_threads"]
        return self._num_threads

    def cpu_percent(self, interval=None) -> float:
        if "cpu_percent" in self._raise_on:
            raise self._raise_on["cpu_percent"]
        return self._cpu_percent

    def memory_percent(self) -> float:
        if "memory_percent" in self._raise_on:
            raise self._raise_on["memory_percent"]
        return self._memory_percent

    def memory_info(self):
        if "memory_info" in self._raise_on:
            raise self._raise_on["memory_info"]
        return SimpleNamespace(rss=self._rss, vms=self._vms)

    def create_time(self) -> float:
        if "create_time" in self._raise_on:
            raise self._raise_on["create_time"]
        return self._create_time

    def suspend(self) -> None:
        if "suspend" in self._raise_on:
            raise self._raise_on["suspend"]
        self.actions_called.append("suspend")

    def resume(self) -> None:
        if "resume" in self._raise_on:
            raise self._raise_on["resume"]
        self.actions_called.append("resume")

    def terminate(self) -> None:
        if "terminate" in self._raise_on:
            raise self._raise_on["terminate"]
        self.actions_called.append("terminate")

    def kill(self) -> None:
        if "kill" in self._raise_on:
            raise self._raise_on["kill"]
        self.actions_called.append("kill")


def test_get_detail_returns_complete_process_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    created_ts = 1_710_000_000.0
    fake_proc = _FakePsutilProcess(
        1234,
        name="uvicorn",
        username="dev",
        status="running",
        exe="/opt/venv/bin/python",
        cmdline=["/opt/venv/bin/python", "-m", "uvicorn", "app:main"],
        num_threads=8,
        cpu_percent=24.5,
        memory_percent=6.2,
        rss=300 * 1024 * 1024,
        vms=900 * 1024 * 1024,
        create_time=created_ts,
    )
    monkeypatch.setattr("psutil.Process", lambda pid: fake_proc)

    service = ProcessControlService()
    detail = service.get_detail(1234)

    assert isinstance(detail, ProcessDetail)
    assert detail.pid == 1234
    assert detail.name == "uvicorn"
    assert detail.username == "dev"
    assert detail.status == "running"
    assert detail.exe == "/opt/venv/bin/python"
    assert detail.cmdline == ["/opt/venv/bin/python", "-m", "uvicorn", "app:main"]
    assert detail.num_threads == 8
    assert detail.cpu_percent == 24.5
    assert detail.memory_percent == 6.2
    assert detail.rss_bytes == 300 * 1024 * 1024
    assert detail.vms_bytes == 900 * 1024 * 1024
    assert detail.created_at == datetime.fromtimestamp(created_ts).strftime("%Y-%m-%d %H:%M:%S")


def test_get_detail_handles_restricted_or_missing_attributes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_proc = _FakePsutilProcess(
        777,
        name="kworker",
        raise_on={
            "username": psutil.AccessDenied(pid=777),
            "exe": psutil.AccessDenied(pid=777),
            "cmdline": psutil.AccessDenied(pid=777),
            "num_threads": psutil.NoSuchProcess(pid=777),
            "cpu_percent": psutil.AccessDenied(pid=777),
            "memory_percent": psutil.AccessDenied(pid=777),
            "memory_info": psutil.AccessDenied(pid=777),
            "create_time": psutil.AccessDenied(pid=777),
        },
    )
    monkeypatch.setattr("psutil.Process", lambda pid: fake_proc)

    service = ProcessControlService()
    detail = service.get_detail(777)

    assert detail.pid == 777
    assert detail.name == "kworker"
    assert detail.username == "N/D"
    assert detail.exe == "Sin permiso / N/D"
    assert detail.cmdline == []
    assert detail.num_threads is None
    assert detail.cpu_percent is None
    assert detail.memory_percent is None
    assert detail.rss_bytes is None
    assert detail.vms_bytes is None
    assert detail.created_at == "N/D"


def test_get_detail_propagates_no_such_process(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_missing(pid: int):
        raise psutil.NoSuchProcess(pid=pid)

    monkeypatch.setattr("psutil.Process", raise_missing)

    service = ProcessControlService()
    with pytest.raises(psutil.NoSuchProcess):
        service.get_detail(99999)


@pytest.mark.parametrize(
    ("action", "expected_fragment"),
    [
        ("suspend", "pausado"),
        ("resume", "reanudado"),
        ("terminate", "terminación"),
        ("kill", "KILL"),
    ],
)
def test_perform_action_executes_expected_signal(
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    expected_fragment: str,
) -> None:
    fake_proc = _FakePsutilProcess(555, name="demo-app")
    monkeypatch.setattr("psutil.Process", lambda pid: fake_proc)

    service = ProcessControlService()
    message = service.perform_action(555, action)  # type: ignore[arg-type]

    assert fake_proc.actions_called == [action]
    assert "555" in message
    assert expected_fragment in message


def test_perform_action_handles_no_such_process_during_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_proc = _FakePsutilProcess(
        888,
        name="ephemeral",
        raise_on={"terminate": psutil.NoSuchProcess(pid=888)},
    )
    monkeypatch.setattr("psutil.Process", lambda pid: fake_proc)

    service = ProcessControlService()
    message = service.perform_action(888, "terminate")

    assert "888" in message
    assert "ya no existe" in message.lower()


def test_perform_action_raises_permission_error_on_access_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_proc = _FakePsutilProcess(
        1,
        name="init",
        raise_on={"kill": psutil.AccessDenied(pid=1)},
    )
    monkeypatch.setattr("psutil.Process", lambda pid: fake_proc)

    service = ProcessControlService()
    with pytest.raises(PermissionError, match="PID 1"):
        service.perform_action(1, "kill")


def test_perform_action_raises_value_error_for_unsupported_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_proc = _FakePsutilProcess(4321, name="worker")
    monkeypatch.setattr("psutil.Process", lambda pid: fake_proc)

    service = ProcessControlService()
    with pytest.raises(ValueError, match="Acción no soportada"):
        service.perform_action(4321, "restart")  # type: ignore[arg-type]