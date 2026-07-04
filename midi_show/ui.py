"""Tkinter-based GUI for MIDI Show player."""

from __future__ import annotations

import logging
import os
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Optional

from .midi_parser import MidiData, parse_midi
from .engine import PlaybackEngine
from .piano_roll import PianoRoll
from .outputs import LocalSynthOutput, VirtualMidiOutput, OscOutput, MidiInput
from .library import LibraryManager
from .i18n import tr as _tr, trf as _trf, set_language, get_language
from .settings import load_settings, save_settings, AppSettings

logger = logging.getLogger(__name__)


class MidiShowUI:
    """Main application window."""

    def __init__(self):
        # Load persisted settings
        self._settings = load_settings()

        # Restore language before building UI
        set_language(self._settings.language)

        self.root = tk.Tk()
        self.root.title(_tr("window.title"))

        # Window geometry
        w, h = self._settings.window_width, self._settings.window_height
        wx, wy = self._settings.window_x, self._settings.window_y
        self.root.geometry(f"{w}x{h}")
        if wx >= 0 and wy >= 0:
            self.root.geometry(f"+{wx}+{wy}")
        self.root.minsize(640, 420)

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
        self._note_on_count: int = 0
        self._note_off_count: int = 0

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

        # Connect engine callbacks
        self._engine.set_callbacks(
            on_note_on=self._on_note_on,
            on_note_off=self._on_note_off,
            on_finish=self._on_finish,
            on_update=self._on_engine_update,
        )

        self._build_ui()
        self._update_timer()

    def _build_ui(self):
        root = self.root

        # ===================== Top: File info =====================
        top_frame = ttk.Frame(root, padding=(10, 8, 10, 4))
        top_frame.pack(fill=tk.X)

        ttk.Button(top_frame, text=_tr("btn.load_midi"), command=self._load_file).pack(
            side=tk.LEFT, padx=(0, 8)
        )

        self._file_label = ttk.Label(
            top_frame, text=_tr("label.no_file"), foreground="#888"
        )
        self._file_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(
            top_frame, text=_tr("btn.lang"), command=self._toggle_language, width=6
        ).pack(side=tk.RIGHT, padx=(4, 0))

        # ===================== Song info =====================
        info_frame = ttk.Frame(root, padding=(10, 0, 10, 4))
        info_frame.pack(fill=tk.X)

        self._title_label = ttk.Label(
            info_frame, text="", font=("Segoe UI", 11, "bold")
        )
        self._title_label.pack(anchor=tk.W)

        stats_frame = ttk.Frame(info_frame)
        stats_frame.pack(anchor=tk.W, fill=tk.X)
        self._note_count_var = tk.StringVar(value=_tr("note_count.default"))
        ttk.Label(
            stats_frame, textvariable=self._note_count_var, foreground="#666"
        ).pack(side=tk.LEFT)

        # ===================== Transport controls =====================
        ctrl_frame = ttk.Frame(root, padding=(10, 4, 10, 4))
        ctrl_frame.pack(fill=tk.X)

        btn_frame = ttk.Frame(ctrl_frame)
        btn_frame.pack()

        self._play_btn = ttk.Button(
            btn_frame, text=_tr("btn.play"), command=self._play, width=10
        )
        self._play_btn.pack(side=tk.LEFT, padx=2)

        self._pause_btn = ttk.Button(
            btn_frame,
            text=_tr("btn.pause"),
            command=self._pause,
            width=10,
            state=tk.DISABLED,
        )
        self._pause_btn.pack(side=tk.LEFT, padx=2)

        self._stop_btn = ttk.Button(
            btn_frame,
            text=_tr("btn.stop"),
            command=self._stop,
            width=10,
            state=tk.DISABLED,
        )
        self._stop_btn.pack(side=tk.LEFT, padx=2)

        ttk.Separator(ctrl_frame, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=10
        )

        ttk.Label(ctrl_frame, text=_tr("label.speed")).pack(side=tk.LEFT)
        self._speed_var = tk.DoubleVar(value=self._settings.speed)
        self._speed_spinbox = ttk.Spinbox(
            ctrl_frame,
            from_=0.25,
            to=4.0,
            increment=0.25,
            textvariable=self._speed_var,
            width=5,
            command=self._on_speed_change,
        )
        self._speed_spinbox.pack(side=tk.LEFT, padx=4)
        # 绑定回车键以支持手动输入
        self._speed_spinbox.bind("<Key-Return>", self._on_speed_change_event)
        self._speed_spinbox.bind("<FocusOut>", self._on_speed_change_event)
        ttk.Label(ctrl_frame, text=_tr("label.speed_x")).pack(side=tk.LEFT)

        # -- Playback Transpose --
        ttk.Label(ctrl_frame, text="  ").pack(side=tk.LEFT)
        ttk.Label(ctrl_frame, text=_tr("playback.transpose")).pack(side=tk.LEFT)
        self._playback_transpose_var = tk.IntVar(
            value=self._settings.playback_transpose
        )
        self._playback_transpose_spinbox = ttk.Spinbox(
            ctrl_frame,
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
        ttk.Label(ctrl_frame, text=_tr("label.semitones")).pack(side=tk.LEFT)

        # ===================== Progress =====================
        prog_frame = ttk.Frame(root, padding=(10, 2, 10, 4))
        prog_frame.pack(fill=tk.X)

        self._time_label = ttk.Label(
            prog_frame, text=_tr("label.time_default"), width=16
        )
        self._time_label.pack(side=tk.RIGHT)

        self._progress_bar = ttk.Progressbar(prog_frame, mode="determinate")
        self._progress_bar.pack(fill=tk.X, expand=True, padx=(0, 8))
        # Seek bindings
        self._progress_bar.bind("<Button-1>", self._on_progress_click)
        self._progress_bar.bind("<B1-Motion>", self._on_progress_drag)
        self._progress_bar.bind("<ButtonRelease-1>", self._on_progress_release)

        # ===================== Output settings =====================
        nb = ttk.Notebook(root)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 8))

        # -- Library tab --
        lib_frame = ttk.Frame(nb, padding=6)
        nb.add(lib_frame, text=_tr("tab.library"))

        # Buttons toolbar
        lib_toolbar = ttk.Frame(lib_frame)
        lib_toolbar.pack(fill=tk.X, pady=(0, 4))

        ttk.Button(
            lib_toolbar, text=_tr("library.add_files"), command=self._library_add_files
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            lib_toolbar,
            text=_tr("library.add_folder"),
            command=self._library_add_folder,
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            lib_toolbar, text=_tr("library.remove"), command=self._library_remove
        ).pack(side=tk.LEFT, padx=2)

        # TreeView for library
        columns = ("title", "duration", "bpm", "notes")
        self._lib_tree = ttk.Treeview(
            lib_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
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

        scrollbar = ttk.Scrollbar(
            lib_frame, orient=tk.VERTICAL, command=self._lib_tree.yview
        )
        self._lib_tree.configure(yscrollcommand=scrollbar.set)
        self._lib_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Double-click to play
        self._lib_tree.bind("<Double-1>", self._library_play_selected)

        # Right-click context menu
        self._lib_context = tk.Menu(self.root, tearoff=0)
        self._lib_context.add_command(
            label=_tr("library.play"), command=self._library_play_selected
        )
        self._lib_context.add_command(
            label=_tr("library.remove"), command=self._library_remove
        )
        self._lib_tree.bind("<Button-3>", self._library_context_menu)

        # Placeholder label when empty
        self._lib_placeholder = ttk.Label(
            lib_frame,
            text=_tr("library.empty"),
            foreground="#999",
            anchor=tk.CENTER,
            justify=tk.CENTER,
        )

        # Populate the tree with existing entries
        self._library_refresh_tree()

        # -- Output tab --
        out_frame = ttk.Frame(nb, padding=10)
        nb.add(out_frame, text=_tr("tab.output"))

        self._local_audio_var = tk.BooleanVar(value=self._settings.local_audio_enabled)
        self._virtual_var = tk.BooleanVar(value=self._settings.virtual_midi_enabled)
        self._osc_var = tk.BooleanVar(value=self._settings.osc_output_enabled)
        self._volume_var = tk.DoubleVar(value=self._settings.volume)

        # Local Audio
        local_cb = ttk.Checkbutton(
            out_frame,
            text=_tr("output.local_audio"),
            variable=self._local_audio_var,
            command=self._toggle_local,
        )
        local_cb.grid(row=0, column=0, sticky=tk.W, pady=2)

        self._synth_port_var = tk.StringVar(value=self._local_synth.get_port_name())
        ttk.Label(
            out_frame,
            textvariable=self._synth_port_var,
            foreground="#888",
            font=("Segoe UI", 9),
        ).grid(row=1, column=0, sticky=tk.W, padx=20)

        # Virtual MIDI
        virtual_cb = ttk.Checkbutton(
            out_frame,
            text=_tr("output.virtual_midi"),
            variable=self._virtual_var,
            command=self._toggle_virtual,
        )
        virtual_cb.grid(row=2, column=0, sticky=tk.W, pady=2)

        vm_frame = ttk.Frame(out_frame)
        vm_frame.grid(row=3, column=0, sticky=tk.W, padx=20)
        ttk.Label(vm_frame, text=_tr("output.port"), font=("Segoe UI", 9)).pack(
            side=tk.LEFT
        )
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

        # OSC Output
        osc_cb = ttk.Checkbutton(
            out_frame,
            text=_tr("output.osc"),
            variable=self._osc_var,
            command=self._toggle_osc,
        )
        osc_cb.grid(row=4, column=0, sticky=tk.W, pady=2)

        osc_frame = ttk.Frame(out_frame)
        osc_frame.grid(row=5, column=0, sticky=tk.W, padx=20)
        ttk.Label(osc_frame, text=_tr("output.address"), font=("Segoe UI", 9)).pack(
            side=tk.LEFT
        )
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

        # OSC mode
        mode_frame = ttk.Frame(out_frame)
        mode_frame.grid(row=6, column=0, sticky=tk.W, padx=20, pady=2)
        ttk.Label(mode_frame, text=_tr("output.mode"), font=("Segoe UI", 9)).pack(
            side=tk.LEFT
        )
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

        # ── Volume ──
        ttk.Separator(out_frame, orient=tk.HORIZONTAL).grid(
            row=7, column=0, columnspan=2, sticky=tk.EW, pady=6
        )
        vol_frame = ttk.Frame(out_frame)
        vol_frame.grid(row=8, column=0, sticky=tk.W, pady=2)
        ttk.Label(vol_frame, text=_tr("output.volume")).pack(side=tk.LEFT)
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
        # Manual bindings for both trough-click and drag
        self._volume_scale.bind("<Button-1>", self._on_volume_trough_click)
        self._volume_scale.bind("<B1-Motion>", self._on_volume_drag)
        self._volume_label_var = tk.StringVar(
            value=f"{int(self._settings.volume * 100)}%"
        )
        ttk.Label(vol_frame, textvariable=self._volume_label_var, width=5).pack(
            side=tk.LEFT
        )
        ttk.Label(vol_frame, text="  ").pack(side=tk.LEFT)
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
        ttk.Label(vol_frame, text="%").pack(side=tk.LEFT)

        # -- MIDI Input --
        ttk.Separator(out_frame, orient=tk.HORIZONTAL).grid(
            row=9, column=0, columnspan=2, sticky=tk.EW, pady=6
        )
        self._midi_input_var = tk.BooleanVar(value=self._settings.midi_input_enabled)
        midi_input_cb = ttk.Checkbutton(
            out_frame,
            text=_tr("midi.input"),
            variable=self._midi_input_var,
            command=self._toggle_midi_input,
        )
        midi_input_cb.grid(row=10, column=0, sticky=tk.W, pady=2)

        midi_input_port_frame = ttk.Frame(out_frame)
        midi_input_port_frame.grid(row=11, column=0, sticky=tk.W, pady=2)
        ttk.Label(midi_input_port_frame, text=_tr("midi.input_port")).pack(side=tk.LEFT)
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
        self._refresh_midi_input_ports()

        # -- MIDI Input Transpose --
        midi_input_transpose_frame = ttk.Frame(out_frame)
        midi_input_transpose_frame.grid(row=12, column=0, sticky=tk.W, pady=2)
        ttk.Label(midi_input_transpose_frame, text=_tr("midi.input_transpose")).pack(
            side=tk.LEFT
        )
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
        ttk.Label(midi_input_transpose_frame, text=_tr("label.semitones")).pack(
            side=tk.LEFT
        )

        # ===================== Track Filter tab =====================
        track_frame = ttk.Frame(nb, padding=6)
        nb.add(track_frame, text=_tr("tab.track_filter"))

        # Canvas + Scrollbar for scrolling track list
        track_canvas = tk.Canvas(track_frame, highlightthickness=0, borderwidth=0)
        track_scrollbar = ttk.Scrollbar(
            track_frame, orient=tk.VERTICAL, command=track_canvas.yview
        )
        track_canvas.configure(yscrollcommand=track_scrollbar.set)
        track_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        track_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Inner frame for track rows
        track_inner = ttk.Frame(track_canvas, padding=2)
        track_inner.bind(
            "<Configure>",
            lambda e: track_canvas.configure(scrollregion=track_canvas.bbox("all")),
        )
        track_canvas.create_window(
            (0, 0), window=track_inner, anchor="nw", tags="track_inner"
        )

        # Allow mousewheel scrolling when hovering over canvas
        def _on_track_mousewheel(event):
            track_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        track_canvas.bind(
            "<Enter>",
            lambda e: track_canvas.bind_all("<MouseWheel>", _on_track_mousewheel),
        )
        track_canvas.bind("<Leave>", lambda e: track_canvas.unbind_all("<MouseWheel>"))

        self._track_inner = track_inner
        self._track_rows: list[
            dict
        ] = []  # list of dicts: frame, name_label, notes_label, mute_btn, solo_btn

        # Placeholder when no file loaded
        self._track_placeholder = ttk.Label(
            track_inner,
            text=_tr("track.no_tracks"),
            foreground="#999",
            anchor=tk.CENTER,
            justify=tk.CENTER,
        )

        # -- Live Passthrough --
        ttk.Separator(out_frame, orient=tk.HORIZONTAL).grid(
            row=13, column=0, columnspan=2, sticky=tk.EW, pady=6
        )
        passthrough_frame = ttk.Frame(out_frame)
        passthrough_frame.grid(row=14, column=0, sticky=tk.W, pady=2)
        self._passthrough_cb = ttk.Checkbutton(
            passthrough_frame,
            text=_tr("midi.passthrough"),
            variable=self._passthrough_var,
            command=self._toggle_passthrough,
        )
        self._passthrough_cb.pack(side=tk.LEFT)
        self._passthrough_status_var = tk.StringVar(value="")
        ttk.Label(
            passthrough_frame,
            textvariable=self._passthrough_status_var,
            font=("Segoe UI", 9, "italic"),
            foreground="#555",
        ).pack(side=tk.LEFT, padx=8)

        # -- Piano Roll tab --
        piano_frame = ttk.Frame(nb, padding=0)
        nb.add(piano_frame, text=_tr("tab.piano_roll") + " [测试]")

        self._piano_roll = PianoRoll(piano_frame, height=300)
        self._piano_roll.pack(fill=tk.BOTH, expand=True)

        # Enable/disable checkbox
        piano_ctrl_frame = ttk.Frame(piano_frame, padding=(4, 2, 4, 4))
        piano_ctrl_frame.pack(fill=tk.X)
        self._piano_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            piano_ctrl_frame,
            text=_tr("output.local_audio"),
            variable=self._piano_enabled_var,
            command=self._toggle_piano,
        ).pack(side=tk.LEFT)

        # -- Info tab --
        info_tab = ttk.Frame(nb, padding=10)
        nb.add(info_tab, text=_tr("tab.how_to_use"))

        help_label = tk.Text(
            info_tab,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            bg=root.cget("bg"),
            relief=tk.FLAT,
            bd=0,
            padx=4,
            pady=4,
        )
        help_label.insert(tk.END, _tr("help.content"))
        help_label.config(state=tk.DISABLED)
        help_label.pack(fill=tk.BOTH, expand=True)

        # ===================== Status bar =====================
        status_frame = ttk.Frame(root, padding=(10, 2, 10, 6))
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self._status_var = tk.StringVar(value=_tr("status.ready"))
        status_label = tk.Label(
            status_frame, textvariable=self._status_var, relief=tk.SUNKEN, anchor=tk.W
        )
        status_label.pack(fill=tk.X)

    # ===================== Event handlers =====================

    def _apply_loaded_midi(self, data: MidiData, path: str):
        """Apply parsed MIDI data to engine and update UI (no status message)."""
        self._data = data
        self._engine.load(data)

        self._note_on_count = 0
        self._note_off_count = 0

        filename = os.path.basename(path)
        self._file_label.config(text=filename)
        self._title_label.config(text=data.title)

        dur = data.total_duration
        dur_str = f"{int(dur // 60)}:{int(dur % 60):02d}"
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

        # Load notes into piano roll
        if hasattr(self, "_piano_roll"):
            self._piano_roll.set_data(data.notes, data.total_duration)

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
        # Reset counters
        self._note_on_count = 0
        self._note_off_count = 0

        # Send all notes off
        self._local_synth.all_notes_off()
        self._virtual_midi.all_notes_off()
        self._osc.all_notes_off()

        self._engine.stop()
        # Reset piano roll
        if hasattr(self, "_piano_roll"):
            self._piano_roll.update_playback(0, {})
        self._play_btn.config(state=tk.NORMAL)
        self._pause_btn.config(text=_tr("btn.pause_text"), state=tk.DISABLED)
        self._stop_btn.config(state=tk.DISABLED)
        self._progress_bar["value"] = 0
        if self._data:
            dur = self._data.total_duration
            tot_str = f"{int(dur // 60)}:{int(dur % 60):02d}"
            self._time_label.config(text=f"0:00 / {tot_str}")
        self._status_var.set(_tr("status.stopped"))

    # ===================== Track Filter =====================

    def _refresh_track_list(self):
        """Rebuild the track filter rows in the Track Filter tab."""
        # Clear existing rows
        for row in self._track_rows:
            row["frame"].destroy()
        self._track_rows.clear()
        self._track_placeholder.pack_forget()

        if self._data is None or not self._data.track_names:
            self._track_placeholder.pack(fill=tk.BOTH, expand=True, pady=20)
            return

        # Header row
        hdr = ttk.Frame(self._track_inner)
        hdr.pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            hdr, text="#", font=("Segoe UI", 9, "bold"), width=3, anchor=tk.W
        ).pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(
            hdr,
            text=_tr("track.column_name"),
            font=("Segoe UI", 9, "bold"),
            width=20,
            anchor=tk.W,
        ).pack(side=tk.LEFT, padx=4)
        tk.Label(
            hdr,
            text=_tr("track.column_notes"),
            font=("Segoe UI", 9, "bold"),
            width=10,
            anchor=tk.W,
        ).pack(side=tk.LEFT, padx=4)
        tk.Label(
            hdr,
            text=_tr("track.mute"),
            font=("Segoe UI", 9, "bold"),
            width=4,
            anchor=tk.CENTER,
        ).pack(side=tk.LEFT, padx=4)
        tk.Label(
            hdr,
            text=_tr("track.solo"),
            font=("Segoe UI", 9, "bold"),
            width=4,
            anchor=tk.CENTER,
        ).pack(side=tk.LEFT, padx=4)
        ttk.Separator(self._track_inner, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=2)

        muted = set(self._engine.muted_tracks)
        soloed = set(self._engine.solo_tracks)
        any_solo = bool(soloed)

        for idx, name in enumerate(self._data.track_names):
            row_frame = ttk.Frame(self._track_inner)
            row_frame.pack(fill=tk.X, pady=1)

            # Track number
            tk.Label(row_frame, text=str(idx + 1), width=3, anchor=tk.W).pack(
                side=tk.LEFT, padx=(0, 4)
            )
            # Track name
            tk.Label(
                row_frame,
                text=name or f"Track {idx + 1}",
                width=20,
                anchor=tk.W,
                font=("Segoe UI", 9),
            ).pack(side=tk.LEFT, padx=4)
            # Note count
            note_count = sum(1 for n in self._data.notes if n.track == idx)
            tk.Label(
                row_frame,
                text=str(note_count),
                width=10,
                anchor=tk.W,
                foreground="#666",
            ).pack(side=tk.LEFT, padx=4)

            # Mute button (toggle)
            is_muted = idx in muted
            mute_btn = tk.Button(
                row_frame,
                text="M",
                width=3,
                font=("Segoe UI", 8, "bold"),
                relief=tk.SUNKEN if is_muted else tk.RAISED,
                bg="#ffcccc" if is_muted else "#e0e0e0",
                command=lambda i=idx: self._toggle_track_mute(i),
            )
            mute_btn.pack(side=tk.LEFT, padx=4)

            # Solo button (toggle)
            is_soloed = idx in soloed
            solo_btn = tk.Button(
                row_frame,
                text="S",
                width=3,
                font=("Segoe UI", 8, "bold"),
                relief=tk.SUNKEN if is_soloed else tk.RAISED,
                bg="#ccffcc" if is_soloed else "#e0e0e0",
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
            solo_note = ttk.Label(
                self._track_inner,
                text=_tr("track.solo_active"),
                foreground="#2a7f2a",
                font=("Segoe UI", 8, "italic"),
            )
            solo_note.pack(anchor=tk.W, pady=(4, 0))
            self._track_solo_note = solo_note
        else:
            if hasattr(self, "_track_solo_note"):
                self._track_solo_note.destroy()
                del self._track_solo_note

    def _toggle_track_mute(self, track_idx: int):
        """Toggle mute state for a track."""
        muted = set(self._engine.muted_tracks)
        if track_idx in muted:
            muted.discard(track_idx)
        else:
            muted.add(track_idx)
        self._engine.muted_tracks = muted
        self._refresh_track_list()

    def _toggle_track_solo(self, track_idx: int):
        """Toggle solo state for a track."""
        soloed = set(self._engine.solo_tracks)
        if track_idx in soloed:
            soloed.discard(track_idx)
        else:
            soloed.add(track_idx)
        self._engine.solo_tracks = soloed
        self._refresh_track_list()

    def _on_speed_change(self):
        try:
            speed = float(self._speed_var.get())
            self._engine.set_speed(speed)
            self._status_var.set(_trf("status.speed", speed=speed))
        except (ValueError, tk.TclError):
            pass

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
        cur_str = f"{int(target // 60)}:{int(target % 60):02d}"
        tot_str = f"{int(total // 60)}:{int(total % 60):02d}"
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
        cur_str = f"{int(target // 60)}:{int(target % 60):02d}"
        tot_str = f"{int(total // 60)}:{int(total % 60):02d}"
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

    def _toggle_language(self):
        """Toggle between Chinese and English interface."""
        new_lang = "en" if get_language() == "zh" else "zh"

        # Sync current state to settings before destroying widgets
        self._sync_settings_to_object()
        self._settings.language = new_lang
        set_language(new_lang)

        # Cancel update timer to avoid referencing destroyed widgets
        if self._update_id is not None:
            self.root.after_cancel(self._update_id)
            self._update_id = None

        # Destroy all existing widgets and rebuild UI
        for child in self.root.winfo_children():
            child.destroy()

        self._build_ui()
        self._update_timer()

    def _toggle_local(self):
        enabled = self._local_audio_var.get()
        self._local_synth.enabled = enabled
        self._synth_port_var.set(self._local_synth.get_port_name())
        self._status_var.set(
            _tr("status.local_on") if enabled else _tr("status.local_off")
        )

    def _toggle_virtual(self):
        enabled = self._virtual_var.get()
        if enabled and not self._virtual_midi.get_port_name().startswith("Not"):
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
        self._note_on_count += 1
        vel = self._get_scaled_velocity(note_event.velocity)
        transpose = self._settings.playback_transpose
        self._dispatch_note_to_outputs(
            "note_on", note_event.note + transpose, vel, note_event.channel
        )

    def _on_note_off(self, note_event):
        self._note_off_count += 1
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

    # ===================== MIDI Input =====================

    def _toggle_midi_input(self):
        enabled = self._midi_input_var.get()
        # Apply the selected port before toggling
        port = self._midi_input_port_var.get().strip()
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
            dur_str = (
                f"{int(entry.duration_sec // 60)}:{int(entry.duration_sec % 60):02d}"
            )
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

        # Show/hide placeholder
        if self._library.count == 0:
            self._lib_placeholder.pack(fill=tk.BOTH, expand=True)
        else:
            self._lib_placeholder.pack_forget()

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
        """Remove the currently selected entry from the library."""
        sel = self._lib_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        entry = self._library.get_by_index(idx)
        if entry is None:
            return
        self._library.remove_index(idx)
        self._library_refresh_tree()
        self._status_var.set(_trf("library.removed", title=entry.title))

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
            self._lib_tree.selection_set(item)
            self._lib_context.post(event.x_root, event.y_root)

    def _load_file_by_path(self, path: str):
        """Load a MIDI file by its path (used by library)."""
        data = parse_midi(path)
        if data is None:
            self._status_var.set(_trf("status.load_failed", path=path))
            return

        self._apply_loaded_midi(data, path)

    # ===================== Timer for progress =====================

    def _toggle_piano(self):
        """Toggle piano roll visualization on/off."""
        pass  # Controlled by _update_timer's conditional check

    def _update_timer(self):
        if self._engine.is_playing and not self._engine.is_paused:
            current = self._engine.current_time
            total = self._engine.total_duration
            if total > 0:
                self._progress_bar["value"] = current
                cur_str = f"{int(current // 60)}:{int(current % 60):02d}"
                tot_str = f"{int(total // 60)}:{int(total % 60):02d}"
                self._time_label.config(text=f"{cur_str} / {tot_str}")
                # Update piano roll if enabled
                if (
                    hasattr(self, "_piano_enabled_var")
                    and self._piano_enabled_var.get()
                ):
                    active = self._engine.get_active_notes()
                    self._piano_roll.update_playback(current, active)
        self._update_id = self.root.after(50, self._update_timer)

    # ===================== Run =====================

    def _on_close(self):
        """Save settings and close the application."""
        self._sync_settings_to_object()
        save_settings(self._settings)
        self._engine.stop()
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
        """Called periodically from the engine thread (~100ms) to update progress.

        Uses ``root.after(0, ...)`` to safely schedule the UI update on the
        main thread, keeping the progress bar smooth during long silent gaps.
        """
        try:
            self.root.after(0, self._update_timer)
        except tk.TclError:
            pass  # window was destroyed

    def run(self):
        self.root.mainloop()
