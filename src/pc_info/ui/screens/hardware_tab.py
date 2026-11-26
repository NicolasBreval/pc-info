from __future__ import annotations

from collections import deque

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import DataTable, Label, ProgressBar, Static

from pc_info.models.gpu import SystemGpuSnapshot
from pc_info.models.hardware import SystemHardwareSnapshot

_SPARK_CHARS = "▁▂▃▄▅▆▇█"
_HISTORY_MAX_POINTS = 60
_TWO_COLUMN_THRESHOLD = 8

_INTEL_ART = """\
   .-------------------------.
  /   _             _   _     \\
 |   (_)           | | | |     |
 |    _   _ __   ___| |_| |    |
 |   | | | '_ \\ / _ \\ __| |    |
 |   | | | | | |  __/ |_| |    |
  \\  |_| |_| |_|\\___|\\__|_|   /
   '-------------------------'\
"""

_AMD_ART = """\
      /\\        _    __  __ ____
     /  \\      / \\  |  \\/  |  _ \\
    / /\\ \\    / _ \\ | |\\/| | | | |
   / ____ \\  / ___ \\| |  | | |_| |
  /_/    \\_\\/_/   \\_\\_|  |_|____/
      \\  /
       \\/\
"""

_APPLE_ART = """\
          .:'
      __ :'__
   .'`__`-'__``.
  :__________.-'
  :_________:
   :_________`-;
    `.__.-.__.'
"""

_GENERIC_CPU_ART = """\
   +---------------+
   |  .---------.  |
   |  |   CPU   |  |
   |  '---------'  |
   +---------------+
     | | | | | | |\
"""


def _format_bytes(num_bytes: int | float | None) -> str:
    if num_bytes is None:
        return "N/D"
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return "N/D"


def _select_cpu_ascii_art(model_name: str, architecture: str) -> str:
    haystack = f"{model_name} {architecture}".lower()
    if "intel" in haystack:
        return _INTEL_ART
    if "amd" in haystack or "ryzen" in haystack or "epyc" in haystack or "threadripper" in haystack:
        return _AMD_ART
    if "apple" in haystack:
        return _APPLE_ART
    return _GENERIC_CPU_ART


def _build_sparkline(
    values: list[float], *, min_val: float | None = None, max_val: float | None = None
) -> str:
    if not values:
        return "Sin datos aún"

    low = min_val if min_val is not None else min(values)
    high = max_val if max_val is not None else max(values)

    if high <= low:
        return _SPARK_CHARS[len(_SPARK_CHARS) // 2] * len(values)

    span = high - low
    chars: list[str] = []
    for val in values:
        clamped = min(max(val, low), high)
        ratio = (clamped - low) / span
        idx = min(int(ratio * (len(_SPARK_CHARS) - 1)), len(_SPARK_CHARS) - 1)
        chars.append(_SPARK_CHARS[idx])
    return "".join(chars)


def _build_bar(ratio: float, width: int = 16) -> str:
    clamped = min(max(ratio, 0.0), 1.0)
    filled = round(clamped * width)
    return "█" * filled + "░" * (width - filled)


def _format_core_lines(cores: list[tuple[int, float]], *, max_mhz: float, bar_width: int) -> str:
    lines: list[str] = []
    for idx, mhz in cores:
        bar = _build_bar(mhz / max_mhz, width=bar_width)
        lines.append(f"C{idx:02d}: {bar} {mhz:6.0f} MHz")
    return "\n".join(lines)


class HardwareTab(VerticalScroll):
    """Pestaña informacional desplazable de hardware, GPU y gráficos en terminal."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._freq_history: deque[float] = deque(maxlen=_HISTORY_MAX_POINTS)
        self._ram_history: deque[float] = deque(maxlen=_HISTORY_MAX_POINTS)

    def compose(self) -> ComposeResult:
        yield Label("Resumen de Equipo y CPU", classes="section-title")

        with Horizontal(classes="summary-grid"):
            with Container(classes="card"):
                yield Label("Sistema", classes="card-title")
                yield Static("Equipo: N/D", id="hw-host")
                yield Static("SO: N/D", id="hw-os")
                yield Static("Batería: N/D", id="hw-battery")

            with Container(classes="card card-last"):
                yield Label("Procesador (CPU)", classes="card-title")
                with Horizontal(classes="cpu-header-grid"):
                    with Container(classes="cpu-details"):
                        yield Static("Modelo: N/D", id="cpu-model")
                        yield Static("Arquitectura: N/D", id="cpu-arch")
                        yield Static("Núcleos: N/D", id="cpu-cores")
                        yield Static("Frecuencia actual: N/D", id="cpu-freq")
                    yield Static(_GENERIC_CPU_ART, id="cpu-ascii-art", classes="cpu-art")

        yield Label("Gráficos de Rendimiento", classes="section-title")

        with Horizontal(classes="summary-grid"):
            with Container(classes="card chart-box"):
                yield Label("Historial de Frecuencia CPU", classes="chart-title")
                yield Static("Sin datos aún", id="freq-sparkline", classes="chart-sparkline")
                yield Static("Mín / Máx: N/D", id="freq-stats", classes="chart-meta")

            with Container(classes="card card-last chart-box"):
                yield Label("Historial de Uso de RAM (%)", classes="chart-title")
                yield Static("Sin datos aún", id="ram-sparkline", classes="chart-sparkline")
                yield Static("0% - 100%", id="ram-stats", classes="chart-meta")

        with Container(classes="chart-box"):
            yield Label("Frecuencia por Núcleo Lógico", classes="chart-title")
            with Horizontal(classes="cores-columns"):
                yield Static(
                    "Sin datos de frecuencia por núcleo disponibles",
                    id="per-core-left",
                    classes="chart-bars core-col-left",
                )
                yield Static(
                    "",
                    id="per-core-right",
                    classes="chart-bars core-col-right",
                )

        yield Label("Memoria RAM y Swap", classes="section-title")

        with Horizontal(classes="summary-grid"):
            with Container(classes="card"):
                yield Label("RAM", classes="card-title")
                yield Static("Uso: N/D", id="ram-text", classes="progress-label")
                yield ProgressBar(total=100, show_eta=False, id="ram-bar")

            with Container(classes="card card-last"):
                yield Label("Swap", classes="card-title")
                yield Static("Uso: N/D", id="swap-text", classes="progress-label")
                yield ProgressBar(total=100, show_eta=False, id="swap-bar")

        yield Label("Almacenamiento", classes="section-title")
        yield DataTable(id="disks-table")

        yield Label("Gráficos (GPU)", classes="section-title")
        yield Static("Detectando GPUs...", id="gpu-summary-meta", classes="chart-meta")
        yield DataTable(id="gpu-table")

        yield Label("Sensores de Temperatura", classes="section-title")
        yield Static("Sin sensores disponibles o N/D", id="temps-summary")

    def on_mount(self) -> None:
        table = self.query_one("#disks-table", DataTable)
        table.add_columns("Dispositivo", "Montaje", "FS", "Usado / Total", "Uso %")
        table.cursor_type = "row"

        gpu_table = self.query_one("#gpu-table", DataTable)
        gpu_table.add_columns(
            "Idx", "Modelo", "Fabricante", "Uso %", "VRAM Usada / Total", "Temp / Potencia"
        )
        gpu_table.cursor_type = "row"

    @staticmethod
    def _safe_scroll_xy(widget: object) -> tuple[float, float]:
        try:
            sx = float(getattr(widget, "scroll_x", 0.0) or 0.0)
            sy = float(getattr(widget, "scroll_y", 0.0) or 0.0)
            return sx, sy
        except Exception:
            return 0.0, 0.0

    def _restore_scroll(
        self,
        tab_scroll_x: float,
        tab_scroll_y: float,
        disks_table: DataTable | None,
        disks_scroll_x: float,
        disks_scroll_y: float,
        gpu_table: DataTable | None,
        gpu_scroll_x: float,
        gpu_scroll_y: float,
    ) -> None:
        if tab_scroll_x > 0 or tab_scroll_y > 0:
            self.scroll_to(x=tab_scroll_x, y=tab_scroll_y, animate=False)
        if disks_table is not None and (disks_scroll_x > 0 or disks_scroll_y > 0):
            disks_table.scroll_to(x=disks_scroll_x, y=disks_scroll_y, animate=False)
        if gpu_table is not None and (gpu_scroll_x > 0 or gpu_scroll_y > 0):
            gpu_table.scroll_to(x=gpu_scroll_x, y=gpu_scroll_y, animate=False)

    def _schedule_scroll_restore(self) -> None:
        tab_sx, tab_sy = self._safe_scroll_xy(self)
        disks_table = self.query_one("#disks-table", DataTable)
        gpu_table = self.query_one("#gpu-table", DataTable)
        disks_sx, disks_sy = self._safe_scroll_xy(disks_table)
        gpu_sx, gpu_sy = self._safe_scroll_xy(gpu_table)

        self.refresh(layout=True)
        self.call_after_refresh(
            self._restore_scroll,
            tab_sx,
            tab_sy,
            disks_table,
            disks_sx,
            disks_sy,
            gpu_table,
            gpu_sx,
            gpu_sy,
        )

    def _update_per_core_bars(self, per_core: list[float]) -> None:
        left_widget = self.query_one("#per-core-left", Static)
        right_widget = self.query_one("#per-core-right", Static)

        if not per_core:
            left_widget.update("Sin datos de frecuencia por núcleo disponibles")
            right_widget.update("")
            right_widget.display = False
            return

        core_max = max(per_core) if max(per_core) > 0 else 1.0
        indexed = list(enumerate(per_core))

        if len(indexed) > _TWO_COLUMN_THRESHOLD:
            midpoint = (len(indexed) + 1) // 2
            left_widget.update(
                _format_core_lines(indexed[:midpoint], max_mhz=core_max, bar_width=12)
            )
            right_widget.update(
                _format_core_lines(indexed[midpoint:], max_mhz=core_max, bar_width=12)
            )
            right_widget.display = True
        else:
            left_widget.update(_format_core_lines(indexed, max_mhz=core_max, bar_width=18))
            right_widget.update("")
            right_widget.display = False

    def update_gpu_snapshot(self, gpu_snapshot: SystemGpuSnapshot) -> None:
        gpu_table = self.query_one("#gpu-table", DataTable)
        meta_widget = self.query_one("#gpu-summary-meta", Static)

        if not gpu_snapshot.gpus:
            meta_widget.update(
                f"Sin GPUs detectadas o métricas no disponibles (fuente: {gpu_snapshot.source})"
            )
        else:
            meta_widget.update(
                f"GPUs detectadas: {len(gpu_snapshot.gpus)} · Fuente: {gpu_snapshot.source}"
            )

        gpu_table.clear()
        for gpu in gpu_snapshot.gpus:
            util_str = (
                f"{gpu.utilization_percent:.0f}%"
                if gpu.utilization_percent is not None
                else "N/D"
            )
            if gpu.memory_used_bytes is not None or gpu.memory_total_bytes is not None:
                vram_str = (
                    f"{_format_bytes(gpu.memory_used_bytes)} / "
                    f"{_format_bytes(gpu.memory_total_bytes)}"
                )
            else:
                vram_str = "N/D"

            temp_part = f"{gpu.temperature_c:.0f} °C" if gpu.temperature_c is not None else "N/D"
            power_part = f"{gpu.power_watts:.1f} W" if gpu.power_watts is not None else "N/D"
            gpu_table.add_row(
                str(gpu.index),
                gpu.name,
                gpu.vendor,
                util_str,
                vram_str,
                f"{temp_part} / {power_part}",
            )

        self._schedule_scroll_restore()

    def update_snapshot(self, snapshot: SystemHardwareSnapshot) -> None:
        disks_table = self.query_one("#disks-table", DataTable)

        cpu = snapshot.cpu_static
        freq_mhz = snapshot.cpu_dynamic.current_freq_mhz
        freq_text = f"{freq_mhz:.0f} MHz" if freq_mhz is not None else "N/D"

        phys = cpu.physical_cores if cpu.physical_cores is not None else "?"
        logic = cpu.logical_cores if cpu.logical_cores is not None else "?"

        self.query_one("#hw-host", Static).update(f"Equipo: {snapshot.hostname}")
        self.query_one("#hw-os", Static).update(f"SO: {snapshot.os_name} ({snapshot.os_version})")

        if snapshot.battery_percent is not None:
            estado = "Cargando / Conectado" if snapshot.battery_plugged else "En batería"
            bat_str = f"{snapshot.battery_percent:.0f}% ({estado})"
        else:
            bat_str = "N/D"
        self.query_one("#hw-battery", Static).update(f"Batería: {bat_str}")

        self.query_one("#cpu-model", Static).update(f"Modelo: {cpu.model_name}")
        self.query_one("#cpu-arch", Static).update(f"Arquitectura: {cpu.architecture}")
        self.query_one("#cpu-cores", Static).update(f"Núcleos: {phys} físicos / {logic} lógicos")
        self.query_one("#cpu-freq", Static).update(f"Frecuencia actual: {freq_text}")
        self.query_one("#cpu-ascii-art", Static).update(
            _select_cpu_ascii_art(cpu.model_name, cpu.architecture)
        )

        if freq_mhz is not None:
            self._freq_history.append(freq_mhz)

        freq_values = list(self._freq_history)
        spark_widget = self.query_one("#freq-sparkline", Static)
        stats_widget = self.query_one("#freq-stats", Static)
        if freq_values:
            min_f = min(freq_values)
            max_f = max(freq_values)
            spark_widget.update(_build_sparkline(freq_values, min_val=min_f, max_val=max_f))
            stats_widget.update(
                f"Ventana ({len(freq_values)} muestras) · Mín: {min_f:.0f} MHz · Máx: {max_f:.0f} MHz"
            )
        else:
            spark_widget.update("Sin datos de frecuencia")
            stats_widget.update("N/D")

        self._update_per_core_bars(snapshot.cpu_dynamic.per_core_freq_mhz)

        mem = snapshot.memory
        ram_pct = mem.percent if mem.percent is not None else 0.0
        if mem.percent is not None:
            self._ram_history.append(ram_pct)

        ram_values = list(self._ram_history)
        ram_spark = self.query_one("#ram-sparkline", Static)
        ram_stats = self.query_one("#ram-stats", Static)
        if ram_values:
            ram_spark.update(_build_sparkline(ram_values, min_val=0.0, max_val=100.0))
            ram_stats.update(
                f"Actual: {ram_values[-1]:.1f}% · Mín: {min(ram_values):.1f}% · Máx: {max(ram_values):.1f}%"
            )
        else:
            ram_spark.update("Sin datos de RAM")
            ram_stats.update("N/D")

        ram_label = (
            f"Uso: {_format_bytes(mem.used_bytes)} / {_format_bytes(mem.total_bytes)}"
            if mem.percent is not None
            else "Uso: N/D"
        )
        self.query_one("#ram-text", Static).update(ram_label)
        self.query_one("#ram-bar", ProgressBar).update(progress=min(max(ram_pct, 0.0), 100.0))

        swap_pct = mem.swap_percent if mem.swap_percent is not None else 0.0
        swap_label = (
            f"Uso: {_format_bytes(mem.swap_used_bytes)} / {_format_bytes(mem.swap_total_bytes)}"
            if mem.swap_percent is not None
            else "Uso: N/D"
        )
        self.query_one("#swap-text", Static).update(swap_label)
        self.query_one("#swap-bar", ProgressBar).update(progress=min(max(swap_pct, 0.0), 100.0))

        disks_table.clear()
        for disk in snapshot.disks:
            pct_str = f"{disk.percent:.1f}%" if disk.percent is not None else "N/D"
            size_str = f"{_format_bytes(disk.used_bytes)} / {_format_bytes(disk.total_bytes)}"
            disks_table.add_row(disk.device, disk.mountpoint, disk.fstype, size_str, pct_str)

        if snapshot.temperatures:
            items = [
                f"{t.label}: {t.current_c:.1f} °C"
                for t in snapshot.temperatures[:6]
                if t.current_c is not None
            ]
            temps_str = " | ".join(items) if items else "Sin lecturas válidas"
        else:
            temps_str = "Sin sensores disponibles o N/D"
        self.query_one("#temps-summary", Static).update(temps_str)

        self._schedule_scroll_restore()