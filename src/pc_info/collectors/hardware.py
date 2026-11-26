from __future__ import annotations

import platform
import socket

import cpuinfo
import psutil

from pc_info.models.hardware import (
    CpuDynamicInfo,
    CpuStaticInfo,
    DiskPartitionInfo,
    MemoryInfo,
    SystemHardwareSnapshot,
    TemperatureSensorInfo,
)

_SAFE_EXCEPTIONS = (
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
    NotImplementedError,
    psutil.Error,
)


def _get_cpu_model_name() -> str:
    try:
        info = cpuinfo.get_cpu_info()
        brand = info.get("brand_raw")
        if isinstance(brand, str) and brand.strip():
            return brand.strip()
    except _SAFE_EXCEPTIONS:
        pass

    processor = platform.processor()
    if processor and processor.strip():
        return processor.strip()

    machine = platform.machine()
    return machine.strip() if machine else "N/D"


def collect_cpu_static() -> CpuStaticInfo:
    physical_cores: int | None = None
    logical_cores: int | None = None
    min_freq: float | None = None
    max_freq: float | None = None

    try:
        physical_cores = psutil.cpu_count(logical=False)
    except _SAFE_EXCEPTIONS:
        physical_cores = None

    try:
        logical_cores = psutil.cpu_count(logical=True)
    except _SAFE_EXCEPTIONS:
        logical_cores = None

    try:
        freq = psutil.cpu_freq()
        if freq is not None:
            min_freq = float(freq.min) if freq.min else None
            max_freq = float(freq.max) if freq.max else None
    except _SAFE_EXCEPTIONS:
        min_freq = None
        max_freq = None

    try:
        arch = platform.machine() or "N/D"
    except _SAFE_EXCEPTIONS:
        arch = "N/D"

    return CpuStaticInfo(
        model_name=_get_cpu_model_name(),
        architecture=arch,
        physical_cores=physical_cores,
        logical_cores=logical_cores,
        max_freq_mhz=max_freq,
        min_freq_mhz=min_freq,
    )


def collect_cpu_dynamic() -> CpuDynamicInfo:
    current_freq: float | None = None
    per_core_freq: list[float] = []

    try:
        freq = psutil.cpu_freq()
        if freq is not None and freq.current is not None:
            current_freq = float(freq.current)
    except _SAFE_EXCEPTIONS:
        current_freq = None

    try:
        per_cpu = psutil.cpu_freq(percpu=True)
        if per_cpu:
            per_core_freq = [
                float(item.current) for item in per_cpu if item is not None and item.current is not None
            ]
    except _SAFE_EXCEPTIONS:
        per_core_freq = []

    return CpuDynamicInfo(
        current_freq_mhz=current_freq,
        per_core_freq_mhz=per_core_freq,
    )


def collect_memory_info() -> MemoryInfo:
    mem_info = MemoryInfo()

    try:
        vm = psutil.virtual_memory()
        mem_info.total_bytes = int(vm.total)
        mem_info.available_bytes = int(vm.available)
        mem_info.used_bytes = int(vm.used)
        mem_info.percent = float(vm.percent)
    except _SAFE_EXCEPTIONS:
        pass

    try:
        sm = psutil.swap_memory()
        mem_info.swap_total_bytes = int(sm.total)
        mem_info.swap_used_bytes = int(sm.used)
        mem_info.swap_percent = float(sm.percent)
    except _SAFE_EXCEPTIONS:
        pass

    return mem_info


def collect_disk_partitions() -> list[DiskPartitionInfo]:
    partitions: list[DiskPartitionInfo] = []

    try:
        raw_parts = psutil.disk_partitions(all=False)
    except _SAFE_EXCEPTIONS:
        return partitions

    for part in raw_parts:
        total: int | None = None
        used: int | None = None
        free: int | None = None
        percent: float | None = None

        try:
            usage = psutil.disk_usage(part.mountpoint)
            total = int(usage.total)
            used = int(usage.used)
            free = int(usage.free)
            percent = float(usage.percent)
        except _SAFE_EXCEPTIONS:
            pass

        partitions.append(
            DiskPartitionInfo(
                device=part.device or "N/D",
                mountpoint=part.mountpoint or "N/D",
                fstype=part.fstype or "N/D",
                total_bytes=total,
                used_bytes=used,
                free_bytes=free,
                percent=percent,
            )
        )

    return partitions


def collect_temperatures() -> list[TemperatureSensorInfo]:
    sensors: list[TemperatureSensorInfo] = []

    if not hasattr(psutil, "sensors_temperatures"):
        return sensors

    try:
        raw_temps = psutil.sensors_temperatures()
    except _SAFE_EXCEPTIONS:
        return sensors

    if not raw_temps:
        return sensors

    for chip_name, entries in raw_temps.items():
        for index, entry in enumerate(entries):
            label = entry.label.strip() if entry.label else f"{chip_name} #{index + 1}"
            sensors.append(
                TemperatureSensorInfo(
                    label=label,
                    current_c=float(entry.current) if entry.current is not None else None,
                    high_c=float(entry.high) if entry.high is not None else None,
                    critical_c=float(entry.critical) if entry.critical is not None else None,
                )
            )

    return sensors


def collect_battery_info() -> tuple[float | None, bool | None]:
    if not hasattr(psutil, "sensors_battery"):
        return None, None

    try:
        battery = psutil.sensors_battery()
    except _SAFE_EXCEPTIONS:
        return None, None

    if battery is None:
        return None, None

    percent = float(battery.percent) if battery.percent is not None else None
    plugged = bool(battery.power_plugged) if battery.power_plugged is not None else None
    return percent, plugged


class HardwareCollector:
    """Recolector multiplataforma de información de hardware con caché de datos estáticos."""

    def __init__(self) -> None:
        self._cpu_static: CpuStaticInfo | None = None
        self._os_name: str = self._read_os_name()
        self._os_version: str = self._read_os_version()
        self._hostname: str = self._read_hostname()

    @staticmethod
    def _read_os_name() -> str:
        try:
            return platform.system() or "N/D"
        except _SAFE_EXCEPTIONS:
            return "N/D"

    @staticmethod
    def _read_os_version() -> str:
        try:
            return platform.release() or platform.version() or "N/D"
        except _SAFE_EXCEPTIONS:
            return "N/D"

    @staticmethod
    def _read_hostname() -> str:
        try:
            return socket.gethostname() or "N/D"
        except _SAFE_EXCEPTIONS:
            return "N/D"

    def get_cpu_static(self, *, refresh: bool = False) -> CpuStaticInfo:
        if self._cpu_static is None or refresh:
            self._cpu_static = collect_cpu_static()
        return self._cpu_static

    def collect_snapshot(self) -> SystemHardwareSnapshot:
        battery_percent, battery_plugged = collect_battery_info()
        return SystemHardwareSnapshot(
            os_name=self._os_name,
            os_version=self._os_version,
            hostname=self._hostname,
            cpu_static=self.get_cpu_static(),
            cpu_dynamic=collect_cpu_dynamic(),
            memory=collect_memory_info(),
            disks=collect_disk_partitions(),
            temperatures=collect_temperatures(),
            battery_percent=battery_percent,
            battery_plugged=battery_plugged,
        )