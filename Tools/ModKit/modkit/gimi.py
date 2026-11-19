"""
Reading and writing a GIMI mod's buffers (Genshin Impact, the classic 40 / 32 / 20 byte layout).

A :class:`Mesh` holds one vertex pool and a dict of named components (``Head``, ``Body``, ``Dress``, ...),
each a (T, 3) triangle index array into that pool -- the same shape the game draws.
"""

import os
import numpy as np

POS_DTYPE = np.dtype([("pos", "<f4", 3), ("nrm", "<f4", 3), ("tan", "<f4", 4)])
BLEND_DTYPE = np.dtype([("w", "<f4", 4), ("i", "<i4", 4)])
TEX_DTYPE = np.dtype([("col", "u1", 4), ("uv", "<f4", 2), ("uv2", "<f4", 2)])
TEX12_DTYPE = np.dtype([("col", "u1", 4), ("uv", "<f4", 2)])     # characters with one UV set (Mavuika): stride 12


class Mesh:
    def __init__(self, pos, nrm, tan, w, vg, col, uv, uv2, comps):
        self.pos = np.asarray(pos, np.float32)
        self.nrm = np.asarray(nrm, np.float32)
        self.tan = np.asarray(tan, np.float32)
        self.w = np.asarray(w, np.float32)
        self.vg = np.asarray(vg, np.int32)
        self.col = np.asarray(col, np.uint8)
        self.uv = np.asarray(uv, np.float32)
        self.uv2 = np.asarray(uv2, np.float32)
        self.comps = {k: np.asarray(v, np.uint32).reshape(-1, 3) for k, v in comps.items()}

    @property
    def n(self):
        return len(self.pos)

    @classmethod
    def load(cls, folder, name, comps, tex_stride=20):
        """tex_stride: 20 (colour, uv, uv2) or 12 (colour, uv; uv2 is then a copy of uv)"""
        j = lambda f: os.path.join(folder, f)
        p = np.fromfile(j(name + "Position.buf"), POS_DTYPE)
        b = np.fromfile(j(name + "Blend.buf"), BLEND_DTYPE)
        t = np.fromfile(j(name + "Texcoord.buf"), TEX_DTYPE if tex_stride == 20 else TEX12_DTYPE)
        ibs = {c: np.fromfile(j(name + c + ".ib"), "<u4").reshape(-1, 3) for c in comps}
        return cls(p["pos"], p["nrm"], p["tan"], b["w"], b["i"], t["col"], t["uv"],
                   t["uv2"] if tex_stride == 20 else t["uv"].copy(), ibs)

    def save(self, folder, name, tex_stride=20):
        os.makedirs(folder, exist_ok=True)
        j = lambda f: os.path.join(folder, f)
        p = np.zeros(self.n, POS_DTYPE)
        p["pos"], p["nrm"], p["tan"] = self.pos, self.nrm, self.tan
        b = np.zeros(self.n, BLEND_DTYPE)
        b["w"], b["i"] = self.w, self.vg
        if tex_stride == 20:
            t = np.zeros(self.n, TEX_DTYPE)
            t["col"], t["uv"], t["uv2"] = self.col, self.uv, self.uv2
        else:
            t = np.zeros(self.n, TEX12_DTYPE)
            t["col"], t["uv"] = self.col, self.uv
        p.tofile(j(name + "Position.buf"))
        b.tofile(j(name + "Blend.buf"))
        t.tofile(j(name + "Texcoord.buf"))
        for c, ib in self.comps.items():
            ib.astype("<u4").tofile(j(name + c + ".ib"))

    def subset(self, vmask_or_idx):
        """vertex attribute dict for a selection (used when appending parts of one mesh to another)"""
        s = vmask_or_idx
        return dict(pos=self.pos[s], nrm=self.nrm[s], tan=self.tan[s], w=self.w[s], vg=self.vg[s],
                    col=self.col[s], uv=self.uv[s], uv2=self.uv2[s])


def islands(tris, n):
    """connected components over shared vertex indices; returns a label per vertex (-1 = unused)"""
    parent = np.arange(n)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b, c in tris:
        ra, rb, rc = find(a), find(b), find(c)
        parent[rb] = ra
        parent[rc] = ra
    used = np.zeros(n, bool)
    used[np.unique(tris)] = True
    lab = np.full(n, -1)
    roots = {}
    for v in np.nonzero(used)[0]:
        r = find(v)
        lab[v] = roots.setdefault(r, len(roots))
    return lab


def weld_islands(pos, tris, tol=1e-5):
    """like :func:`islands` but vertices at the same position count as one (UV seams do not split a part)"""
    key = np.round(pos / tol).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    lab_w = islands(inv[tris], inv.max() + 1)
    lab = lab_w[inv]
    used = np.zeros(len(pos), bool)
    used[np.unique(tris)] = True
    lab[~used] = -1
    return lab


def load_dump(vb_path, ib_path):
    """
    a 3DMigoto frame-analysis TEXT dump (the form GI-Model-Importer-Assets stores models in: ``<Name>-vb0=<hash>.txt``
    and ``<Name>-ib=<hash>.txt``) -> dict of arrays pos, nrm, tan, w, vg, col (0..1 floats), uv, uv2 over the whole
    vertex pool, and tris (the triangles of that one component)
    """
    import re
    names = {"POSITION": "pos", "NORMAL": "nrm", "TANGENT": "tan", "BLENDWEIGHT": "w", "BLENDINDICES": "vg",
             "COLOR": "col", "TEXCOORD": "uv", "TEXCOORD1": "uv2"}
    out = {v: [] for v in names.values()}
    rx = re.compile(r"^vb0\[(\d+)\]\+\d+ (\w+): (.*)$")
    with open(vb_path) as f:
        for line in f:
            m = rx.match(line)
            if m and m.group(2) in names:
                out[names[m.group(2)]].append([float(x) for x in m.group(3).split(",")])
    a = {k: np.array(v, np.float32) for k, v in out.items() if v}
    tris = []
    with open(ib_path) as f:
        for line in f:
            q = line.split()
            if len(q) == 3 and q[0].isdigit():
                tris.append([int(x) for x in q])
    a["tris"] = np.array(tris, np.int64)
    return a
