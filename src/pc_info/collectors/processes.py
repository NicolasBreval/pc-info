from __future__ import annotations

import psutil

from pc_info.models.processes import ProcessEntry, SystemProcessesSnapshot

_PROC_SAFE_EXCEPTIONS = (
    psutil.NoSuchProcess,
    psutil.AccessDenied,
    psutil.ZombieProcess,
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
)


class ProcessCollector:
    """Recolector multiplataforma de uso de CPU global y procesos activos."""

    def __init__(self, *, max_processes: int = 50) -> None:
        self._max_processes = max_processes
        # Primera llamada no bloqueante para inicializar el contador delta de psutil
        self._prime_cpu_counters()

    @staticmethod
    def _prime_cpu_counters() -> None:
        try:
            psutil.cpu_percent(interval=None)
            psutil.cpu_percent(interval=None, percpu=True)
        except _PROC_SAFE_EXCEPTIONS:
            pass

    def _collect_cpu_usage(self) -> tuple[float | None, list[float]]:
        total_cpu: float | None = None
        per_core: list[float] = []

        try:
            value = psutil.cpu_percent(interval=None)
            if value is not None:
                total_cpu = float(value)
        except _PROC_SAFE_EXCEPTIONS:
            total_cpu = None

        try:
            core_values = psutil.cpu_percent(interval=None, percpu=True)
            if core_values:
                per_core = [float(v) for v in core_values if v is not None]
        except _PROC_SAFE_EXCEPTIONS:
            per_core = []

        return total_cpu, per_core

    def collect_snapshot(self) -> SystemProcessesSnapshot:
        total_cpu, per_core = self._collect_cpu_usage()

        entries: list[ProcessEntry] = []
        total_count = 0
        running_count = 0

        attrs = [
            "pid",
            "name",
            "username",
            "status",
            "cpu_percent",
            "memory_percent",
            "memory_info",
        ]

        try:
            iterator = psutil.process_iter(attrs=attrs)
        except _PROC_SAFE_EXCEPTIONS:
            iterator = ()

        for proc in iterator:
            try:
                info = proc.info
                total_count += 1

                status_raw = info.get("status")
                status_str = str(status_raw) if status_raw else "N/D"
                if status_str == psutil.STATUS_RUNNING:
                    running_count += 1

                pid = int(info.get("pid") or proc.pid)
                name_raw = info.get("name")
                name = str(name_raw).strip() if name_raw else f"pid-{pid}"

                user_raw = info.get("username")
                username = str(user_raw).strip() if user_raw else "N/D"

                cpu_raw = info.get("cpu_percent")
                cpu_pct = float(cpu_raw) if cpu_raw is not None else None

                mem_raw = info.get("memory_percent")
                mem_pct = float(mem_raw) if mem_raw is not None else None

                mem_info = info.get("memory_info")
                rss_val = getattr(mem_info, "rss", None) if mem_info is not None else None
                rss_bytes = int(rss_val) if rss_val is not None else None

                entries.append(
                    ProcessEntry(
                        pid=pid,
                        name=name,
                        username=username,
                        status=status_str,
                        cpu_percent=cpu_pct,
                        memory_percent=mem_pct,
                        rss_bytes=rss_bytes,
                    )
                )
            except _PROC_SAFE_EXCEPTIONS:
                continue

        entries.sort(
            key=lambda item: (
                item.cpu_percent if item.cpu_percent is not None else -1.0,
                item.memory_percent if item.memory_percent is not None else -1.0,
                item.rss_bytes if item.rss_bytes is not None else -1,
            ),
            reverse=True,
        )

        return SystemProcessesSnapshot(
            total_cpu_percent=total_cpu,
            per_core_cpu_percent=per_core,
            total_processes=total_count,
            running_processes=running_count,
            processes=entries[: self._max_processes],
        )