# pc-info

Cross-platform interactive terminal system monitor (**TUI**) built with **Python**, **Textual**, and **`psutil`**. Inspect hardware, GPU metrics, active processes, and network/disk I/O in real time without blocking the UI thread.

---

## Features

* **Hardware Tab:**
  * Hostname, operating system details, and battery status.
  * CPU overview (model, architecture, physical/logical cores, current frequency, and vendor ASCII art).
  * Terminal charts (*sparklines* for CPU frequency and RAM usage, plus per-logical-core frequency bars).
  * RAM and Swap usage, storage tables, and temperature sensors.
  * **GPU** detection and metrics via `nvidia-smi` (utilization %, used/total VRAM, temperature, and power draw) with cross-platform fallbacks (`system_profiler` on macOS, `lspci` on Linux, and `CIM`/PowerShell on Windows).
* **Processes & CPU Tab:**
  * Live filtering by process name, PID, username, or status.
  * Sorting by CPU %, Memory %, RSS, Name, or PID in ascending or descending order.
  * Scroll position preservation and focus tracking by `PID` across refreshes (clearing focus automatically if the process disappears).
  * **Process Inspector (`Enter` on a row):** displays detailed process info (executable path, command line, threads, RSS/VMS, start time) and supports suspending, resuming, terminating, or killing the process with double confirmation.
* **Network & I/O Tab:**
  * Live network transmit/receive rates and disk read/write rates computed across refresh intervals.
* **Non-blocking & Resilient:**
  * Threaded worker collection with in-flight guards and safe handling of missing metrics or access-denied errors.

---

## Project Architecture

```text
src/pc_info/
├── app.py                              # Main Textual application and worker orchestration
├── collectors/                         # System metric collectors and process control
│   ├── gpu.py                          # GpuCollector (nvidia-smi / macOS / Linux / Windows)
│   ├── hardware.py                     # HardwareCollector (CPU, RAM, disks, battery, temps)
│   ├── io_stats.py                     # IoCollector (network and disk I/O rates)
│   ├── process_control.py              # ProcessControlService (details and safe signals)
│   └── processes.py                    # ProcessCollector (process list and metrics)
├── models/                             # Data structures (dataclasses)
│   ├── gpu.py
│   ├── hardware.py
│   ├── io_stats.py
│   ├── process_detail.py
│   └── processes.py
└── ui/
    ├── screens/
    │   ├── hardware_tab.py             # Hardware and GPU tab
    │   ├── io_tab.py                   # Network and I/O tab
    │   ├── process_inspector_modal.py  # Process inspection and control modal
    │   └── processes_tab.py            # Processes filtering, sorting, and table tab
    └── styles/
        └── app.tcss                    # Textual CSS stylesheet
```

---

## Direct Installation from GitHub

Replace `<owner>/<repo>` with the actual GitHub repository path.

### Using `pip`

```bash
pip install "git+[https://github.com/](https://github.com/)<owner>/<repo>.git"
```

To install a specific branch, tag, or commit:

```bash
pip install "git+[https://github.com/](https://github.com/)<owner>/<repo>.git@main"
# or:
pip install "git+[https://github.com/](https://github.com/)<owner>/<repo>.git@v0.1.0"
```

### Using `uv`

```bash
uv pip install "git+[https://github.com/](https://github.com/)<owner>/<repo>.git"
# or run directly without installing permanently:
uvx --from "git+[https://github.com/](https://github.com/)<owner>/<repo>.git" pc-info
```

### Using `pipx`

```bash
pipx install "git+[https://github.com/](https://github.com/)<owner>/<repo>.git"
```

### Local Development & Tests

```bash
git clone [https://github.com/](https://github.com/)<owner>/<repo>.git
cd <repo>
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -v
```

---

## Usage & Keybindings

Launch the TUI from your terminal:

```bash
pc-info
```

* **`r`:** trigger an immediate refresh of system metrics.
* **`Tab` / click:** move focus between controls and tables.
* **`Enter` (on a process row):** open the Process Inspector modal for the selected PID.
* **`Esc` (inside the modal):** close the Process Inspector.
* **`q`:** quit `pc-info`.