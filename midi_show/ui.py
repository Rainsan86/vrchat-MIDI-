"""Tkinter-based GUI for VRChat MIDI Player."""

from __future__ import annotations

import logging
import os
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from PIL import Image, ImageDraw, ImageTk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _HAS_DND = True
except ImportError:
    _HAS_DND = False

from .midi_parser import MidiData, parse_midi
from .engine import PlaybackEngine
from .outputs import LocalSynthOutput, VirtualMidiOutput, OscOutput, MidiInput
from .library import LibraryManager
from .i18n import (
    tr as _tr,
    trf as _trf,
    set_language,
    get_language,
    language_text_map,
)
from .settings import load_settings, save_settings, AppSettings
from .icon_art import draw_piano_icon

logger = logging.getLogger(__name__)


class MidiShowUI:
    """Main application window."""

    def __init__(self):
        # Load persisted settings
        self._settings = load_settings()

        # Restore language before building UI
        set_language(self._settings.language)

        self.root = tk.Tk() if not _HAS_DND else TkinterDnD.Tk()
        self.root.title(_tr("window.title"))

        # Window geometry
        w, h = self._settings.window_width, self._settings.window_height
        wx, wy = self._settings.window_x, self._settings.window_y
        self.root.geometry(f"{w}x{h}")
        if wx >= 0 and wy >= 0:
            self.root.geometry(f"+{wx}+{wy}")
        self.root.minsize(640, 420)
        self._setup_styles()

        # Save settings on close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # State
        self._data: Optional[MidiData] = None
        self._engine = PlaybackEngine()
        self._local_synth = LocalSynthOutput(enabled=self._settings.local_audio_enabled)
        self._virtual_midi = VirtualMidiOutput(
            enabled=self._settings.virtual_midi_enabled,
            port_name=self._settings.virtual_midi_port,
        )
        self._osc = OscOutput(
            enabled=self._settings.osc_output_enabled,
            ip=self._settings.osc_address_ip,
            port=self._settings.osc_address_port,
            mode=self._settings.osc_mode,
        )

        self._update_id: Optional[str] = None
        self._last_update_time: float = 0.0

        # MidiInput
        self._midi_input = MidiInput(enabled=self._settings.midi_input_enabled)

        # Library manager
        self._library = LibraryManager()
        self._midi_input.set_callbacks(
            note_on=self._on_midi_input_note_on,
            note_off=self._on_midi_input_note_off,
        )

        # Live Passthrough mode
        self._passthrough_var = tk.BooleanVar(value=False)
        self._midi_input_was_enabled = False  # saved state before passthrough

        # UI elements (initialized in _build_ui)
        self._file_label: Optional[tk.Label] = None
        self._title_label: Optional[tk.Label] = None
        self._play_btn: Optional[tk.Button] = None
        self._pause_btn: Optional[tk.Button] = None
        self._stop_btn: Optional[tk.Button] = None
        self._passthrough_cb: Optional[ttk.Checkbutton] = None
        self._passthrough_status_var: Optional[tk.StringVar] = None
        self._progress_bar: Optional[ttk.Progressbar] = None
        self._time_label: Optional[tk.Label] = None
        self._speed_var: Optional[tk.DoubleVar] = None
        self._status_var: Optional[tk.StringVar] = None
        self._note_count_var: Optional[tk.StringVar] = None
        self._local_audio_var: Optional[tk.BooleanVar] = None
        self._virtual_var: Optional[tk.BooleanVar] = None
        self._osc_var: Optional[tk.BooleanVar] = None
        self._synth_port_var: Optional[tk.StringVar] = None
        self._virtual_port_var: Optional[tk.StringVar] = None
        self._osc_addr_var: Optional[tk.StringVar] = None
        self._playback_transpose_var: Optional[tk.IntVar] = None
        self._midi_input_transpose_var: Optional[tk.IntVar] = None

        # Custom background (Canvas layer + create_window UI; never parent widgets to image Label)
        self._bg_canvas: Optional[tk.Canvas] = None
        self._bg_image_id: Optional[int] = None
        self._bg_photo: Optional[ImageTk.PhotoImage] = None
        self._bg_src: Optional[Image.Image] = None
        self._bg_resize_job: Optional[str] = None
        self._bg_draw_key: Optional[tuple] = None
        self._bg_path_var: Optional[tk.StringVar] = None
        self._ui_player: Optional[ttk.Frame] = None
        self._ui_notebook: Optional[ttk.Notebook] = None
        self._ui_status: Optional[tk.Frame] = None
        self._canvas_player: Optional[int] = None
        self._canvas_nb: Optional[int] = None
        self._canvas_status: Optional[int] = None
        self._wallpaper_active: bool = False

        # Connect engine callbacks
        self._engine.set_callbacks(
            on_note_on=self._on_note_on,
            on_note_off=self._on_note_off,
            on_finish=self._on_finish,
            on_update=self._on_engine_update,
        )

        self._build_ui()
        self._update_timer()



    @staticmethod
    def _fmt_time(seconds: float) -> str:
        seconds = max(0, int(seconds))
        return f"{seconds // 60}:{seconds % 60:02d}"

    def _resolve_ui_font(self) -> str:
        """Pick a rounded, readable UI font (anime-friendly on Windows)."""
        for name in ("Yu Gothic UI", "Microsoft YaHei UI", "Segoe UI"):
            if name in tkfont.families(self.root):
                return name
        return "Segoe UI"

    def _font(self, size: int = 10, bold: bool = False) -> tuple[str, int, str]:
        style = "bold" if bold else "normal"
        return (self._ui_font, size, style)

    def _t(self, key: str) -> str:
        return self._theme[key]

    def _resolve_app_icon_path(self) -> Optional[str]:
        """Locate app_icon.ico next to the exe (frozen) or project root."""
        import sys

        candidates = []
        if getattr(sys, "frozen", False):
            candidates.append(os.path.join(os.path.dirname(sys.executable), "app_icon.ico"))
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                candidates.append(os.path.join(meipass, "app_icon.ico"))
        else:
            here = os.path.dirname(os.path.abspath(__file__))
            candidates.append(os.path.join(here, "..", "app_icon.ico"))
            candidates.append(os.path.join(os.getcwd(), "app_icon.ico"))
        for path in candidates:
            path = os.path.normpath(path)
            if os.path.isfile(path):
                return path
        return None

    def _set_window_icon(self):
        """Set title-bar / taskbar icon from the same artwork as the EXE icon."""
        import tempfile

        try:
            # Always use the shared art (identical to app_icon.ico / desktop icon)
            img16 = draw_piano_icon(16)
            img32 = draw_piano_icon(32)

            # Prefer embedded ICO frames when available (same source as Explorer)
            ico_path = self._resolve_app_icon_path()
            if ico_path:
                try:
                    with Image.open(ico_path) as ico:
                        sizes = set(ico.info.get("sizes") or [])
                        if (16, 16) in sizes:
                            ico.size = (16, 16)
                            img16 = ico.convert("RGBA").copy()
                        if (32, 32) in sizes:
                            ico.size = (32, 32)
                            img32 = ico.convert("RGBA").copy()
                except Exception as e:
                    logger.debug("ICO load for window icon failed: %s", e)

            # Pillow-standard ICO under ASCII TEMP (BMP Explorer ICO blanks in Tk).
            # Same artwork: derive both sizes from img32 so title/taskbar stay unified.
            try:
                tmp_ico = os.path.join(tempfile.gettempdir(), "midi_show_tk_icon.ico")
                img32.save(tmp_ico, format="ICO", sizes=[(16, 16), (32, 32)])
                self.root.iconbitmap(default=tmp_ico)
            except Exception as e:
                logger.debug("iconbitmap skipped: %s", e)

            photos = [ImageTk.PhotoImage(img16), ImageTk.PhotoImage(img32)]
            self._icon_photos = photos
            self._icon_photo = photos[-1]
            self.root.iconphoto(True, *photos)
        except Exception:
            logger.debug("Could not set custom icon, using default", exc_info=True)
            try:
                img = draw_piano_icon(32)
                self._icon_photo = ImageTk.PhotoImage(img)
                self.root.iconphoto(True, self._icon_photo)
            except Exception:
                pass

    @staticmethod
    def _draw_checkbutton_icon(size: int, checked: bool) -> Image.Image:
        """Draw a checkbutton indicator icon: ☐ unchecked or ✅ checked."""
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        pad = 1
        # Draw rounded rectangle border
        draw.rounded_rectangle(
            [pad, pad, size - pad - 1, size - pad - 1],
            radius=3,
            fill="#ffffff",
            outline="#E87898",
            width=2,
        )
        if checked:
            draw.rounded_rectangle(
                [pad + 1, pad + 1, size - pad - 2, size - pad - 2],
                radius=2,
                fill="#6BBF9A",
                outline=None,
            )
            # Draw checkmark ✓
            cx, cy = size // 2, size // 2
            s = size // 4
            draw.line(
                [cx - s, cy, cx - s // 3, cy + s],
                fill="#ffffff",
                width=max(2, size // 8),
            )
            draw.line(
                [cx - s // 3, cy + s, cx + s, cy - s],
                fill="#ffffff",
                width=max(2, size // 8),
            )
        return img

    def _setup_styles(self):
        """小清新 sakura UI: soft pastels, one accent, readable contrast (Taste redesign)."""
        root = self.root
        self._ui_font = self._resolve_ui_font()

        # One locked accent (sakura) + mist neutrals. Sky is secondary ornament only.
        BG_MAIN = "#F6F2F7"
        BG_PANEL = "#FFFFFF"
        BG_STATUS = "#F3EAF2"
        BG_ENTRY = "#FFFBFC"
        BTN_BG = "#FFFFFF"
        BTN_ACTIVE = "#FFE4EF"
        BTN_PRESSED = "#FFD0E2"
        BTN_NEUTRAL = "#F0ECF4"
        ACCENT = "#E87A9A"
        ACCENT_SOFT = "#F2A8BC"
        ACCENT_DARK = "#C45A7A"
        ACCENT_SECONDARY = "#7BC4D8"
        TEXT_MAIN = "#2F2A38"
        TEXT_DIM = "#6F6680"
        BORDER = "#EDD5E2"
        SUCCESS = "#5BB894"
        WARNING = "#E8B060"
        DANGER_BG = "#FFF5F5"
        DANGER_FG = "#C94B4B"
        DANGER_BORDER = "#F5C8C8"
        MUTE_ACTIVE = "#FFD6DC"
        SOLO_ACTIVE = "#D4F5E4"
        BTN_DISABLED = "#F3EEF2"
        TEXT_DISABLED = "#B0A8BC"
        ACCENT_BTN_DISABLED = "#E5C0CD"

        root.configure(bg=BG_MAIN)
        self._set_window_icon()

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            ".", background=BG_MAIN, foreground=TEXT_MAIN, font=self._font(10)
        )
        style.configure("TFrame", background=BG_MAIN)
        style.configure("TLabel", background=BG_MAIN, foreground=TEXT_MAIN)
        style.configure("Dim.TLabel", background=BG_MAIN, foreground=TEXT_DIM)
        style.configure(
            "Brand.TLabel",
            background=BG_MAIN,
            foreground=ACCENT_DARK,
            font=self._font(12, bold=True),
        )
        style.configure(
            "Title.TLabel",
            background=BG_PANEL,
            foreground=ACCENT_DARK,
            font=self._font(13, bold=True),
        )
        style.configure(
            "Header.TLabel",
            background=BG_PANEL,
            foreground=ACCENT,
            font=self._font(11, bold=True),
        )
        style.configure("Soft.TLabel", background=BG_PANEL, foreground=TEXT_MAIN)
        style.configure("Soft.Dim.TLabel", background=BG_PANEL, foreground=TEXT_DIM)
        style.configure(
            "Soft.Section.TLabel",
            background=BG_PANEL,
            foreground=ACCENT,
            font=self._font(10, bold=True),
        )

        style.configure(
            "TButton",
            padding=(14, 8),
            font=self._font(10),
            background=BTN_BG,
            foreground=ACCENT_DARK,
            borderwidth=1,
            relief="solid",
            bordercolor=BORDER,
            focusthickness=0,
            focuscolor=BTN_ACTIVE,
        )
        style.map(
            "TButton",
            background=[
                ("active", BTN_ACTIVE),
                ("pressed", BTN_PRESSED),
                ("disabled", BTN_DISABLED),
            ],
            foreground=[("disabled", TEXT_DISABLED)],
            bordercolor=[("active", ACCENT_SOFT), ("pressed", ACCENT)],
        )

        style.configure(
            "Accent.TButton",
            padding=(16, 9),
            font=self._font(10, bold=True),
            background=ACCENT,
            foreground="#ffffff",
            borderwidth=0,
            relief="flat",
            focusthickness=0,
        )
        style.map(
            "Accent.TButton",
            background=[
                ("active", ACCENT_SOFT),
                ("pressed", ACCENT_DARK),
                ("disabled", ACCENT_BTN_DISABLED),
            ],
            foreground=[("disabled", "#ffffff")],
        )

        style.configure(
            "Danger.TButton",
            padding=(12, 8),
            font=self._font(10),
            background=DANGER_BG,
            foreground=DANGER_FG,
            borderwidth=1,
            relief="solid",
            bordercolor=DANGER_BORDER,
            focusthickness=0,
        )
        style.map(
            "Danger.TButton",
            background=[("active", "#FFEAEA"), ("pressed", DANGER_BORDER)],
            bordercolor=[("active", DANGER_FG), ("pressed", DANGER_FG)],
        )

        style.configure("Soft.TFrame", background=BG_PANEL)
        style.configure("Soft.TLabelframe", background=BG_PANEL, bordercolor=BORDER)
        style.configure(
            "Soft.TLabelframe.Label",
            background=BG_PANEL,
            foreground=ACCENT,
            font=self._font(10, bold=True),
        )

        style.configure("TNotebook", background=BG_MAIN, borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            padding=(20, 8),
            font=self._font(10, bold=True),
            background=BG_PANEL,
            foreground=TEXT_DIM,
            borderwidth=1,
            bordercolor=BORDER,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#FFF8FB"), ("active", BTN_ACTIVE)],
            foreground=[("selected", ACCENT), ("active", ACCENT_DARK)],
            bordercolor=[("selected", ACCENT_SOFT)],
        )

        style.configure(
            "TProgressbar",
            thickness=11,
            background=ACCENT,
            troughcolor="#F7EAF1",
            bordercolor=BORDER,
            lightcolor=ACCENT_SOFT,
            darkcolor=ACCENT,
        )

        style.configure(
            "TEntry",
            fieldbackground=BG_ENTRY,
            background=BG_ENTRY,
            foreground=TEXT_MAIN,
            borderwidth=1,
            relief="solid",
            bordercolor=BORDER,
            padding=4,
        )
        style.map("TEntry", bordercolor=[("focus", ACCENT_SOFT)])
        style.configure(
            "TCombobox",
            fieldbackground=BG_ENTRY,
            background=BG_ENTRY,
            foreground=TEXT_MAIN,
            borderwidth=1,
            relief="solid",
            bordercolor=BORDER,
            arrowcolor=ACCENT,
            padding=3,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", BG_ENTRY)],
            bordercolor=[("focus", ACCENT_SOFT)],
        )
        style.configure(
            "TSpinbox",
            fieldbackground=BG_ENTRY,
            background=BG_ENTRY,
            foreground=TEXT_MAIN,
            bordercolor=BORDER,
            arrowcolor=ACCENT,
            padding=2,
        )

        cb_size = 18
        self._cb_unchecked_img = ImageTk.PhotoImage(
            self._draw_checkbutton_icon(cb_size, checked=False)
        )
        self._cb_checked_img = ImageTk.PhotoImage(
            self._draw_checkbutton_icon(cb_size, checked=True)
        )
        style.configure(
            "Custom.TCheckbutton",
            background=BG_PANEL,
            foreground=TEXT_MAIN,
            image=self._cb_unchecked_img,
            indicatoron=False,
            borderwidth=0,
            relief=tk.FLAT,
            focuscolor=BG_PANEL,
            padding=(4, 4),
        )
        style.map(
            "Custom.TCheckbutton",
            background=[("active", BG_PANEL)],
            image=[("selected", self._cb_checked_img)],
        )
        style.configure(
            "TRadiobutton",
            background=BG_PANEL,
            foreground=TEXT_MAIN,
            indicatorcolor=BG_ENTRY,
        )
        style.map(
            "TRadiobutton",
            background=[("active", BG_PANEL)],
            indicatorcolor=[("selected", ACCENT)],
        )

        style.configure(
            "Horizontal.TScale",
            background=BG_PANEL,
            troughcolor="#F7EAF1",
            bordercolor=BORDER,
            lightcolor=ACCENT_SECONDARY,
            darkcolor=ACCENT,
        )

        style.configure(
            "Treeview",
            background=BG_ENTRY,
            fieldbackground=BG_ENTRY,
            foreground=TEXT_MAIN,
            borderwidth=1,
            relief="solid",
            bordercolor=BORDER,
            rowheight=32,
        )
        style.configure(
            "Treeview.Heading",
            font=self._font(10, bold=True),
            background="#FFF8FB",
            foreground=ACCENT_DARK,
            bordercolor=BORDER,
            relief="flat",
        )
        style.map(
            "Treeview",
            background=[("selected", BTN_ACTIVE)],
            foreground=[("selected", ACCENT_DARK)],
        )
        style.map("Treeview.Heading", background=[("active", BTN_ACTIVE)])

        style.configure("TSeparator", background=BORDER)

        style.configure(
            "Vertical.TScrollbar",
            background=BG_PANEL,
            troughcolor=BG_MAIN,
            bordercolor=BORDER,
            arrowcolor=ACCENT,
            width=12,
        )
        style.map("Vertical.TScrollbar", background=[("active", BTN_ACTIVE)])

        self._theme = {
            "BG_MAIN": BG_MAIN,
            "BG_PANEL": BG_PANEL,
            "BG_STATUS": BG_STATUS,
            "BG_ENTRY": BG_ENTRY,
            "BTN_BG": BTN_BG,
            "BTN_ACTIVE": BTN_ACTIVE,
            "BTN_PRESSED": BTN_PRESSED,
            "BTN_NEUTRAL": BTN_NEUTRAL,
            "ACCENT": ACCENT,
            "ACCENT_SOFT": ACCENT_SOFT,
            "ACCENT_DARK": ACCENT_DARK,
            "ACCENT_SECONDARY": ACCENT_SECONDARY,
            "TEXT_MAIN": TEXT_MAIN,
            "TEXT_DIM": TEXT_DIM,
            "BORDER": BORDER,
            "SUCCESS": SUCCESS,
            "WARNING": WARNING,
            "DANGER_BG": DANGER_BG,
            "DANGER_FG": DANGER_FG,
            "MUTE_ACTIVE": MUTE_ACTIVE,
            "SOLO_ACTIVE": SOLO_ACTIVE,
        }

    def _make_chip(
        self,
        parent: tk.Misc,
        text: str,
        *,
        bg: str,
        command,
        pack_side=tk.RIGHT,
        padx=(6, 0),
    ) -> tk.Label:
        """Compact pill-like action label (lang / pin)."""
        t = self._theme
        chip = tk.Label(
            parent,
            text=text,
            font=self._font(9),
            bg=bg,
            fg="#ffffff",
            padx=12,
            pady=4,
            cursor="hand2",
            borderwidth=0,
            relief=tk.FLAT,
        )
        chip.pack(side=pack_side, padx=padx)
        chip.bind("<Button-1>", lambda e: command())
        chip.bind("<Enter>", lambda e: chip.config(bg=t["ACCENT_SOFT"]))
        return chip

    @staticmethod
    def _hex_to_rgb(color: str) -> tuple[int, int, int]:
        h = color.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    @staticmethod
    def _mix_hex(c1: str, c2: str, t: float) -> str:
        """Mix two #RRGGBB colors; t=1 keeps c2."""
        a = MidiShowUI._hex_to_rgb(c1)
        b = MidiShowUI._hex_to_rgb(c2)
        t = max(0.0, min(1.0, t))
        rgb = tuple(int(round(a[i] * (1 - t) + b[i] * t)) for i in range(3))
        return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"

    def _load_bg_source(self, path: str) -> bool:
        """Load and cache the source background image. Returns True on success."""
        if not path or not os.path.isfile(path):
            self._bg_src = None
            return False
        try:
            with Image.open(path) as img:
                self._bg_src = img.convert("RGB")
            return True
        except Exception as e:
            logger.warning("Failed to load background image %s: %s", path, e)
            self._bg_src = None
            return False

    def _compose_background_photo(
        self, width: int, height: int
    ) -> Optional[ImageTk.PhotoImage]:
        """Cover-fit wallpaper with a light wash so gaps stay soft on the eyes."""
        if self._bg_src is None or width < 2 or height < 2:
            return None
        img = self._bg_src
        scale = max(width / img.width, height / img.height)
        nw = max(1, int(img.width * scale + 0.5))
        nh = max(1, int(img.height * scale + 0.5))
        resample = getattr(Image, "Resampling", Image).LANCZOS
        resized = img.resize((nw, nh), resample)
        left = max(0, (nw - width) // 2)
        top = max(0, (nh - height) // 2)
        cropped = resized.crop((left, top, left + width, top + height))
        # Fixed wash: wallpaper clearly visible, never crushing UI contrast nearby
        wash = Image.new("RGB", (width, height), self._hex_to_rgb("#FFF7FA"))
        blended = Image.blend(wash, cropped, 0.82)
        return ImageTk.PhotoImage(blended)

    def _frost_panel_color(self) -> str:
        """Soft panel fill: mostly white mixed with wallpaper average for a translucent feel."""
        if self._bg_src is None:
            return "#FFF8FB"
        sample = self._bg_src.resize((32, 32))
        pixels = list(sample.getdata())
        n = max(len(pixels), 1)
        avg = tuple(sum(p[i] for p in pixels) // n for i in range(3))
        avg_hex = f"#{avg[0]:02X}{avg[1]:02X}{avg[2]:02X}"
        # ~72% white keeps text readable while panels pick up wallpaper tone
        return self._mix_hex(avg_hex, "#FFFFFF", 0.72)

    def _set_wallpaper_styles(self, enabled: bool):
        """Frost Soft panels when wallpaper is on so cards stay readable over the photo."""
        style = ttk.Style(self.root)
        t = self._theme
        self._wallpaper_active = enabled
        if enabled:
            frost = self._frost_panel_color()
            frost_dim = self._mix_hex(frost, t["TEXT_MAIN"], 0.45)
            style.configure("Soft.TFrame", background=frost)
            style.configure("Soft.TLabel", background=frost, foreground=t["TEXT_MAIN"])
            style.configure(
                "Soft.Dim.TLabel", background=frost, foreground=frost_dim
            )
            style.configure(
                "Soft.Section.TLabel",
                background=frost,
                foreground=t["ACCENT_DARK"],
                font=self._font(10, bold=True),
            )
            style.configure(
                "Title.TLabel",
                background=frost,
                foreground=t["ACCENT_DARK"],
                font=self._font(13, bold=True),
            )
            style.configure("TNotebook", background=frost, borderwidth=0)
            style.configure(
                "TNotebook.Tab",
                background=frost,
                foreground=t["TEXT_DIM"],
            )
            style.map(
                "TNotebook.Tab",
                background=[("selected", "#FFFFFF"), ("active", t["BTN_ACTIVE"])],
                foreground=[("selected", t["ACCENT"]), ("active", t["ACCENT_DARK"])],
            )
            style.configure(
                "Treeview",
                background="#FFFFFF",
                fieldbackground="#FFFFFF",
                foreground=t["TEXT_MAIN"],
            )
            style.configure(
                "Treeview.Heading",
                background=frost,
                foreground=t["ACCENT_DARK"],
            )
            if self._bg_canvas is not None and self._bg_canvas.winfo_exists():
                self._bg_canvas.configure(bg=t["BG_MAIN"])
            self._retint_tk_panel_widgets(frost)
        else:
            # Restore solid theme panels
            style.configure("Soft.TFrame", background=t["BG_PANEL"])
            style.configure(
                "Soft.TLabel", background=t["BG_PANEL"], foreground=t["TEXT_MAIN"]
            )
            style.configure(
                "Soft.Dim.TLabel",
                background=t["BG_PANEL"],
                foreground=t["TEXT_DIM"],
            )
            style.configure(
                "Soft.Section.TLabel",
                background=t["BG_PANEL"],
                foreground=t["ACCENT"],
                font=self._font(10, bold=True),
            )
            style.configure(
                "Title.TLabel",
                background=t["BG_PANEL"],
                foreground=t["ACCENT_DARK"],
                font=self._font(13, bold=True),
            )
            style.configure("TNotebook", background=t["BG_MAIN"], borderwidth=0)
            style.configure(
                "TNotebook.Tab",
                background=t["BG_PANEL"],
                foreground=t["TEXT_DIM"],
            )
            style.map(
                "TNotebook.Tab",
                background=[("selected", "#FFF8FB"), ("active", t["BTN_ACTIVE"])],
                foreground=[("selected", t["ACCENT"]), ("active", t["ACCENT_DARK"])],
            )
            style.configure(
                "Treeview",
                background=t["BG_ENTRY"],
                fieldbackground=t["BG_ENTRY"],
                foreground=t["TEXT_MAIN"],
            )
            style.configure(
                "Treeview.Heading",
                background="#FFF8FB",
                foreground=t["ACCENT_DARK"],
            )
            if self._bg_canvas is not None and self._bg_canvas.winfo_exists():
                self._bg_canvas.configure(bg=t["BG_MAIN"])
            self._retint_tk_panel_widgets(t["BG_PANEL"])

    def _retint_tk_panel_widgets(self, color: str):
        """Keep native tk Checkbutton/Text backgrounds in sync with Soft panel colors."""
        roots = [self._ui_player, self._ui_notebook]
        for root_w in roots:
            if root_w is None:
                continue
            stack = list(root_w.winfo_children())
            while stack:
                w = stack.pop()
                stack.extend(w.winfo_children())
                try:
                    cls = w.winfo_class()
                except tk.TclError:
                    continue
                if cls == "Checkbutton":
                    try:
                        w.configure(bg=color, activebackground=color)
                    except tk.TclError:
                        pass
                elif cls == "Text":
                    try:
                        w.configure(bg=color)
                    except tk.TclError:
                        pass
                elif cls == "Canvas":
                    try:
                        w.configure(bg=color, highlightthickness=0)
                    except tk.TclError:
                        pass

    def _on_canvas_configure(self, event=None):
        if event is not None and event.widget is not self._bg_canvas:
            return
        if self._bg_resize_job is not None:
            self.root.after_cancel(self._bg_resize_job)
        self._bg_resize_job = self.root.after(60, self._layout_canvas)

    def _layout_canvas(self):
        """Place floating UI windows over the wallpaper and (re)draw the image."""
        self._bg_resize_job = None
        canvas = self._bg_canvas
        if canvas is None or not canvas.winfo_exists():
            return
        width = max(canvas.winfo_width(), 2)
        height = max(canvas.winfo_height(), 2)
        if width < 40 or height < 40:
            return

        self._paint_wallpaper(width, height)

        pad = 12
        player = self._ui_player
        notebook = self._ui_notebook
        status = self._ui_status
        if player is None or notebook is None or status is None:
            return

        player.update_idletasks()
        status.update_idletasks()
        ph = max(player.winfo_reqheight(), 1)
        sh = max(status.winfo_reqheight(), 1)

        if self._canvas_player is not None:
            canvas.coords(self._canvas_player, pad, pad)
            canvas.itemconfigure(self._canvas_player, width=max(width - pad * 2, 40))

        if self._canvas_status is not None:
            canvas.coords(self._canvas_status, 0, height - sh)
            canvas.itemconfigure(self._canvas_status, width=width)

        nb_y = pad + ph + 8
        nb_h = max(height - nb_y - sh - 8, 80)
        if self._canvas_nb is not None:
            canvas.coords(self._canvas_nb, pad, nb_y)
            canvas.itemconfigure(
                self._canvas_nb, width=max(width - pad * 2, 40), height=nb_h
            )

        # Keep UI windows above the wallpaper image item
        canvas.tag_raise(self._canvas_player)
        canvas.tag_raise(self._canvas_nb)
        canvas.tag_raise(self._canvas_status)

    def _paint_wallpaper(self, width: int, height: int):
        canvas = self._bg_canvas
        if canvas is None or self._bg_image_id is None:
            return
        path = (self._settings.bg_image_path or "").strip()
        if not path:
            if self._wallpaper_active:
                self._set_wallpaper_styles(False)
            self._bg_photo = None
            self._bg_draw_key = None
            canvas.itemconfigure(self._bg_image_id, image="")
            canvas.configure(bg=self._t("BG_MAIN"))
            return

        if self._bg_src is None and not self._load_bg_source(path):
            self._settings.bg_image_path = ""
            if self._bg_path_var is not None:
                self._bg_path_var.set(_tr("appearance.none"))
            if self._wallpaper_active:
                self._set_wallpaper_styles(False)
            self._bg_photo = None
            self._bg_draw_key = None
            canvas.itemconfigure(self._bg_image_id, image="")
            return

        draw_key = (width, height, path)
        if draw_key == self._bg_draw_key and self._bg_photo is not None:
            return

        photo = self._compose_background_photo(width, height)
        if photo is None:
            return
        self._bg_photo = photo
        self._bg_draw_key = draw_key
        canvas.itemconfigure(self._bg_image_id, image=self._bg_photo)
        canvas.coords(self._bg_image_id, 0, 0)
        canvas.tag_lower(self._bg_image_id)
        if not self._wallpaper_active:
            self._set_wallpaper_styles(True)

    def _choose_background_image(self):
        path = filedialog.askopenfilename(
            title=_tr("appearance.dialog_title"),
            filetypes=[
                (
                    _tr("appearance.image_files"),
                    "*.png *.jpg *.jpeg *.webp *.bmp *.gif",
                ),
                (_tr("dialog.all_files"), "*.*"),
            ],
        )
        if not path:
            return
        if not self._load_bg_source(path):
            self._status_var.set(_trf("status.bg_failed", path=path))
            return
        self._settings.bg_image_path = path
        self._bg_draw_key = None
        if self._bg_path_var is not None:
            self._bg_path_var.set(os.path.basename(path))
        self._layout_canvas()
        self._status_var.set(_trf("status.bg_set", name=os.path.basename(path)))

    def _clear_background_image(self):
        self._settings.bg_image_path = ""
        self._bg_src = None
        self._bg_photo = None
        self._bg_draw_key = None
        if self._bg_path_var is not None:
            self._bg_path_var.set(_tr("appearance.none"))
        if self._bg_canvas is not None and self._bg_image_id is not None:
            self._bg_canvas.itemconfigure(self._bg_image_id, image="")
        self._set_wallpaper_styles(False)
        self._layout_canvas()
        self._status_var.set(_tr("status.bg_cleared"))

    def _build_ui(self):
        root = self.root
        t = self._theme
        root.configure(bg=t["BG_MAIN"])
        self._bg_draw_key = None
        self._wallpaper_active = False

        # Wallpaper canvas under floating UI windows (no Label parenting = no hover ghost bug)
        self._bg_canvas = tk.Canvas(
            root, highlightthickness=0, bd=0, bg=t["BG_MAIN"]
        )
        self._bg_canvas.pack(fill=tk.BOTH, expand=True)
        self._bg_image_id = self._bg_canvas.create_image(
            0, 0, anchor="nw", tags=("wallpaper",)
        )
        host = self._bg_canvas

        if self._settings.bg_image_path:
            self._load_bg_source(self._settings.bg_image_path)

        # ===================== Player card =====================
        player = ttk.Frame(host, padding=(16, 12, 16, 12), style="Soft.TFrame")
        self._ui_player = player

        top_row = ttk.Frame(player, style="Soft.TFrame")
        top_row.pack(fill=tk.X)

        ttk.Button(
            top_row,
            text=_tr("btn.load_midi"),
            command=self._load_file,
            style="Accent.TButton",
        ).pack(side=tk.LEFT, padx=(0, 10))

        self._file_label = ttk.Label(
            top_row,
            text=_tr("label.no_file"),
            style="Soft.Dim.TLabel",
            font=self._font(9),
        )
        self._file_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._lang_btn = self._make_chip(
            top_row,
            _tr("btn.lang"),
            bg=t["ACCENT"],
            command=self._toggle_language,
            padx=(8, 0),
        )
        self._lang_btn.bind("<Leave>", lambda e: self._lang_btn.config(bg=t["ACCENT"]))

        self._on_top_var = tk.BooleanVar(value=self._settings.always_on_top)
        on_top_text = (
            _tr("btn.always_on_top_off")
            if self._settings.always_on_top
            else _tr("btn.always_on_top")
        )
        on_top_bg = t["SUCCESS"] if self._settings.always_on_top else t["TEXT_DIM"]
        self._on_top_btn = self._make_chip(
            top_row,
            on_top_text,
            bg=on_top_bg,
            command=self._toggle_always_on_top,
            padx=(6, 0),
        )
        self._on_top_btn.bind(
            "<Leave>",
            lambda e: self._on_top_btn.config(
                bg=t["SUCCESS"] if self._on_top_var.get() else t["TEXT_DIM"]
            ),
        )
        if self._settings.always_on_top:
            self.root.attributes("-topmost", True)

        self._title_label = ttk.Label(player, text="", style="Title.TLabel")
        self._title_label.pack(anchor=tk.W, pady=(10, 2))

        self._note_count_var = tk.StringVar(value=_tr("note_count.default"))
        ttk.Label(
            player,
            textvariable=self._note_count_var,
            style="Soft.Dim.TLabel",
            font=self._font(9),
        ).pack(anchor=tk.W)

        # Transport + parameters on one readable row
        ctrl_frame = ttk.Frame(player, style="Soft.TFrame", padding=(0, 10, 0, 4))
        ctrl_frame.pack(fill=tk.X)

        transport = ttk.Frame(ctrl_frame, style="Soft.TFrame")
        transport.pack(side=tk.LEFT)

        self._play_btn = ttk.Button(
            transport,
            text=_tr("btn.play"),
            command=self._play,
            width=9,
            style="Accent.TButton",
        )
        self._play_btn.pack(side=tk.LEFT, padx=(0, 4))

        self._pause_btn = ttk.Button(
            transport,
            text=_tr("btn.pause"),
            command=self._pause,
            width=9,
            state=tk.DISABLED,
        )
        self._pause_btn.pack(side=tk.LEFT, padx=3)

        self._stop_btn = ttk.Button(
            transport,
            text=_tr("btn.stop"),
            command=self._stop,
            width=9,
            state=tk.DISABLED,
        )
        self._stop_btn.pack(side=tk.LEFT, padx=3)

        params = ttk.Frame(ctrl_frame, style="Soft.TFrame")
        params.pack(side=tk.LEFT, padx=(16, 0))

        ttk.Label(params, text=_tr("label.speed"), style="Soft.TLabel").pack(
            side=tk.LEFT
        )
        self._speed_var = tk.DoubleVar(value=self._settings.speed)
        self._speed_spinbox = ttk.Spinbox(
            params,
            from_=0.1,
            to=4.0,
            increment=0.1,
            textvariable=self._speed_var,
            width=5,
            command=self._on_speed_change,
        )
        self._speed_spinbox.pack(side=tk.LEFT, padx=4)
        self._speed_spinbox.bind("<Key-Return>", self._on_speed_change_event)
        self._speed_spinbox.bind("<FocusOut>", self._on_speed_change_event)
        ttk.Label(params, text=_tr("label.speed_x"), style="Soft.TLabel").pack(
            side=tk.LEFT
        )

        ttk.Label(params, text=_tr("playback.transpose"), style="Soft.TLabel").pack(
            side=tk.LEFT, padx=(14, 0)
        )
        self._playback_transpose_var = tk.IntVar(
            value=self._settings.playback_transpose
        )
        self._playback_transpose_spinbox = ttk.Spinbox(
            params,
            from_=-12,
            to=12,
            increment=1,
            textvariable=self._playback_transpose_var,
            width=5,
            command=self._on_playback_transpose_change,
        )
        self._playback_transpose_spinbox.pack(side=tk.LEFT, padx=4)
        self._playback_transpose_spinbox.bind(
            "<Key-Return>", self._on_playback_transpose_event
        )
        self._playback_transpose_spinbox.bind(
            "<FocusOut>", self._on_playback_transpose_event
        )
        ttk.Label(params, text=_tr("label.semitones"), style="Soft.TLabel").pack(
            side=tk.LEFT
        )

        ttk.Button(
            params,
            text=_tr("btn.reset"),
            command=self._reset_speed_transpose,
            width=6,
        ).pack(side=tk.LEFT, padx=(12, 0))

        prog_frame = ttk.Frame(player, style="Soft.TFrame", padding=(0, 6, 0, 0))
        prog_frame.pack(fill=tk.X)

        self._time_label = ttk.Label(
            prog_frame,
            text=_tr("label.time_default"),
            width=16,
            style="Soft.Dim.TLabel",
            font=self._font(9),
        )
        self._time_label.pack(side=tk.RIGHT)

        self._progress_bar = ttk.Progressbar(prog_frame, mode="determinate")
        self._progress_bar.pack(fill=tk.X, expand=True, padx=(0, 10))
        self._progress_bar.bind("<Button-1>", self._on_progress_click)
        self._progress_bar.bind("<B1-Motion>", self._on_progress_drag)
        self._progress_bar.bind("<ButtonRelease-1>", self._on_progress_release)

        # ===================== Tabs =====================
        nb = ttk.Notebook(host)
        self._ui_notebook = nb

        # -- Library tab --
        lib_frame = ttk.Frame(nb, padding=10, style="Soft.TFrame")
        nb.add(lib_frame, text=_tr("tab.library"))

        lib_toolbar = ttk.Frame(lib_frame, style="Soft.TFrame")
        lib_toolbar.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(
            lib_toolbar,
            text=_tr("library.add_files"),
            command=self._library_add_files,
            style="Accent.TButton",
        ).pack(side=tk.LEFT, padx=(0, 4))

        ttk.Button(
            lib_toolbar,
            text=_tr("library.add_folder"),
            command=self._library_add_folder,
            style="Accent.TButton",
        ).pack(side=tk.LEFT, padx=4)

        ttk.Button(
            lib_toolbar,
            text=_tr("library.remove"),
            command=self._library_remove,
            style="Danger.TButton",
        ).pack(side=tk.LEFT, padx=4)

        lib_body = ttk.Frame(lib_frame, style="Soft.TFrame")
        lib_body.pack(fill=tk.BOTH, expand=True)

        columns = ("title", "duration", "bpm", "notes")
        self._lib_tree = ttk.Treeview(
            lib_body,
            columns=columns,
            show="headings",
            selectmode="extended",
            height=10,
        )
        self._lib_tree.heading("title", text=_tr("library.column.title"))
        self._lib_tree.heading("duration", text=_tr("library.column.duration"))
        self._lib_tree.heading("bpm", text=_tr("library.column.bpm"))
        self._lib_tree.heading("notes", text=_tr("library.column.notes"))
        self._lib_tree.column("title", width=260, minwidth=120)
        self._lib_tree.column("duration", width=80, minwidth=60, anchor=tk.CENTER)
        self._lib_tree.column("bpm", width=60, minwidth=50, anchor=tk.CENTER)
        self._lib_tree.column("notes", width=80, minwidth=60, anchor=tk.CENTER)

        self._lib_scrollbar = ttk.Scrollbar(
            lib_body, orient=tk.VERTICAL, command=self._lib_tree.yview
        )
        self._lib_tree.configure(yscrollcommand=self._lib_scrollbar.set)
        self._lib_body = lib_body

        self._lib_tree.bind("<Double-1>", self._library_play_selected)

        self._lib_context = tk.Menu(
            self.root,
            tearoff=0,
            bg=t["BG_PANEL"],
            fg=t["TEXT_MAIN"],
            activebackground=t["BTN_ACTIVE"],
            activeforeground=t["ACCENT_DARK"],
            bd=0,
            relief=tk.FLAT,
        )
        self._lib_context.add_command(
            label=_tr("library.play"), command=self._library_play_selected
        )
        self._lib_context.add_command(
            label=_tr("library.remove_selected"), command=self._library_remove
        )
        self._lib_tree.bind("<Button-3>", self._library_context_menu)

        self._lib_placeholder = ttk.Label(
            lib_body,
            text=_tr("library.empty"),
            style="Soft.Dim.TLabel",
            anchor=tk.CENTER,
            justify=tk.CENTER,
            font=self._font(10),
        )

        self._library_refresh_tree()

        if _HAS_DND:
            self._lib_tree.drop_target_register(DND_FILES)
            self._lib_tree.dnd_bind("<<Drop>>", self._on_library_drop)
            lib_frame.drop_target_register(DND_FILES)
            lib_frame.dnd_bind("<<Drop>>", self._on_library_drop)
            self._lib_placeholder.drop_target_register(DND_FILES)
            self._lib_placeholder.dnd_bind("<<Drop>>", self._on_library_drop)

        # -- Output tab (scrollable) --
        out_outer = ttk.Frame(nb, padding=0, style="Soft.TFrame")
        nb.add(out_outer, text=_tr("tab.output"))

        out_canvas = tk.Canvas(
            out_outer, highlightthickness=0, borderwidth=0, bg=t["BG_PANEL"]
        )
        out_scrollbar = ttk.Scrollbar(
            out_outer, orient=tk.VERTICAL, command=out_canvas.yview
        )
        out_canvas.configure(yscrollcommand=out_scrollbar.set)
        out_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        out_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        out_frame = ttk.Frame(out_canvas, padding=14, style="Soft.TFrame")
        out_canvas.create_window(
            (0, 0), window=out_frame, anchor="nw", tags="out_frame"
        )
        out_frame.bind(
            "<Configure>",
            lambda e: out_canvas.configure(scrollregion=out_canvas.bbox("all")),
        )
        out_canvas.bind(
            "<Configure>", lambda e: out_canvas.itemconfig("out_frame", width=e.width)
        )

        def _on_out_mousewheel(event):
            out_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        out_canvas.bind(
            "<Enter>",
            lambda e: out_canvas.bind_all("<MouseWheel>", _on_out_mousewheel),
        )
        out_canvas.bind(
            "<Leave>", lambda e: out_canvas.unbind_all("<MouseWheel>")
        )

        out_frame.grid_columnconfigure(0, weight=1)

        self._local_audio_var = tk.BooleanVar(value=self._settings.local_audio_enabled)
        self._virtual_var = tk.BooleanVar(value=self._settings.virtual_midi_enabled)
        self._osc_var = tk.BooleanVar(value=self._settings.osc_output_enabled)
        self._volume_var = tk.DoubleVar(value=self._settings.volume)

        def _make_section_cb(parent, row, text, var, cmd, desc_text=None):
            section_row = ttk.Frame(parent, style="Soft.TFrame")
            section_row.grid(row=row, column=0, sticky=tk.W, pady=(10, 0))
            cb = tk.Checkbutton(
                section_row,
                text="",
                variable=var,
                command=cmd,
                indicatoron=False,
                image=self._cb_unchecked_img,
                selectimage=self._cb_checked_img,
                bg=t["BG_PANEL"],
                activebackground=t["BG_PANEL"],
                relief=tk.FLAT,
                bd=0,
                padx=4,
                pady=2,
            )
            cb.pack(side=tk.LEFT)
            ttk.Label(section_row, text=text, style="Soft.Section.TLabel").pack(
                side=tk.LEFT, padx=(4, 0)
            )
            if desc_text:
                ttk.Label(
                    parent,
                    text=desc_text,
                    style="Soft.Dim.TLabel",
                    font=self._font(9),
                ).grid(row=row + 1, column=0, sticky=tk.W, padx=28)
            return cb

        self._synth_port_var = tk.StringVar(value=self._local_synth.get_port_name())
        _make_section_cb(
            out_frame,
            0,
            _tr("output.local_audio"),
            self._local_audio_var,
            self._toggle_local,
        )
        ttk.Label(
            out_frame,
            textvariable=self._synth_port_var,
            style="Soft.Dim.TLabel",
            font=self._font(9),
        ).grid(row=1, column=0, sticky=tk.W, padx=28)

        ttk.Separator(out_frame, orient=tk.HORIZONTAL).grid(
            row=2, column=0, sticky=tk.EW, pady=8
        )
        _make_section_cb(
            out_frame,
            3,
            _tr("output.virtual_midi"),
            self._virtual_var,
            self._toggle_virtual,
        )
        vm_frame = ttk.Frame(out_frame, style="Soft.TFrame")
        vm_frame.grid(row=4, column=0, sticky=tk.W, padx=28)
        ttk.Label(
            vm_frame, text=_tr("output.port"), style="Soft.TLabel", font=self._font(9)
        ).pack(side=tk.LEFT)
        self._virtual_port_var = tk.StringVar(value=self._settings.virtual_midi_port)
        self._virtual_port_combo = ttk.Combobox(
            vm_frame,
            textvariable=self._virtual_port_var,
            width=24,
            state="readonly",
        )
        self._virtual_port_combo.pack(side=tk.LEFT, padx=4)
        ttk.Button(
            vm_frame,
            text=_tr("output.refresh"),
            command=self._refresh_virtual_ports,
            width=8,
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            vm_frame,
            text=_tr("output.apply"),
            command=self._apply_virtual_port,
            width=6,
        ).pack(side=tk.LEFT)

        ttk.Separator(out_frame, orient=tk.HORIZONTAL).grid(
            row=5, column=0, sticky=tk.EW, pady=8
        )
        _make_section_cb(
            out_frame, 6, _tr("output.osc"), self._osc_var, self._toggle_osc
        )
        osc_frame = ttk.Frame(out_frame, style="Soft.TFrame")
        osc_frame.grid(row=7, column=0, sticky=tk.W, padx=28)
        ttk.Label(
            osc_frame,
            text=_tr("output.address"),
            style="Soft.TLabel",
            font=self._font(9),
        ).pack(side=tk.LEFT)
        self._osc_addr_var = tk.StringVar(
            value=f"{self._settings.osc_address_ip}:{self._settings.osc_address_port}"
        )
        ttk.Entry(osc_frame, textvariable=self._osc_addr_var, width=20).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(
            osc_frame,
            text=_tr("output.apply_osc"),
            command=self._apply_osc_addr,
            width=6,
        ).pack(side=tk.LEFT)
        mode_frame = ttk.Frame(out_frame, style="Soft.TFrame")
        mode_frame.grid(row=8, column=0, sticky=tk.W, padx=28, pady=4)
        ttk.Label(
            mode_frame, text=_tr("output.mode"), style="Soft.TLabel", font=self._font(9)
        ).pack(side=tk.LEFT)
        self._osc_mode_var = tk.StringVar(value=self._settings.osc_mode)
        ttk.Radiobutton(
            mode_frame,
            text=_tr("output.osc_mode_piano"),
            variable=self._osc_mode_var,
            value="piano",
            command=self._apply_osc_mode,
        ).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(
            mode_frame,
            text=_tr("output.osc_mode_avatar"),
            variable=self._osc_mode_var,
            value="avatar",
            command=self._apply_osc_mode,
        ).pack(side=tk.LEFT, padx=2)

        ttk.Separator(out_frame, orient=tk.HORIZONTAL).grid(
            row=9, column=0, sticky=tk.EW, pady=8
        )
        vol_frame = ttk.Frame(out_frame, style="Soft.TFrame")
        vol_frame.grid(row=10, column=0, sticky=tk.W, pady=2)
        ttk.Label(vol_frame, text=_tr("output.volume"), style="Soft.TLabel").pack(
            side=tk.LEFT
        )
        self._volume_scale = ttk.Scale(
            vol_frame,
            from_=0,
            to=1,
            variable=self._volume_var,
            orient=tk.HORIZONTAL,
            length=150,
            command=self._on_volume_change,
        )
        self._volume_scale.pack(side=tk.LEFT, padx=6)
        self._volume_scale.bind("<Button-1>", self._on_volume_trough_click)
        self._volume_scale.bind("<B1-Motion>", self._on_volume_drag)
        self._volume_label_var = tk.StringVar(
            value=f"{int(self._settings.volume * 100)}%"
        )
        ttk.Label(
            vol_frame,
            textvariable=self._volume_label_var,
            width=5,
            style="Soft.TLabel",
        ).pack(side=tk.LEFT)
        ttk.Label(vol_frame, text="  ", style="Soft.TLabel").pack(side=tk.LEFT)
        self._volume_spin_var = tk.StringVar(
            value=f"{int(self._settings.volume * 100)}"
        )
        self._volume_spinbox = ttk.Spinbox(
            vol_frame,
            from_=0,
            to=100,
            increment=1,
            textvariable=self._volume_spin_var,
            width=5,
            command=self._on_volume_spin_change,
        )
        self._volume_spinbox.pack(side=tk.LEFT)
        self._volume_spinbox.bind("<Key-Return>", self._on_volume_spin_event)
        self._volume_spinbox.bind("<FocusOut>", self._on_volume_spin_event)
        ttk.Label(vol_frame, text="%", style="Soft.TLabel").pack(side=tk.LEFT)

        ttk.Separator(out_frame, orient=tk.HORIZONTAL).grid(
            row=11, column=0, sticky=tk.EW, pady=8
        )
        self._midi_input_var = tk.BooleanVar(value=self._settings.midi_input_enabled)
        _make_section_cb(
            out_frame,
            12,
            _tr("midi.input"),
            self._midi_input_var,
            self._toggle_midi_input,
        )
        midi_input_port_frame = ttk.Frame(out_frame, style="Soft.TFrame")
        midi_input_port_frame.grid(row=13, column=0, sticky=tk.W, padx=28, pady=2)
        ttk.Label(
            midi_input_port_frame,
            text=_tr("midi.input_port"),
            style="Soft.TLabel",
        ).pack(side=tk.LEFT)
        self._midi_input_port_var = tk.StringVar(value=self._settings.midi_input_port)
        self._midi_input_combo = ttk.Combobox(
            midi_input_port_frame,
            textvariable=self._midi_input_port_var,
            width=28,
            state="readonly",
        )
        self._midi_input_combo.pack(side=tk.LEFT, padx=4)
        ttk.Button(
            midi_input_port_frame,
            text=_tr("midi.refresh"),
            command=self._refresh_midi_input_ports,
        ).pack(side=tk.LEFT, padx=2)
        self.root.after_idle(self._refresh_midi_input_ports)
        midi_input_transpose_frame = ttk.Frame(out_frame, style="Soft.TFrame")
        midi_input_transpose_frame.grid(row=14, column=0, sticky=tk.W, padx=28, pady=2)
        ttk.Label(
            midi_input_transpose_frame,
            text=_tr("midi.input_transpose"),
            style="Soft.TLabel",
        ).pack(side=tk.LEFT)
        self._midi_input_transpose_var = tk.IntVar(
            value=self._settings.midi_input_transpose
        )
        self._midi_input_transpose_spinbox = ttk.Spinbox(
            midi_input_transpose_frame,
            from_=-12,
            to=12,
            increment=1,
            textvariable=self._midi_input_transpose_var,
            width=5,
            command=self._on_midi_input_transpose_change,
        )
        self._midi_input_transpose_spinbox.pack(side=tk.LEFT, padx=4)
        self._midi_input_transpose_spinbox.bind(
            "<Key-Return>", self._on_midi_input_transpose_event
        )
        self._midi_input_transpose_spinbox.bind(
            "<FocusOut>", self._on_midi_input_transpose_event
        )
        ttk.Label(
            midi_input_transpose_frame,
            text=_tr("label.semitones"),
            style="Soft.TLabel",
        ).pack(side=tk.LEFT)

        ttk.Separator(out_frame, orient=tk.HORIZONTAL).grid(
            row=15, column=0, sticky=tk.EW, pady=8
        )
        passthrough_frame = ttk.Frame(out_frame, style="Soft.TFrame")
        passthrough_frame.grid(row=16, column=0, sticky=tk.W, pady=2)
        self._passthrough_cb = tk.Checkbutton(
            passthrough_frame,
            text="",
            variable=self._passthrough_var,
            command=self._toggle_passthrough,
            indicatoron=False,
            image=self._cb_unchecked_img,
            selectimage=self._cb_checked_img,
            bg=t["BG_PANEL"],
            activebackground=t["BG_PANEL"],
            relief=tk.FLAT,
            bd=0,
            padx=4,
            pady=2,
        )
        self._passthrough_cb.pack(side=tk.LEFT)
        ttk.Label(
            passthrough_frame,
            text=_tr("midi.passthrough"),
            style="Soft.Section.TLabel",
        ).pack(side=tk.LEFT, padx=(4, 0))
        self._passthrough_status_var = tk.StringVar(value="")
        ttk.Label(
            passthrough_frame,
            textvariable=self._passthrough_status_var,
            style="Soft.Dim.TLabel",
            font=self._font(9),
        ).pack(side=tk.LEFT, padx=8)

        # ===================== Track Filter tab =====================
        track_frame = ttk.Frame(nb, padding=10, style="Soft.TFrame")
        nb.add(track_frame, text=_tr("tab.track_filter"))

        track_canvas = tk.Canvas(
            track_frame, highlightthickness=0, borderwidth=0, bg=t["BG_PANEL"]
        )
        track_scrollbar = ttk.Scrollbar(
            track_frame, orient=tk.VERTICAL, command=track_canvas.yview
        )
        track_canvas.configure(yscrollcommand=track_scrollbar.set)
        track_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        track_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        track_inner = ttk.Frame(track_canvas, padding=4, style="Soft.TFrame")
        track_inner.bind(
            "<Configure>",
            lambda e: track_canvas.configure(scrollregion=track_canvas.bbox("all")),
        )
        track_canvas.create_window(
            (0, 0), window=track_inner, anchor="nw", tags="track_inner"
        )

        def _on_track_mousewheel(event):
            track_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        track_canvas.bind(
            "<Enter>",
            lambda e: track_canvas.bind_all("<MouseWheel>", _on_track_mousewheel),
        )
        track_canvas.bind("<Leave>", lambda e: track_canvas.unbind_all("<MouseWheel>"))

        self._track_inner = track_inner
        self._track_rows: list[dict] = []
        self._track_header: Optional[ttk.Frame] = None
        self._track_separator: Optional[ttk.Separator] = None

        self._track_placeholder = ttk.Label(
            track_inner,
            text=_tr("track.no_tracks"),
            style="Soft.Dim.TLabel",
            anchor=tk.CENTER,
            justify=tk.CENTER,
            font=self._font(10),
        )

        # -- Info tab --
        info_tab = ttk.Frame(nb, padding=12, style="Soft.TFrame")
        nb.add(info_tab, text=_tr("tab.how_to_use"))

        self._help_text = tk.Text(
            info_tab,
            wrap=tk.WORD,
            font=self._font(10),
            bg=t["BG_PANEL"],
            fg=t["TEXT_MAIN"],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=4,
            selectbackground=t["BTN_ACTIVE"],
            selectforeground=t["TEXT_MAIN"],
            insertbackground=t["ACCENT"],
            spacing1=2,
            spacing3=4,
        )
        self._help_text.insert(tk.END, _tr("help.content"))
        self._help_text.config(state=tk.DISABLED)
        self._help_text.pack(fill=tk.BOTH, expand=True)

        # -- Appearance tab (after How to Use) --
        appear_tab = ttk.Frame(nb, padding=16, style="Soft.TFrame")
        nb.add(appear_tab, text=_tr("tab.appearance"))

        ttk.Label(
            appear_tab,
            text=_tr("appearance.section"),
            style="Soft.Section.TLabel",
        ).pack(anchor=tk.W)
        ttk.Label(
            appear_tab,
            text=_tr("appearance.hint"),
            style="Soft.Dim.TLabel",
            font=self._font(9),
            wraplength=560,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(6, 14))

        bg_btn_row = ttk.Frame(appear_tab, style="Soft.TFrame")
        bg_btn_row.pack(anchor=tk.W)
        ttk.Button(
            bg_btn_row,
            text=_tr("appearance.choose"),
            command=self._choose_background_image,
            style="Accent.TButton",
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            bg_btn_row,
            text=_tr("appearance.clear"),
            command=self._clear_background_image,
        ).pack(side=tk.LEFT)

        bg_name = (
            os.path.basename(self._settings.bg_image_path)
            if self._settings.bg_image_path
            else _tr("appearance.none")
        )
        self._bg_path_var = tk.StringVar(value=bg_name)
        ttk.Label(
            appear_tab,
            textvariable=self._bg_path_var,
            style="Soft.Dim.TLabel",
            font=self._font(9),
        ).pack(anchor=tk.W, pady=(12, 0))

        # ===================== Status bar =====================
        status_wrap = tk.Frame(host, bg=t["BG_STATUS"], bd=0, highlightthickness=0)
        self._ui_status = status_wrap

        self._status_var = tk.StringVar(value=_tr("status.ready"))
        tk.Label(
            status_wrap,
            textvariable=self._status_var,
            anchor=tk.W,
            relief=tk.FLAT,
            bg=t["BG_STATUS"],
            fg=t["TEXT_DIM"],
            padx=16,
            pady=7,
            font=self._font(9),
        ).pack(fill=tk.X)

        # Floating windows over wallpaper (gaps reveal the custom background)
        self._canvas_player = host.create_window(
            12, 12, window=player, anchor="nw", tags=("ui",)
        )
        self._canvas_nb = host.create_window(
            12, 120, window=nb, anchor="nw", tags=("ui",)
        )
        self._canvas_status = host.create_window(
            0, 0, window=status_wrap, anchor="nw", tags=("ui",)
        )
        host.bind("<Configure>", self._on_canvas_configure)
        self.root.after_idle(self._layout_canvas)
        if self._settings.bg_image_path:
            self.root.after_idle(lambda: self._set_wallpaper_styles(True))

    # ===================== Event handlers =====================

    def _apply_loaded_midi(self, data: MidiData, path: str):
        """Apply parsed MIDI data to engine and update UI (no status message)."""
        self._data = data
        self._loaded_midi_path = path
        self._engine.load(data)

        filename = os.path.basename(path)
        self._file_label.config(text=filename)
        self._title_label.config(text=data.title)

        dur = data.total_duration
        dur_str = self._fmt_time(dur)
        self._note_count_var.set(
            _trf(
                "note_count.format",
                count=len(data.notes),
                tracks=len(data.track_names),
                dur=dur_str,
                bpm=f"{data.bpm:.0f}",
            )
        )

        self._progress_bar["maximum"] = data.total_duration
        self._progress_bar["value"] = 0
        self._time_label.config(text=f"0:00 / {dur_str}")
        self._play_btn.config(state=tk.NORMAL)

        # Refresh track filter
        self._refresh_track_list()

    def _load_file(self):
        path = filedialog.askopenfilename(
            title=_tr("dialog.select_midi"),
            filetypes=[
                (_tr("dialog.midi_files"), "*.mid *.midi"),
                (_tr("dialog.all_files"), "*.*"),
            ],
        )
        if not path:
            return

        data = parse_midi(path)
        if data is None:
            self._status_var.set(_trf("status.load_failed", path=path))
            return

        self._apply_loaded_midi(data, path)
        self._status_var.set(
            _trf(
                "status.loaded", filename=os.path.basename(path), count=len(data.notes)
            )
        )

    def _play(self):
        if self._data is None:
            return
        self._engine.play()
        self._play_btn.config(state=tk.DISABLED)
        self._pause_btn.config(text=_tr("btn.pause_text"), state=tk.NORMAL)
        self._stop_btn.config(state=tk.NORMAL)
        self._status_var.set(_tr("status.playing"))

    def _pause(self):
        if self._engine.is_paused:
            self._engine.resume()
            self._pause_btn.config(text=_tr("btn.pause_text"))
            self._status_var.set(_tr("status.playing"))
        elif self._engine.is_playing:
            self._engine.pause()
            self._pause_btn.config(text=_tr("btn.resume_text"))
            self._status_var.set(_tr("status.paused"))

    def _stop(self):
        # Send all notes off
        self._local_synth.all_notes_off()
        self._virtual_midi.all_notes_off()
        self._osc.all_notes_off()

        self._engine.stop()
        self._play_btn.config(state=tk.NORMAL)
        self._pause_btn.config(text=_tr("btn.pause_text"), state=tk.DISABLED)
        self._stop_btn.config(state=tk.DISABLED)
        self._progress_bar["value"] = 0
        if self._data:
            dur = self._data.total_duration
            tot_str = self._fmt_time(dur)
            self._time_label.config(text=f"0:00 / {tot_str}")
        self._status_var.set(_tr("status.stopped"))

    # ===================== Track Filter =====================

    def _refresh_track_list(self):
        """Rebuild the track filter rows in the Track Filter tab."""
        t = self._theme
        # Destroy old header and separator (they accumulate on each rebuild)
        if self._track_header is not None:
            self._track_header.destroy()
            self._track_header = None
        if self._track_separator is not None:
            self._track_separator.destroy()
            self._track_separator = None

        # Clear existing rows
        for row in self._track_rows:
            row["frame"].destroy()
        self._track_rows.clear()
        self._track_placeholder.pack_forget()

        if self._data is None or not self._data.track_names:
            self._track_placeholder.pack(fill=tk.BOTH, expand=True, pady=20)
            return

        # Header row
        hdr = ttk.Frame(self._track_inner, style="Soft.TFrame")
        hdr.pack(fill=tk.X, pady=(0, 4))
        self._track_header = hdr
        for text, width, anchor in (
            ("#", 3, tk.W),
            (_tr("track.column_name"), 20, tk.W),
            (_tr("track.column_notes"), 10, tk.W),
            (_tr("track.mute"), 4, tk.CENTER),
            (_tr("track.solo"), 4, tk.CENTER),
        ):
            tk.Label(
                hdr,
                text=text,
                font=self._font(9, bold=True),
                width=width,
                anchor=anchor,
                bg=t["BG_PANEL"],
                fg=t["ACCENT_DARK"],
            ).pack(side=tk.LEFT, padx=4)
        sep = ttk.Separator(self._track_inner, orient=tk.HORIZONTAL)
        sep.pack(fill=tk.X, pady=4)
        self._track_separator = sep

        muted = set(self._engine.muted_tracks)
        soloed = set(self._engine.solo_tracks)
        any_solo = bool(soloed)

        for idx, name in enumerate(self._data.track_names):
            row_frame = ttk.Frame(self._track_inner, style="Soft.TFrame")
            row_frame.pack(fill=tk.X, pady=2)

            tk.Label(
                row_frame,
                text=str(idx + 1),
                width=3,
                anchor=tk.W,
                bg=t["BG_PANEL"],
                fg=t["TEXT_DIM"],
                font=self._font(9),
            ).pack(side=tk.LEFT, padx=4)
            tk.Label(
                row_frame,
                text=name or f"Track {idx + 1}",
                width=20,
                anchor=tk.W,
                font=self._font(9),
                bg=t["BG_PANEL"],
                fg=t["TEXT_MAIN"],
            ).pack(side=tk.LEFT, padx=4)
            note_count = sum(1 for n in self._data.notes if n.track == idx)
            tk.Label(
                row_frame,
                text=str(note_count),
                width=10,
                anchor=tk.W,
                fg=t["TEXT_DIM"],
                bg=t["BG_PANEL"],
                font=self._font(9),
            ).pack(side=tk.LEFT, padx=4)

            is_muted = idx in muted
            mute_btn = tk.Button(
                row_frame,
                text="M",
                width=3,
                font=self._font(8, bold=True),
                relief=tk.FLAT,
                bg=t["MUTE_ACTIVE"] if is_muted else t["BTN_NEUTRAL"],
                fg=t["TEXT_MAIN"],
                activebackground=t["MUTE_ACTIVE"],
                bd=0,
                padx=6,
                pady=2,
                cursor="hand2",
                command=lambda i=idx: self._toggle_track_mute(i),
            )
            mute_btn.pack(side=tk.LEFT, padx=4)

            is_soloed = idx in soloed
            solo_btn = tk.Button(
                row_frame,
                text="S",
                width=3,
                font=self._font(8, bold=True),
                relief=tk.FLAT,
                bg=t["SOLO_ACTIVE"] if is_soloed else t["BTN_NEUTRAL"],
                fg=t["TEXT_MAIN"],
                activebackground=t["SOLO_ACTIVE"],
                bd=0,
                padx=6,
                pady=2,
                cursor="hand2",
                command=lambda i=idx: self._toggle_track_solo(i),
            )
            solo_btn.pack(side=tk.LEFT, padx=4)

            self._track_rows.append(
                {
                    "frame": row_frame,
                    "mute_btn": mute_btn,
                    "solo_btn": solo_btn,
                    "idx": idx,
                }
            )

        # Show solo indicator if any track is soloed
        if any_solo:
            # Destroy previous solo note if it exists (to avoid accumulation)
            if hasattr(self, "_track_solo_note"):
                self._track_solo_note.destroy()
            solo_note = ttk.Label(
                self._track_inner,
                text=_tr("track.solo_active"),
                style="Soft.Dim.TLabel",
                foreground=t["SUCCESS"],
                font=self._font(9),
            )
            solo_note.pack(anchor=tk.W, pady=(4, 0))
            self._track_solo_note = solo_note
        else:
            if hasattr(self, "_track_solo_note"):
                self._track_solo_note.destroy()
                del self._track_solo_note

    def _toggle_track_mute(self, track_idx: int):
        """Toggle mute state for a track.

        Muting a track automatically removes it from solo.
        """
        muted = set(self._engine.muted_tracks)
        if track_idx in muted:
            muted.discard(track_idx)
        else:
            muted.add(track_idx)
            # Muting → also unsolo
            soloed = set(self._engine.solo_tracks)
            soloed.discard(track_idx)
            self._engine.solo_tracks = soloed
        self._engine.muted_tracks = muted
        self._refresh_track_list()

    def _toggle_track_solo(self, track_idx: int):
        """Toggle solo state for a track.

        Soloing a track automatically removes it from mute.
        """
        soloed = set(self._engine.solo_tracks)
        if track_idx in soloed:
            soloed.discard(track_idx)
        else:
            soloed.add(track_idx)
            # Soloing → also unmute
            muted = set(self._engine.muted_tracks)
            muted.discard(track_idx)
            self._engine.muted_tracks = muted
        self._engine.solo_tracks = soloed
        self._refresh_track_list()

    def _on_speed_change(self):
        try:
            speed = float(self._speed_var.get())
            self._engine.set_speed(speed)
            self._status_var.set(_trf("status.speed", speed=speed))
        except (ValueError, tk.TclError):
            pass

    def _reset_speed_transpose(self):
        """Reset speed to 1.0x and playback transpose to 0."""
        self._speed_var.set(1.0)
        self._engine.set_speed(1.0)
        self._playback_transpose_var.set(0)
        self._settings.playback_transpose = 0
        self._status_var.set(_tr("status.reset"))

    # ===================== Progress seeking =====================

    def _seek_to_ratio(self, ratio: float):
        """Seek playback to a fractional position 0..1."""
        if self._data is None:
            return
        total = self._engine.total_duration
        target = max(0.0, min(total, ratio * total))
        was_playing = self._engine.is_playing and not self._engine.is_paused
        self._engine.seek(target)
        self._progress_bar["value"] = target
        cur_str = self._fmt_time(target)
        tot_str = self._fmt_time(total)
        self._time_label.config(text=f"{cur_str} / {tot_str}")
        if not was_playing:
            self._engine.pause()  # keep paused if user was dragging while stopped/paused

    def _update_progress_preview(self, event) -> float | None:
        """Update progress bar visual from click/drag event. Returns ratio or None."""
        if self._data is None:
            return None
        w = event.widget.winfo_width()
        if w <= 0:
            return None
        total = self._engine.total_duration
        ratio = event.x / w
        target = max(0.0, min(total, ratio * total))
        self._progress_bar["value"] = target
        cur_str = self._fmt_time(target)
        tot_str = self._fmt_time(total)
        self._time_label.config(text=f"{cur_str} / {tot_str}")
        return ratio

    def _on_progress_click(self, event):
        """Click on progress bar — visual-only update, actual seek on release."""
        self._update_progress_preview(event)

    def _on_progress_drag(self, event):
        """Drag on progress bar — visual-only update, actual seek on release."""
        if self._update_progress_preview(event) is not None:
            self._status_var.set(_tr("status.seeking"))

    def _on_progress_release(self, event):
        if self._data is None:
            return
        w = event.widget.winfo_width()
        if w > 0:
            self._seek_to_ratio(event.x / w)
        self._status_var.set(
            _tr("status.playing")
            if self._engine.is_playing and not self._engine.is_paused
            else _tr("status.paused")
        )

    def _on_speed_change_event(self, event=None):
        """Handle speed change from either arrow buttons or Enter key."""
        self._on_speed_change()

    def _apply_text_map(self, widget: tk.Misc, mapping: dict[str, str]) -> None:
        """Recursively replace known translated strings without rebuilding widgets."""
        try:
            if isinstance(widget, ttk.Notebook):
                for i in range(widget.index("end")):
                    text = widget.tab(i, "text")
                    if text in mapping:
                        widget.tab(i, text=mapping[text])
            elif isinstance(widget, ttk.Treeview):
                cols = widget.cget("columns")
                if isinstance(cols, str):
                    cols = cols.split() if cols else ()
                for col in cols:
                    text = widget.heading(col).get("text", "")
                    if text in mapping:
                        widget.heading(col, text=mapping[text])
            elif isinstance(widget, tk.Menu):
                end = widget.index("end")
                if end is not None:
                    for i in range(int(end) + 1):
                        try:
                            if widget.type(i) not in ("command", "checkbutton", "radiobutton"):
                                continue
                            label = widget.entrycget(i, "label")
                            if label in mapping:
                                widget.entryconfig(i, label=mapping[label])
                        except tk.TclError:
                            pass
            elif isinstance(widget, tk.Text):
                pass  # handled separately (help content)
            else:
                try:
                    has_tv = bool(str(widget.cget("textvariable") or ""))
                except tk.TclError:
                    has_tv = False
                if not has_tv:
                    try:
                        text = widget.cget("text")
                    except tk.TclError:
                        text = None
                    if isinstance(text, str) and text in mapping:
                        widget.configure(text=mapping[text])
        except tk.TclError:
            pass

        try:
            children = widget.winfo_children()
        except tk.TclError:
            return
        for child in children:
            self._apply_text_map(child, mapping)

    def _retranslate_ui(self, from_lang: str, to_lang: str) -> None:
        """Update all UI strings in place (no widget destroy → no flicker)."""
        mapping = language_text_map(from_lang, to_lang)
        if mapping and self.root is not None:
            self._apply_text_map(self.root, mapping)

        self.root.title(_tr("window.title"))

        help_w = getattr(self, "_help_text", None)
        if help_w is not None:
            try:
                help_w.config(state=tk.NORMAL)
                help_w.delete("1.0", tk.END)
                help_w.insert(tk.END, _tr("help.content"))
                help_w.config(state=tk.DISABLED)
            except tk.TclError:
                pass

        if self._data is None:
            if self._file_label is not None:
                self._file_label.config(text=_tr("label.no_file"))
            if self._note_count_var is not None:
                self._note_count_var.set(_tr("note_count.default"))
            if self._time_label is not None:
                self._time_label.config(text=_tr("label.time_default"))
        else:
            dur = self._data.total_duration
            dur_str = self._fmt_time(dur)
            if self._note_count_var is not None:
                self._note_count_var.set(
                    _trf(
                        "note_count.format",
                        count=len(self._data.notes),
                        tracks=len(self._data.track_names),
                        dur=dur_str,
                        bpm=f"{self._data.bpm:.0f}",
                    )
                )
            self._refresh_track_list()

        on_top_btn = getattr(self, "_on_top_btn", None)
        if on_top_btn is not None and self._on_top_var is not None:
            if self._on_top_var.get():
                on_top_btn.config(text=_tr("btn.always_on_top_off"))
            else:
                on_top_btn.config(text=_tr("btn.always_on_top"))

        if self._pause_btn is not None:
            if self._engine.is_paused:
                self._pause_btn.config(text=_tr("btn.resume_text"))
            else:
                self._pause_btn.config(text=_tr("btn.pause_text"))

        lib_ph = getattr(self, "_lib_placeholder", None)
        if lib_ph is not None:
            lib_ph.config(text=_tr("library.empty"))
        track_ph = getattr(self, "_track_placeholder", None)
        if track_ph is not None:
            track_ph.config(text=_tr("track.no_tracks"))

        if self._bg_path_var is not None and not (self._settings.bg_image_path or "").strip():
            self._bg_path_var.set(_tr("appearance.none"))

        if self._status_var is not None:
            if self._engine.is_paused:
                self._status_var.set(_tr("status.paused"))
            elif self._engine.is_playing:
                self._status_var.set(_tr("status.playing"))
            else:
                self._status_var.set(_tr("status.ready"))

    def _toggle_language(self):
        """Toggle between Chinese and English interface."""
        old_lang = get_language()
        new_lang = "en" if old_lang == "zh" else "zh"

        # If playback is in progress, warn user and abort switch
        if self._engine.is_playing:
            messagebox.showwarning(
                title=_tr("dialog.playback_in_progress"),
                message=_tr("dialog.switch_lang_stop_playback"),
            )
            return

        self._sync_settings_to_object()
        self._settings.language = new_lang
        set_language(new_lang)
        self._retranslate_ui(old_lang, new_lang)

    def _toggle_always_on_top(self):
        """Toggle the always-on-top window state."""
        t = self._theme
        new_val = not self._on_top_var.get()
        self._on_top_var.set(new_val)
        self.root.attributes("-topmost", new_val)
        if new_val:
            self._on_top_btn.config(text=_tr("btn.always_on_top_off"), bg=t["SUCCESS"])
        else:
            self._on_top_btn.config(text=_tr("btn.always_on_top"), bg=t["TEXT_DIM"])
        self._status_var.set(_tr("status.always_on_top_on" if new_val else "status.always_on_top_off"))

    def _toggle_local(self):
        enabled = self._local_audio_var.get()
        self._local_synth.enabled = enabled
        self._synth_port_var.set(self._local_synth.get_port_name())
        self._status_var.set(
            _tr("status.local_on") if enabled else _tr("status.local_off")
        )

    @staticmethod
    def _normalize_port_name(name: str) -> str:
        return name.lower().replace(" ", "").strip()

    def _has_loop_port_conflict(self, virtual_port: str, input_port: str) -> bool:
        if not virtual_port or not input_port:
            return False
        return self._normalize_port_name(virtual_port) == self._normalize_port_name(
            input_port
        )

    def _toggle_virtual(self):
        enabled = self._virtual_var.get()
        input_port = (
            self._midi_input_port_var.get().strip() if self._midi_input_port_var else ""
        )
        if enabled and not self._virtual_midi.get_port_name().startswith("Not"):
            if self._has_loop_port_conflict(
                self._virtual_midi.get_port_name(), input_port
            ):
                self._virtual_var.set(False)
                self._virtual_midi.enabled = False
                self._status_var.set(_tr("status.midi_loop_conflict"))
                return
            self._virtual_midi.enabled = True
            self._status_var.set(
                _trf("status.virtual_on", port=self._virtual_midi.get_port_name())
            )
        elif enabled:
            # Try to find a suitable port, preferring loopMIDI ports
            ports = self._virtual_midi.get_available_ports()
            synth_name = self._local_synth.get_port_name()

            # Filter out the synth port and prefer loopMIDI
            def _port_priority(p):
                lo = p.lower()
                if "loopmidi" in lo.replace(" ", ""):
                    return 0  # loopMIDI first
                if synth_name != "None" and lo == synth_name.lower():
                    return 999  # synth port last (should be excluded)
                return 1  # other ports in between

            candidates = sorted(
                [
                    p
                    for p in ports
                    if synth_name == "None" or p.lower() != synth_name.lower()
                ],
                key=_port_priority,
            )
            if candidates:
                port = candidates[0]
                if self._has_loop_port_conflict(port, input_port):
                    self._virtual_var.set(False)
                    self._status_var.set(_tr("status.midi_loop_conflict"))
                    return
                self._virtual_midi.set_port_name(port)
                self._virtual_port_var.set(port)
                self._virtual_midi.enabled = True
                if self._virtual_midi.get_port_name() == "Not connected":
                    # Port failed to open
                    self._virtual_var.set(False)
                    self._status_var.set(_tr("status.virtual_no_ports"))
                else:
                    self._status_var.set(_trf("status.virtual_on", port=port))
            else:
                self._virtual_var.set(False)
                self._status_var.set(_tr("status.virtual_no_ports"))
        else:
            self._virtual_midi.enabled = False
            self._status_var.set(_tr("status.virtual_off"))

    def _refresh_virtual_ports(self):
        ports = self._virtual_midi.get_available_ports()
        self._virtual_port_combo["values"] = ports
        if ports:
            cur = self._virtual_port_var.get()
            if cur not in ports:
                self._virtual_port_var.set(ports[0])
            self._status_var.set(_trf("status.virtual_refresh", count=len(ports)))
        else:
            self._virtual_port_combo["values"] = []
            self._virtual_port_var.set("")
            self._status_var.set(_tr("status.virtual_no_ports_short"))

    def _apply_virtual_port(self):
        name = self._virtual_port_var.get().strip()
        if name:
            input_port = (
                self._midi_input_port_var.get().strip()
                if self._midi_input_port_var
                else ""
            )
            if self._has_loop_port_conflict(name, input_port):
                self._status_var.set(_tr("status.midi_loop_conflict"))
                return
            self._virtual_midi.set_port_name(name)
            ports = self._virtual_midi.get_available_ports()
            for p in ports:
                if name.lower().replace(" ", "") in p.lower().replace(" ", ""):
                    self._virtual_port_var.set(p)
                    break
            self._status_var.set(
                _trf("status.virtual_applied", name=self._virtual_midi.get_port_name())
            )

    def _toggle_osc(self):
        enabled = self._osc_var.get()
        self._osc.enabled = enabled
        self._status_var.set(_tr("status.osc_on") if enabled else _tr("status.osc_off"))

    def _apply_osc_addr(self):
        addr = self._osc_addr_var.get().strip()
        if ":" in addr:
            parts = addr.split(":")
            ip = parts[0]
            try:
                port = int(parts[1])
                self._osc.set_address(ip, port)
                self._status_var.set(_trf("status.osc_addr_set", ip=ip, port=port))
            except ValueError:
                self._status_var.set(_tr("status.osc_addr_invalid"))

    def _apply_osc_mode(self):
        mode = self._osc_mode_var.get()
        self._osc.mode = mode
        mode_name = (
            "/PianoKeys/ (Piano Avatar)"
            if mode == "piano"
            else "/avatar/parameters/ (Custom Avatar)"
        )
        self._status_var.set(_trf("status.osc_mode", mode=mode_name))



    # ===================== Engine callbacks =====================

    def _on_volume_change(self, value):
        volume = float(value)
        self._settings.volume = volume
        pct = int(volume * 100)
        self._volume_label_var.set(f"{pct}%")
        self._volume_spin_var.set(str(pct))

    def _on_volume_trough_click(self, event):
        """Handle mouse press on volume scale (both trough and thumb).
        Completely takes over the native handler so that drag works
        consistently whether the user first clicks trough or thumb."""
        w = event.widget.winfo_width()
        if w <= 0:
            return "break"
        ratio = max(0.0, min(1.0, event.x / w))
        self._volume_var.set(ratio)
        self._on_volume_change(ratio)
        return "break"  # Prevent native handler — we manage everything

    def _on_volume_drag(self, event):
        """Handle mouse drag on volume scale after initial Button-1."""
        w = event.widget.winfo_width()
        if w <= 0:
            return "break"
        ratio = max(0.0, min(1.0, event.x / w))
        self._volume_var.set(ratio)
        self._on_volume_change(ratio)
        return "break"

    def _on_volume_spin_change(self):
        """Handle volume change from Spinbox arrows or Enter key."""
        self._apply_volume_spin_value()

    def _on_volume_spin_event(self, event=None):
        """Handle Enter key or focus out on the volume Spinbox."""
        self._apply_volume_spin_value()

    def _apply_volume_spin_value(self):
        """Read Spinbox value and apply to volume."""
        try:
            pct = int(self._volume_spin_var.get())
            pct = max(0, min(100, pct))
            volume = pct / 100.0
            self._volume_var.set(volume)
            self._on_volume_change(volume)
        except (ValueError, tk.TclError):
            # Revert to current volume
            self._volume_spin_var.set(str(int(self._settings.volume * 100)))

    def _get_scaled_velocity(self, velocity: int) -> int:
        """Scale MIDI velocity (0-127) by current volume setting."""
        scaled = int(round(velocity * self._settings.volume))
        return max(0, min(127, scaled))

    def _dispatch_note_to_outputs(
        self, method: str, note: int, velocity: int, channel: int
    ):
        """Dispatch a note event to all enabled outputs."""
        for out in (self._local_synth, self._virtual_midi, self._osc):
            if out.enabled:
                getattr(out, method)(note, velocity, channel)

    def _on_note_on(self, note_event):
        vel = self._get_scaled_velocity(note_event.velocity)
        transpose = self._settings.playback_transpose
        self._dispatch_note_to_outputs(
            "note_on", note_event.note + transpose, vel, note_event.channel
        )

    def _on_note_off(self, note_event):
        transpose = self._settings.playback_transpose
        self._dispatch_note_to_outputs(
            "note_off",
            note_event.note + transpose,
            note_event.velocity,
            note_event.channel,
        )

    def _on_finish(self):
        self.root.after(0, self._on_finish_ui)

    def _on_finish_ui(self):
        self._play_btn.config(state=tk.NORMAL)
        self._pause_btn.config(text=_tr("btn.pause_text"), state=tk.DISABLED)
        self._stop_btn.config(state=tk.DISABLED)
        self._status_var.set(_tr("status.finished"))
        # Show playback completed at 100% on the progress bar
        total = self._engine.total_duration
        self._progress_bar["value"] = total
        tot_str = f"{int(total // 60)}:{int(total % 60):02d}"
        self._time_label.config(text=f"{tot_str} / {tot_str}")

    # ===================== MIDI Input =====================

    def _toggle_midi_input(self):
        enabled = self._midi_input_var.get()
        # Apply the selected port before toggling
        port = self._midi_input_port_var.get().strip()
        virtual_port = (
            self._virtual_port_var.get().strip() if self._virtual_port_var else ""
        )
        if (
            enabled
            and self._virtual_midi.enabled
            and self._has_loop_port_conflict(virtual_port, port)
        ):
            self._midi_input_var.set(False)
            self._status_var.set(_tr("status.midi_loop_conflict"))
            return
        if port:
            self._midi_input.set_port_name(port)
        self._midi_input.enabled = enabled
        self._status_var.set(
            _tr("status.midi_input_on") if enabled else _tr("status.midi_input_off")
        )

    def _refresh_midi_input_ports(self):
        ports = self._midi_input.get_available_ports()
        self._midi_input_combo["values"] = ports
        if ports and not self._midi_input_port_var.get():
            self._midi_input_port_var.set(ports[0])

    def _toggle_passthrough(self):
        """Toggle Live MIDI Passthrough mode."""
        enabled = self._passthrough_var.get()
        if enabled:
            # Save current MIDI input state and force enable
            self._midi_input_was_enabled = self._midi_input.enabled
            if not self._midi_input.enabled:
                self._midi_input_var.set(True)
                self._toggle_midi_input()
            self._passthrough_status_var.set(_tr("status.passthrough_active"))
            self._status_var.set(_tr("status.passthrough_on"))
        else:
            # Restore previous MIDI input state
            if not self._midi_input_was_enabled:
                self._midi_input_var.set(False)
                self._midi_input.enabled = False
            self._passthrough_status_var.set("")
            self._status_var.set(_tr("status.passthrough_off"))

    # ===================== Transpose handlers =====================

    def _on_playback_transpose_change(self):
        """Called when playback transpose spinbox changes via buttons."""
        self._settings.playback_transpose = self._playback_transpose_var.get()

    def _on_playback_transpose_event(self, event=None):
        """Called when playback transpose spinbox is edited manually."""
        self._settings.playback_transpose = self._playback_transpose_var.get()

    def _on_midi_input_transpose_change(self):
        """Called when MIDI input transpose spinbox changes via buttons."""
        self._settings.midi_input_transpose = self._midi_input_transpose_var.get()

    def _on_midi_input_transpose_event(self, event=None):
        """Called when MIDI input transpose spinbox is edited manually."""
        self._settings.midi_input_transpose = self._midi_input_transpose_var.get()

    def _on_midi_input_note_on(self, note: int, velocity: int, channel: int):
        vel = self._get_scaled_velocity(velocity)
        transpose = self._settings.midi_input_transpose
        self._dispatch_note_to_outputs("note_on", note + transpose, vel, channel)

    def _on_midi_input_note_off(self, note: int, velocity: int, channel: int):
        transpose = self._settings.midi_input_transpose
        self._dispatch_note_to_outputs("note_off", note + transpose, velocity, channel)

    # ===================== Library management =====================

    def _library_refresh_tree(self):
        """Repopulate the TreeView from self._library.entries."""
        tree = self._lib_tree
        for item in tree.get_children():
            tree.delete(item)

        for i, entry in enumerate(self._library.entries):
            dur_str = self._fmt_time(entry.duration_sec)
            tree.insert(
                "",
                tk.END,
                iid=str(i),
                values=(
                    entry.title,
                    dur_str,
                    f"{entry.bpm:.0f}",
                    str(entry.note_count),
                ),
            )

        # Empty state: hide tree so the hint is visible; otherwise show list
        if self._library.count == 0:
            self._lib_tree.pack_forget()
            self._lib_scrollbar.pack_forget()
            self._lib_placeholder.pack(fill=tk.BOTH, expand=True, pady=40)
        else:
            self._lib_placeholder.pack_forget()
            self._lib_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self._lib_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _library_add_files(self):
        """Open file dialog, allow multi-select, add to library."""
        paths = filedialog.askopenfilenames(
            title=_tr("dialog.select_midi"),
            filetypes=[
                (_tr("dialog.midi_files"), "*.mid *.midi"),
                (_tr("dialog.all_files"), "*.*"),
            ],
        )
        if not paths:
            return

        added = self._library.add_files(list(paths))
        self._library_refresh_tree()
        self._status_var.set(_trf("library.added", count=len(added)))

    def _library_add_folder(self):
        """Open folder dialog, scan for .mid/.midi files, add all."""
        from tkinter import filedialog as fd

        folder = fd.askdirectory(title="Select folder")
        if not folder:
            return

        paths = []
        for root_dir, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith((".mid", ".midi")):
                    paths.append(os.path.join(root_dir, f))

        if not paths:
            self._status_var.set(_tr("library.no_midi_found"))
            return

        added = self._library.add_files(paths)
        self._library_refresh_tree()
        self._status_var.set(_trf("library.added", count=len(added)))

    def _library_remove(self):
        """Remove selected entries from the library (supports multi-select)."""
        sel = self._lib_tree.selection()
        if not sel:
            return
        # Collect indices (reverse sort so removal doesn't shift indices)
        indices = sorted((int(s) for s in sel), reverse=True)
        removed_titles = []
        for idx in indices:
            entry = self._library.get_by_index(idx)
            if entry is not None:
                removed_titles.append(entry.title)
                self._library.remove_index(idx)
        self._library_refresh_tree()
        if len(removed_titles) == 1:
            self._status_var.set(_trf("library.removed", title=removed_titles[0]))
        elif removed_titles:
            self._status_var.set(
                _trf("library.removed_multi", count=len(removed_titles))
            )

    def _library_play_selected(self, event=None):
        """Load and play the currently selected library entry."""
        sel = self._lib_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        entry = self._library.get_by_index(idx)
        if entry is None:
            return

        # Check file still exists
        if not os.path.exists(entry.path):
            self._status_var.set(_trf("library.file_not_found", path=entry.path))
            return

        self._stop()  # Stop current playback
        self._load_file_by_path(entry.path)
        self._play()
        self._status_var.set(_trf("library.playing", title=entry.title))

    def _library_context_menu(self, event):
        """Show right-click context menu on library tree item."""
        item = self._lib_tree.identify_row(event.y)
        if item:
            # If the item is not already in the selection, select only it
            if item not in self._lib_tree.selection():
                self._lib_tree.selection_set(item)
            self._lib_context.post(event.x_root, event.y_root)

    def _on_library_drop(self, event):
        """Handle drag-and-drop of MIDI files onto the library."""
        if not _HAS_DND:
            return
        import re
        raw = event.data
        # tkinterdnd2 on Windows: paths with spaces are wrapped in {curly braces}
        # Multiple files are separated by spaces, so we need to parse carefully.
        # Regex: match either {anything} or non-space sequences
        tokens = re.findall(r'\{[^}]*\}|\S+', raw)
        paths = []
        for token in tokens:
            clean = token.strip('{}')
            # Normalize path separators
            clean = clean.replace('/', '\\')
            if clean.lower().endswith((".mid", ".midi")):
                paths.append(clean)
        if paths:
            added = self._library.add_files(paths)
            self._library_refresh_tree()
            self._status_var.set(_trf("library.added", count=len(added)))

    def _load_file_by_path(self, path: str):
        """Load a MIDI file by its path (used by library)."""
        data = parse_midi(path)
        if data is None:
            self._status_var.set(_trf("status.load_failed", path=path))
            return

        self._apply_loaded_midi(data, path)

    # ===================== Timer for progress =====================

    def _update_timer(self):
        if self._engine.is_playing and not self._engine.is_paused:
            current = self._engine.current_time
            total = self._engine.total_duration
            if total > 0:
                self._progress_bar["value"] = current
                cur_str = f"{int(current // 60)}:{int(current % 60):02d}"
                tot_str = f"{int(total // 60)}:{int(total % 60):02d}"
                self._time_label.config(text=f"{cur_str} / {tot_str}")
        self._update_id = self.root.after(50, self._update_timer)

    # ===================== Run =====================

    def _on_close(self):
        """Save settings and close the application."""
        self._sync_settings_to_object()
        save_settings(self._settings)
        self._engine.stop()
        # Clean up MIDI outputs
        self._local_synth.all_notes_off()
        self._virtual_midi.all_notes_off()
        self._osc.all_notes_off()
        self.root.destroy()

    def _sync_settings_to_object(self):
        """Sync current UI state back into the settings object."""
        try:
            geom = self.root.geometry()
            parts = geom.replace("+", " ").replace("x", " ").split()
            if len(parts) >= 2:
                self._settings.window_width = int(parts[0])
                self._settings.window_height = int(parts[1])
            if len(parts) >= 4:
                self._settings.window_x = int(parts[2])
                self._settings.window_y = int(parts[3])
        except Exception:
            pass

        self._settings.language = get_language()
        try:
            self._settings.speed = float(self._speed_var.get())
        except Exception:
            self._settings.speed = 1.0
        self._settings.local_audio_enabled = self._local_synth.enabled
        self._settings.virtual_midi_enabled = self._virtual_midi.enabled
        self._settings.osc_output_enabled = self._osc.enabled
        self._settings.always_on_top = self._on_top_var.get()
        self._settings.virtual_midi_port = self._virtual_port_var.get()
        try:
            self._settings.osc_mode = self._osc_mode_var.get()
        except Exception:
            pass
        try:
            ip, port_str = self._osc_addr_var.get().rsplit(":", 1)
            self._settings.osc_address_ip = ip.strip()
            self._settings.osc_address_port = int(port_str.strip())
        except Exception:
            pass
        self._settings.midi_input_enabled = self._midi_input.enabled
        self._settings.midi_input_port = self._midi_input_port_var.get()
        self._settings.playback_transpose = self._playback_transpose_var.get()
        self._settings.midi_input_transpose = self._midi_input_transpose_var.get()
        self._settings.volume = float(self._volume_var.get())


    def _on_engine_update(self, current_time: float):
        """Called periodically from the engine thread (~100ms).

        Keep this callback lightweight so the UI relies on the single
        ``_update_timer`` after-chain instead of queueing extra Tk events.
        """
        self._last_update_time = current_time

    def run(self):
        self.root.mainloop()
