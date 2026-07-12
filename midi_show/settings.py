"""Application settings persistence via JSON config file."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# Default config file path: alongside the package directory
_CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
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

    # Background image
    background_image_path: str = ""
    background_enabled: bool = False
    background_mode: str = "cover"  # cover | contain

    # Transpose (semitones, -12 .. +12)
    midi_input_transpose: int = 0
    playback_transpose: int = 0


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
            if hasattr(settings, key) and value is not None:
                setattr(settings, key, value)
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
