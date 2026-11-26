from __future__ import annotations

import json
import platform
import shutil
import subprocess

from pc_info.models.gpu import GpuInfo, SystemGpuSnapshot

_GPU_SAFE_EXCEPTIONS = (
    OSError,
    subproc_err := subprocess.SubprocessError,
    ValueError,
    TypeError,
    KeyError,
    json.JSONDecodeError,
)


def _parse_float(raw: str | float | int | None) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip().replace("%", "").replace("C", "").replace("W", "")
    if not text or text.upper() in {"N/A", "[N/A]", "NA", "NONE"}:
        return None
    return float(text)


def _parse_mib_to_bytes(raw: str | float | int | None) -> int | None:
    val = _parse_float(raw)
    if val is None:
        return None
    return int(val * 1024 * 1024)


def _detect_vendor(name: str) -> str:
    lower = name.lower()
    if "nvidia" in lower or "geforce" in lower or "quadro" in lower or "rtx" in lower or "gtx" in lower:
        return "NVIDIA"
    if "amd" in lower or "radeon" in lower or "instinct" in lower:
        return "AMD"
    if "intel" in lower or "arc" in lower or "iris" in lower or "uhd" in lower:
        return "Intel"
    if "apple" in lower or "m1" in lower or "m2" in lower or "m3" in lower or "m4" in lower:
        return "Apple"
    return "N/D"


class GpuCollector:
    """Recolector multiplataforma de información de GPU con manejo seguro de fallos."""

    def __init__(self, *, timeout_sec: float = 1.5) -> None:
        self._timeout_sec = timeout_sec

    def _run_cmd(self, args: list[str]) -> str | None:
        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=self._timeout_sec,
                check=False,
            )
            if proc.returncode != 0 or not proc.stdout.strip():
                return None
            return proc.stdout.strip()
        except _GPU_SAFE_EXCEPTIONS:
            return None

    def _collect_nvidia_smi(self) -> list[GpuInfo]:
        if shutil.which("nvidia-smi") is None:
            return []

        output = self._run_cmd(
            [
                "nvidia-smi",
                "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits",
            ]
        )
        if not output:
            return []

        gpus: list[GpuInfo] = []
        for fallback_idx, line in enumerate(output.splitlines()):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2:
                continue
            try:
                idx = int(_parse_float(parts[0]) or fallback_idx)
                name = parts[1] or f"GPU {idx}"
                util = _parse_float(parts[2]) if len(parts) > 2 else None
                mem_used = _parse_mib_to_bytes(parts[3]) if len(parts) > 3 else None
                mem_total = _parse_mib_to_bytes(parts[4]) if len(parts) > 4 else None
                temp = _parse_float(parts[5]) if len(parts) > 5 else None
                power = _parse_float(parts[6]) if len(parts) > 6 else None

                gpus.append(
                    GpuInfo(
                        index=idx,
                        name=name,
                        vendor=_detect_vendor(name),
                        utilization_percent=util,
                        memory_used_bytes=mem_used,
                        memory_total_bytes=mem_total,
                        temperature_c=temp,
                        power_watts=power,
                    )
                )
            except _GPU_SAFE_EXCEPTIONS:
                continue
        return gpus

    def _collect_macos(self) -> list[GpuInfo]:
        if shutil.which("system_profiler") is None:
            return []

        raw = self._run_cmd(["system_profiler", "SPDisplaysDataType", "-json"])
        if not raw:
            return []

        data = json.loads(raw)
        displays = data.get("SPDisplaysDataType", [])
        if not isinstance(displays, list):
            return []

        gpus: list[GpuInfo] = []
        for idx, item in enumerate(displays):
            if not isinstance(item, dict):
                continue
            name = str(item.get("sppci_model") or item.get("_name") or f"GPU {idx}")
            vram_raw = item.get("spdisplays_vram") or item.get("spdisplays_vram_shared")
            mem_total: int | None = None
            if isinstance(vram_raw, str):
                parts = vram_raw.strip().split()
                if len(parts) >= 2:
                    num = _parse_float(parts[0])
                    unit = parts[1].upper()
                    if num is not None:
                        mult = 1024**3 if "GB" in unit else 1024**2
                        mem_total = int(num * mult)

            gpus.append(
                GpuInfo(
                    index=idx,
                    name=name,
                    vendor=_detect_vendor(name),
                    memory_total_bytes=mem_total,
                )
            )
        return gpus

    def _collect_linux_lspci(self) -> list[GpuInfo]:
        if shutil.which("lspci") is None:
            return []

        raw = self._run_cmd(["lspci"])
        if not raw:
            return []

        gpus: list[GpuInfo] = []
        for line in raw.splitlines():
            lower = line.lower()
            if "vga compatible controller" in lower or "3d controller" in lower or "display controller" in lower:
                desc = line.split(":", 2)[-1].strip() if ":" in line else line.strip()
                idx = len(gpus)
                gpus.append(
                    GpuInfo(
                        index=idx,
                        name=desc or f"GPU {idx}",
                        vendor=_detect_vendor(desc),
                    )
                )
        return gpus

    def _collect_windows(self) -> list[GpuInfo]:
        if shutil.which("powershell") is None and shutil.which("pwsh") is None:
            return []

        shell = shutil.which("pwsh") or shutil.which("powershell")
        assert shell is not None
        cmd = (
            "Get-CimInstance Win32_VideoController | "
            "Select-Object Name,AdapterRAM | ConvertTo-Json -Compress"
        )
        raw = self._run_cmd([shell, "-NoProfile", "-Command", cmd])
        if not raw:
            return []

        parsed = json.loads(raw)
        items = parsed if isinstance(parsed, list) else [parsed]
        gpus: list[GpuInfo] = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            name = str(item.get("Name") or f"GPU {idx}")
            ram_val = item.get("AdapterRAM")
            mem_total = int(ram_val) if isinstance(ram_val, (int, float)) and ram_val > 0 else None
            gpus.append(
                GpuInfo(
                    index=idx,
                    name=name,
                    vendor=_detect_vendor(name),
                    memory_total_bytes=mem_total,
                )
            )
        return gpus

    def collect_snapshot(self) -> SystemGpuSnapshot:
        try:
            nvidia = self._collect_nvidia_smi()
            if nvidia:
                return SystemGpuSnapshot(gpus=nvidia, source="nvidia-smi")

            system = platform.system().lower()
            if system == "darwin":
                macos = self._collect_macos()
                if macos:
                    return SystemGpuSnapshot(gpus=macos, source="system_profiler")
            elif system == "linux":
                linux = self._collect_linux_lspci()
                if linux:
                    return SystemGpuSnapshot(gpus=linux, source="lspci")
            elif system == "windows":
                win = self._collect_windows()
                if win:
                    return SystemGpuSnapshot(gpus=win, source="Win32_VideoController")
        except _GPU_SAFE_EXCEPTIONS:
            pass

        return SystemGpuSnapshot(gpus=[], source="N/D")