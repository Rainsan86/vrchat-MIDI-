"""Real-time piano roll visualization widget."""

from __future__ import annotations

import tkinter as tk
from typing import Optional

from .midi_parser import NoteEvent

# Piano roll visual constants
KEYBOARD_WIDTH = 50  # px for the keyboard strip on the left
NOTE_AREA_LEFT = KEYBOARD_WIDTH + 2  # where the note grid starts
MIN_NOTE = 21  # A0 (lowest piano note)
MAX_NOTE = 108  # C8 (highest piano note)
NUM_KEYS = MAX_NOTE - MIN_NOTE + 1  # 88 keys
WHITE_KEYS = {0, 2, 4, 5, 7, 9, 11}  # C, D, E, F, G, A, B (within octave)

# Colors
COLOR_WHITE_KEY = "#F5F5F0"
COLOR_BLACK_KEY = "#333333"
COLOR_ACTIVE_NOTE = "#4CAF50"  # green for currently playing
COLOR_GRID_LINE = "#E0E0E0"
COLOR_PLAYHEAD = "#FF4444"
COLOR_BG = "#FFFFFF"
COLOR_KEYBOARD_BG = "#E8E8E8"
COLOR_NOTE_OFF = "#90CAF9"  # light blue for notes that recently played


class PianoRoll(tk.Canvas):
    """Canvas-based piano roll with scrolling note visualization."""

    def __init__(self, parent, **kwargs):
        kwargs.setdefault("bg", COLOR_BG)
        kwargs.setdefault("highlightthickness", 0)
        super().__init__(parent, **kwargs)

        self._note_range = (MIN_NOTE, MAX_NOTE)
        self._row_height = max(4, min(8, self.winfo_height() // NUM_KEYS))

        # Data
        self._all_notes: list[NoteEvent] = []
        self._active_notes: dict[int, list[NoteEvent]] = {}  # note_num -> events
        self._current_time: float = 0.0
        self._duration: float = 1.0  # avoid division by zero
        self._playhead_x: float = NOTE_AREA_LEFT
        self._total_width: int = 800

        # Cache
        self._key_rects: dict[int, int] = {}  # note -> canvas rect id
        self._bg_initialized = False

        self.bind("<Configure>", self._on_resize)
        self._redraw_background()

    def set_data(self, notes: list[NoteEvent], duration: float):
        """Load note data for a new song."""
        self._all_notes = notes
        self._duration = duration if duration > 0 else 1.0
        self._active_notes.clear()
        self._current_time = 0.0
        self._compute_note_range(notes)
        self._redraw_background()

    def _compute_note_range(self, notes: list[NoteEvent]):
        """Adjust visible note range to fit the song's notes."""
        if not notes:
            self._note_range = (MIN_NOTE, MAX_NOTE)
            return
        min_n = min(n.note for n in notes)
        max_n = max(n.note for n in notes)
        # Add padding
        min_n = max(MIN_NOTE, min_n - 3)
        max_n = min(MAX_NOTE, max_n + 3)
        self._note_range = (min_n, max_n)

    def update_playback(self, current_time: float, active: dict[int, list[NoteEvent]]):
        """Update the display for the current playback frame."""
        self._current_time = current_time
        self._active_notes = active
        self._redraw_notes()

    def _on_resize(self, event=None):
        """Handle widget resize."""
        self._total_width = max(400, self.winfo_width())
        self._row_height = self._compute_row_height()
        self._redraw_background()
        self._redraw_notes()

    def _compute_row_height(self) -> int:
        """Compute the height per note row based on widget height."""
        lo, hi = self._note_range
        n_notes = hi - lo + 1
        h = self.winfo_height()
        return max(4, min(12, h // n_notes if n_notes > 0 else 8))

    def _note_to_y(self, note: int) -> float:
        """Convert MIDI note number to Y coordinate (bottom = low notes)."""
        lo, hi = self._note_range
        rh = self._compute_row_height()
        # Invert: low notes at bottom
        idx = hi - note
        return float(idx * rh)

    def _time_to_x(self, time_sec: float) -> float:
        """Convert time in seconds to X coordinate with scrolling window."""
        w = self._total_width - NOTE_AREA_LEFT - 10
        if self._duration <= 0:
            return NOTE_AREA_LEFT
        # Show a sliding window of 4 seconds
        window = 4.0
        # Center the playhead at 30% of the note area
        center_ratio = 0.3
        visible_start = time_sec - window * center_ratio
        if visible_start < 0:
            visible_start = 0
        x = NOTE_AREA_LEFT + ((time_sec - visible_start) / window) * w
        return max(NOTE_AREA_LEFT, min(self._total_width - 10, x))

    def _redraw_background(self):
        """Draw static background: keyboard + grid lines."""
        self.delete("bg")
        self.delete("keyboard")
        self.delete("grid")

        w = max(400, self.winfo_width())
        h = max(100, self.winfo_height())
        rh = self._compute_row_height()
        lo, hi = self._note_range

        # Keyboard background
        self.create_rectangle(
            0, 0, KEYBOARD_WIDTH, h, fill=COLOR_KEYBOARD_BG, outline="", tags="bg"
        )

        # Draw keys and grid
        for note in range(lo, hi + 1):
            y = self._note_to_y(note)
            oct_note = note % 12
            is_white = oct_note in WHITE_KEYS
            is_c = oct_note == 0  # C note

            if is_white:
                # White key background
                key_color = COLOR_WHITE_KEY
                border = "#CCCCCC" if not is_c else "#AAAAAA"
                self.create_rectangle(
                    1,
                    y,
                    KEYBOARD_WIDTH - 1,
                    y + rh,
                    fill=key_color,
                    outline=border,
                    tags=("bg", "key"),
                )
            else:
                # Black key (smaller, overlaid)
                key_color = COLOR_BLACK_KEY
                self.create_rectangle(
                    1,
                    y,
                    KEYBOARD_WIDTH * 0.65,
                    y + rh,
                    fill=key_color,
                    outline="#222222",
                    tags=("bg", "key"),
                )

            # Grid lines
            if is_c:
                self.create_line(
                    NOTE_AREA_LEFT,
                    y + rh,
                    w - 2,
                    y + rh,
                    fill="#CCCCCC",
                    width=1,
                    tags="grid",
                )
            else:
                self.create_line(
                    NOTE_AREA_LEFT,
                    y + rh,
                    w - 2,
                    y + rh,
                    fill=COLOR_GRID_LINE,
                    width=1,
                    tags="grid",
                )

        # Separator between keyboard and note area
        self.create_line(
            NOTE_AREA_LEFT - 1,
            0,
            NOTE_AREA_LEFT - 1,
            h,
            fill="#999999",
            width=1,
            tags="bg",
        )

        # Octave labels
        for octave in range(-2, 10):
            note_c = 12 * (octave + 2)  # C in this octave (C0 = MIDI 12)
            if lo <= note_c <= hi:
                y = self._note_to_y(note_c)
                label = f"C{octave}"
                self.create_text(
                    3,
                    y + rh / 2,
                    text=label,
                    anchor="w",
                    font=("Arial", max(6, min(9, rh - 1))),
                    fill="#888888",
                    tags="bg",
                )

        self._bg_initialized = True

    def _redraw_notes(self):
        """Draw active notes and playhead."""
        self.delete("notes")
        self.delete("playhead")

        w = max(400, self.winfo_width())
        rh = self._compute_row_height()

        # Draw currently-active notes
        for note_num, events in self._active_notes.items():
            if not events:
                continue
            y = self._note_to_y(note_num)
            for ev in events:
                start_x = self._time_to_x(ev.start_time)
                end_x = self._time_to_x(self._current_time)
                if end_x <= start_x:
                    end_x = start_x + 4
                bar_w = max(3, end_x - start_x)
                self.create_rectangle(
                    start_x,
                    y + 1,
                    start_x + bar_w,
                    y + rh - 1,
                    fill=COLOR_ACTIVE_NOTE,
                    outline="#388E3C",
                    tags="notes",
                )

        # Draw playhead line
        ph_x = self._time_to_x(self._current_time)
        self.create_line(
            ph_x,
            0,
            ph_x,
            self.winfo_height(),
            fill=COLOR_PLAYHEAD,
            width=2,
            tags="playhead",
        )
