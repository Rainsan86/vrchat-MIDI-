#!/usr/bin/env python3
"""MIDI Show - VRChat MIDI Player

A tool to play MIDI files with:
  - Local audio via Windows synthesizer
  - Virtual MIDI port output (for VRChat worlds with VRC Midi Listener)
  - OSC output (for VRChat avatar control)

Requirements:
  pip install mido python-rtmidi python-osc
"""

import logging
import os
import sys

# Add parent dir to path so 'midi_show' package is importable
# When running as PyInstaller bundle, sys._MEIPASS points to the temp extraction dir
if getattr(sys, "frozen", False):
    # Running as compiled exe — PyInstaller sets sys._MEIPASS
    sys.path.insert(0, sys._MEIPASS)
else:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _show_error_and_exit(title: str, message: str):
    """Display a pop-up error box and exit with code 1."""
    import ctypes

    ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)  # MB_ICONERROR
    sys.exit(1)


def _check_critical_imports():
    """Check critical dependencies before entering the UI event loop."""
    missing = []
    for mod_name, pip_name in [
        ("tkinter", "tkinter (Python stdlib, should come with Python)"),
        ("mido", "mido"),
        ("rtmidi", "python-rtmidi"),
        ("pythonosc", "python-osc"),
    ]:
        try:
            __import__(mod_name)
        except ImportError:
            missing.append(pip_name)

    if missing:
        msg = (
            "MIDI Show 缺少必要的 Python 依赖：\n\n"
            + "\n".join(f"  \u2022 {m}" for m in missing)
            + "\n\n请运行以下命令安装：\n"
            "  pip install mido python-rtmidi python-osc\n\n"
            "或删除 .venv 目录后重新运行 start.bat。"
        )
        _show_error_and_exit("MIDI Show - 依赖缺失", msg)


def main():
    # Configure logging at module level
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Fix Windows console encoding for emoji
    # When running as GUI (no console), sys.stdout may be None — skip this
    if sys.stdout is not None and hasattr(sys.stdout, "buffer"):
        import io

        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )

    # === 启动前安全检查 ===
    _check_critical_imports()

    # Only print if stdout is available (not None in GUI mode)
    if sys.stdout is not None:
        print("[MIDI Show] VRChat MIDI Player")
        print("Loading...")

    try:
        from midi_show.ui import MidiShowUI

        app = MidiShowUI()
        app.run()
    except Exception as exc:
        logging.getLogger(__name__).exception("Fatal error during startup")
        _show_error_and_exit(
            "MIDI Show - 启动失败",
            f"启动过程中发生未预期的错误：\n\n  {exc}\n\n"
            "请截图此消息，或在命令行中手动运行查看详细错误。",
        )


if __name__ == "__main__":
    main()
