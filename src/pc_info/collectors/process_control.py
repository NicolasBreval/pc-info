from __future__ import annotations

from datetime import datetime
from typing import Literal

import psutil

from pc_info.models.process_detail import ProcessDetail

ProcessAction = Literal["suspend", "resume", "terminate", "kill"]

_DETAIL_SAFE_EXCEPTIONS = (
    psutil.NoSuchProcess,
    psutil.AccessDenied,
    psutil.ZombieProcess,
    OSError,
    ValueError,
    TypeError,
)


class ProcessControlService:
    """Inspección detallada y control seguro de procesos mediante psutil."""

    def get_detail(self, pid: int) -> ProcessDetail:
        proc = psutil.Process(pid)
        with proc.oneshot():
            name = proc.name()
            try:
                username = proc.username() or "N/D"
            except _DETAIL_SAFE_EXCEPTIONS:
                username = "N/D"

            try:
                status = str(proc.status())
            except _DETAIL_SAFE_EXCEPTIONS:
                status = "N/D"

            try:
                exe = proc.exe() or "N/D"
            except _DETAIL_SAFE_EXCEPTIONS:
                exe = "Sin permiso / N/D"

            try:
                cmd = list(proc.cmdline() or [])
            except _DETAIL_SAFE_EXCEPTIONS:
                cmd = []

            try:
                threads = int(proc.num_threads())
            except _DETAIL_SAFE_EXCEPTIONS:
                threads = None

            try:
                cpu_pct = float(proc.cpu_percent(interval=None))
            except _DETAIL_SAFE_EXCEPTIONS:
                cpu_pct = None

            try:
                mem_pct = float(proc.memory_percent())
            except _DETAIL_SAFE_EXCEPTIONS:
                mem_pct = None

            rss: int | None = None
            vms: int | None = None
            try:
                mem_info = proc.memory_info()
                rss = int(getattr(mem_info, "rss", 0))
                vms = int(getattr(mem_info, "vms", 0))
            except _DETAIL_SAFE_EXCEPTIONS:
                pass

            created_str = "N/D"
            try:
                created_ts = float(proc.create_time())
                created_str = datetime.fromtimestamp(created_ts).strftime("%Y-%m-%d %H:%M:%S")
            except _DETAIL_SAFE_EXCEPTIONS:
                pass

        return ProcessDetail(
            pid=pid,
            name=name,
            username=username,
            status=status,
            exe=exe,
            cmdline=cmd,
            num_threads=threads,
            cpu_percent=cpu_pct,
            memory_percent=mem_pct,
            rss_bytes=rss,
            vms_bytes=vms,
            created_at=created_str,
        )

    def perform_action(self, pid: int, action: ProcessAction) -> str:
        proc = psutil.Process(pid)
        proc_name = f"{proc.name()} (PID {pid})"
        try:
            if action == "suspend":
                proc.suspend()
                return f"Proceso pausado: {proc_name}"
            if action == "resume":
                proc.resume()
                return f"Proceso reanudado: {proc_name}"
            if action == "terminate":
                proc.terminate()
                return f"Señal de terminación enviada a {proc_name}"
            if action == "kill":
                proc.kill()
                return f"Señal KILL enviada a {proc_name}"
        except psutil.NoSuchProcess:
            return f"El proceso PID {pid} ya no existe"
        except psutil.AccessDenied:
            raise PermissionError(f"Permiso denegado al ejecutar '{action}' sobre PID {pid}")
        raise ValueError(f"Acción no soportada: {action}")