"""Single sakura piano icon artwork shared by ICO generation and the window title icon."""

from __future__ import annotations

from PIL import Image, ImageDraw

# Match UI theme accent in midi_show/ui.py
ACCENT = "#E87A9A"
ACCENT_DARK = "#C45A7A"
KEY_OUTLINE = "#F3D9E4"
BLACK_KEY = "#3D3647"
BLACK_OUTLINE = "#2A2433"

MASTER_SIZE = 256


def draw_piano_icon_master(size: int = MASTER_SIZE) -> Image.Image:
    """Draw the canonical icon at any size with the same proportions."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size / MASTER_SIZE

    pad = max(1, int(8 * s))
    radius = max(2, int(40 * s))
    draw.rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=radius,
        fill=ACCENT,
        outline=ACCENT_DARK,
        width=max(1, int(3 * s)),
    )

    key_w = max(2, int(28 * s))
    gap = max(1, int(3 * s))
    n_keys = 7
    total_w = n_keys * key_w + (n_keys - 1) * gap
    start_x = (size - total_w) // 2
    key_top = max(pad + 1, int(56 * s))
    key_bot = size - max(pad + 1, int(20 * s))

    for i in range(n_keys):
        x = start_x + i * (key_w + gap)
        draw.rectangle(
            [x, key_top, x + key_w, key_bot],
            fill="#ffffff",
            outline=KEY_OUTLINE,
            width=max(1, int(1 * s)),
        )

    black_positions = [0, 1, 3, 4, 5]
    bk_w = max(1, int(16 * s))
    bk_bot = max(key_top + 1, int(155 * s))
    for i in black_positions:
        x = start_x + i * (key_w + gap) + key_w - max(1, int(5 * s))
        draw.rectangle(
            [x, key_top, x + bk_w, bk_bot],
            fill=BLACK_KEY,
            outline=BLACK_OUTLINE,
            width=max(1, int(1 * s)),
        )

    # Musical note (skip only when impossibly tiny)
    if size >= 20:
        note_cx = int(128 * s)
        note_cy = int(34 * s)
        note_r = max(1, int(9 * s))
        draw.ellipse(
            [note_cx - note_r, note_cy - note_r, note_cx + note_r, note_cy + note_r],
            fill="#ffffff",
        )
        stem_w = max(1, int(3 * s))
        stem_top = max(1, int(12 * s))
        draw.line(
            [note_cx + note_r - 1, note_cy, note_cx + note_r - 1, stem_top],
            fill="#ffffff",
            width=stem_w,
        )
    return img


def draw_piano_icon(size: int) -> Image.Image:
    """
    Icon of the requested size.

    Small sizes are downscaled from the master artwork so every surface
    (desktop / taskbar / title bar) shows the same piano design.
    """
    if size <= 0:
        raise ValueError("size must be positive")
    if size == MASTER_SIZE:
        return draw_piano_icon_master(MASTER_SIZE)
    if size >= 48:
        return draw_piano_icon_master(size)
    master = draw_piano_icon_master(MASTER_SIZE)
    resample = getattr(Image, "Resampling", Image).LANCZOS
    return master.resize((size, size), resample)
