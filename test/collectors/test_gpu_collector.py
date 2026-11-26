from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

from pc_info.collectors.gpu import GpuCollector
from pc_info.models.gpu import SystemGpuSnapshot


def test_gpu_collector_nvidia_smi_parsing(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/nvidia-smi" if cmd == "nvidia-smi" else None)

    csv_output = (
        "0, NVIDIA GeForce RTX 4080, 37, 2048, 16384, 54, 112.5\n"
        "1, NVIDIA RTX A2000, 12, N/A, 6144, 45, [N/A]\n"
    )

    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout=csv_output, stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    collector = GpuCollector()
    snapshot = collector.collect_snapshot()

    assert isinstance(snapshot, SystemGpuSnapshot)
    assert snapshot.source == "nvidia-smi"
    assert len(snapshot.gpus) == 2

    gpu0 = snapshot.gpus[0]
    assert gpu0.index == 0
    assert gpu0.name == "NVIDIA GeForce RTX 4080"
    assert gpu0.vendor == "NVIDIA"
    assert gpu0.utilization_percent == 37.0
    assert gpu0.memory_used_bytes == 2048 * 1024 * 1024
    assert gpu0.memory_total_bytes == 16384 * 1024 * 1024
    assert gpu0.temperature_c == 54.0
    assert gpu0.power_watts == 112.5

    gpu1 = snapshot.gpus[1]
    assert gpu1.memory_used_bytes is None
    assert gpu1.power_watts is None
    assert gpu1.memory_total_bytes == 6144 * 1024 * 1024


def test_gpu_collector_macos_system_profiler(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/sbin/system_profiler" if cmd == "system_profiler" else None)
    monkeypatch.setattr("platform.system", lambda: "Darwin")

    payload = {
        "SPDisplaysDataType": [
            {
                "sppci_model": "Apple M3 Pro",
                "spdisplays_vram_shared": "18 GB",
            }
        ]
    }

    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""),
    )

    collector = GpuCollector()
    snapshot = collector.collect_snapshot()

    assert snapshot.source == "system_profiler"
    assert len(snapshot.gpus) == 1
    assert snapshot.gpus[0].name == "Apple M3 Pro"
    assert snapshot.gpus[0].vendor == "Apple"
    assert snapshot.gpus[0].memory_total_bytes == 18 * 1024**3


def test_gpu_collector_linux_lspci_fallback(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/lspci" if cmd == "lspci" else None)
    monkeypatch.setattr("platform.system", lambda: "Linux")

    lspci_out = (
        "00:02.0 VGA compatible controller: Intel Corporation AlderLake-GT2 [Iris Xe Graphics]\n"
        "01:00.0 3D controller: AMD/ATI [Advanced Micro Devices, Inc.] Navi 31 [Radeon RX 7900 XTX]\n"
    )

    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=lspci_out, stderr=""),
    )

    collector = GpuCollector()
    snapshot = collector.collect_snapshot()

    assert snapshot.source == "lspci"
    assert len(snapshot.gpus) == 2
    assert snapshot.gpus[0].vendor == "Intel"
    assert snapshot.gpus[1].vendor == "AMD"


def test_gpu_collector_handles_timeout_and_missing_tools(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    monkeypatch.setattr("platform.system", lambda: "Linux")

    collector = GpuCollector()
    snapshot = collector.collect_snapshot()

    assert snapshot.gpus == []
    assert snapshot.source == "N/D"

    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/nvidia-smi" if cmd == "nvidia-smi" else None)

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="nvidia-smi", timeout=1.5)

    monkeypatch.setattr("subprocess.run", raise_timeout)
    snapshot_after_timeout = collector.collect_snapshot()
    assert snapshot_after_timeout.gpus == []
    assert snapshot_after_timeout.source == "N/D"