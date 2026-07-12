"""MIDI Library — persistent catalog of MIDI files with cached metadata."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, asdict
from typing import Optional

from .midi_parser import parse_midi

logger = logging.getLogger(__name__)

_LIBRARY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
_LIBRARY_PATH = os.path.join(_LIBRARY_DIR, "midi_show_library.json")


@dataclass
class LibraryEntry:
    """A single entry in the MIDI library."""

    path: str
    title: str = ""
    duration_sec: float = 0.0
    bpm: float = 120.0
    note_count: int = 0
    track_count: int = 0
    file_hash: str = ""


class LibraryManager:
    """Manages a persistent catalog of MIDI files.

    Each entry caches metadata (title, duration, BPM, note count)
    so the library list can be displayed instantly without re-parsing
    every file on startup.
    """

    def __init__(self):
        self._entries: list[LibraryEntry] = []
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def entries(self) -> list[LibraryEntry]:
        return list(self._entries)

    @property
    def count(self) -> int:
        return len(self._entries)

    def add_file(self, path: str) -> Optional[LibraryEntry]:
        """Add a single MIDI file to the library.

        Parses the file to extract metadata, computes a hash for
        deduplication, and persists immediately.
        Returns the new entry, or None if the file was already present
        or could not be parsed.
        """
        added = self.add_files([path])
        return added[0] if added else None

    def add_files(self, paths: list[str]) -> list[LibraryEntry]:
        """Batch-add multiple files. Returns list of successfully added entries.

        Only persists to disk once after all files are added.
        """
        added: list[LibraryEntry] = []
        for p in paths:
            p = os.path.abspath(p)
            # Dedup by path
            if any(e.path == p for e in self._entries):
                logger.info("Library duplicate ignored: %s", p)
                continue
            entry = self._build_entry(p)
            if entry is not None:
                self._entries.append(entry)
                added.append(entry)
        if added:
            self._save()
        return added

    def remove(self, path: str) -> bool:
        """Remove an entry by path."""
        for i, e in enumerate(self._entries):
            if e.path == path:
                self._entries.pop(i)
                self._save()
                return True
        return False

    def remove_index(self, index: int) -> bool:
        """Remove an entry by list index."""
        if 0 <= index < len(self._entries):
            self._entries.pop(index)
            self._save()
            return True
        return False

    def get_by_index(self, index: int) -> Optional[LibraryEntry]:
        if 0 <= index < len(self._entries):
            return self._entries[index]
        return None

    def get_by_path(self, path: str) -> Optional[LibraryEntry]:
        path = os.path.abspath(path)
        for e in self._entries:
            if e.path == path:
                return e
        return None

    def clear(self):
        """Remove all entries."""
        self._entries.clear()
        self._save()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self):
        if not os.path.exists(_LIBRARY_PATH):
            return
        try:
            with open(_LIBRARY_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
            entries: list[LibraryEntry] = []
            for d in raw:
                entries.append(
                    LibraryEntry(
                        path=d.get("path", ""),
                        title=d.get("title", ""),
                        duration_sec=d.get("duration_sec", 0.0),
                        bpm=d.get("bpm", 120.0),
                        note_count=d.get("note_count", 0),
                        track_count=d.get("track_count", 0),
                        file_hash=d.get("file_hash", ""),
                    )
                )
            self._entries = entries
            logger.info("Loaded %d library entries", len(entries))
        except Exception as exc:
            logger.warning("Failed to load library: %s", exc)

    def _save(self):
        try:
            data = [asdict(e) for e in self._entries]
            with open(_LIBRARY_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("Saved %d library entries", len(self._entries))
        except Exception as exc:
            logger.warning("Failed to save library: %s", exc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_entry(self, path: str) -> Optional[LibraryEntry]:
        """Parse a MIDI file and build a library entry.

        Returns None if the file doesn't exist or can't be parsed.
        """
        if not os.path.exists(path):
            logger.warning("Library add: file not found: %s", path)
            return None

        # Quick hash of the path for lightweight dedup
        file_hash = hashlib.md5(path.encode("utf-8")).hexdigest()[:8]

        data = parse_midi(path)
        if data is None:
            return None

        title = data.title or os.path.splitext(os.path.basename(path))[0]
        return LibraryEntry(
            path=path,
            title=title,
            duration_sec=data.total_duration,
            bpm=data.bpm,
            note_count=len(data.notes),
            track_count=len(data.track_names),
            file_hash=file_hash,
        )
