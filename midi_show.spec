# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for MIDI Show - VRChat MIDI Player

Usage:
    pip install pyinstaller
    pyinstaller midi_show.spec

Or use the build script:
    build_exe.bat
"""

from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
from PyInstaller.utils.hooks import collect_all
import sys
import os

block_cipher = None

# Determine the project root directory
PROJECT_ROOT = os.path.abspath('.')

# Bundle tkinterdnd2 native tkdnd files for drag-and-drop
_tkdnd_datas, _tkdnd_binaries, _tkdnd_hidden = collect_all("tkinterdnd2")

a = Analysis(
    ['main.py'],
    pathex=[PROJECT_ROOT],
    binaries=_tkdnd_binaries,
    datas=[
        # Include sample config files for reference
        ('midi_show_config.sample.json', '.'),
        ('midi_show_library.sample.json', '.'),
        # Same icon file used by window/taskbar so colors match the desktop shortcut
        ('app_icon.ico', '.'),
    ] + _tkdnd_datas,
    hiddenimports=[
        'mido',
        'mido.backends',
        'mido.backends.rtmidi',
        'rtmidi',
        'pythonosc',
        'pythonosc.udp_client',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageTk',
        'tkinterdnd2',
    ] + _tkdnd_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'tkinter.test',
        'unittest',
        'pydoc',
        'doctest',
        'difflib',
        'lib2to3',
        'setuptools',
        'pip',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='VRChat_MIDI_Player',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI mode - no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.ico',
)