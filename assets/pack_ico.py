"""Tiny stdlib-only ICO packer — rebuild ``brain.ico`` from ``brain.png``.

Used when ImageMagick / Pillow are unavailable (e.g. the dev laptop that
produced the committed ``brain.ico``). On Linux prefer ImageMagick's
``magick convert ... -define icon:auto-resize=16,32,48,256``.

Usage:
    python3 assets/pack_ico.py assets/brain.ico 16 32 48 256

The PNG for each size is resampled from ``<out>.parent / "brain.png"``
via ``sips`` on macOS. Override by editing ``_resample`` if you're not on
a Mac.

ICO format (ICONDIR + ICONDIRENTRY[] + PNG blobs):
  ICONDIR:       6 bytes  (reserved=0, type=1, count)
  ICONDIRENTRY: 16 bytes each (width, height, colors, reserved, planes,
                 bitcount, size, offset) — width/height 0 means 256+
  Image data:   raw PNG bytes (Vista+ supports embedded PNG)
"""

from __future__ import annotations

import struct
import subprocess
import sys
import tempfile
from pathlib import Path


def _resample(master: Path, size: int, dest: Path) -> None:
    """Write ``master`` resampled to ``size``×``size`` at ``dest`` (uses ``sips``)."""
    subprocess.run(
        ["sips", "-z", str(size), str(size), str(master), "--out", str(dest)],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def pack_ico(master_png: Path, out_path: Path, sizes: list[int]) -> None:
    """Build ``out_path`` from ``master_png`` resampled to each size in ``sizes``."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        entries: list[tuple[int, bytes]] = []
        for size in sizes:
            png = tmp / f"brain_{size}.png"
            _resample(master_png, size, png)
            entries.append((size, png.read_bytes()))

    header = struct.pack("<HHH", 0, 1, len(entries))
    dir_size = 16 * len(entries)
    offset = 6 + dir_size

    dir_blob = b""
    data_blob = b""
    for size, data in entries:
        w = size if size < 256 else 0  # 0 encodes "256+" in the ICO spec.
        dir_blob += struct.pack(
            "<BBBBHHII",
            w,       # width
            w,       # height
            0,       # color count (0 = 256+ or true color)
            0,       # reserved
            1,       # color planes
            32,      # bits per pixel
            len(data),  # byte size of image data
            offset,     # offset to image data
        )
        data_blob += data
        offset += len(data)

    out_path.write_bytes(header + dir_blob + data_blob)


def main(argv: list[str]) -> None:
    if len(argv) < 3:
        print(
            "usage: pack_ico.py <brain.ico> <size> [<size> ...]",
            file=sys.stderr,
        )
        sys.exit(2)

    out = Path(argv[1])
    sizes = [int(s) for s in argv[2:]]
    master = out.parent / "brain.png"
    if not master.exists():
        print(f"error: master PNG not found at {master}", file=sys.stderr)
        sys.exit(1)

    pack_ico(master, out, sizes)
    print(f"wrote {out} ({out.stat().st_size} bytes, {len(sizes)} sizes)")


if __name__ == "__main__":
    main(sys.argv)
