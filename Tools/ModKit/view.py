"""
Render a built GIMI mod folder to a PNG contact sheet, to LOOK at it.

    python Tools/ModKit/view.py <mod folder> <Name> --out sheet.png
           [--yaw 0 90 180 270] [--pitch 0] [--bounds x0 x1 y0 y1] [--size 600 900]
           [--comps Head Body Dress] [--mark] [--bg 0 200 0] [--plain] [--stride 12] [--ssaa 2]

--mark paints back faces magenta, --bg picks a background that makes holes obvious,
--plain ignores textures (grey), --bounds is in view space (x right, y up) after the yaw.
"""

import argparse
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modkit.gimi import Mesh  # noqa: E402
from modkit.render import render, sheet  # noqa: E402


def read_tex(path):
    """RGBA float texture; reads the uncompressed DX10 files modkit writes, else falls back to Pillow"""
    with open(path, "rb") as f:
        b = f.read()
    if b[84:88] == b"DX10" and int.from_bytes(b[128:132], "little") in (28, 29):
        h, w = int.from_bytes(b[12:16], "little"), int.from_bytes(b[16:20], "little")
        return np.frombuffer(b, np.uint8, w * h * 4, 148).reshape(h, w, 4).astype(np.float32) / 255
    return np.asarray(Image.open(path).convert("RGBA"), np.float32) / 255


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("name")
    ap.add_argument("--out", required=True)
    ap.add_argument("--yaw", type=float, nargs="+", default=[0, 90, 180, 270])
    ap.add_argument("--pitch", type=float, default=0)
    ap.add_argument("--bounds", type=float, nargs=4)
    ap.add_argument("--size", type=int, nargs=2, default=[600, 900])
    ap.add_argument("--comps", nargs="+", default=["Head", "Body", "Dress"])
    ap.add_argument("--mark", action="store_true")
    ap.add_argument("--plain", action="store_true")
    ap.add_argument("--bg", type=int, nargs=3, default=[52, 52, 60])
    ap.add_argument("--stride", type=int, default=20, help="Texcoord.buf stride: 20, or 12 for characters with one UV set")
    ap.add_argument("--ssaa", type=int, default=1)
    a = ap.parse_args()
    m = Mesh.load(a.folder, a.name, a.comps, tex_stride=a.stride)
    tex = None if a.plain else [read_tex(os.path.join(a.folder, f"{a.name}{c}Diffuse.dds")) for c in a.comps]
    ims = [render(m.pos, m.nrm, list(m.comps.values()), size=tuple(a.size), yaw=y, pitch=a.pitch, uv=m.uv,
                  textures=tex, cull="mark" if a.mark else False, bg=tuple(a.bg),
                  bounds=tuple(a.bounds) if a.bounds else None, ssaa=a.ssaa) for y in a.yaw]
    sheet(ims, labels=a.yaw).save(a.out)
