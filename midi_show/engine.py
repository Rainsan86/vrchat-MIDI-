"""Playback engine - schedules and dispatches MIDI events in real-time."""

from __future__ import annotations

import logging
import threading
import time as time_module
from typing import Callable, Optional, Set

from .midi_parser import MidiData, NoteEvent

# Type alias for note event callbacks
PlayCallback = Callable[[NoteEvent], None]


class PlaybackEngine:
    """Real-time MIDI note scheduler.

    Walks through parsed NoteEvents and dispatches note_on / note_off
    callbacks at the correct wall-clock times.
    """

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._on_note_on: Optional[PlayCallback] = None
        self._on_note_off: Optional[PlayCallback] = None
        self._on_finish: Optional[Callable[[], None]] = None
        self._on_update: Optional[Callable[[float], None]] = None
        self._data: Optional[MidiData] = None
        self._current_time: float = 0.0
        self._speed: float = 1.0
        self._is_playing: bool = False
        self._is_paused: bool = False

        # Track filtering
        self._muted_tracks: set[int] = set()
        self._solo_tracks: set[int] = set()
        self._track_filter_lock = threading.Lock()

        # Active note tracking for piano roll visualization
        self._sounding_notes: dict[
            tuple[int, int], list[NoteEvent]
        ] = {}  # (note, channel) -> list of NoteEvent
        self._sounding_lock = threading.Lock()

        # Wall-clock tracking for smooth progress
        self._wall_start: float = 0.0
        self._wall_offset: float = 0.0  # accumulated pause time
        self._start_time_sec: float = 0.0

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    # ---- Track filtering -----------------------------------------------------------------

    @property
    def muted_tracks(self) -> set[int]:
        with self._track_filter_lock:
            return set(self._muted_tracks)

    @muted_tracks.setter
    def muted_tracks(self, value: set[int]):
        with self._track_filter_lock:
            self._muted_tracks = set(value)

    @property
    def solo_tracks(self) -> set[int]:
        with self._track_filter_lock:
            return set(self._solo_tracks)

    @solo_tracks.setter
    def solo_tracks(self, value: set[int]):
        with self._track_filter_lock:
            self._solo_tracks = set(value)

    def _is_track_active(self, track_idx: int) -> bool:
        """Check if a track should be heard considering mute/solo state."""
        with self._track_filter_lock:
            if track_idx in self._muted_tracks:
                return False
            if self._solo_tracks:
                # If any track is soloed, only soloed tracks play
                return track_idx in self._solo_tracks
            return True

    @property
    def current_time(self) -> float:
        """Current playback position based on wall clock (for smooth progress)."""
        if self._is_playing and not self._is_paused:
            elapsed = time_module.perf_counter() - self._wall_start - self._wall_offset
            projected = self._start_time_sec + elapsed * self._speed
            total = self.total_duration
            if total > 0:
                projected = min(projected, total)
            # Don't return projected if it's behind event-based time
            # (can happen during initial buffering)
            return max(projected, self._current_time)
        return self._current_time

    def set_callbacks(
        self,
        on_note_on: Optional[PlayCallback] = None,
        on_note_off: Optional[PlayCallback] = None,
        on_finish: Optional[Callable[[], None]] = None,
        on_update: Optional[Callable[[float], None]] = None,
    ):
        self._on_note_on = on_note_on
        self._on_note_off = on_note_off
        self._on_finish = on_finish
        self._on_update = on_update

    def load(self, data: MidiData):
        """Load MIDI data for playback."""
        self._data = data
        self._current_time = 0.0
        with self._sounding_lock:
            self._sounding_notes.clear()

    def set_speed(self, speed: float):
        """Set playback speed multiplier (0.25 - 4.0).

        During active playback, adjusts wall_offset so the remaining
        events play at the new speed WITHOUT restarting the playback
        thread.  (The current event's pre-computed sleep may be off
        by at most one inter-event interval, which is imperceptible.)
        """
        speed = max(0.25, min(4.0, speed))
        if speed != self._speed:
            old_speed = self._speed
            self._speed = speed
            if self._is_playing:
                # Recalibrate wall_offset so target_wall for all remaining
                # events stays continuous at the new speed.
                self._wall_offset += (self._current_time - self._start_time_sec) * (
                    1.0 / old_speed - 1.0 / speed
                )

    def play(self, from_time: float = 0.0):
        """Start playback from the given time offset."""
        if self._data is None:
            return
        if self._thread is not None and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                logging.getLogger(__name__).warning(
                    "Previous thread did not stop in time, continuing anyway"
                )
        self._is_playing = True
        self._is_paused = False
        self._current_time = from_time
        self._start_time_sec = from_time
        self._wall_start = time_module.perf_counter()
        self._wall_offset = 0.0
        self._stop_event.clear()
        self._pause_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def pause(self):
        """Pause playback."""
        if self._is_playing and not self._is_paused:
            self._is_paused = True
            self._pause_event.set()

    def resume(self):
        """Resume from pause."""
        if self._is_playing and self._is_paused:
            self._is_paused = False
            self._pause_event.clear()

    def stop(self):
        """Stop playback and reset."""
        if self._is_playing:
            self._stop_event.set()
            self._pause_event.clear()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2.0)
            self._is_playing = False
            self._is_paused = False
            self._current_time = 0.0
            with self._sounding_lock:
                self._sounding_notes.clear()

    def seek(self, position: float):
        """Seek to a specific time position in seconds.

        When playback is running, this restarts the playback thread
        from the new position. When stopped/paused, it merely sets the
        starting position for the next play() or resume() call.
        """
        self._current_time = max(0.0, min(position, self.total_duration))
        if self._is_playing:
            was_paused = self._is_paused
            self._stop_event.set()
            if not was_paused:
                self._pause_event.clear()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2.0)
            if self._thread and self._thread.is_alive():
                logger = logging.getLogger(__name__)
                logger.warning("Seek: old thread did not stop in time, may cause race")
            self._stop_event.clear()
            self._is_playing = True
            self._is_paused = was_paused
            # Restore pause state for the new thread
            if was_paused:
                self._pause_event.set()
            else:
                self._pause_event.clear()
            self._start_time_sec = self._current_time
            self._wall_start = time_module.perf_counter()
            self._wall_offset = 0.0
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    @property
    def total_duration(self) -> float:
        return self._data.total_duration if self._data else 0.0

    def get_active_notes(self) -> dict[int, list[NoteEvent]]:
        """Return a shallow copy of currently sounding notes grouped by note number.
        Returns dict: note_number -> list of NoteEvent"""
        with self._sounding_lock:
            result: dict[int, list[NoteEvent]] = {}
            for (note_num, channel), events in self._sounding_notes.items():
                result[note_num] = list(events)
            return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _wait_while_paused(self) -> bool:
        """Block while paused, staying responsive to stop signals.

        Returns True if a stop was requested during the pause wait.
        """
        if not self._pause_event.is_set():
            return False
        pause_start = time_module.perf_counter()
        while self._pause_event.is_set():
            if self._stop_event.wait(timeout=0.05):
                return True  # stop requested during pause
        pause_duration = time_module.perf_counter() - pause_start
        self._wall_offset += pause_duration
        return False

    def _is_note_active(self, note: NoteEvent) -> bool:
        """Check if a NoteEvent belongs to a track that should be heard."""
        return self._is_track_active(note.track)

    def _send_all_notes_off(self, notes: list[NoteEvent]):
        """Send note_off for every note currently sounding."""
        for note in notes:
            if not self._is_note_active(note):
                continue
            if note.start_time <= self._current_time < note.end_time:
                if self._on_note_off:
                    self._on_note_off(note)

    def _dispatch_note(
        self, note: NoteEvent, is_note_on: bool, all_note_offs: set
    ) -> None:
        """Dispatch a note_on or note_off event, respecting seek-time note state."""
        # Track filtering: skip muted/solo-filtered tracks
        if not self._is_track_active(note.track):
            return

        if (note.note, note.channel) in all_note_offs and is_note_on:
            # This note was already on at seek point; treat as new note_on
            all_note_offs.discard((note.note, note.channel))
            if self._on_note_on:
                self._on_note_on(note)
            with self._sounding_lock:
                key = (note.note, note.channel)
                if key not in self._sounding_notes:
                    self._sounding_notes[key] = []
                self._sounding_notes[key].append(note)
        elif is_note_on:
            if self._on_note_on:
                self._on_note_on(note)
            with self._sounding_lock:
                key = (note.note, note.channel)
                if key not in self._sounding_notes:
                    self._sounding_notes[key] = []
                self._sounding_notes[key].append(note)
        else:
            if self._on_note_off:
                self._on_note_off(note)
            with self._sounding_lock:
                key = (note.note, note.channel)
                if key in self._sounding_notes:
                    try:
                        self._sounding_notes[key].remove(note)
                    except ValueError:
                        pass
                    if not self._sounding_notes[key]:
                        del self._sounding_notes[key]

    def _wait_for_next_event(
        self,
        event_time: float,
        start_time_sec: float,
        on_update: Optional[Callable[[float], None]] = None,
        update_interval: float = 0.1,
    ) -> bool:
        """Sleep until the next event time, handling pause/resume.

        Periodically calls *on_update* with the current wall-clock-based
        playback position so that the UI can update even during long
        silent gaps between MIDI events.

        Returns True if stop was requested during the wait.
        """
        adjusted_time = (event_time - start_time_sec) / self._speed
        target_wall = self._wall_start + self._wall_offset + adjusted_time

        now = time_module.perf_counter()
        sleep_time = target_wall - now
        if sleep_time <= 0.001:
            return False

        last_update = now

        while sleep_time > 0.01:
            if self._stop_event.is_set():
                return True
            if self._pause_event.is_set():
                if self._wait_while_paused():
                    return True
                # Recalculate target after pause
                adjusted_time = (event_time - start_time_sec) / self._speed
                target_wall = self._wall_start + self._wall_offset + adjusted_time
                now = time_module.perf_counter()
                sleep_time = target_wall - now
                last_update = now
                continue
            time_module.sleep(min(0.01, sleep_time))
            now = time_module.perf_counter()
            sleep_time = target_wall - now

            # Fire periodic update callback during long waits
            if on_update and now - last_update >= update_interval:
                last_update = now
                on_update(self.current_time)

        if sleep_time > 0 and not self._stop_event.is_set():
            time_module.sleep(sleep_time)

        return False

    # ------------------------------------------------------------------
    # Main playback loop
    # ------------------------------------------------------------------

    def _run(self):
        """Playback thread."""
        if self._data is None:
            return

        notes = self._data.notes
        notes.sort(key=lambda x: x.start_time)

        # Separate note-on and note-off events into a unified timeline
        events: list[tuple[float, bool, NoteEvent]] = []
        for note in notes:
            events.append((note.start_time, True, note))  # note_on
            events.append((note.end_time, False, note))  # note_off
        events.sort(key=lambda x: x[0])

        # Find starting index based on seek position
        start_idx = 0
        start_time_sec = self._start_time_sec
        for i, (t, is_on, note) in enumerate(events):
            if t >= start_time_sec:
                start_idx = i
                break

        # If any notes were already sounding at the seek point, send note_offs first
        cutoff = start_time_sec
        all_note_offs: set[tuple[int, int]] = set()
        for t, is_on, note in events:
            if t < cutoff and is_on:
                # This note started before seek point
                all_note_offs.add((note.note, note.channel))

        # Seek: send note_on for any notes already sounding at the seek point
        if start_time_sec > 0:
            for note in notes:
                if not self._is_note_active(note):
                    continue
                if note.start_time < start_time_sec < note.end_time:
                    if self._on_note_on:
                        self._on_note_on(note)
                    # Don't wait for the note_off from the timeline;
                    # treat subsequent note_on as new hits
                    all_note_offs.discard((note.note, note.channel))

        last_update = time_module.perf_counter()
        UPDATE_INTERVAL = 0.1

        for i in range(start_idx, len(events)):
            if self._stop_event.is_set():
                break

            # Handle pause
            if self._wait_while_paused():
                break

            event_time, is_note_on, note = events[i]

            # Pass on_update so _wait_for_next_event can fire it during long waits
            if self._wait_for_next_event(
                event_time, start_time_sec, on_update=self._on_update
            ):
                break

            if self._stop_event.is_set():
                break

            # Update current time tracker
            self._current_time = event_time

            # Periodic UI update between events (catches gaps when events are sparse)
            now = time_module.perf_counter()
            if self._on_update and now - last_update >= UPDATE_INTERVAL:
                last_update = now
                self._on_update(self.current_time)

            # Guard: don't dispatch if stop was set just now (race window)
            if self._stop_event.is_set():
                break

            self._dispatch_note(note, is_note_on, all_note_offs)

        # Cleanup: send note_off for all held notes regardless of stop reason
        self._send_all_notes_off(notes)

        self._is_playing = False
        self._is_paused = False

        # Only notify natural completion (not when stop/seek/speed-change interrupted)
        if not self._stop_event.is_set():
            if self._on_finish:
                self._on_finish()
