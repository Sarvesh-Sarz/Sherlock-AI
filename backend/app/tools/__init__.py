"""Diagnostic tools.

Each module here (cpu.py, memory.py, disk.py today; battery.py, wifi.py,
startup.py planned) exposes a single `run() -> ToolResult` function that
collects one kind of evidence about the machine. A tool:

- never raises — any failure is caught and returned as an error
  `ToolResult` instead, so one broken sensor can't take down an
  investigation.
- takes no arguments and returns a single `ToolResult` (see
  `app.models.tool_result`) — the uniform shape every tool shares.

Tools are plain functions rather than classes: there's no state to hold
between runs, and `tool_manager.py` — also in this package, since it
exists specifically to run the tools defined here — just needs one
callable per tool to invoke.
"""
