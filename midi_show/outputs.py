"""Output modules for MIDI playback.

Supports:
  - Local Windows synthesizer (Microsoft GS Wavetable Synth)
  - Virtual MIDI port (for VRChat world integration via LoopMIDI)
  - OSC output (for VRChat avatar control)
"""

from __future__ import annotations

import atexit
import logging
import queue
import threading
import time
from typing import Callable, Optional

import mido

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared MIDI message builder (reused by LocalSynthOutput & VirtualMidiOutput)
# ---------------------------------------------------------------------------


def _build_midi_msg(
    msg_type: str,
    note: int = 0,
    velocity: int = 0,
    control: int = 0,
    value: int = 0,
    channel: int = 0,
):
    """Build a mido.Message for the given type and parameters."""

    if msg_type == "note_on":
        return mido.Message("note_on", note=note, velocity=velocity, channel=channel)
    elif msg_type == "note_off":
        return mido.Message("note_off", note=note, velocity=velocity, channel=channel)
    elif msg_type == "control_change":
        return mido.Message(
            "control_change", control=control, value=value, channel=channel
        )
    logger.warning("Unrecognized MIDI message type: %s", msg_type)
    return None


# ---------------------------------------------------------------------------
# Base class for MIDI output (shared note_on / note_off / all_notes_off)
# ---------------------------------------------------------------------------


class _BaseMidiOutput:
    """Shared MIDI output logic for local synth and virtual port."""

    def __init__(self, enabled: bool = True):
        self._enabled = enabled
        self._port: Optional = None
        self._lock = threading.Lock()

    # --- Subclass hooks ---
    def _open(self):  # pragma: no cover
        raise NotImplementedError

    def _close(self):
        with self._lock:
            if self._port is not None:
                try:
                    self._port.close()
                except Exception:
                    pass
                self._port = None

    def _log_note_error(self, action: str, exc: Exception):
        logger.debug("%s %s failed: %s", type(self).__name__, action, exc)

    # --- Public API ---
    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, val: bool):
        self._enabled = val
        if val and self._port is None:
            self._open()
        elif not val:
            self._close()

    def get_port_name(self) -> str:
        if self._port:
            try:
                return str(self._port.name)
            except Exception:
                pass
        return "Not connected"

    def note_on(self, note: int, velocity: int, channel: int = 0):
        if not self._enabled or self._port is None:
            return
        msg = _build_midi_msg("note_on", note, velocity, channel=channel)
        if msg is None:
            return
        with self._lock:
            try:
                self._port.send(msg)
            except Exception as e:
                self._log_note_error("note_on", e)

    def note_off(self, note: int, velocity: int, channel: int = 0):
        if not self._enabled or self._port is None:
            return
        msg = _build_midi_msg("note_off", note, velocity, channel=channel)
        if msg is None:
            return
        with self._lock:
            try:
                self._port.send(msg)
            except Exception as e:
                self._log_note_error("note_off", e)

    def all_notes_off(self):
        if self._port is None:
            return
        with self._lock:
            try:
                for ch in range(16):
                    cc_msg = _build_midi_msg(
                        "control_change", control=123, value=0, channel=ch
                    )
                    if cc_msg is None:
                        continue
                    self._port.send(cc_msg)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Local Audio Synthesizer (Windows GS Wavetable Synth)
# ---------------------------------------------------------------------------


class LocalSynthOutput(_BaseMidiOutput):
    """Sends MIDI notes to the Windows built-in synthesizer for audio.

    Uses mido with rtmidi backend to open the 'Microsoft GS Wavetable Synth'
    port. Audio plays through the computer speakers.
    """

    def __init__(self, enabled: bool = True):
        super().__init__(enabled)
        self._open()
        atexit.register(self._close)

    def _open(self):
        if not self._enabled:
            return
        try:
            # Find Microsoft GS Wavetable Synth
            for name in mido.get_output_names():
                if "microsoft" in name.lower() and "wavetable" in name.lower():
                    self._port = mido.open_output(name)
                    logger.info("Local synth opened: %s", name)
                    return
            # Fallback: first available output
            outputs = mido.get_output_names()
            if outputs:
                self._port = mido.open_output(outputs[0])
                logger.info("Local synth opened (fallback): %s", outputs[0])
            else:
                logger.warning("No MIDI output ports found for local synth")
        except Exception as e:
            logger.warning("Could not open local synth: %s", e)
            self._enabled = False

    def get_port_name(self) -> str:
        name = super().get_port_name()
        return "None" if name == "Not connected" else name


# ---------------------------------------------------------------------------
# Virtual MIDI Output (for VRChat world with VRC Midi Listener)
# ---------------------------------------------------------------------------


class VirtualMidiOutput(_BaseMidiOutput):
    """Sends MIDI events to a virtual MIDI port (requires LoopMIDI).

    In VRChat, a world with a VRC Midi Listener component can receive
    these events for visualization, sound triggering, or other effects.
    """

    def __init__(self, enabled: bool = True, port_name: str = "LoopMIDI Port"):
        self._port_name = port_name
        self._send_queue: "queue.Queue[mido.Message]" = queue.Queue(maxsize=2048)
        self._send_thread: Optional[threading.Thread] = None
        self._send_stop_event = threading.Event()
        self._last_queue_full_warning = 0.0
        super().__init__(enabled)
        self._open()
        atexit.register(self._close)

    def _send_worker(self):
        while not self._send_stop_event.is_set() or not self._send_queue.empty():
            try:
                msg = self._send_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                with self._lock:
                    port = self._port
                    if port is not None:
                        port.send(msg)
            except Exception as e:
                logger.warning("Virtual MIDI send failed: %s", e)
            finally:
                self._send_queue.task_done()

    def _start_send_thread(self):
        if self._send_thread is not None and self._send_thread.is_alive():
            return
        self._send_stop_event = threading.Event()
        self._send_thread = threading.Thread(
            target=self._send_worker,
            name="VirtualMidiOutputSender",
            daemon=True,
        )
        self._send_thread.start()

    def _enqueue_message(self, msg: Optional[mido.Message]):
        if msg is None:
            return
        try:
            self._send_queue.put_nowait(msg)
        except queue.Full:
            now = time.monotonic()
            if now - self._last_queue_full_warning >= 5.0:
                self._last_queue_full_warning = now
                logger.warning("Virtual MIDI send queue full, dropping newest message")

    def _open(self):
        if not self._enabled:
            return

        outputs = mido.get_output_names()
        # Find the specified virtual port
        for name in outputs:
            if self._port_name.lower().replace(" ", "") in name.lower().replace(
                " ", ""
            ):
                try:
                    with self._lock:
                        self._port = mido.open_output(name)
                    self._start_send_thread()
                    logger.info("Virtual MIDI port opened: %s", name)
                    return
                except Exception as e:
                    logger.warning(
                        f"Virtual port '{name}' found but failed to open: {e}"
                    )
                    return
        # Show available ports but don't auto-connect
        logger.info(
            "Virtual port '%s' not found. Available: %s", self._port_name, outputs
        )

    def _close(self):
        with self._lock:
            send_thread = self._send_thread
            self._send_thread = None
            self._send_stop_event.set()

        if send_thread is not None and send_thread.is_alive():
            send_thread.join(timeout=1.0)

        with self._lock:
            if self._port is not None:
                try:
                    self._port.close()
                except Exception:
                    pass
                self._port = None

        while True:
            try:
                self._send_queue.get_nowait()
            except queue.Empty:
                break
            else:
                self._send_queue.task_done()

    def get_available_ports(self) -> list[str]:
        return mido.get_output_names()

    def note_on(self, note: int, velocity: int, channel: int = 0):
        if not self._enabled or self._port is None:
            return
        self._enqueue_message(
            _build_midi_msg("note_on", note, velocity, channel=channel)
        )

    def note_off(self, note: int, velocity: int, channel: int = 0):
        if not self._enabled or self._port is None:
            return
        self._enqueue_message(
            _build_midi_msg("note_off", note, velocity, channel=channel)
        )

    def all_notes_off(self):
        if self._port is None:
            return
        for ch in range(16):
            self._enqueue_message(
                _build_midi_msg("control_change", control=123, value=0, channel=ch)
            )

    def set_port_name(self, name: str):
        """Change virtual port and reconnect."""
        if name != self._port_name:
            self._close()
            self._port_name = name
            if self._enabled:
                self._open()


# ---------------------------------------------------------------------------
# OSC Output (for VRChat Avatar Control)
# ---------------------------------------------------------------------------


class OscOutput:
    """Sends MIDI note data to VRChat via OSC protocol.

    Supports two modes:
      - 'piano' (default): /PianoKeys/<note> (for piano avatars like Kade's Piano)
      - 'avatar'         : /avatar/parameters/note<NNN> (for custom avatar params)
    """

    MODE_PIANO = "piano"
    MODE_AVATAR = "avatar"

    def __init__(
        self,
        enabled: bool = True,
        ip: str = "127.0.0.1",
        port: int = 9000,
        mode: str = MODE_PIANO,
    ):
        self._enabled = enabled
        self._ip = ip
        self._port = port
        self._mode = mode
        self._sender: Optional = None
        self._lock = threading.Lock()
        self._open()
        atexit.register(self._close)

    def _open(self):
        if not self._enabled:
            return
        try:
            from pythonosc.udp_client import SimpleUDPClient

            self._sender = SimpleUDPClient(self._ip, self._port)
            logger.info("OSC sender opened: %s:%s", self._ip, self._port)
        except Exception as e:
            logger.warning("Could not open OSC sender: %s", e)
            self._enabled = False

    def _close(self):
        with self._lock:
            self._sender = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, val: bool):
        was_enabled = self._enabled
        self._enabled = val
        if val and not was_enabled:
            self._open()
        elif not val and was_enabled:
            self._close()

    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, val: str):
        if val in (self.MODE_PIANO, self.MODE_AVATAR):
            self._mode = val

    def note_on(self, note: int, velocity: int, channel: int = 0):
        if not self._enabled or self._sender is None:
            return
        val = min(1.0, velocity / 127.0)
        with self._lock:
            try:
                if self._mode == self.MODE_PIANO:
                    # /PianoKeys/<note> convention used by most VRChat piano avatars
                    self._sender.send(f"/PianoKeys/{note}", val)
                else:
                    self._sender.send(f"/avatar/parameters/note{note:03d}", val)
                    ch_addr = f"/avatar/parameters/note_ch{channel:02d}_{note:03d}"
                    self._sender.send(ch_addr, val)
            except Exception as e:
                logger.debug("OSC note_on failed: %s", e)

    def note_off(self, note: int, velocity: int, channel: int = 0):
        if not self._enabled or self._sender is None:
            return
        with self._lock:
            try:
                if self._mode == self.MODE_PIANO:
                    self._sender.send(f"/PianoKeys/{note}", 0.0)
                else:
                    self._sender.send(f"/avatar/parameters/note{note:03d}", 0.0)
                    ch_addr = f"/avatar/parameters/note_ch{channel:02d}_{note:03d}"
                    self._sender.send(ch_addr, 0.0)
            except Exception as e:
                logger.debug("OSC note_off failed: %s", e)

    def all_notes_off(self):
        if not self._enabled or self._sender is None:
            return
        with self._lock:
            try:
                if self._mode == self.MODE_PIANO:
                    for note in range(128):
                        self._sender.send(f"/PianoKeys/{note}", 0.0)
                else:
                    for note in range(128):
                        self._sender.send(f"/avatar/parameters/note{note:03d}", 0.0)
                        for ch in range(16):
                            ch_addr = f"/avatar/parameters/note_ch{ch:02d}_{note:03d}"
                            self._sender.send(ch_addr, 0.0)
            except Exception:
                pass

    def set_address(self, ip: str, port: int):
        """Set OSC address and reconnect if enabled."""
        was_enabled = self._enabled
        if was_enabled:
            self._close()
        self._ip = ip
        self._port = port
        if was_enabled:
            self._open()

    @property
    def address(self) -> str:
        return f"{self._ip}:{self._port}"


# ---------------------------------------------------------------------------
# MIDI Input (Live Passthrough from MidiPiano / LoopMIDI)
# ---------------------------------------------------------------------------


class MidiInput:
    """Receives live MIDI input from a virtual MIDI port (e.g. LoopMIDI).

    Dispatches incoming note_on / note_off messages to registered callbacks.
    Used in Live Passthrough mode to forward real-time MidiPiano performance
    to all enabled outputs (LocalSynth, VirtualMIDI, OSC).
    """

    def __init__(self, enabled: bool = True, port_name: str = "LoopMIDI Port"):
        self._enabled = enabled
        self._port_name = port_name
        self._port: Optional = None
        self._callbacks: dict[str, Optional[Callable]] = {
            "note_on": None,
            "note_off": None,
        }
        self._lock = threading.Lock()
        self._open()
        atexit.register(self._close)

    def _open(self):
        if not self._enabled:
            return
        try:
            for name in mido.get_input_names():
                if self._port_name.lower().replace(" ", "") in name.lower().replace(
                    " ", ""
                ):
                    self._port = mido.open_input(name, callback=self._on_message)
                    logger.info("MIDI input opened: %s", name)
                    return
            logger.info(
                f"Input port '{self._port_name}' not found. "
                f"Available inputs: {mido.get_input_names()}"
            )
        except Exception as e:
            logger.warning("Could not open MIDI input: %s", e)

    def _close(self):
        with self._lock:
            if self._port is not None:
                try:
                    self._port.close()
                except Exception:
                    pass
                self._port = None

    def _on_message(self, msg):
        """Callback from mido for every incoming MIDI message."""
        # Read callbacks under lock, execute outside lock to avoid deadlock
        with self._lock:
            cb_note_on = self._callbacks.get("note_on")
            cb_note_off = self._callbacks.get("note_off")
        try:
            if msg.type == "note_on" and msg.velocity > 0:
                if cb_note_on:
                    cb_note_on(msg.note, msg.velocity, msg.channel)
            elif msg.type == "note_off" or (
                msg.type == "note_on" and msg.velocity == 0
            ):
                if cb_note_off:
                    cb_note_off(msg.note, msg.velocity, msg.channel)
        except Exception as e:
            logger.debug("MidiInput callback error: %s", e)

    def set_callbacks(
        self, note_on: Optional[Callable] = None, note_off: Optional[Callable] = None
    ):
        """Register callbacks for incoming MIDI events.

        Callbacks signature: fn(note: int, velocity: int, channel: int)
        """
        with self._lock:
            self._callbacks["note_on"] = note_on
            self._callbacks["note_off"] = note_off

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, val: bool):
        self._enabled = val
        if val and self._port is None:
            self._open()
        elif not val:
            self._close()

    @property
    def port_name(self) -> str:
        return self._port_name

    def get_port_name(self) -> str:
        if self._port:
            try:
                return str(self._port.name)
            except Exception:
                pass
        return "Not connected"

    def get_available_ports(self) -> list[str]:
        return mido.get_input_names()

    def set_port_name(self, name: str):
        """Change input port and reconnect."""
        if name != self._port_name:
            self._close()
            self._port_name = name
            self._open()
