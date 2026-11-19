"""
Mesh-building helpers: parts, parametric surfaces, mirroring, weight transfer, UV-space baking, .dds writing.

A *part* is a plain dict of arrays -- ``pos nrm tan w vg col uv uv2`` per vertex and ``tris`` (T, 3) local
indices -- so a recipe can cut, generate and join pieces before :func:`assemble` packs them into a
:class:`modkit.gimi.Mesh`.
"""

import struct
import numpy as np
from .gimi import Mesh

VKEYS = ("pos", "nrm", "tan", "w", "vg", "col", "uv", "uv2")


# ---------------------------------------------------------------- parts

def part_from_mesh(mesh, tris):
    """cut the triangles ``tris`` (global indices) out of a mesh as a part, with compacted vertices"""
    used, inv = np.unique(tris, return_inverse=True)
    p = mesh.subset(used)
    p = {k: v.copy() for k, v in p.items()}
    p["tris"] = inv.reshape(-1, 3).astype(np.int64)
    p["src"] = used
    return p


def new_part(pos, tris, uv, col=(255, 128, 128, 128)):
    n = len(pos)
    p = dict(pos=np.asarray(pos, np.float32), tris=np.asarray(tris, np.int64),
             uv=np.asarray(uv, np.float32), uv2=np.asarray(uv, np.float32).copy(),
             col=np.tile(np.array(col, np.uint8), (n, 1)),
             w=np.zeros((n, 4), np.float32), vg=np.zeros((n, 4), np.int32))
    p["nrm"] = compute_normals(p["pos"], p["tris"])
    p["tan"] = compute_tangents(p["pos"], p["nrm"], p["uv"], p["tris"])
    return p


def join(parts):
    out = {k: np.concatenate([p[k] for p in parts]) for k in VKEYS}
    off, tl = 0, []
    for p in parts:
        tl.append(p["tris"] + off)
        off += len(p["pos"])
    out["tris"] = np.concatenate(tl)
    return out


def assemble(comps):
    """comps: dict name -> part (or list of parts). Returns a Mesh with one shared vertex pool."""
    arrs = {k: [] for k in VKEYS}
    ibs, off = {}, 0
    for name, p in comps.items():
        if isinstance(p, (list, tuple)):
            p = join(p)
        for k in VKEYS:
            arrs[k].append(p[k])
        ibs[name] = (p["tris"] + off).astype(np.uint32)
        off += len(p["pos"])
    a = {k: np.concatenate(v) for k, v in arrs.items()}
    return Mesh(a["pos"], a["nrm"], a["tan"], a["w"], a["vg"], a["col"], a["uv"], a["uv2"], ibs)


def mirror_part(p, vgmap):
    """mirror a part across x = 0; vgmap maps each vertex group to its other-side twin (missing = itself)"""
    q = {k: v.copy() for k, v in p.items()}
    q["pos"][:, 0] *= -1
    q["nrm"][:, 0] *= -1
    q["tan"][:, 0] *= -1
    q["tris"] = q["tris"][:, ::-1].copy()
    lut = np.arange(max(int(p["vg"].max()) + 1, max(list(vgmap) + [0]) + 1))
    for a, b in vgmap.items():
        lut[a] = b
    q["vg"] = lut[p["vg"]].astype(np.int32)
    return q


# ---------------------------------------------------------------- geometry

def compute_normals(pos, tris):
    """area-weighted vertex normals; a front face is counter-clockwise (cross(p1 - p0, p2 - p0) points out)"""
    p = pos[tris]
    fn = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    n = np.zeros_like(pos, dtype=np.float64)
    for i in range(3):
        np.add.at(n, tris[:, i], fn)
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    return n.astype(np.float32)


def compute_tangents(pos, nrm, uv, tris):
    p, t = pos[tris], uv[tris]
    e1, e2 = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]
    d1, d2 = t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]
    det = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
    det = np.where(np.abs(det) < 1e-12, 1e-12, det)
    tg = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / det[:, None]
    acc = np.zeros_like(pos, dtype=np.float64)
    for i in range(3):
        np.add.at(acc, tris[:, i], tg)
    acc -= nrm * np.einsum("ij,ij->i", acc, nrm)[:, None]
    ln = np.linalg.norm(acc, axis=1, keepdims=True)
    bad = ln[:, 0] < 1e-9
    acc[bad] = np.cross(nrm[bad], [0, 1, 0]) + 1e-6
    acc /= np.linalg.norm(acc, axis=1, keepdims=True)
    out = np.empty((len(pos), 4), np.float32)
    out[:, :3] = acc
    out[:, 3] = -1.0
    return out


def grid_surface(P, uv_rect, closed=False, flip=False):
    """
    a (R, C, 3) grid of points -> vertices, triangles and UVs.

    rows run along v (top to bottom of ``uv_rect`` = (u0, v0, u1, v1)), columns along u. ``closed`` joins
    the last column back to the first (the seam column is duplicated so its UVs stay continuous).
    """
    R, C, _ = P.shape
    if closed:
        P = np.concatenate([P, P[:, :1]], 1)
        C += 1
    u0, v0, u1, v1 = uv_rect
    uu, vv = np.meshgrid(np.linspace(u0, u1, C), np.linspace(v0, v1, R))
    idx = np.arange(R * C).reshape(R, C)
    a, b, c, d = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, :-1].ravel(), idx[1:, 1:].ravel()
    tris = np.concatenate([np.stack([a, c, b], 1), np.stack([b, c, d], 1)])
    if flip:
        tris = tris[:, ::-1]
    return P.reshape(-1, 3), tris, np.stack([uu.ravel(), vv.ravel()], 1)


def weld_normals(p, tol=1e-5):
    """average the normals of vertices that share a position (hides a UV seam's shading break)"""
    key = np.round(p["pos"] / tol).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    acc = np.zeros((inv.max() + 1, 3))
    np.add.at(acc, inv, p["nrm"])
    acc /= np.linalg.norm(acc, axis=1, keepdims=True) + 1e-12
    p["nrm"] = acc[inv].astype(np.float32)


def catmull_closed(pts, n):
    """n points along a closed Catmull-Rom spline through pts"""
    pts = np.asarray(pts, float)
    k = len(pts)
    out = []
    for i in range(n):
        t = i / n * k
        j = int(t)
        f = t - j
        p0, p1, p2, p3 = pts[(j - 1) % k], pts[j % k], pts[(j + 1) % k], pts[(j + 2) % k]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f * f
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * f ** 3))
    return np.array(out)


def radial_envelope(pos, tris, cx, cz, ys, thetas):
    """
    cast horizontal rays outward from the vertical axis (cx, cz) and return, per height and angle, the
    distance to the OUTERMOST triangle hit (nan where a ray hits nothing): the outline of a body, from
    which a garment that wraps it can be generated.
    """
    P = pos[tris].astype(np.float64)
    v0, e1, e2 = P[:, 0], P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]
    ymin, ymax = P[:, :, 1].min(1), P[:, :, 1].max(1)
    out = np.full((len(ys), len(thetas)), np.nan)
    for i, y in enumerate(ys):
        sel = (ymin <= y) & (ymax >= y)
        if not sel.any():
            continue
        a0, b1, b2 = v0[sel], e1[sel], e2[sel]
        sv = np.array([cx, y, cz]) - a0
        q = np.cross(sv, b1)
        for j, th in enumerate(thetas):
            d = np.array([np.sin(th), 0.0, np.cos(th)])
            hh = np.cross(d, b2)
            det = (b1 * hh).sum(1)
            ok = np.abs(det) > 1e-12
            inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
            u = (sv * hh).sum(1) * inv
            v = (q @ d) * inv
            t = (b2 * q).sum(1) * inv
            hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0)
            if hit.any():
                out[i, j] = t[hit].max()
    return out


def clip_part(part, fn):
    """
    cut a part along the surface fn(pos) = 0, keeping the side where fn >= 0. Triangles crossing the cut are
    split exactly on it (new vertices interpolate every attribute; blend weights keep the heaviest four), so
    the cut edge is a clean line whatever the mesh's own triangulation.
    """
    f = fn(part["pos"])
    n0 = len(part["pos"])
    new = {k: [] for k in VKEYS}
    cache, tris = {}, []
    ng = int(part["vg"].max()) + 1

    def cut(i, j):
        key = (min(i, j), max(i, j))
        if key not in cache:
            t = f[i] / (f[i] - f[j])
            for k in ("pos", "nrm", "tan", "uv", "uv2"):
                new[k].append(part[k][i] * (1 - t) + part[k][j] * t)
            new["col"].append(np.round(part["col"][i] * (1 - t) + part["col"][j] * t))
            d = np.zeros(ng, np.float32)
            np.add.at(d, part["vg"][i], part["w"][i] * (1 - t))
            np.add.at(d, part["vg"][j], part["w"][j] * t)
            top = np.argsort(-d)[:4]
            new["w"].append(d[top] / d[top].sum())
            new["vg"].append(np.where(d[top] > 0, top, 0))
            cache[key] = n0 + len(new["pos"]) - 1
        return cache[key]

    for tri in part["tris"]:
        ins = f[tri] >= 0
        if ins.all():
            tris.append(tri)
            continue
        if not ins.any():
            continue
        poly = []
        for k in range(3):
            i, j = tri[k], tri[(k + 1) % 3]
            if f[i] >= 0:
                poly.append(i)
            if (f[i] >= 0) != (f[j] >= 0):
                poly.append(cut(i, j))
        for k in range(1, len(poly) - 1):
            tris.append([poly[0], poly[k], poly[k + 1]])
    out = {k: (np.concatenate([part[k], np.array(new[k], part[k].dtype)]) if new[k] else part[k].copy()) for k in VKEYS}
    tris = np.array(tris, np.int64)
    used, inv = np.unique(tris, return_inverse=True)
    out = {k: v[used] for k, v in out.items()}
    out["tris"] = inv.reshape(-1, 3)
    return out


# ---------------------------------------------------------------- skinning

def knn_weights(src_pos, src_w, src_vg, dst_pos, k=6, power=2.0, n_groups=None):
    """blend weights for new vertices from their k nearest source vertices (inverse-distance), top 4 kept"""
    n_groups = n_groups or int(src_vg.max()) + 1
    dense = np.zeros((len(src_pos), n_groups), np.float32)
    np.add.at(dense, (np.arange(len(src_pos))[:, None].repeat(4, 1), src_vg), src_w)
    out_w = np.zeros((len(dst_pos), 4), np.float32)
    out_g = np.zeros((len(dst_pos), 4), np.int32)
    for s in range(0, len(dst_pos), 512):
        d = np.linalg.norm(dst_pos[s:s + 512, None] - src_pos[None], axis=2)
        nn = np.argsort(d, axis=1)[:, :k]
        dd = np.take_along_axis(d, nn, 1)
        ww = 1.0 / (dd ** power + 1e-8)
        ww /= ww.sum(1, keepdims=True)
        acc = np.einsum("nk,nkg->ng", ww, dense[nn])
        top = np.argsort(-acc, axis=1)[:, :4]
        tw = np.take_along_axis(acc, top, 1)
        tw /= tw.sum(1, keepdims=True)
        out_w[s:s + 512], out_g[s:s + 512] = tw, top
    out_g[out_w == 0] = 0
    return out_w, out_g


def dense_weights(w, vg, n_groups):
    dense = np.zeros((len(w), n_groups), np.float32)
    np.add.at(dense, (np.arange(len(w))[:, None].repeat(4, 1), vg), w)
    return dense


def top4(dense):
    top = np.argsort(-dense, axis=1)[:, :4]
    tw = np.take_along_axis(dense, top, 1)
    tw = tw / tw.sum(1, keepdims=True)
    top = np.where(tw == 0, 0, top)
    return tw.astype(np.float32), top.astype(np.int32)


# ---------------------------------------------------------------- UV-space baking

def bake_uv(uv, tris, size, attrs):
    """
    rasterise triangles in UV space.

    attrs: dict name -> (N, k) per-vertex array. Returns (mask HxW bool, dict name -> HxWxk float32):
    for each covered texel, the interpolated attribute of the triangle drawn there.
    """
    W = H = size
    mask = np.zeros((H, W), bool)
    out = {k: np.zeros((H, W, np.asarray(v).reshape(len(v), -1).shape[1]), np.float32) for k, v in attrs.items()}
    attrs = {k: np.asarray(v, np.float32).reshape(len(v), -1) for k, v in attrs.items()}
    px = uv * size
    for a, b, c in tris:
        ax, ay, bx, by, cx, cy = px[a, 0], px[a, 1], px[b, 0], px[b, 1], px[c, 0], px[c, 1]
        area = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)
        if area == 0:
            continue
        x0, x1 = max(int(np.floor(min(ax, bx, cx))) - 1, 0), min(int(np.ceil(max(ax, bx, cx))) + 1, W - 1)
        y0, y1 = max(int(np.floor(min(ay, by, cy))) - 1, 0), min(int(np.ceil(max(ay, by, cy))) + 1, H - 1)
        if x0 > x1 or y0 > y1:
            continue
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        w0 = ((bx - X) * (cy - Y) - (cx - X) * (by - Y)) / area
        w1 = ((cx - X) * (ay - Y) - (ax - X) * (cy - Y)) / area
        w2 = 1 - w0 - w1
        e = -0.75 / max(abs(area) ** 0.5, 1e-6)  # a texel of slack, so seams are covered
        m = (w0 >= e) & (w1 >= e) & (w2 >= e)
        if not m.any():
            continue
        mask[y0:y1 + 1, x0:x1 + 1] |= m
        for k, v in attrs.items():
            val = w0[m, None] * v[a] + w1[m, None] * v[b] + w2[m, None] * v[c]
            out[k][y0:y1 + 1, x0:x1 + 1][m] = val
    return mask, out


def dilate(mask, n):
    m = mask.copy()
    for _ in range(n):
        g = m.copy()
        g[1:] |= m[:-1]
        g[:-1] |= m[1:]
        g[:, 1:] |= m[:, :-1]
        g[:, :-1] |= m[:, 1:]
        m = g
    return m


def distance(mask, limit):
    """approximate (city-block) distance in texels from each texel to the mask, capped at limit"""
    d = np.full(mask.shape, limit, np.float32)
    d[mask] = 0
    m = mask.copy()
    for i in range(1, limit):
        g = dilate(m, 1)
        d[g & ~m] = i
        m = g
    return d


def bleed(img, mask, n=6):
    """grow painted texels outward into unpainted ones, so bilinear filtering and mips do not pick up junk"""
    img = img.copy()
    m = mask.copy()
    for _ in range(n):
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sh_m = np.roll(m, (dy, dx), (0, 1))
            sh_i = np.roll(img, (dy, dx), (0, 1))
            take = sh_m & ~m
            img[take] = sh_i[take]
            m = m | take
    return img


def inpaint(img, known, need=None):
    """
    fill texels outside ``known`` with the average of their already-filled neighbours, growing outward from
    it; stops once every texel of ``need`` (default: all of them) is filled
    """
    img = np.asarray(img, np.float32).copy()
    m = known.copy()
    while not (m.all() if need is None else m[need].all()):
        acc = np.zeros_like(img)
        cnt = np.zeros(m.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sm = np.roll(m, (dy, dx), (0, 1))
            acc += np.roll(img, (dy, dx), (0, 1)) * sm[..., None]
            cnt += sm
        take = (cnt > 0) & ~m
        if not take.any():
            break
        img[take] = acc[take] / cnt[take][:, None]
        m |= take
    return img


# ---------------------------------------------------------------- .dds

def save_dds(path, rgba, srgb, mips=True):
    """write an uncompressed RGBA8 .dds with a DX10 header (sRGB flag as given) and a full mip chain"""
    rgba = np.ascontiguousarray(rgba, np.uint8)
    h, w = rgba.shape[:2]
    levels = [rgba]
    if mips:
        cur = rgba.astype(np.float32)
        # stop before a side goes odd: a non-square texture (2048 x 3072) reaches 2 x 3, and halving 3 rows here
        # gave a 2-row level where Direct3D expects 1 (every level after it misplaced)
        while cur.shape[0] % 2 == 0 and cur.shape[1] % 2 == 0:
            cur = (cur[0::2, 0::2] + cur[1::2, 0::2] + cur[0::2, 1::2] + cur[1::2, 1::2]) / 4
            levels.append(np.clip(cur + 0.5, 0, 255).astype(np.uint8))
    flags = 0x1 | 0x2 | 0x4 | 0x8 | 0x1000 | (0x20000 if len(levels) > 1 else 0)
    caps = 0x1000 | (0x400008 if len(levels) > 1 else 0)
    hdr = struct.pack("<4s7I44x", b"DDS ", 124, flags, h, w, w * 4, 0, len(levels))
    hdr += struct.pack("<2I4s5I", 32, 0x4, b"DX10", 0, 0, 0, 0, 0)
    hdr += struct.pack("<5I", caps, 0, 0, 0, 0)
    hdr += struct.pack("<5I", 29 if srgb else 28, 3, 0, 1, 0)
    with open(path, "wb") as f:
        f.write(hdr)
        for lv in levels:
            f.write(lv.tobytes())


def dds_format(path):
    """the DXGI format number of a DX10 .dds (None for a legacy header)"""
    with open(path, "rb") as f:
        b = f.read(148)
    if b[84:88] != b"DX10":
        return None
    return struct.unpack("<I", b[128:132])[0]
