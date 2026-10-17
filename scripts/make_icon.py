"""Generate a multi-size CiscoMan .ico (switch / network motif) with stdlib only."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path


def _png(width: int, height: int, rgba: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b""
    stride = width * 4
    for y in range(height):
        raw += b"\x00" + rgba[y * stride : (y + 1) * stride]
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def _blend(dst, src, a: float):
    return tuple(int(d * (1 - a) + s * a) for d, s in zip(dst, src))


def _draw(size: int) -> bytes:
    """Dark rounded tile + switch chassis + port LEDs + 3-node mesh."""
    px = bytearray(size * size * 4)
    bg = (11, 31, 51)
    tile = (15, 42, 68)
    chassis = (20, 72, 86)
    led_on = (80, 220, 255)
    led_amber = (255, 186, 73)
    node = (96, 205, 255)

    def setp(x, y, rgb, a=255):
        if 0 <= x < size and 0 <= y < size:
            i = (y * size + x) * 4
            px[i : i + 4] = bytes((rgb[0], rgb[1], rgb[2], a))

    def getp(x, y):
        i = (y * size + x) * 4
        return (px[i], px[i + 1], px[i + 2])

    radius = max(2, size // 6)
    for y in range(size):
        for x in range(size):
            # rounded-rect mask
            cx = min(x, size - 1 - x)
            cy = min(y, size - 1 - y)
            inside = True
            if cx < radius and cy < radius:
                inside = (cx - radius) ** 2 + (cy - radius) ** 2 <= radius ** 2
            if inside:
                setp(x, y, tile)
            else:
                setp(x, y, bg, 0)

    # chassis
    x0, x1 = int(size * 0.16), int(size * 0.84)
    y0, y1 = int(size * 0.38), int(size * 0.68)
    for y in range(y0, y1):
        for x in range(x0, x1):
            setp(x, y, chassis)

    # port LEDs
    ports = 8 if size >= 32 else 4
    gap = max(1, (x1 - x0 - 2) // (ports + 1))
    led_y = (y0 + y1) // 2
    for i in range(ports):
        lx = x0 + 2 + gap * (i + 1)
        color = led_amber if i % 5 == 4 else led_on
        for dy in range(-1 if size >= 32 else 0, 2):
            for dx in range(-1 if size >= 32 else 0, 2):
                setp(lx + dx, led_y + dy, color)

    # three network nodes above the chassis
    nodes = [
        (size // 2, int(size * 0.22)),
        (int(size * 0.30), int(size * 0.30)),
        (int(size * 0.70), int(size * 0.30)),
    ]
    if size >= 24:
        # lines
        def line(a, b):
            x1_, y1_ = a
            x2_, y2_ = b
            steps = max(abs(x2_ - x1_), abs(y2_ - y1_)) or 1
            for s in range(steps + 1):
                x = x1_ + (x2_ - x1_) * s // steps
                y = y1_ + (y2_ - y1_) * s // steps
                setp(x, y, node)

        line(nodes[0], nodes[1])
        line(nodes[0], nodes[2])
        line(nodes[1], nodes[2])
        r = 2 if size >= 48 else 1
        for nx, ny in nodes:
            for y in range(ny - r, ny + r + 1):
                for x in range(nx - r, nx + r + 1):
                    if (x - nx) ** 2 + (y - ny) ** 2 <= r * r + 1:
                        setp(x, y, node)

    return bytes(px)


def write_ico(path: Path, sizes=(16, 24, 32, 48, 64, 128, 256)) -> None:
    images = []
    for s in sizes:
        images.append(_png(s, s, _draw(s)))

    # ICONDIR + entries + PNG payloads (Vista+ ICO)
    offset = 6 + 16 * len(images)
    entries = b""
    payload = b""
    for s, data in zip(sizes, images):
        w = 0 if s >= 256 else s
        h = 0 if s >= 256 else s
        entries += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(data), offset)
        payload += data
        offset += len(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack("<HHH", 0, 1, len(images)) + entries + payload)
    print(f"Wrote {path} ({path.stat().st_size} bytes, {len(images)} sizes)")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    write_ico(root / "ciscoman_gui" / "icon.ico")
    # also drop a 256 PNG next to it for docs / tray fallbacks
    png = _png(256, 256, _draw(256))
    (root / "ciscoman_gui" / "icon.png").write_bytes(png)
