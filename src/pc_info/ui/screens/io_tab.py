from __future__ import annotations

from collections import deque

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import DataTable, Label, Static

from pc_info.models.io_stats import SystemIoSnapshot

_SPARK_CHARS = "▁▂▃▄▅▆▇█"
_HISTORY_MAX_POINTS = 60


def _format_bytes(num_bytes: int | float | None) -> str:
    if num_bytes is None:
        return "N/D"
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return "N/D"


def _format_rate(bytes_per_sec: float | None) -> str:
    if bytes_per_sec is None:
        return "N/D"
    return f"{_format_bytes(bytes_per_sec)}/s"


def _build_sparkline(values: list[float]) -> str:
    if not values:
        return "Sin datos aún"
    low = min(values)
    high = max(values)
    if high <= low:
        return _SPARK_CHARS[len(_SPARK_CHARS) // 2] * len(values)
    span = high - low
    chars: list[str] = []
    for val in values:
        ratio = (val - low) / span
        idx = min(int(ratio * (len(_SPARK_CHARS) - 1)), len(_SPARK_CHARS) - 1)
        chars.append(_SPARK_CHARS[idx])
    return "".join(chars)


class IoTab(VerticalScroll):
    """Tercera pestaña con tráfico de red y lectura/escritura de disco en tiempo real."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._net_rate_history: deque[float] = deque(maxlen=_HISTORY_MAX_POINTS)
        self._disk_rate_history: deque[float] = deque(maxlen=_HISTORY_MAX_POINTS)

    def compose(self) -> ComposeResult:
        yield Label("Resumen de Red y Almacenamiento I/O", classes="section-title")

        with Horizontal(classes="summary-grid"):
            with Container(classes="card"):
                yield Label("Tráfico de Red Global", classes="card-title")
                yield Static("Subida (TX): 0.0 B/s", id="net-tx-rate")
                yield Static("Bajada (RX): 0.0 B/s", id="net-rx-rate")
                yield Static("Sin datos aún", id="net-sparkline", classes="chart-sparkline")
                yield Static("Máx reciente: N/D", id="net-spark-meta", classes="chart-meta")

            with Container(classes="card card-last"):
                yield Label("I/O de Disco Global", classes="card-title")
                yield Static("Lectura: 0.0 B/s", id="disk-read-rate")
                yield Static("Escritura: 0.0 B/s", id="disk-write-rate")
                yield Static("Sin datos aún", id="disk-sparkline", classes="chart-sparkline")
                yield Static("Máx reciente: N/D", id="disk-spark-meta", classes="chart-meta")

        yield Label("Interfaces de Red", classes="section-title")
        yield DataTable(id="net-interfaces-table")

        yield Label("Actividad de Discos / Dispositivos", classes="section-title")
        yield DataTable(id="disk-io-table")

    def on_mount(self) -> None:
        net_table = self.query_one("#net-interfaces-table", DataTable)
        net_table.add_columns(
            "Interfaz", "Estado", "TX / s", "RX / s", "Enviado total", "Recibido total", "Errores"
        )
        net_table.cursor_type = "row"

        disk_table = self.query_one("#disk-io-table", DataTable)
        disk_table.add_columns(
            "Dispositivo", "Lectura / s", "Escritura / s", "Leído total", "Escrito total", "Ops (R/W)"
        )
        disk_table.cursor_type = "row"

    def _restore_scroll(
        self,
        tab_scroll_x: float,
        tab_scroll_y: float,
        net_table: DataTable,
        net_scroll_x: float,
        net_scroll_y: float,
        disk_table: DataTable,
        disk_scroll_x: float,
        disk_scroll_y: float,
    ) -> None:
        if tab_scroll_x > 0 or tab_scroll_y > 0:
            self.scroll_to(x=tab_scroll_x, y=tab_scroll_y, animate=False)
        if net_scroll_x > 0 or net_scroll_y > 0:
            net_table.scroll_to(x=net_scroll_x, y=net_scroll_y, animate=False)
        if disk_scroll_x > 0 or disk_scroll_y > 0:
            disk_table.scroll_to(x=disk_scroll_x, y=disk_scroll_y, animate=False)

    def update_snapshot(self, snapshot: SystemIoSnapshot) -> None:
        tab_scroll_x = self.scroll_x
        tab_scroll_y = self.scroll_y
        net_table = self.query_one("#net-interfaces-table", DataTable)
        disk_table = self.query_one("#disk-io-table", DataTable)
        net_scroll_x, net_scroll_y = net_table.scroll_x, net_table.scroll_y
        disk_scroll_x, disk_scroll_y = disk_table.scroll_x, disk_table.scroll_y

        self.query_one("#net-tx-rate", Static).update(
            f"Subida (TX): {_format_rate(snapshot.total_tx_bytes_per_sec)}"
        )
        self.query_one("#net-rx-rate", Static).update(
            f"Bajada (RX): {_format_rate(snapshot.total_rx_bytes_per_sec)}"
        )

        combined_net = snapshot.total_tx_bytes_per_sec + snapshot.total_rx_bytes_per_sec
        self._net_rate_history.append(combined_net)
        net_hist = list(self._net_rate_history)
        self.query_one("#net-sparkline", Static).update(_build_sparkline(net_hist))
        self.query_one("#net-spark-meta", Static).update(
            f"Total actual: {_format_rate(combined_net)} · Pico: {_format_rate(max(net_hist))}"
        )

        self.query_one("#disk-read-rate", Static).update(
            f"Lectura: {_format_rate(snapshot.total_read_bytes_per_sec)}"
        )
        self.query_one("#disk-write-rate", Static).update(
            f"Escritura: {_format_rate(snapshot.total_write_bytes_per_sec)}"
        )

        combined_disk = snapshot.total_read_bytes_per_sec + snapshot.total_write_bytes_per_sec
        self._disk_rate_history.append(combined_disk)
        disk_hist = list(self._disk_rate_history)
        self.query_one("#disk-sparkline", Static).update(_build_sparkline(disk_hist))
        self.query_one("#disk-spark-meta", Static).update(
            f"Total actual: {_format_rate(combined_disk)} · Pico: {_format_rate(max(disk_hist))}"
        )

        net_table.clear()
        for iface in snapshot.interfaces:
            state_str = "UP" if iface.is_up else "DOWN"
            err_in = iface.errin if iface.errin is not None else 0
            err_out = iface.errout if iface.errout is not None else 0
            err_str = f"{err_in}/{err_out}"
            net_table.add_row(
                iface.name,
                state_str,
                _format_rate(iface.tx_bytes_per_sec),
                _format_rate(iface.rx_bytes_per_sec),
                _format_bytes(iface.bytes_sent),
                _format_bytes(iface.bytes_recv),
                err_str,
            )

        disk_table.clear()
        for disk in snapshot.disks:
            r_ops = disk.read_count if disk.read_count is not None else 0
            w_ops = disk.write_count if disk.write_count is not None else 0
            disk_table.add_row(
                disk.name,
                _format_rate(disk.read_bytes_per_sec),
                _format_rate(disk.write_bytes_per_sec),
                _format_bytes(disk.read_bytes),
                _format_bytes(disk.write_bytes),
                f"{r_ops}/{w_ops}",
            )

        self.call_after_refresh(
            self._restore_scroll,
            tab_scroll_x,
            tab_scroll_y,
            net_table,
            net_scroll_x,
            net_scroll_y,
            disk_table,
            disk_scroll_x,
            disk_scroll_y,
        )