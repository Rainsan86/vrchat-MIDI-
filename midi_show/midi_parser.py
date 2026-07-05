"""MIDI file parser - extracts note events with precise timing."""

from __future__ import annotations

import os

import mido
from mido import MidiFile
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class NoteEvent:
    """A single note event with timing information."""

    note: int  # MIDI note number (0-127, 60 = Middle C)
    velocity: int  # Velocity (0-127)
    start_time: float  # Start time in seconds
    end_time: float  # End time in seconds
    channel: int  # MIDI channel (0-15)
    track: int = 0  # MIDI file track index


@dataclass
class MidiData:
    """Parsed MIDI file data ready for playback."""

    notes: list[NoteEvent] = field(default_factory=list)
    tempo_changes: list[tuple[float, int]] = field(default_factory=list)
    time_signatures: list[tuple[float, int, int]] = field(default_factory=list)
    total_duration: float = 0.0
    file_path: str = ""
    track_names: list[str] = field(default_factory=list)
    ticks_per_beat: int = 480
    bpm: float = 120.0
    title: str = ""


def _clean_midi_name(raw: str) -> str:
    """Clean a MIDI text field (track/instrument name) for display.

    Recovers text from common encodings (UTF-8, GBK, Shift-JIS, Big5, EUC-KR)
    that was mis-decoded as Latin-1 by mido's default reader.
    Removes remaining non-printable characters.
    """
    if not isinstance(raw, str):
        return ""

    # Recover original bytes: mido decodes MIDI text meta events as
    # Latin-1, so each character's code point == original byte value.
    try:
        raw_bytes = raw.encode('latin-1')
    except (UnicodeEncodeError, ValueError):
        return _filter_midi_text(raw)

    # Try common encodings in order of likelihood.
    # Accept the first result that doesn't contain replacement chars
    # or excessive control characters.
    for encoding in ('utf-8', 'gbk', 'shift-jis', 'big5', 'euc-kr', 'gb2312', 'gb18030'):
        try:
            recovered = raw_bytes.decode(encoding)
        except (UnicodeDecodeError, ValueError):
            continue
        if _looks_reasonable(recovered):
            return _filter_midi_text(recovered)

    # Fallback: strip non-printable chars from the original Latin-1 string
    return _filter_midi_text(raw)


def _looks_reasonable(text: str) -> bool:
    """Heuristic: the decoded text should have few garbage characters.

    Replacement char (U+FFFD), C0/C1 control chars are signs of wrong encoding.
    """
    bad_count = 0
    for c in text:
        cp = ord(c)
        # Replacement character
        if cp == 0xFFFD:
            bad_count += 1
        # C0 control codes (except common ones like TAB, LF, CR)
        elif 0x00 <= cp <= 0x08 or 0x0B <= cp <= 0x0C or 0x0E <= cp <= 0x1F:
            bad_count += 1
        # C1 control codes (DEL + high control chars)
        elif 0x7F <= cp <= 0x9F:
            bad_count += 1
    return bad_count / max(len(text), 1) < 0.3


def _filter_midi_text(text: str) -> str:
    """Remove non-printable characters from MIDI text fields."""
    cleaned = "".join(
        c if c.isprintable() or c in " \t_-" or ord(c) > 126 else ""
        for c in text
    )
    return cleaned.strip()


def parse_midi(file_path: str) -> Optional[MidiData]:
    """Parse a .mid file into MidiData with note events in seconds.

    Handles format 0, 1, 2 MIDI files, tempo changes, and
    converts all timing from ticks to wall-clock seconds.
    """
    try:
        mid = MidiFile(file_path)
    except Exception:
        return None

    data = MidiData()
    data.file_path = file_path
    data.ticks_per_beat = mid.ticks_per_beat

    # -- Collect all events from all tracks with absolute tick positions --
    all_events: list[tuple[int, mido.Message, int]] = []
    track_names: dict[int, str] = {}

    for track_idx, track in enumerate(mid.tracks):
        abs_tick = 0
        for msg in track:
            abs_tick += msg.time
            all_events.append((abs_tick, msg, track_idx))

    all_events.sort(key=lambda x: x[0])

    # -- Walk through events, converting ticks -> wall clock seconds --
    current_tempo = 500_000  # default 120 BPM in µs per beat
    current_time = 0.0
    last_tick = 0
    active_notes: dict[
        tuple[int, int], tuple[float, int]
    ] = {}  # (note, ch) -> (start_time, velocity)

    for tick, msg, track_idx in all_events:
        delta_ticks = tick - last_tick
        # Convert tick delta to seconds
        sec_per_tick = current_tempo / 1_000_000.0 / data.ticks_per_beat
        current_time += delta_ticks * sec_per_tick
        last_tick = tick

        if msg.type == "set_tempo":
            current_tempo = msg.tempo
            data.tempo_changes.append((current_time, msg.tempo))
            data.bpm = 60_000_000.0 / msg.tempo

        elif msg.type == "time_signature":
            data.time_signatures.append((current_time, msg.numerator, msg.denominator))

        elif msg.type == "track_name":
            if track_idx not in track_names:
                name = _clean_midi_name(msg.name) or f"Track {track_idx}"
                track_names[track_idx] = name

        elif msg.type == "instrument_name":
            if track_idx not in track_names:
                name = _clean_midi_name(msg.name) or f"Track {track_idx}"
                track_names[track_idx] = name

        elif msg.type == "note_on" and msg.velocity > 0:
            key = (msg.note, msg.channel)
            active_notes[key] = (current_time, msg.velocity)

        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            key = (msg.note, msg.channel)
            if key in active_notes:
                start, vel = active_notes.pop(key)
                note_ev = NoteEvent(
                    note=msg.note,
                    velocity=vel,
                    start_time=start,
                    end_time=current_time,
                    channel=msg.channel,
                    track=track_idx,
                )
                data.notes.append(note_ev)

    # Close any notes still held at end of file
    for (note, ch), (start, vel) in active_notes.items():
        # We lost track_idx for hanging notes; assign -1 as unknown
        data.notes.append(NoteEvent(note, vel, start, current_time, ch, track=-1))

    data.total_duration = current_time
    data.notes.sort(key=lambda x: x.start_time)

    # Build track_names list aligned with track indices
    num_tracks = len(mid.tracks)
    data.track_names = []
    for i in range(num_tracks):
        if i in track_names:
            data.track_names.append(track_names[i])
        else:
            data.track_names.append(f'Track {i}')

    # Use filename as title (track names are often internal labels like "MIDI Out")
    data.title = os.path.splitext(os.path.basename(file_path))[0]

    return data
