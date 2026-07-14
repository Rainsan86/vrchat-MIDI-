"""Application settings persistence via JSON config file."""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


def _get_app_dir() -> str:
    """Return the directory where config/library files should be stored.

    When running as a PyInstaller bundle (frozen exe), store config files
    next to the executable so users can easily find and edit them.
    When running as a normal Python script, store them alongside the package.
    """
    if getattr(sys, "frozen", False):
        # Running as PyInstaller bundle — use exe directory
        return os.path.dirname(sys.executable)
    # Running as normal Python — use package parent directory
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


# Default config file path
_CONFIG_DIR = _get_app_dir()
_CONFIG_PATH = os.path.join(_CONFIG_DIR, "midi_show_config.json")


@dataclass
class AppSettings:
    """User-configurable application settings."""

    # Window geometry
    window_width: int = 780
    window_height: int = 520
    window_x: int = -1  # -1 = default / center
    window_y: int = -1

    # Language
    language: str = "zh"

    # Playback speed
    speed: float = 1.0

    # Global volume (0.0 = muted, 1.0 = full)
    volume: float = 1.0

    # Output states
    local_audio_enabled: bool = True
    virtual_midi_enabled: bool = False
    osc_output_enabled: bool = False

    # Virtual MIDI port
    virtual_midi_port: str = "LoopMIDI Port"

    # OSC
    osc_address_ip: str = "127.0.0.1"
    osc_address_port: int = 9000
    osc_mode: str = "piano"

    # MIDI Input
    midi_input_enabled: bool = False
    midi_input_port: str = ""

    # Window always on top
    always_on_top: bool = False

    # Transpose (semitones, -12 .. +12)
    midi_input_transpose: int = 0
    playback_transpose: int = 0

    # Custom UI background image (path empty = theme color only)
    bg_image_path: str = ""


def load_settings() -> AppSettings:
    """Load settings from JSON config file, falling back to defaults."""
    if not os.path.exists(_CONFIG_PATH):
        logger.info("No config file found, using defaults")
        return AppSettings()

    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        settings = AppSettings()
        for key, value in raw.items():
            # Ignore removed keys from older configs (e.g. bg_image_opacity)
            if hasattr(settings, key) and value is not None:
                setattr(settings, key, value)
        if not isinstance(settings.bg_image_path, str):
            settings.bg_image_path = ""
        logger.info(f"Loaded settings from {_CONFIG_PATH}")
        return settings
    except Exception as e:
        logger.warning(f"Failed to load settings: {e}, using defaults")
        return AppSettings()


def save_settings(settings: AppSettings) -> bool:
    """Save settings to JSON config file. Returns True on success."""
    try:
        data = asdict(settings)
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved settings to {_CONFIG_PATH}")
        return True
    except Exception as e:
        logger.warning(f"Failed to save settings: {e}")
        return False


def get_config_path() -> str:
    """Return the path where settings are stored (for info/debug)."""
    return _CONFIG_PATH
