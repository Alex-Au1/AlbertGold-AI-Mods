"""
Blender as a build step, run without its window. The recipe stays code: a part goes out as arrays, a script
under ``Tools/ModKit/blender/`` does one job on it inside Blender, and arrays come back.

Blender is found through the environment variable ``MODKIT_BLENDER`` (the path of blender.exe), else in the
usual install folder. ``find()`` returns None when there is none, and callers keep their hand-made shape.
"""
import glob
import os
import subprocess
import tempfile

import numpy as np

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "blender")


def find():
    exe = os.environ.get("MODKIT_BLENDER")
    if exe:
        return exe if os.path.isfile(exe) else None
    found = sorted(p for p in glob.glob(r"C:\Program Files\Blender Foundation\*\blender.exe"))
    return found[-1] if found else None


def _weld(pos, tris, tol=1e-4):
    _, first, wi = np.unique(np.round(pos / tol).astype(np.int64), axis=0, return_index=True, return_inverse=True)
    wi = wi.reshape(-1)
    t = wi[tris]
    t = t[(t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])]
    return pos[first].astype(np.float64), t, wi


def cloth_drape(part, colliders, pin, frames=60, grow=0.04, dist=0.004, bend=0.5, quality=10, exe=None):
    """
    let a part settle as cloth on the colliders (parts or (pos, tris) pairs) under gravity, in place.
    pin: per vertex, 0 = free ... 1 = held. grow: how much bigger than its starting shape the cloth is cut.
    Only positions change; the caller recomputes normals. Returns how far each vertex moved (metres).
    """
    exe = exe or find()
    if not exe:
        raise FileNotFoundError("Blender not found (set MODKIT_BLENDER)")
    pos, tris, wi = _weld(part["pos"], part["tris"])
    wpin = np.zeros(len(pos))
    np.maximum.at(wpin, wi, pin)
    data = {"pos": pos, "tris": tris, "pin": wpin, "params": np.array([frames, grow, dist, bend, quality], float)}
    for i, c in enumerate(colliders):
        cp, ct = (c["pos"], c["tris"]) if isinstance(c, dict) else c
        data[f"col_pos_{i}"], data[f"col_tris_{i}"], _ = _weld(np.asarray(cp), np.asarray(ct))
    with tempfile.TemporaryDirectory() as tmp:
        fin, fout = os.path.join(tmp, "in.npz"), os.path.join(tmp, "out.npy")
        np.savez(fin, **data)
        r = subprocess.run([exe, "--background", "--factory-startup", "--python", os.path.join(SCRIPTS, "cloth_drape.py"),
                            "--", fin, fout], capture_output=True, text=True)
        if not os.path.isfile(fout):
            raise RuntimeError("Blender's cloth step failed:\n" + r.stdout[-3000:] + r.stderr[-3000:])
        for line in r.stdout.splitlines():
            if line.startswith("cloth_drape:"):
                print("   blender", line)
        new = np.load(fout)
    moved = np.linalg.norm(new - pos, axis=1)[wi]
    part["pos"] = new[wi].astype(np.float32)
    return moved


def fbx_dump(fbx, out_npz, exe=None):  # also .dae, .obj, .blend (by extension)
    """
    read an .fbx (a model that is not a 3DMigoto dump) into arrays in the mod's coordinates: see
    ``Tools/ModKit/blender/fbx_dump.py`` for the keys. Returns the loaded npz. The FBX's unit is kept
    (Ever Crisis models come out 100 times too small: multiply positions by 100).
    """
    exe = exe or find()
    if not exe:
        raise FileNotFoundError("Blender not found (set MODKIT_BLENDER)")
    os.makedirs(os.path.dirname(os.path.abspath(out_npz)), exist_ok=True)
    r = subprocess.run([exe, "--background", "--factory-startup", "--python", os.path.join(SCRIPTS, "fbx_dump.py"),
                        "--", fbx, out_npz], capture_output=True, text=True)
    if not os.path.isfile(out_npz):
        raise RuntimeError("Blender's fbx step failed:\n" + r.stdout[-3000:] + r.stderr[-3000:])
    return np.load(out_npz)
