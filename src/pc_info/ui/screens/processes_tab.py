from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.message import Message
from textual.widgets import Button, DataTable, Input, Label, Select, Static

from pc_info.models.processes import ProcessEntry, SystemProcessesSnapshot

_SORT_OPTIONS: list[tuple[str, str]] = [
    ("CPU %", "cpu"),
    ("Memoria %", "mem"),
    ("RSS (bytes)", "rss"),
    ("Nombre", "name"),
    ("PID", "pid"),
]


def _format_bytes(num_bytes: int | None) -> str:
    if num_bytes is None:
        return "N/D"
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return "N/D"


def _matches_filter(proc: ProcessEntry, query: str) -> bool:
    needle = query.strip().lower()
    if not needle:
        return True
    haystack = " ".join(
        [
            str(proc.pid),
            proc.name or "",
            proc.username or "",
            proc.status or "",
        ]
    ).lower()
    return needle in haystack


def _sort_processes(
    processes: list[ProcessEntry],
    *,
    sort_by: str,
    descending: bool,
) -> list[ProcessEntry]:
    if sort_by == "name":
        return sorted(
            processes,
            key=lambda p: ((p.name or "").lower(), p.pid),
            reverse=descending,
        )
    if sort_by == "pid":
        return sorted(
            processes,
            key=lambda p: p.pid,
            reverse=descending,
        )
    if sort_by == "mem":
        return sorted(
            processes,
            key=lambda p: (
                p.memory_percent is not None,
                p.memory_percent if p.memory_percent is not None else -1.0,
            ),
            reverse=descending,
        )
    if sort_by == "rss":
        return sorted(
            processes,
            key=lambda p: (
                p.rss_bytes is not None,
                p.rss_bytes if p.rss_bytes is not None else -1,
            ),
            reverse=descending,
        )
    return sorted(
        processes,
        key=lambda p: (
            p.cpu_percent is not None,
            p.cpu_percent if p.cpu_percent is not None else -1.0,
        ),
        reverse=descending,
    )


class ProcessesTab(VerticalScroll):
    """Pestaña de procesos con filtrado, ordenación y apertura del inspector."""

    class ProcessInspectRequested(Message):
        """Solicita abrir el inspector para un PID seleccionado."""

        def __init__(self, pid: int) -> None:
            super().__init__()
            self.pid = pid

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._processes: list[ProcessEntry] = []
        self._filter_text: str = ""
        self._sort_by: str = "cpu"
        self._descending: bool = True
        self._total_cpu: float | None = None
        self._total_procs: int = 0
        self._running_procs: int = 0
        self._focused_pid: int | None = None

    def compose(self) -> ComposeResult:
        yield Label("Resumen de CPU y Procesos", classes="section-title")
        with Container(classes="card"):
            yield Static("CPU Global: N/D", id="proc-cpu-summary")
            yield Static(
                "Procesos: N/D (Enter en una fila para inspeccionar)",
                id="proc-count-summary",
            )

        yield Label("Filtrar y Ordenar", classes="section-title")
        with Horizontal(classes="proc-toolbar"):
            yield Input(
                placeholder="Filtrar por nombre, PID, usuario o estado...",
                id="proc-filter-input",
            )
            yield Select(
                options=_SORT_OPTIONS,
                value="cpu",
                allow_blank=False,
                id="proc-sort-select",
            )
            yield Button("Descendente", id="proc-sort-dir-btn", variant="primary")

        yield Label("Procesos Activos", classes="section-title")
        yield DataTable(id="processes-table")

    def on_mount(self) -> None:
        table = self.query_one("#processes-table", DataTable)
        table.add_columns("PID", "Nombre", "Usuario", "Estado", "CPU %", "MEM %", "RSS")
        table.cursor_type = "row"

    def _capture_focused_pid(self, table: DataTable, current_rows: list[ProcessEntry]) -> None:
        cursor_row = table.cursor_row
        if cursor_row is None or cursor_row < 0:
            return
        if cursor_row < len(current_rows):
            self._focused_pid = current_rows[cursor_row].pid
        else:
            self._focused_pid = None

    def _restore_pid_and_scroll(
        self,
        table: DataTable,
        matched_row_index: int | None,
        tab_scroll_x: float,
        tab_scroll_y: float,
        table_scroll_x: float,
        table_scroll_y: float,
    ) -> None:
        if matched_row_index is not None:
            table.move_cursor(row=matched_row_index, animate=False)
        else:
            self._focused_pid = None

        if tab_scroll_x > 0 or tab_scroll_y > 0:
            self.scroll_to(x=tab_scroll_x, y=tab_scroll_y, animate=False)
        if table_scroll_x > 0 or table_scroll_y > 0:
            table.scroll_to(x=table_scroll_x, y=table_scroll_y, animate=False)

    def _render_table(self) -> None:
        table = self.query_one("#processes-table", DataTable)
        table.cursor_type = "row"

        previous_visible = [
            p for p in self._processes if _matches_filter(p, self._filter_text)
        ]
        previous_ordered = _sort_processes(
            previous_visible,
            sort_by=self._sort_by,
            descending=self._descending,
        )
        self._capture_focused_pid(table, previous_ordered)

        tab_sx, tab_sy = self.scroll_x, self.scroll_y
        tbl_sx, tbl_sy = table.scroll_x, table.scroll_y

        filtered = [p for p in self._processes if _matches_filter(p, self._filter_text)]
        ordered = _sort_processes(
            filtered,
            sort_by=self._sort_by,
            descending=self._descending,
        )

        matched_row_index: int | None = None
        if self._focused_pid is not None:
            for idx, item in enumerate(ordered):
                if item.pid == self._focused_pid:
                    matched_row_index = idx
                    break
            if matched_row_index is None:
                self._focused_pid = None

        table.clear()
        for proc in ordered:
            cpu_str = f"{proc.cpu_percent:.1f}%" if proc.cpu_percent is not None else "N/D"
            mem_str = f"{proc.memory_percent:.1f}%" if proc.memory_percent is not None else "N/D"
            table.add_row(
                str(proc.pid),
                proc.name or "N/D",
                proc.username or "N/D",
                proc.status or "N/D",
                cpu_str,
                mem_str,
                _format_bytes(proc.rss_bytes),
                key=str(proc.pid),
            )

        cpu_label = f"{self._total_cpu:.1f}%" if self._total_cpu is not None else "N/D"
        self.query_one("#proc-cpu-summary", Static).update(f"CPU Global: {cpu_label}")
        self.query_one("#proc-count-summary", Static).update(
            f"Mostrando {len(ordered)} de {len(self._processes)} listados "
            f"(Total sistema: {self._total_procs} · En ejecución: {self._running_procs}) "
            f"— Pulsa Enter en una fila para inspeccionar"
        )

        self.refresh(layout=True)
        self.call_after_refresh(
            self._restore_pid_and_scroll,
            table,
            matched_row_index,
            tab_sx,
            tab_sy,
            tbl_sx,
            tbl_sy,
        )

    def update_snapshot(self, snapshot: SystemProcessesSnapshot) -> None:
        self._processes = list(snapshot.processes)
        self._total_cpu = snapshot.total_cpu_percent
        self._total_procs = snapshot.total_processes
        self._running_procs = snapshot.running_processes
        self._render_table()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id != "processes-table":
            return
        raw_key = event.row_key.value if event.row_key is not None else None
        if raw_key is not None:
            try:
                self._focused_pid = int(str(raw_key))
            except ValueError:
                self._focused_pid = None

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "proc-filter-input":
            self._filter_text = event.value
            self._render_table()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "proc-sort-select" and isinstance(event.value, str):
            self._sort_by = event.value
            self._render_table()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "proc-sort-dir-btn":
            self._descending = not self._descending
            event.button.label = "Descendente" if self._descending else "Ascendente"
            self._render_table()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "processes-table":
            return
        raw_key = event.row_key.value if event.row_key is not None else None
        if raw_key is None:
            return
        try:
            pid = int(str(raw_key))
        except ValueError:
            return
        self._focused_pid = pid
        self.post_message(self.ProcessInspectRequested(pid))