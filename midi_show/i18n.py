"""Internationalization (i18n) support for MIDI Show."""

from __future__ import annotations

from typing import Dict, Tuple

# Translation dictionary: key -> (en, zh)
_TRANSLATIONS: Dict[str, Tuple[str, str]] = {
    # ── Window title ──
    "window.title": (
        "MIDI Show - VRChat MIDI Player",
        "MIDI Show - VRChat MIDI 播放器",
    ),
    # ── Top buttons & labels ──
    "btn.load_midi": ("🎹 Load MIDI File", "🎹 加载 MIDI 文件"),
    "label.no_file": ("No file loaded", "未加载文件"),
    "btn.play": ("▶ Play", "▶ 播放"),
    "btn.pause": ("⏸ Pause", "⏸ 暂停"),
    "btn.resume": ("▶ Resume", "▶ 继续"),
    "btn.stop": ("⏹ Stop", "⏹ 停止"),
    "label.speed": ("Speed:", "速度:"),
    "label.speed_x": ("x", "倍"),
    "label.time_default": ("0:00 / 0:00", "0:00 / 0:00"),
    # ── Note count (default before loading) ──
    "note_count.default": (
        "Notes: 0 | Duration: 0:00 | Tempo: -- BPM",
        "音符: 0 | 时长: 0:00 | 速度: -- BPM",
    ),
    # ── Tabs ──
    "tab.output": ("Output Settings", "输出设置"),
    "tab.track_filter": ("Track Filter", "轨道滤波器"),
    "tab.how_to_use": ("How to Use", "使用帮助"),
    # ── Track Filter ──
    "track.no_tracks": (
        "Load a MIDI file to see tracks here.",
        "加载 MIDI 文件后在此显示轨道。",
    ),
    "track.mute": ("M", "M"),
    "track.solo": ("S", "S"),
    "track.unmute": ("Unmute", "取消静音"),
    "track.unsolo": ("Unsolo", "取消独奏"),
    "track.solo_active": (
        "Solo mode: only soloed tracks will play",
        "独奏模式：仅播放选了独奏的轨道",
    ),
    "track.num_notes": ("{n} notes", "{n} 个音符"),
    "track.column_name": ("Track Name", "轨道名称"),
    "track.column_notes": ("Notes", "音符数"),
    # ── Output: Local Audio ──
    "output.local_audio": (
        "Local Audio (Windows Synthesizer)",
        "本地音频 (Windows 合成器)",
    ),
    # ── Output: Virtual MIDI ──
    "output.virtual_midi": (
        "Virtual MIDI Port (for VRChat world)",
        "虚拟 MIDI 端口 (用于 VRChat 世界)",
    ),
    "output.port": ("Port:", "端口:"),
    "output.refresh": ("Refresh", "刷新"),
    "output.apply": ("Apply", "应用"),
    # ── Output: Volume ──
    "output.volume": ("Volume:", "音量:"),
    "output.volume_muted": ("Muted", "已静音"),
    # ── Output: OSC ──
    "output.osc": (
        "OSC Output (for VRChat Avatar)",
        "OSC 输出 (用于 VRChat 虚拟人物)",
    ),
    "output.address": ("Address:", "地址:"),
    "output.mode": ("Mode:", "模式:"),
    "output.osc_mode_piano": (
        "/PianoKeys/ (Piano Avatar)",
        "/PianoKeys/ (钢琴虚拟人物)",
    ),
    "output.osc_mode_avatar": (
        "/avatar/parameters/ (Custom Avatar)",
        "/avatar/parameters/ (自定义虚拟人物)",
    ),
    # ── MIDI Input ──
    "midi.input": (
        "MIDI Input (Live Passthrough)",
        "MIDI 输入 (实时直通)",
    ),
    "midi.input_port": ("MIDI In Port:", "MIDI 输入端口:"),
    "midi.passthrough": ("Live MIDI Passthrough", "实时 MIDI 直通"),
    # ── Status bar ──
    "status.ready": (
        "Ready. Load a MIDI file to start.",
        "就绪。加载 MIDI 文件开始播放。",
    ),
    "status.playing": ("Playing...", "播放中..."),
    "status.paused": ("Paused", "已暂停"),
    "status.stopped": ("Stopped", "已停止"),
    "status.seeking": ("Seeking...", "拖动中..."),
    "status.finished": ("Playback finished", "播放结束"),
    # ── File dialog ──
    "dialog.select_midi": ("Select MIDI file", "选择 MIDI 文件"),
    "dialog.midi_files": ("MIDI files", "MIDI 文件"),
    "dialog.all_files": ("All files", "所有文件"),
    "dialog.playback_in_progress": ("Please Stop Playback", "请先停止播放"),
    "dialog.switch_lang_stop_playback": (
        "Please stop the song before switching language.",
        "请先停止歌曲，再进行语言切换。",
    ),
    # ── Status: initial ready ──
    "status.ready_short": ("Ready", "就绪"),
    # ── Library tab ──
    "tab.library": ("My Library", "我的曲库"),
    "library.empty": (
        "Library is empty.\nClick 'Add Files' to import MIDI files.",
        "曲库为空。\n点击「添加文件」导入 MIDI 文件。",
    ),
    "library.add_files": ("+ Add Files", "＋ 添加文件"),
    "library.add_folder": ("+ Add Folder", "＋ 添加文件夹"),
    "library.remove": ("Remove", "移除"),
    "library.play": ("Play", "播放"),
    "library.clear_all": ("Clear All", "清空"),
    "library.file_not_found": ("File not found: {path}", "文件不存在: {path}"),
    "library.already_exists": ("Already in library: {path}", "已在曲库中: {path}"),
    "library.added": ("Added {count} file(s)", "已添加 {count} 首"),
    "library.removed": ("Removed: {title}", "已移除: {title}"),
    "library.playing": ("Now playing: {title}", "正在播放: {title}"),
    "library.column.title": ("Title", "标题"),
    "library.column.duration": ("Duration", "时长"),
    "library.column.bpm": ("BPM", "BPM"),
    "library.column.notes": ("Notes", "音符数"),
    "library.no_midi_found": (
        "No MIDI files found in this folder",
        "未找到 MIDI 文件",
    ),
    "library.confirm_clear": (
        "Clear all {count} items from library?",
        "确认清空全部 {count} 首曲目？",
    ),
    # ── Language button ──
    "btn.lang": ("中/EN", "中/EN"),
    # ── Output: Apply (OSC address) ──
    "output.apply_osc": ("Apply", "应用"),
    # ── MIDI: Refresh ──
    "midi.refresh": ("Refresh", "刷新"),
    # ── Status bar (parameterized) ──
    "status.speed": ("Speed: {speed}x", "速度: {speed}倍"),
    "status.loaded": (
        "Loaded: {filename} ({count} notes)",
        "已加载: {filename} ({count} 个音符)",
    ),
    "status.load_failed": ("Failed to load: {path}", "加载失败: {path}"),
    "status.local_on": ("Local audio ON", "本地音频已开"),
    "status.local_off": ("Local audio OFF", "本地音频已关"),
    "status.virtual_on": ("Virtual MIDI ON: {port}", "虚拟 MIDI 已开: {port}"),
    "status.virtual_off": ("Virtual MIDI OFF", "虚拟 MIDI 已关"),
    "status.virtual_no_ports": (
        "No MIDI output ports found. Install LoopMIDI first.",
        "未找到 MIDI 输出端口。请先安装 LoopMIDI。",
    ),
    "status.virtual_refresh": (
        "Found {count} MIDI output(s). Select one from the dropdown and Apply.",
        "找到 {count} 个 MIDI 输出。请从下拉列表中选择一个并点击应用。",
    ),
    "status.virtual_no_ports_short": (
        "No MIDI output ports found. Install LoopMIDI.",
        "未找到 MIDI 输出端口。请安装 LoopMIDI。",
    ),
    "status.virtual_applied": (
        "Virtual port set to: {name}",
        "虚拟端口已设置为: {name}",
    ),
    "status.osc_on": ("OSC output ON", "OSC 输出已开"),
    "status.osc_off": ("OSC output OFF", "OSC 输出已关"),
    "status.osc_addr_set": (
        "OSC address set to {ip}:{port}",
        "OSC 地址已设置为 {ip}:{port}",
    ),
    "status.osc_addr_invalid": (
        "Invalid OSC address. Use format: IP:PORT",
        "无效的 OSC 地址。请使用格式: IP:PORT",
    ),
    "status.osc_mode": ("OSC mode: {mode}", "OSC 模式: {mode}"),
    "status.midi_input_on": ("MIDI Input ON", "MIDI 输入已开"),
    "status.midi_input_off": ("MIDI Input OFF", "MIDI 输入已关"),
    "status.passthrough_on": ("Live MIDI Passthrough ON", "实时 MIDI 直通已开"),
    "status.passthrough_off": ("Live MIDI Passthrough OFF", "实时 MIDI 直通已关"),
    "status.passthrough_active": (
        "Live forwarding to all outputs",
        "实时转发到所有输出",
    ),
    # ── MIDI Input Transpose ──
    "midi.input_transpose": (
        "Input Transpose:",
        "输入移调:",
    ),
    "midi.input_transpose_hint": (
        "Shift MIDI input notes by ±{n} semitones",
        "将 MIDI 输入音符移调 ±{n} 个半音",
    ),
    # ── Playback Transpose ──
    "playback.transpose": (
        "Transpose:",
        "移调:",
    ),
    "playback.transpose_hint": (
        "Shift playback notes by ±{n} semitones",
        "将播放音符移调 ±{n} 个半音",
    ),
    "status.transpose_set": (
        "Playback transpose: {n} semitones",
        "播放移调: {n} 个半音",
    ),
    "status.midi_input_transpose_set": (
        "MIDI input transpose: {n} semitones",
        "MIDI 输入移调: {n} 个半音",
    ),
    "label.semitones": ("st", "半音"),
    # ── Note count display ──
    "note_count.format": (
        "Notes: {count} | Tracks: {tracks} | Duration: {dur} | Tempo: {bpm} BPM",
        "音符: {count} | 轨道: {tracks} | 时长: {dur} | 节奏: {bpm} BPM",
    ),
    # ── Time display ──
    "time.format": ("{cur} / {tot}", "{cur} / {tot}"),
    # ── Buttons: dynamic state text ──
    "btn.pause_text": ("⏸ Pause", "⏸ 暂停"),
    "btn.resume_text": ("▶ Resume", "▶ 继续"),
    # ── Help tab content (zh) ──
    "help.content": (
        "MIDI Show — VRChat MIDI Player\n\n"
        "How to use in VRChat:\n\n"
        "1. Local Audio:\n"
        "   Plays MIDI through your computer speakers.\n"
        "   Uses Microsoft GS Wavetable Synth.\n\n"
        "2. Virtual MIDI Port (VRChat World):\n"
        "   - Install LoopMIDI (free) and create a virtual port\n"
        "   - In VRChat, visit a world with VRC Midi Listener\n"
        "   - Enable Virtual MIDI output in this tool\n"
        "   - Notes will be sent to the world in real-time\n\n"
        "3. OSC Output (VRChat Avatar):\n"
        "   - Enable OSC in VRChat settings\n"
        "   - Select OSC mode in this tool:\n"
        "     - /PianoKeys/ mode: for piano avatars (Kade's Piano, etc.)\n"
        "     - /avatar/parameters/ mode: for custom avatar parameters\n"
        "   - Your avatar needs matching float parameters\n\n"
        "4. Try our example VRChat world:\n"
        "   Search 'MIDI Show Piano' in VRChat world menu",
        "MIDI Show — VRChat MIDI 播放器\n\n"
        "如何在 VRChat 中使用：\n\n"
        "1. 本地音频：\n"
        "   通过电脑扬声器播放 MIDI。\n"
        "   使用 Microsoft GS Wavetable Synth。\n\n"
        "2. 虚拟 MIDI 端口（VRChat 世界）：\n"
        "   - 安装 LoopMIDI（免费）并创建一个虚拟端口\n"
        "   - 在 VRChat 中进入支持 VRC Midi Listener 的世界\n"
        "   - 在此工具中启用虚拟 MIDI 输出\n"
        "   - 音符将实时发送到世界\n\n"
        "3. OSC 输出（VRChat 虚拟人物）：\n"
        "   - 在 VRChat 设置中启用 OSC\n"
        "   - 在此工具中选择 OSC 模式：\n"
        "     - /PianoKeys/ 模式：用于钢琴虚拟人物\n"
        "     - /avatar/parameters/ 模式：用于自定义虚拟人物参数\n"
        "   - 你的虚拟人物需要有匹配的浮点参数\n\n"
        "4. 尝试我们的示例 VRChat 世界：\n"
        "   在 VRChat 世界菜单中搜索 'MIDI Show Piano'",
    ),
}

_current_lang: str = "zh"


def set_language(lang: str) -> None:
    """Set current language ('en' or 'zh')."""
    global _current_lang
    if lang in ("en", "zh"):
        _current_lang = lang


def get_language() -> str:
    """Get current language code."""
    return _current_lang


def tr(key: str) -> str:
    """Return translated text for the given key in the current language."""
    pair = _TRANSLATIONS.get(key)
    if pair is None:
        return key
    return pair[1] if _current_lang == "zh" else pair[0]


def trf(key: str, **kwargs) -> str:
    """Translate and format with keyword arguments.

    Usage: trf("status.speed", speed=1.5) -> "Speed: 1.5x" / "速度: 1.5倍"
    """
    return tr(key).format(**kwargs)
