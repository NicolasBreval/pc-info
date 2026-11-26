from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from pc_info.collectors.process_control import ProcessAction, ProcessControlService
from pc_info.models.process_detail import ProcessDetail


def _format_bytes(num_bytes: int | None) -> str:
    if num_bytes is None:
        return "N/D"
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return "N/D"


class ProcessInspectorModal(ModalScreen[str | None]):
    """Modal de inspección y control seguro para un proceso concreto."""

    BINDINGS = [
        ("escape", "close_modal", "Cerrar"),
    ]

    DEFAULT_CSS = """
    ProcessInspectorModal {
        align: center middle;
        background: $background 70%;
    }

    #inspector-dialog {
        width: 108;
        max-width: 96%;
        min-width: 50;
        height: 88%;
        max-height: 92%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
        overflow: auto;
        scrollbar-gutter: stable;
    }

    #inspector-title {
        text-style: bold;
        color: $accent;
        height: auto;
        margin-bottom: 1;
    }

    #inspector-body {
        width: 1fr;
        height: 1fr;
        min-height: 8;
        overflow: auto;
        scrollbar-gutter: stable;
        border: round $primary;
        padding: 1 2;
        margin-bottom: 1;
    }

    .inspector-line {
        width: 1fr;
        height: auto;
        margin-bottom: 1;
    }

    .inspector-actions {
        layout: horizontal;
        width: 1fr;
        height: auto;
        min-height: 3;
        overflow-x: auto;
        margin-bottom: 1;
    }

    .inspector-actions Button {
        width: auto;
        min-width: 12;
        margin-right: 1;
    }

    #confirm-box {
        width: 1fr;
        height: auto;
        border: round $warning;
        padding: 1 2;
        margin-bottom: 1;
        overflow: auto;
    }

    #confirm-text {
        width: 1fr;
        height: auto;
        color: $warning;
        margin-bottom: 1;
    }
    """

    def __init__(self, pid: int, control_service: ProcessControlService | None = None) -> None:
        super().__init__()
        self._pid = pid
        self._service = control_service or ProcessControlService()
        self._pending_action: ProcessAction | None = None

    def compose(self) -> ComposeResult:
        with Container(id="inspector-dialog"):
            yield Label(f"Inspector de Proceso — PID {self._pid}", id="inspector-title")
            with VerticalScroll(id="inspector-body"):
                yield Static(
                    "Cargando información del proceso...",
                    id="proc-detail-summary",
                    classes="inspector-line",
                )
                yield Static("Ejecutable: N/D", id="proc-detail-exe", classes="inspector-line")
                yield Static("Comando: N/D", id="proc-detail-cmd", classes="inspector-line")
            with Container(id="confirm-box"):
                yield Static("", id="confirm-text")
                with Horizontal(classes="inspector-actions"):
                    yield Button("Confirmar acción", id="btn-confirm-action", variant="warning")
                    yield Button("Cancelar", id="btn-cancel-confirm", variant="default")
            with Horizontal(classes="inspector-actions"):
                yield Button("Refrescar", id="btn-refresh-proc", variant="primary")
                yield Button("Pausar", id="btn-suspend-proc", variant="default")
                yield Button("Reanudar", id="btn-resume-proc", variant="default")
                yield Button("Terminar", id="btn-terminate-proc", variant="warning")
                yield Button("Matar (KILL)", id="btn-kill-proc", variant="error")
                yield Button("Cerrar (Esc)", id="btn-close-proc", variant="default")

    def on_mount(self) -> None:
        self.query_one("#confirm-box", Container).display = False
        self._load_detail()

    def action_close_modal(self) -> None:
        self.dismiss(None)

    def _load_detail(self) -> None:
        summary_w = self.query_one("#proc-detail-summary", Static)
        exe_w = self.query_one("#proc-detail-exe", Static)
        cmd_w = self.query_one("#proc-detail-cmd", Static)
        try:
            detail: ProcessDetail = self._service.get_detail(self._pid)
            cpu_str = f"{detail.cpu_percent:.1f}%" if detail.cpu_percent is not None else "N/D"
            mem_str = f"{detail.memory_percent:.1f}%" if detail.memory_percent is not None else "N/D"
            threads_str = str(detail.num_threads) if detail.num_threads is not None else "N/D"
            summary_w.update(
                f"Nombre: {detail.name} | Usuario: {detail.username} | Estado: {detail.status}\n"
                f"CPU: {cpu_str} | RAM: {mem_str} | RSS: {_format_bytes(detail.rss_bytes)} | "
                f"VMS: {_format_bytes(detail.vms_bytes)}\n"
                f"Hilos: {threads_str} | Inicio: {detail.created_at}"
            )
            exe_w.update(f"Ejecutable: {detail.exe}")
            cmd_text = " ".join(detail.cmdline) if detail.cmdline else "N/D"
            cmd_w.update(f"Comando: {cmd_text}")
        except Exception as exc:
            summary_w.update(f"No se pudo leer el detalle del PID {self._pid}: {exc}")
            exe_w.update("Ejecutable: N/D")
            cmd_w.update("Comando: N/D")

    def _request_confirmation(self, action: ProcessAction, prompt: str) -> None:
        self._pending_action = action
        confirm_box = self.query_one("#confirm-box", Container)
        self.query_one("#confirm-text", Static).update(prompt)
        confirm_box.display = True

    def _hide_confirmation(self) -> None:
        self._pending_action = None
        self.query_one("#confirm-box", Container).display = False

    @on(Button.Pressed, "#btn-close-proc")
    def _on_close_pressed(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn-refresh-proc")
    def _on_refresh_pressed(self) -> None:
        self._hide_confirmation()
        self._load_detail()

    @on(Button.Pressed, "#btn-suspend-proc")
    def _on_suspend_pressed(self) -> None:
        self._request_confirmation(
            "suspend",
            f"¿Confirmas PAUSAR (SIGSTOP) el proceso PID {self._pid}?",
        )

    @on(Button.Pressed, "#btn-resume-proc")
    def _on_resume_pressed(self) -> None:
        self._request_confirmation(
            "resume",
            f"¿Confirmas REANUDAR (SIGCONT) el proceso PID {self._pid}?",
        )

    @on(Button.Pressed, "#btn-terminate-proc")
    def _on_terminate_pressed(self) -> None:
        self._request_confirmation(
            "terminate",
            f"¿Confirmas TERMINAR (SIGTERM) de forma limpia el proceso PID {self._pid}?",
        )

    @on(Button.Pressed, "#btn-kill-proc")
    def _on_kill_pressed(self) -> None:
        self._request_confirmation(
            "kill",
            f"¡ATENCIÓN! ¿Confirmas FORZAR CIERRE (SIGKILL) inmediato del PID {self._pid}?",
        )

    @on(Button.Pressed, "#btn-cancel-confirm")
    def _on_cancel_confirm_pressed(self) -> None:
        self._hide_confirmation()

    @on(Button.Pressed, "#btn-confirm-action")
    def _on_confirm_action_pressed(self) -> None:
        if self._pending_action is None:
            return
        action = self._pending_action
        self._hide_confirmation()
        try:
            message = self._service.perform_action(self._pid, action)
            self.dismiss(message)
        except Exception as exc:
            self.query_one("#proc-detail-summary", Static).update(f"Error: {exc}")