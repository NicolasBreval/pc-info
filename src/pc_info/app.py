from __future__ import annotations

from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, TabbedContent, TabPane

from pc_info.collectors.gpu import GpuCollector
from pc_info.collectors.hardware import HardwareCollector
from pc_info.collectors.io_stats import IoCollector
from pc_info.collectors.processes import ProcessCollector
from pc_info.models.gpu import SystemGpuSnapshot
from pc_info.models.hardware import SystemHardwareSnapshot
from pc_info.models.io_stats import SystemIoSnapshot
from pc_info.models.processes import SystemProcessesSnapshot
from pc_info.ui.screens.hardware_tab import HardwareTab
from pc_info.ui.screens.io_tab import IoTab
from pc_info.ui.screens.process_inspector_modal import ProcessInspectorModal
from pc_info.ui.screens.processes_tab import ProcessesTab

STYLES_PATH = Path(__file__).resolve().parent / "ui" / "styles" / "app.tcss"


class PcInfoApp(App[None]):
    """Aplicación TUI informacional para inspección del sistema."""

    TITLE = "pc-info"
    SUB_TITLE = "Monitor de sistema multiplataforma"
    CSS_PATH = str(STYLES_PATH)

    BINDINGS = [
        ("q", "quit", "Salir"),
        ("r", "refresh_now", "Refrescar"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._hardware_collector = HardwareCollector()
        self._process_collector = ProcessCollector()
        self._io_collector = IoCollector()
        self._gpu_collector = GpuCollector()
        self._hw_refresh_inflight = False
        self._proc_refresh_inflight = False
        self._io_refresh_inflight = False
        self._gpu_refresh_inflight = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="tab-hardware"):
            with TabPane("Hardware", id="tab-hardware"):
                yield HardwareTab(id="hardware-tab-view")
            with TabPane("Procesos y CPU", id="tab-processes"):
                yield ProcessesTab(id="processes-tab-view")
            with TabPane("Red e I/O", id="tab-io"):
                yield IoTab(id="io-tab-view")
        yield Footer()

    def on_mount(self) -> None:
        self.action_refresh_now()
        self.set_interval(2.0, self._scheduled_refresh)

    def _scheduled_refresh(self) -> None:
        self._trigger_hardware_refresh()
        self._trigger_processes_refresh()
        self._trigger_io_refresh()
        self._trigger_gpu_refresh()

    def action_refresh_now(self) -> None:
        self._trigger_hardware_refresh()
        self._trigger_processes_refresh()
        self._trigger_io_refresh()
        self._trigger_gpu_refresh()

    def on_processes_tab_process_inspect_requested(
        self, event: ProcessesTab.ProcessInspectRequested
    ) -> None:
        def _after_modal(result: str | None) -> None:
            if result:
                self.notify(result, severity="information")
            self._trigger_processes_refresh()

        self.push_screen(ProcessInspectorModal(event.pid), callback=_after_modal)

    def _apply_hardware_snapshot(self, snapshot: SystemHardwareSnapshot) -> None:
        self._hw_refresh_inflight = False
        try:
            tab = self.query_one("#hardware-tab-view", HardwareTab)
            tab.update_snapshot(snapshot)
            now_str = datetime.now().strftime("%H:%M:%S")
            self.sub_title = f"Último refresco HW: {now_str}"
        except Exception as exc:
            self.notify(f"Error mostrando Hardware: {exc}", severity="error")

    def _on_hardware_error(self, error: Exception) -> None:
        self._hw_refresh_inflight = False
        self.notify(f"Error recolectando Hardware: {error}", severity="error")

    def _collect_hardware_task(self) -> None:
        try:
            snapshot = self._hardware_collector.collect_snapshot()
            self.call_from_thread(self._apply_hardware_snapshot, snapshot)
        except Exception as exc:
            self.call_from_thread(self._on_hardware_error, exc)

    def _apply_processes_snapshot(self, snapshot: SystemProcessesSnapshot) -> None:
        self._proc_refresh_inflight = False
        try:
            tab = self.query_one("#processes-tab-view", ProcessesTab)
            tab.update_snapshot(snapshot)
        except Exception as exc:
            self.notify(f"Error mostrando Procesos: {exc}", severity="error")

    def _on_processes_error(self, error: Exception) -> None:
        self._proc_refresh_inflight = False
        self.notify(f"Error recolectando Procesos: {error}", severity="error")

    def _collect_processes_task(self) -> None:
        try:
            snapshot = self._process_collector.collect_snapshot()
            self.call_from_thread(self._apply_processes_snapshot, snapshot)
        except Exception as exc:
            self.call_from_thread(self._on_processes_error, exc)

    def _apply_io_snapshot(self, snapshot: SystemIoSnapshot) -> None:
        self._io_refresh_inflight = False
        try:
            tab = self.query_one("#io-tab-view", IoTab)
            tab.update_snapshot(snapshot)
        except Exception as exc:
            self.notify(f"Error mostrando Red e I/O: {exc}", severity="error")

    def _on_io_error(self, error: Exception) -> None:
        self._io_refresh_inflight = False
        self.notify(f"Error recolectando Red e I/O: {error}", severity="error")

    def _collect_io_task(self) -> None:
        try:
            snapshot = self._io_collector.collect_snapshot()
            self.call_from_thread(self._apply_io_snapshot, snapshot)
        except Exception as exc:
            self.call_from_thread(self._on_io_error, exc)

    def _apply_gpu_snapshot(self, snapshot: SystemGpuSnapshot) -> None:
        self._gpu_refresh_inflight = False
        try:
            tab = self.query_one("#hardware-tab-view", HardwareTab)
            tab.update_gpu_snapshot(snapshot)
        except Exception as exc:
            self.notify(f"Error mostrando GPU: {exc}", severity="error")

    def _on_gpu_error(self, error: Exception) -> None:
        self._gpu_refresh_inflight = False
        self.notify(f"Error recolectando GPU: {error}", severity="error")

    def _collect_gpu_task(self) -> None:
        try:
            snapshot = self._gpu_collector.collect_snapshot()
            self.call_from_thread(self._apply_gpu_snapshot, snapshot)
        except Exception as exc:
            self.call_from_thread(self._on_gpu_error, exc)

    def _trigger_hardware_refresh(self) -> None:
        if self._hw_refresh_inflight:
            return
        self._hw_refresh_inflight = True
        self.run_worker(
            self._collect_hardware_task,
            name="collect_hardware_task",
            thread=True,
            exclusive=False,
        )

    def _trigger_processes_refresh(self) -> None:
        if self._proc_refresh_inflight:
            return
        self._proc_refresh_inflight = True
        self.run_worker(
            self._collect_processes_task,
            name="collect_processes_task",
            thread=True,
            exclusive=False,
        )

    def _trigger_io_refresh(self) -> None:
        if self._io_refresh_inflight:
            return
        self._io_refresh_inflight = True
        self.run_worker(
            self._collect_io_task,
            name="collect_io_task",
            thread=True,
            exclusive=False,
        )

    def _trigger_gpu_refresh(self) -> None:
        if self._gpu_refresh_inflight:
            return
        self._gpu_refresh_inflight = True
        self.run_worker(
            self._collect_gpu_task,
            name="collect_gpu_task",
            thread=True,
            exclusive=False,
        )


def main() -> None:
    app = PcInfoApp()
    app.run()


if __name__ == "__main__":
    main()