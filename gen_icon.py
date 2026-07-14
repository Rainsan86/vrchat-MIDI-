"""Generate app_icon.ico — sakura pink piano icon (BMP ICO for Explorer drag/cache)."""
from __future__ import annotations

import os
import struct

from midi_show.icon_art import ACCENT, draw_piano_icon


def _rgba_to_icon_dib(img) -> bytes:
    """Build a 32bpp BI_RGB DIB (bottom-up XOR + AND mask) for classic ICO compatibility."""
    from PIL import Image

    img = img.convert("RGBA")
    w, h = img.size
    pixels = img.load()

    row_xor = w * 4
    xor = bytearray(row_xor * h)
    for y in range(h):
        src_y = h - 1 - y
        row = y * row_xor
        for x in range(w):
            r, g, b, a = pixels[x, src_y]
            i = row + x * 4
            xor[i] = b
            xor[i + 1] = g
            xor[i + 2] = r
            xor[i + 3] = a

    and_stride = ((w + 31) // 32) * 4
    and_mask = bytearray(and_stride * h)
    for y in range(h):
        src_y = h - 1 - y
        for x in range(w):
            if pixels[x, src_y][3] < 128:
                byte_index = y * and_stride + (x // 8)
                and_mask[byte_index] |= 0x80 >> (x % 8)

    header = struct.pack(
        "<IIIHHIIIIII",
        40,
        w,
        h * 2,
        1,
        32,
        0,
        len(xor),
        0,
        0,
        0,
        0,
    )
    return header + bytes(xor) + bytes(and_mask)


def save_bmp_ico(path: str, images: list) -> None:
    """Write a multi-size ICO using BMP/DIB entries (not PNG) for Explorer drag reliability."""
    entries = []
    blobs = []
    offset = 6 + 16 * len(images)
    for im in images:
        w, h = im.size
        dib = _rgba_to_icon_dib(im)
        blobs.append(dib)
        entries.append(
            struct.pack(
                "<BBBBHHII",
                0 if w >= 256 else w,
                0 if h >= 256 else h,
                0,
                0,
                1,
                32,
                len(dib),
                offset,
            )
        )
        offset += len(dib)

    with open(path, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, len(images)))
        for e in entries:
            f.write(e)
        for b in blobs:
            f.write(b)


def main() -> None:
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [draw_piano_icon(sz) for sz in sizes]
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.ico")
    save_bmp_ico(out, images)
    images[-1].save(os.path.join(os.path.dirname(out), "app_icon_preview.png"))
    print(f"Generated {out} ({os.path.getsize(out)} bytes, BMP ICO, sakura {ACCENT})")
    print(f"Sizes: {sizes}")


if __name__ == "__main__":
    main()
