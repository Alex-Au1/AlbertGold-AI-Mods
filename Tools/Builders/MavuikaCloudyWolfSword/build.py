"""
MavuikaCloudyWolf / Sword: Mavuika's signature claymore "A Thousand Blazing Suns" turned into Cloud Strife's Fusion
Sword (Final Fantasy VII Advent Children), assembled form.

    python Tools/Builders/MavuikaCloudyWolfSword/build.py [--preview Docs/Previews/MavuikaCloudyWolfSword.png]

SOURCES
- The game's weapon: a frame dump collected into ``dump/`` beside this file (it is not in GI-Model-Importer-Assets),
  read for its hashes, its frame (where the hand holds it, which way the blade points, which axis is thin), its
  uv2 map and its light map texels.
- The SHAPE and the PAINT: the maintainer's textured Fusion Sword model (a Sketchfab-style .dae with five parts,
  each with its own 2048 albedo / metallic / roughness / normal set; NOT stored in this repo), read through
  headless Blender (``modkit.blender.fbx_dump``, which also reads .dae).

STEPS
1. FRAME: the game weapon's long axis, thin axis, grip (the narrow end) and length; the same for the Fusion Sword.
2. MAP: one rigid turn + one uniform scale puts the Fusion Sword's grip on the game's grip, its blade along the game's
   blade, its flat side on the game's flat side; the scale makes the two weapons the same length.
3. TEXTURE: the five albedos are packed into one atlas (tiles), UVs moved into their tiles. The light map is the
   game's own texels: its metal texel where the model's metallic map says metal, its non-metal texel elsewhere.
   The normal map is the game's flat value (the model's normal maps use another convention and the change is
   small at this size); the game's MetalMap (a reflection lookup) is left bound as it is.
4. BUFFER: the weapon's one vb0 (stride 28: half position, snorm normal, colour, half uv, half uv2, and a "TANGENT"
   that GIMI's own generator fills with the normal's bytes), uv2 from the game's own planar map (fitted).
"""

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO, "Tools", "ModKit"))
from modkit import blender, ops  # noqa: E402
from modkit.gimi import islands, load_dump, weld_islands  # noqa: E402
from modkit.render import render, sheet  # noqa: E402

DUMP = os.environ.get("SWORD_DUMP", os.path.join(HERE, "dump"))   # env: try the recipe on another weapon's dump
REF = r"C:\Users\3dark\Downloads\Cloud Fusion Sword References\fusion-swordfrom-final-fantasy"
REF_DAE = os.path.join(REF, "source", "model", "model", "model.dae")
REF_TEX = os.path.join(REF, "textures")
OUT = os.path.join(REPO, "Mods", "GI", "Mavuika", "MavuikaCloudyWolf", "Sword")
NAME = "AThousandBlazingSuns"
MODNAME = "MavuikaCloudyWolfSword"
CACHE = os.path.join(os.environ.get("TEMP", HERE), "MavuikaCloudyWolfSword_ref.npz")

ATLAS = (2048, 3072)      # width, height
TILES = (2, 3)            # columns, rows: five parts, one 1024 tile each (epoch 2: at 682 px the thin dark slot
                          # marks along the blade's spine were lost)
MAX_ALBEDO = 200          # near-white blooms in game; 225 bloomed to a glowing peach slab on the Weapons tab (2026-11-17)
BLADE_SCALE = 1.0         # the model's own size from the guard up
GRIP_PAST_END = 0.03      # the stretched grip ends this far below the game grip's narrow run (her lower hand)
PART_TINT = {"Sword_03": 0.55}   # Sword_03: the inner core, seen through the column of slots in
# the outer blades; the .blend and the concept art draw those slots dark (cross-check batch, epoch 3: "painted
# squares, 129 against 143, will vanish under toon shading"). Most slots now read dark; a few are the outer blade's paint.   # the hinge piece with the gear disc: the disc was the brightest, near-white surface
# (bloom risk; the art draws a mid-grey gear). Sword_01 also holds the LOWER ANGLED PLATE: a tint of the whole part
# (0.8, then 0.65) turned that plate flat dark grey (epoch 5). Now only Sword_01's bright values are compressed
# (`PART_BRIGHT_CAP`: above 150, 255 lands on 170), which is the disc. The other
# parts keep the model's own greys (epoch 4 of the first batch: shade steps read as a darker, duller blade).
KNEE = 160
PART_BRIGHT_CAP = {"Sword_01": (150, 170)}   # knee, value 255 lands on
SMALL_ISLAND = 200        # triangles: open islands this small are made two-sided
BLEED = 10                # texels each UV island's colours are grown outward in the atlas
# epoch 1: the stacked blades read as one even grey slab; a small shade step per blade, as in the concept art
VERTEX_COLOUR = (255, 128, 128, 128)


def log(*a):
    print(*a, flush=True)


# ------------------------------------------------------------------------------------------------ reading

def load_game():
    hj = json.load(open(os.path.join(DUMP, "hash.json")))[0]
    vb = [f for f in os.listdir(DUMP) if "Head-vb0=" in f][0]
    ib = [f for f in os.listdir(DUMP) if "Head-ib=" in f][0]
    src = vb.split("Head-vb0=")[0]
    a = load_dump(os.path.join(DUMP, vb), os.path.join(DUMP, ib))
    a["pos"] = a["pos"][:, :3]
    a["nrm"] = a["nrm"][:, :3]
    with open(os.path.join(DUMP, vb)) as f:
        head = f.read(4000)
    stride = int(head.split("stride: ")[1].split()[0])
    tex = {}
    for k in ("Diffuse", "LightMap", "NormalMap", "MetalMap"):
        p = os.path.join(DUMP, f"{src}Head{k}.dds")
        if os.path.isfile(p):
            tex[k] = np.asarray(Image.open(p).convert("RGBA"))
    return a, hj, stride, tex


def load_ref():
    if not os.path.isfile(CACHE):
        blender.fbx_dump(REF_DAE, CACHE)
    d = np.load(CACHE)
    parts = []
    for i, n in enumerate(d["names"]):
        mat = str(d[f"{i}_mats"][0])
        parts.append(dict(name=str(n), mat=mat, pos=d[f"{i}_pos"].astype(np.float64), nrm=d[f"{i}_nrm"].astype(np.float64),
                          uv=d[f"{i}_uv"].astype(np.float64), tris=d[f"{i}_tris"].astype(np.int64)))
    return thicken_blade(parts)


# CROSS-CHECK WITH THE OTHER TWO MODELS (2026-11-18, `measure/three_models.py`: the maintainer's .blend and .obj of the
# same sword, scaled to one length, grip down). Widths, the guard's and grip's places agree within 1-2 %. Two things
# the .dae alone gets wrong:
# 1. Above the stacked lower section the .dae's blade is 0.027 thick (sword 2.0 long); the .blend's is 0.048 and the
#    .obj's 0.040 (the reviewers' "very thin edge-on"). That part is thickened to their mean.
# 2. Its crossguard is BLACK on one face and grey on the other; the .blend (steel all round), the .obj and the concept
#    art have one grey riveted bar. The black face's texture is replaced by the grey face's.
BLADE_THICKNESS_TARGET = 0.044   # of a 2.0-long sword
THICKEN_RAMP = 0.06              # metres (model units) over which the factor rises from 1 above the stacked section
SOURCE_PATCHES = {               # material: [(source rect, destination rect)] in the 2048 source maps (x0, y0, x1, y1)
    "Main_Sword": [((1237, 1135, 1767, 1302), (557, 1135, 1087, 1302)),    # guard: grey face (+y) onto black (-y)
                   ((1295, 1135, 1445, 1302), (407, 1135, 557, 1302)),     # its two black END faces: a plain,
                   ((1295, 1135, 1445, 1302), (1087, 1135, 1237, 1302))],  # rivet-free stretch of the grey face
}


def thicken_blade(parts):
    """
    the upper blade (beyond the stacked section) scaled through its thickness about its own middle plane, to
    BLADE_THICKNESS_TARGET; the stacked section stays as it is, with a smooth ramp between. The model's own frame:
    x across, y through (thin), z along with the tip at -z.
    """
    P = np.concatenate([p["pos"] for p in parts])
    T = np.concatenate([p["tris"] + o for p, o in zip(parts, np.cumsum([0] + [len(p["pos"]) for p in parts]))])
    Q = surface_points(P, T)
    L = np.ptp(Q[:, 2])
    tip = Q[:, 2].min()
    bins = np.linspace(tip, Q[:, 2].max(), 101)
    i = np.clip(np.digitize(Q[:, 2], bins) - 1, 0, 99)
    th = np.array([np.ptp(Q[i == k, 1]) if (i == k).sum() > 5 else np.nan for k in range(100)])
    upper = np.nanmedian(th[10:40])                                   # the single blade, 10-40 % from the tip
    # the stacked section begins where the thickness first exceeds 1.4 x the upper blade's, walking from the tip
    k0 = next(k for k in range(10, 100) if th[k] > 1.4 * upper)
    z_step = bins[k0]
    K = BLADE_THICKNESS_TARGET * L / 2.0 / upper
    mid = np.median(Q[Q[:, 2] < z_step, 1])
    log(f"thicken: upper blade {upper / L * 2:.3f} thick (of 2.0), x{K:.2f} beyond z {z_step:.3f} (stacked section below)")
    for p in parts:
        z = p["pos"][:, 2]
        k = 1 + (K - 1) * smoothstep(z_step, z_step - THICKEN_RAMP, z)
        p["pos"] = p["pos"].copy()
        p["pos"][:, 1] = mid + (p["pos"][:, 1] - mid) * k
        n = p["nrm"].copy()
        n[:, 1] /= k                                                  # a stretch through y tilts normals toward x/z
        p["nrm"] = n / (np.linalg.norm(n, axis=1, keepdims=True) + 1e-12)
    return parts


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


GUARD_RECT = (407, 1135, 1767, 1302)   # the guard's faces and ends in Main_Sword's maps
GUARD_SEAM = (72, 72, 75)              # its red line becomes a dark seam (epoch 1 of the cross-check batch: only the
                                       # .dae has a red line; the .blend, the .obj and the art have a plain bar)


def ref_tex(mat, kind):
    im = Image.open(os.path.join(REF_TEX, f"{mat}_{kind}.jpeg")).convert("RGB")
    for (sx0, sy0, sx1, sy1), (dx0, dy0, dx1, dy1) in SOURCE_PATCHES.get(mat, []):
        im.paste(im.crop((sx0, sy0, sx1, sy1)).resize((dx1 - dx0, dy1 - dy0)), (dx0, dy0))
    if mat == "Main_Sword" and kind == "albedo":
        a = np.asarray(im).copy()
        x0, y0, x1, y1 = GUARD_RECT
        g = a[y0:y1, x0:x1].astype(int)
        red = (g[..., 0] > 90) & (g[..., 0] > 1.6 * g[..., 1])
        g[red] = GUARD_SEAM
        a[y0:y1, x0:x1] = g.astype(np.uint8)
        im = Image.fromarray(a)
    return im


# ------------------------------------------------------------------------------------------------ frames

def surface_points(P, T, per_m2=200000, seed=0):
    """points spread over the triangles (area-weighted): long triangles leave slices with no vertex in them"""
    a, b, c = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    rs = np.random.RandomState(seed)
    n = max(20000, int(area.sum() * per_m2))
    k = rs.choice(len(T), n, p=area / area.sum())
    r1, r2 = rs.rand(n, 1), rs.rand(n, 1)
    f = r1 + r2 > 1
    r1[f], r2[f] = 1 - r1[f], 1 - r2[f]
    return np.concatenate([P, a[k] + r1 * (b[k] - a[k]) + r2 * (c[k] - a[k])])


def width_profile(P, axis, thin, n=100):
    """along the long axis: the extent across (the third axis) per slice"""
    across = np.cross(axis, thin)
    t = P @ axis
    w = P @ across
    edges = np.linspace(t.min(), t.max(), n + 1)
    i = np.clip(np.searchsorted(edges, t) - 1, 0, n - 1)
    lo = np.full(n, np.inf)
    hi = np.full(n, -np.inf)
    np.minimum.at(lo, i, w)
    np.maximum.at(hi, i, w)
    return edges, np.where(hi > lo, hi - lo, 0)


GUARD_HALF_WIDTH = 0.06   # wider than any grip (radius ~0.015-0.03) and any pommel cap


def frame(P, T, name, narrow_frac=0.35):
    """
    long axis (from the grip end towards the tip), thin axis, the across axis, the grip's centre and the length.
    The GRIP is the longest run of slices narrower than ``narrow_frac`` of the blade's median width; the axis is
    turned so that the grip is in the lower half.
    """
    Q = surface_points(P, T)
    c = Q.mean(0)
    _, _, vt = np.linalg.svd(Q - c, full_matrices=False)
    axis, thin = vt[0], vt[2]
    edges, prof = width_profile(Q, axis, thin)
    n = len(prof)
    blade_w = np.median(prof)
    narrow = prof < narrow_frac * blade_w
    best, i = (0, 0), 0
    while i < n:
        if narrow[i]:
            j = i
            while j < n and narrow[j]:
                j += 1
            if j - i > best[1] - best[0]:
                best = (i, j)
            i = j
        else:
            i += 1
    if (best[0] + best[1]) / 2 > n / 2:            # the grip is at the + end: turn the axis round
        axis = -axis
        edges, prof = width_profile(Q, axis, thin)
        best = (n - best[1], n - best[0])
    grip = (edges[best[0]], edges[best[1]])
    across = np.cross(axis, thin)
    t = Q @ axis
    m = (t >= grip[0]) & (t <= grip[1])
    gc = axis * (grip[0] + grip[1]) / 2 + across * np.median(Q[m] @ across) + thin * np.median(Q[m] @ thin)
    # the guard's lower face: the lowest point above the grip's middle that is wider than the grip
    a_ = np.abs(Q @ across - np.median(Q[m] @ across))
    up = (t > (grip[0] + grip[1]) / 2) & (a_ > GUARD_HALF_WIDTH)
    guard = t[up].min()
    info = dict(axis=axis, thin=thin, across=across, grip=grip, grip_centre=gc, guard=guard, length=t.max() - t.min(),
                tip=t.max(), butt=t.min(), blade_w=blade_w, prof=prof, edges=edges)
    log(f"{name}: length {info['length']:.3f} ({t.min():.3f} .. {t.max():.3f}), grip {grip[0]:.3f} .. {grip[1]:.3f} "
        f"({grip[1] - grip[0]:.3f} long), guard from {guard:.3f}, centre {np.round(gc, 3)}, blade width {blade_w:.3f}, axis {np.round(axis, 3)}, "
        f"thin {np.round(thin, 3)}")
    return info


def hilt_map(src, dst, flip_across=False):
    """
    the Fusion Sword into the game weapon's frame (reviewer epoch 1: matching the grips' centres put the Fusion
    guard 2-3 cm down over the game's grip top, where her upper hand closes, and left the grip short for the lower
    hand). Now: a turn (axis to axis, thin to thin) and, along the axis, two pieces joined at the guard's lower face:
    - from the guard up, scale BLADE_SCALE (the model's own size: its metres are about right for the AC sword);
    - below it, the grip is stretched so its end lands GRIP_END below the game guard, past the game grip's end.
    Returns a function of (points) and (normals).
    """
    d_thin = dst["thin"] * (-1 if flip_across else 1)
    A = np.stack([src["axis"], src["thin"], np.cross(src["axis"], src["thin"])], 1)
    B = np.stack([dst["axis"], d_thin, np.cross(dst["axis"], d_thin)], 1)
    R = B @ A.T
    g0 = dst["guard"]
    grip_len = g0 - (dst["grip"][0] - GRIP_PAST_END)
    k_grip = grip_len / (src["guard"] - src["butt"])
    # centre the model across and through (its grip's line onto the game grip's line)
    c_src = src["grip_centre"] - src["axis"] * (src["grip_centre"] @ src["axis"])
    c_dst = dst["grip_centre"] - dst["axis"] * (dst["grip_centre"] @ dst["axis"])
    log(f"map: blade scale {BLADE_SCALE}, grip stretched x{k_grip:.3f} ({src['guard'] - src['butt']:.3f} -> {grip_len:.3f}), "
        f"guard at {g0:.3f}")

    def fpos(P):
        t = P @ src["axis"] - src["guard"]
        side = (P - c_src) - np.outer(P @ src["axis"], src["axis"])
        tt = np.where(t >= 0, t * BLADE_SCALE, t * k_grip)
        k_side = np.where(t >= 0, BLADE_SCALE, 1.0)[:, None]      # the grip keeps its girth
        return (side * k_side) @ R.T + np.outer(g0 + tt, dst["axis"]) + c_dst

    def fnrm(P, N):
        t = P @ src["axis"] - src["guard"]
        n_ax = N @ src["axis"]
        n = N - np.outer(n_ax, src["axis"])
        n_ax = np.where(t >= 0, n_ax, n_ax / k_grip)             # a stretch along the axis tilts normals inward
        n = (n + np.outer(n_ax, src["axis"])) @ R.T
        return n / (np.linalg.norm(n, axis=1, keepdims=True) + 1e-12)
    return fpos, fnrm


# ------------------------------------------------------------------------------------------------ texture

def tile_rect(i):
    tw, th = ATLAS[0] // TILES[0], ATLAS[1] // TILES[1]
    return (i % TILES[0]) * tw, (i // TILES[0]) * th, tw, th


def tile_uv(uv, i, inset=2):
    """a part's own 0..1 uv into its tile (inset by a few texels so mips bleed less across tiles)"""
    x, y, w, h = tile_rect(i)
    u = (x + inset + np.clip(uv[:, 0], 0, 1) * (w - 2 * inset)) / ATLAS[0]
    v = (y + inset + np.clip(uv[:, 1], 0, 1) * (h - 2 * inset)) / ATLAS[1]
    return np.stack([u, v], 1)


def resize_channels(img, size):
    """channel by channel (Pillow premultiplies alpha on RGBA resizes: Mod Building, traps)"""
    a = np.asarray(img)
    if a.ndim == 2:
        return np.asarray(Image.fromarray(a).resize(size, Image.Resampling.LANCZOS))
    return np.stack([np.asarray(Image.fromarray(np.ascontiguousarray(a[..., k])).resize(size, Image.Resampling.LANCZOS))
                     for k in range(a.shape[2])], -1)


def game_lightmap_texels(g, gtex, gf):
    """
    the game weapon's light map, read where its own vertices sample it (2026-11-17, `gbands` picture):
    - its BLADE and sunburst guard are alpha 0, red 0, green 255: an unlit code that glows by the diffuse alpha.
      The Fusion Sword's steel must not take it (it would be flat and lit by nothing);
    - its HILT and pommel are alpha 255 (lit, with the MetalMap): bright ornaments red ~255 (specular), the wrapped
      shaft a lower red. Those two are the texels used: "metal" for steel, "wrap" for the cloth and polymer parts.
    """
    lm = gtex["LightMap"]
    H, W = lm.shape[:2]
    pxy = np.clip((g["uv"] * [W - 1, H - 1]).astype(int), 0, [W - 1, H - 1])
    L = lm[pxy[:, 1], pxy[:, 0]].astype(int)
    lit = L[:, 3] > 200
    t = (g["pos"] - gf["grip_centre"]) @ gf["axis"]
    half = (gf["grip"][1] - gf["grip"][0]) / 2
    wrap = lit & (np.abs(t) < 0.7 * half)
    metal = lit & (L[:, 0] > 200)
    out = dict(metal=np.median(L[metal], 0).astype(np.uint8), wrap=np.median(L[wrap], 0).astype(np.uint8))
    log(f"game light map: lit {lit.sum()} / {len(L)} vertices; metal ({metal.sum()}) {out['metal'].tolist()}, "
        f"wrapped shaft ({wrap.sum()}) {out['wrap'].tolist()}; unlit blade {np.median(L[~lit], 0).astype(int).tolist()}")
    return out


def orient_by_visibility(pos, nrm, tris, res=500, per_px=4.0, seed=1):
    """
    look at the mesh from 62 directions with no culling and turn round every triangle that is seen (almost) only
    from its BACK (epoch 3: small tabs on Sword_01 by the guard are inside out in the source, their normals agree
    with that winding, and they sit in larger open islands, so no mesh test tells which side is out).
    Points are spread over the triangles by area (``per_px`` per pixel, at least 3 per triangle) and splatted into a
    depth buffer per view; every front-most point is a hit for its triangle, from the front or from the back.
    A sparse spread (12 per triangle) let far faces show through the gaps of near ones: 10 000 triangles were then
    "seen from both sides". Normals of vertices used only by turned triangles are turned too.
    """
    rs = np.random.RandomState(seed)
    T = len(tris)
    a, b, c = pos[tris[:, 0]], pos[tris[:, 1]], pos[tris[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    px = np.ptp(pos, 0).max() / res
    cnt = np.maximum(3, np.ceil(area / px ** 2 * per_px)).astype(int)
    tid = np.repeat(np.arange(T), cnt)
    r1, r2 = rs.rand(len(tid), 1), rs.rand(len(tid), 1)
    f = (r1 + r2) > 1
    r1[f], r2[f] = 1 - r1[f], 1 - r2[f]
    pts = a[tid] + r1 * (b - a)[tid] + r2 * (c - a)[tid]
    fn = np.cross(b - a, c - a)
    fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-12
    front, back = np.zeros(T), np.zeros(T)
    dirs = []
    for el in np.radians(np.linspace(-75, 75, 6)):
        for az in np.radians(np.arange(0, 360, 36)):
            dirs.append([np.cos(el) * np.sin(az), np.sin(el), np.cos(el) * np.cos(az)])
    dirs += [[0, 1, 0], [0, -1, 0]]
    lo = pos.min(0)
    for d in np.array(dirs):
        u = np.cross(d, [0, 1, 0] if abs(d[1]) < 0.9 else [1, 0, 0])
        u /= np.linalg.norm(u)
        v = np.cross(d, u)
        x, y, z = (pts - lo) @ u, (pts - lo) @ v, pts @ d          # z towards the camera
        ix = ((x - x.min()) / px).astype(np.int64)
        iy = ((y - y.min()) / px).astype(np.int64)
        pix = iy * (ix.max() + 1) + ix
        order = np.lexsort((-z, pix))                              # per pixel, nearest first
        first = order[np.r_[True, pix[order][1:] != pix[order][:-1]]]
        t_ = tid[first]
        facing = np.einsum("ij,j->i", fn[t_], d) > 0
        np.add.at(front, t_[facing], 1)
        np.add.at(back, t_[~facing], 1)
    turn = (back >= 6) & (back > 4 * front)
    # only inside SMALL islands (epoch 4: on the long thin side blades the outer bevels at their tips were voted
    # "from behind" and turned, so the game would cull them and the tips' outline broke edge-on)
    wl = weld_islands(pos, tris, 1e-4)[tris[:, 0]]
    ids, cnt = np.unique(wl, return_counts=True)
    small = np.isin(wl, ids[cnt <= SMALL_ISLAND])
    log(f"   {turn.sum()} voted; {(turn & ~small).sum()} of them in islands over {SMALL_ISLAND} triangles are TWINNED "
        f"(drawn from both sides) instead")
    # and single-sided plates (the side blades' tips are one sheet: hit from both sides about equally): a face in a
    # large island seen from behind at least 30 % as often as from the front is drawn from both sides
    twin = ~small & (back >= 6) & (back >= 0.3 * front)
    log(f"   twinned in large islands (seen from behind 30 %+): {twin.sum()}")
    turn &= small
    log(f"orientation: {len(tid)} points; {turn.sum()} of {T} triangles seen (almost) only from behind: turned round "
        f"(hit from both sides: {((front > 0) & (back > 0)).sum()})")
    tris = tris.copy()
    tris[turn] = tris[turn][:, ::-1]
    nrm = nrm.copy()
    vt = np.unique(tris[turn].reshape(-1))
    keep = np.unique(tris[~turn].reshape(-1))
    shared = np.intersect1d(vt, keep)
    if len(shared):
        log(f"   {len(shared)} vertices are shared between turned and kept triangles: their normals are left")
    nrm[np.setdiff1d(vt, keep)] *= -1
    return tris, nrm, np.nonzero(twin)[0]


def cap_guard(pos, nrm, uv, tris, gf):
    """
    the model's crossguard is a hollow SLEEVE, open at its top and bottom (in game it read as a glassy tray from
    above and behind, 2026-11-17); the Fusion Sword's guard is a block. Each open end gets a flat cap, painted
    with the UV of the guard's own vertex nearest the cap's middle.
    """
    lab = weld_islands(pos, tris, 1e-4)
    tl = lab[tris[:, 0]]
    ax, ac, th = gf["axis"], gf["across"], gf["thin"]
    caps_p, caps_n, caps_uv, caps_t = [], [], [], []
    n0 = len(pos)
    for k in np.unique(tl):
        v = np.unique(tris[tl == k])
        a, c, t = pos[v] @ ax, pos[v] @ ac, pos[v] @ th
        if not (np.ptp(c) > 0.15 and np.ptp(a) < 0.12 and abs((a.min() + a.max()) / 2 - gf["guard"]) < 0.1):
            continue
        log(f"guard sleeve: island {k}, {len(v)} vertices, {np.ptp(c):.3f} x {np.ptp(t):.3f} x {np.ptp(a):.3f}: capped")
        for end, sgn in ((a.min(), -1), (a.max(), 1)):
            corners = [(c0, t0) for c0, t0 in ((c.min(), t.min()), (c.max(), t.min()), (c.max(), t.max()), (c.min(), t.max()))]
            P = np.array([ax * end + ac * c0 + th * t0 for c0, t0 in corners])
            mid = P.mean(0)
            uvk = uv[v[np.argmin(np.linalg.norm(pos[v] - mid, axis=1))]]
            base = n0 + sum(len(x) for x in caps_p)
            tr = np.array([[0, 1, 2], [0, 2, 3]]) + base
            fn = np.cross(P[1] - P[0], P[2] - P[0])
            if fn @ (ax * sgn) < 0:
                tr = tr[:, ::-1]
            caps_p.append(P)
            caps_n.append(np.tile(ax * sgn, (4, 1)))
            caps_uv.append(np.tile(uvk, (4, 1)))
            caps_t.append(tr)
    if not caps_p:
        log("WARNING: no guard sleeve found to cap")
        return pos, nrm, uv, tris
    return (np.concatenate([pos] + caps_p), np.concatenate([nrm] + caps_n), np.concatenate([uv] + caps_uv),
            np.concatenate([tris] + caps_t))


def two_sided_open(pos, nrm, uv, tris, extra=()):
    """
    small OPEN islands (boundary edges, at most SMALL_ISLAND triangles: bolt tubes, tabs) get a reversed twin, so
    looking into an open end shows their inside instead of a hole (epoch 3: two 168-triangle open tubes beside the
    blade root showed their insides as back faces edge-on)
    """
    key = np.round(pos / 1e-4).astype(np.int64)
    _, wi = np.unique(key, axis=0, return_inverse=True)
    wi = wi.reshape(-1)
    lab = weld_islands(pos, tris, 1e-4)
    tl = lab[tris[:, 0]]
    twins = []
    for k in np.unique(tl):
        tt = tris[tl == k]
        if len(tt) > SMALL_ISLAND:
            continue
        e = np.sort(wi[np.concatenate([tt[:, [0, 1]], tt[:, [1, 2]], tt[:, [2, 0]]])], 1)
        _, cnt = np.unique(e, axis=0, return_counts=True)
        if (cnt == 1).any():
            twins.append(tt)
    if len(extra):
        twins.append(tris[extra])
    if not twins:
        return pos, nrm, uv, tris
    tw = np.concatenate(twins)
    vt = np.unique(tw.reshape(-1))
    remap = np.full(len(pos), -1)
    remap[vt] = len(pos) + np.arange(len(vt))
    log(f"two-sided: {len(twins)} small open islands, {len(tw)} triangles twinned")
    return (np.concatenate([pos, pos[vt]]), np.concatenate([nrm, -nrm[vt]]), np.concatenate([uv, uv[vt]]),
            np.concatenate([tris, remap[tw][:, ::-1]]))


def uv_labels(uv, tris):
    """per atlas texel: 1 + the UV island (index-connected triangles) whose triangle covers its centre, 0 = none"""
    from PIL import ImageDraw
    W, H = ATLAS
    lab = islands(tris, len(uv))[tris[:, 0]]
    im = Image.new("I", (W, H), 0)
    d = ImageDraw.Draw(im)
    px = uv * [W, H]
    for t, k in zip(tris, lab):
        d.polygon([tuple(px[j]) for j in t], fill=int(k) + 1)
    return np.asarray(im).astype(np.int32)


def island_bleed(img, lab, trim=2, n=BLEED):
    """
    trim each UV island by ``trim`` texels where it meets ANOTHER island or nothing, then grow every island's own
    colours back over its trimmed border and out over empty texels, never across into another island
    """
    # trimmed only where an island meets ANOTHER island (epoch 4: trimming where it meets nothing cut away the dark
    # outlines the source paints along the blade slots' island borders, and left pale patches)
    edge = np.zeros(lab.shape, bool)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nb = np.roll(lab, (dy, dx), (0, 1))
        edge |= (nb != lab) & (nb > 0) & (lab > 0)
    edge = (ops.dilate(edge, trim - 1) & (lab > 0)) | (lab == 0)
    known = ~edge
    img = img.copy()
    lab = lab.copy()
    for _ in range(trim + n):
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sk = np.roll(known, (dy, dx), (0, 1))
            sl = np.roll(lab, (dy, dx), (0, 1))
            take = sk & ~known & ((lab == sl) | (lab == 0))
            img[take] = np.roll(img, (dy, dx), (0, 1))[take]
            lab[take & (lab == 0)] = sl[take & (lab == 0)]
            known = known | take
    return img


def paint_map(parts, kind):
    """one channel of each part's source map (metallic, roughness, ...) placed in its tile, 0..255"""
    A = np.zeros((ATLAS[1], ATLAS[0], 4), np.uint8)
    for i, p in enumerate(parts):
        x, y, w, h = tile_rect(i)
        A[y:y + h, x:x + w, :3] = resize_channels(ref_tex(p["mat"], kind), (w, h))[..., :1]
    return A


def band_lightmap(met, rough):
    """the material-band light map: per texel the metal or the wrap class, B from (1 - roughness) in its range"""
    smooth = 1 - rough.astype(np.float32) / 255
    out = np.zeros(met.shape + (4,), np.uint8)
    for cls, m in ((BAND_METAL, met), (BAND_WRAP, ~met)):
        lo, hi = cls[2]
        out[m, 0], out[m, 1], out[m, 3] = cls[0], cls[1], cls[3]
        out[m, 2] = np.round(lo + smooth[m] * (hi - lo)).astype(np.uint8)
    return out


def paint_atlas(parts, lm_metal, lm_other, flat_normal):
    D = np.zeros((ATLAS[1], ATLAS[0], 4), np.uint8)
    LM = np.zeros((ATLAS[1], ATLAS[0], 4), np.uint8)
    LM[:] = lm_other
    for i, p in enumerate(parts):
        x, y, w, h = tile_rect(i)
        alb = resize_channels(ref_tex(p["mat"], "albedo"), (w, h)).astype(np.float32)
        # keep the darkest darks, pull the top down under the bloom line
        alb *= PART_TINT.get(p["mat"], 1.0)
        # a soft knee: unchanged up to KNEE, then compressed so 255 lands on MAX_ALBEDO (epoch 2: scaling the
        # whole range down cost a third of the blade's brightness and its scratches)
        knee, top = PART_BRIGHT_CAP.get(p["mat"], (KNEE, MAX_ALBEDO))
        hi = alb > knee
        alb[hi] = knee + (alb[hi] - knee) * (top - knee) / (255.0 - knee)
        D[y:y + h, x:x + w, :3] = alb.astype(np.uint8)
        D[y:y + h, x:x + w, 3] = 0          # diffuse alpha is the glow mask in this game: none
        met = resize_channels(ref_tex(p["mat"], "metallic"), (w, h))[..., 0] > 127
        LM[y:y + h, x:x + w] = np.where(met[..., None], lm_metal, lm_other)
    N = np.zeros((64, 64, 4), np.uint8)
    N[:] = flat_normal
    return D, LM, N


# ------------------------------------------------------------------------------------------------ buffer

def snorm8(v):
    return np.clip(np.round(v * 127), -127, 127).astype(np.int8).view(np.uint8)


def write_vb(path, pos, nrm, col, uv, uv2):
    n = len(pos)
    rec = np.zeros((n, 28), np.uint8)
    p4 = np.c_[pos, np.ones(n)].astype(np.float16)
    rec[:, 0:8] = p4.view(np.uint8).reshape(n, 8)
    nb = snorm8(np.c_[nrm, np.zeros(n)])
    rec[:, 8:12] = nb
    rec[:, 12:16] = col
    rec[:, 16:20] = uv.astype(np.float16).view(np.uint8).reshape(n, 4)
    rec[:, 20:24] = uv2.astype(np.float16).view(np.uint8).reshape(n, 4)
    rec[:, 24:28] = nb                       # as GIMI's generator writes it: the normal's bytes
    rec.tofile(path)


# In game (2026-11-17) the whole sword, red grip included, came out GOLD-PEACH and blooming on the Weapons tab: the
# game weapon's lit code (alpha 255, red = specular 254) is shaded through this weapon's own warm metal settings
# (its MetalMap is plain grey, so the tint is in the shader's constants). Not settled offline: the mod carries
# light map VARIANTS, cycled in game with "]" (persisted), each (steel texel, grip texel):
# Tried in game (2026-11-17, `ingame2_variants.png`): the game's texels gold and blooming; the other three grey steel,
# low specular the best (still shaded). Low specular is variant 0, the default.
# MATERIAL BANDS (AGRemap's lesson: a light map's alpha is a material band; read the legend per object off its own
# texels). This weapon's legend, over every texel its triangles cover (2026-11-17):
#   alpha 0, (0, 255, 0): the blade and sunburst, unlit; green 255 = glow.            NEVER used.
#   alpha 255, metal (254, 128, B): its gold metal; B 75 .. 216 rising with how bright the diffuse is.
#   alpha 255, wrap (101, 128, B): its dark red wrapped shaft; B 25 .. 56.
#   alpha 255, (0, 255, 0) and (0, 129, 0): glowing / matte gold bits, a few hundred texels.  Not used.
# "bands": the Fusion Sword's metal (its metallic map) on the metal class, the rest (red cloth grip, black polymer)
# on the wrap class, B inside each class's range from the model's ROUGHNESS (smooth -> high B).
BAND_METAL = (254, 128, (75, 216), 255)
BAND_WRAP = (101, 128, (25, 56), 255)
# IN GAME (2026-11-18, `ingame6_bands_vs_lowspec.png`): the band copy turned the WHOLE sword peach, the black guard
# face too; low specular stayed grey steel / black / red. Both sit on the lit band (alpha 255), the right band. The
# original's class RGB (specular red 254 on metal, even 101 on the wrap) is tuned to its GOLD: this weapon's specular
# tint is gold, so any real specular paints gold. Low specular is the default; the band copy is kept as variant 1.
LM_VARIANTS = [
    ("low specular", (90, 128, 60, 255), (0, 128, 0, 255)),       # metal and the rest both on the lit band 255
    ("material bands copied", "bands", None),
    ("no specular", (0, 128, 0, 255), (0, 128, 0, 255)),
    ("unlit code", (0, 255, 0, 0), (0, 255, 0, 0)),               # the game blade's code (it glows only by diffuse alpha)
]
LM_KEY = "VK_OEM_6"       # the "]" key

# The guard and grip stayed AMBER under every light map. The weapon's draw binds more textures than the four the
# collector names (frame dump draw 000019): ps-t8 (d36ddf9e, 512) is an EFFECT MASK laid out on the weapon's own UV
# (olive and green shapes of its blade lines, sunburst and hilt), and the mod's atlas UVs put the guard and grip on
# its olive areas, so the fire effect lit them. The mod binds a black texture there: no effect anywhere.
EFFECT_MASK_SLOT = 8      # d36ddf9e in ps-t8 of the main pass (draw 19)


def write_ini(out, hj, stride, slots):
    """
    TEXTURES ARE REPLACED BY THEIR OWN HASH (`this =`), not by slot. The game draws the weapon in four passes that share
    its ib (frame dump draws 19, 27, 63, 71), and they bind its textures in DIFFERENT slots (draw 19: t0 normal map,
    t1 diffuse, t2 light map; draw 27: t0 diffuse, t1 light map; draws 63 / 71: t0 diffuse). Binding by slot on the
    ib, as first built, put the normal map where draw 27 reads a diffuse, and so on (thin orange lines along the
    layer steps and disc arcs in game, 2026-11-17).
    """
    names = {k: h for k, _, h in hj["texture_hashes"][0]}
    s = [f"; {MODNAME}: Mavuika's A Thousand Blazing Suns as Cloud Strife's Fusion Sword (Final Fantasy VII Advent Children)",
         "; Built by Tools/Builders/MavuikaCloudyWolfSword/build.py (AlbertGold AI Mods). Do not edit by hand.",
         "; Hashes from the frame dump in Tools/Builders/MavuikaCloudyWolfSword/dump/hash.json.",
         "; light map variants on " + LM_KEY + ": " + "; ".join(f"{v} {n}" for v, (n, _, _) in enumerate(LM_VARIANTS)), ""]
    s += ["[Constants]", "global persist $lightmap = 0", "",
          "[KeyLightMap]", f"key = {LM_KEY}", "type = cycle",
          "$lightmap = " + ",".join(str(v) for v in range(len(LM_VARIANTS))), ""]
    s += [f"[TextureOverride{NAME}]", f"hash = {hj['draw_vb']}", f"vb0 = Resource{NAME}", ""]
    s += [f"[TextureOverride{NAME}IB]", f"hash = {hj['ib']}", "handling = skip", "drawindexed = auto", ""]
    s += [f"[TextureOverride{NAME}Head]", f"hash = {hj['ib']}", f"match_first_index = {hj['object_indexes'][0]}",
          f"ib = Resource{NAME}HeadIB",
          # the effect mask is bound in ps-t8, and GIMI's d3dx.ini checks texture hashes only in ps-t0..t3
          # (CommandListSkin): a hash override never fires there, so it is bound BY SLOT on the weapon's draw. In
          # game a by-slot ps-t8 (third look) removed the amber; by hash (fourth look) the amber came back.
          f"ps-t{EFFECT_MASK_SLOT} = Resource{NAME}EffectMaskOff", ""]
    for _, k in slots:
        s += [f"[TextureOverride{NAME}Head{k}]", f"hash = {names[k]}"]
        if k == "LightMap":
            for v in range(len(LM_VARIANTS)):
                s += [("if" if v == 0 else "else if") + f" $lightmap == {v}", f"    this = Resource{NAME}HeadLightMap{v}"]
            s += ["endif"]
        else:
            s += [f"this = Resource{NAME}Head{k}"]
        s += [""]
    s += [f"[Resource{NAME}]", "type = Buffer", f"stride = {stride}", f"filename = {NAME}.buf", ""]
    s += [f"[Resource{NAME}HeadIB]", "type = Buffer", "format = DXGI_FORMAT_R32_UINT", f"filename = {NAME}Head.ib", ""]
    for _, k in slots:
        if k == "LightMap":
            for v in range(len(LM_VARIANTS)):
                s += [f"[Resource{NAME}HeadLightMap{v}]", f"filename = {NAME}HeadLightMap{v}.dds", ""]
        else:
            s += [f"[Resource{NAME}Head{k}]", f"filename = {NAME}Head{k}.dds", ""]
    s += [f"[Resource{NAME}EffectMaskOff]", f"filename = {NAME}EffectMaskOff.dds", ""]
    with open(os.path.join(out, f"{MODNAME}.ini"), "w", newline="\r\n") as fh:
        fh.write("\n".join(s))


# ------------------------------------------------------------------------------------------------ build

FLIP_ACROSS = False       # turn the sword 180 degrees round its own axis (which edge faces which side)


def build(out=OUT):
    g, hj, stride, gtex = load_game()
    gf = frame(g["pos"], g["tris"], "game weapon")
    parts = load_ref()
    allp = np.concatenate([p["pos"] for p in parts])
    offs = np.cumsum([0] + [len(p["pos"]) for p in parts])
    allt = np.concatenate([p["tris"] + o for p, o in zip(parts, offs)])
    rf = frame(allp, allt, "Fusion Sword")
    fpos, fnrm = hilt_map(rf, gf, FLIP_ACROSS)

    pos, nrm, uv, tris, off = [], [], [], [], 0
    for i, p in enumerate(parts):
        q = fpos(p["pos"])
        n = fnrm(p["pos"], p["nrm"])
        tr = p["tris"].copy()
        # wind every triangle so that its face normal agrees with its corners' normals (front = counter-clockwise)
        fn = np.cross(q[tr[:, 1]] - q[tr[:, 0]], q[tr[:, 2]] - q[tr[:, 0]])
        flip = (fn * n[tr].sum(1)).sum(1) < 0
        tr[flip] = tr[flip][:, ::-1]
        p_uv = p["uv"]
        log(f"   {p['name']}: {len(q)} vertices, {len(tr)} triangles, {flip.sum()} rewound by normals")
        pos.append(q)
        nrm.append(n)
        uv.append(tile_uv(p_uv, i))
        tris.append(tr + off)
        off += len(q)
    pos, nrm, uv, tris = map(np.concatenate, (pos, nrm, uv, tris))
    pos, nrm, uv, tris = cap_guard(pos, nrm, uv, tris, gf)
    tris, nrm, twin = orient_by_visibility(pos, nrm, tris)
    pos, nrm, uv, tris = two_sided_open(pos, nrm, uv, tris, extra=twin)
    if len(pos) > 65535:
        log("WARNING: over 65535 vertices")

    # uv2: the game's own planar map, fitted on its vertices (it is linear in position)
    A = np.c_[g["pos"], np.ones(len(g["pos"]))]
    C = np.linalg.lstsq(A, g["uv2"], rcond=None)[0]
    rms = np.sqrt(np.mean((A @ C - g["uv2"]) ** 2, 0))
    if rms.max() < 0.02:
        log("uv2 = the game's linear map of position, rms", np.round(rms, 4))
        uv2 = np.c_[pos, np.ones(len(pos))] @ C
    else:
        # this weapon's uv2 is a second unwrap, not a projection (rms of the linear fit ~0.2): give the new mesh a
        # flat map of its own face-on silhouette, continuous and inside 0..1 like the game's
        log("uv2: the game's is an unwrap (linear fit rms", np.round(rms, 3), "): planar map across x along")
        a_ = (pos - gf["grip_centre"]) @ gf["axis"]
        c_ = (pos - gf["grip_centre"]) @ gf["across"]
        uv2 = np.stack([0.5 + 0.47 * c_ / (np.abs(c_).max() + 1e-9),
                        0.02 + 0.97 * (a_ - a_.min()) / (np.ptp(a_) + 1e-9)], 1)
    col = np.tile(np.array(VERTEX_COLOUR, np.uint8), (len(pos), 1))

    # textures
    lmt = game_lightmap_texels(g, gtex, gf)
    nm = gtex["NormalMap"].reshape(-1, 4)
    vals, cnt = np.unique(nm, axis=0, return_counts=True)
    flat = vals[np.argmax(cnt)]
    log("flat normal", flat.tolist())
    D, LM, N = paint_atlas(parts, lmt["metal"], lmt["wrap"], flat)
    # epoch 3: a light dotted seam down the grip and a dark line along the blade's edge: filtering picked up the
    # source maps' texels just outside each UV island. Keep only texels inside the islands (less one texel) and grow
    # the islands' own colours outward over the rest.
    # The source maps' islands TOUCH (the grip's red strip meets the guard's island, whose 1-texel light border
    # then lay beside the grip's seam), so the trim and the regrowth are per island.
    lab = uv_labels(uv, tris)
    D = island_bleed(D, lab)
    LM = island_bleed(LM, lab)
    MET = island_bleed(paint_atlas(parts, (255,) * 4, (0,) * 4, flat)[1], lab)[..., 0] > 127   # steel where set
    ROUGH = island_bleed(paint_map(parts, "roughness"), lab)[..., 0]
    for nm_, m_ in (("metal", MET), ("wrap", ~MET)):
        log(f"material bands: {nm_} on {m_.sum() / MET.size * 100:.1f} % of the atlas, roughness median {np.median(ROUGH[m_]):.0f}")
    log(f"UV islands cover {(lab > 0).mean() * 100:.1f} % of the atlas; borders between islands trimmed and regrown per island")

    os.makedirs(out, exist_ok=True)
    for f_ in os.listdir(out):
        if f_.startswith(NAME) or f_.endswith(".ini"):
            os.remove(os.path.join(out, f_))
    write_vb(os.path.join(out, f"{NAME}.buf"), pos, nrm, col, uv, uv2)
    tris.astype("<u4").tofile(os.path.join(out, f"{NAME}Head.ib"))
    ops.save_dds(os.path.join(out, f"{NAME}HeadDiffuse.dds"), D, srgb=True)
    # the light map holds two texels and the normal map one: smaller files, read by the same UVs
    for v, (vname, steel, grip) in enumerate(LM_VARIANTS):
        if steel == "bands":
            L_ = band_lightmap(MET, ROUGH)
        else:
            L_ = np.where(MET[..., None], np.array(steel, np.uint8), np.array(grip, np.uint8))
        ops.save_dds(os.path.join(out, f"{NAME}HeadLightMap{v}.dds"), L_[::2, ::2].copy(), srgb=False)
    ops.save_dds(os.path.join(out, f"{NAME}HeadNormalMap.dds"), N, srgb=False)
    order = [t_[0] for t_ in hj["texture_hashes"][0]]
    slots = [(j, k) for j, k in enumerate(order) if k in ("Diffuse", "LightMap", "NormalMap")]
    ops.save_dds(os.path.join(out, f"{NAME}EffectMaskOff.dds"), np.zeros((16, 16, 4), np.uint8), srgb=False)
    write_ini(out, hj, stride, slots)
    log(f"wrote {out}: {len(pos)} vertices, {len(tris)} triangles; texture slots {slots}")
    return dict(pos=pos, nrm=nrm, uv=uv, tris=tris, D=D, g=g, gtex=gtex, gf=gf, rf=rf, parts=parts, fpos=fpos, fnrm=fnrm)


# ------------------------------------------------------------------------------------------------ looking

def view_rot(gf):
    """a turn that stands the game weapon up (its axis to +y, its flat side facing the camera, +z)"""
    B = np.stack([gf["across"], gf["axis"], gf["thin"]], 0)
    return B


def preview(r, path):
    gf, g = r["gf"], r["g"]
    V = view_rot(gf)
    mp, mn = r["pos"] @ V.T, r["nrm"] @ V.T
    gp, gn = g["pos"] @ V.T, g["nrm"] @ V.T
    tex = r["D"].astype(np.float32) / 255
    gt = r["gtex"]["Diffuse"].astype(np.float32) / 255
    ys = np.concatenate([mp[:, 1], gp[:, 1]])
    h = ys.max() - ys.min()
    B = (-0.19 * h, 0.19 * h, ys.min() - 0.02 * h, ys.max() + 0.02 * h)
    views = ((0, 0), (90, 0), (180, 0), (270, 0), (30, 20))
    size = (360, 1000)
    row_g = [render(gp, gn, [g["tris"]], size=size, yaw=y, pitch=p_, uv=g["uv"], textures=[gt], bounds=B, cull=True, ssaa=2)
             for y, p_ in views]
    row_m = [render(mp, mn, [r["tris"]], size=size, yaw=y, pitch=p_, uv=r["uv"], textures=[tex], bounds=B, cull=True, ssaa=2)
             for y, p_ in views]
    # the reference model as it is, textured with its own maps, at its own proportions in the same frame
    rp, rn, ru, rt, rx, off = [], [], [], [], [], 0
    for p in r["parts"]:
        q = r["fpos"](p["pos"]) @ V.T
        rp.append(q)
        rn.append(r["fnrm"](p["pos"], p["nrm"]) @ V.T)
        ru.append(p["uv"])
        rt.append(p["tris"] + off)
        rx.append(np.asarray(ref_tex(p["mat"], "albedo").resize((1024, 1024)), np.float32) / 255)
        off += len(q)
    rp, rn, ru = map(np.concatenate, (rp, rn, ru))
    row_r = [render(rp, rn, rt, size=size, yaw=y, pitch=p_, uv=ru, textures=rx, bounds=B, cull=False, ssaa=2)
             for y, p_ in views]
    labels = [f"game weapon yaw {y} pitch {p_}" for y, p_ in views] + [f"reference model {y}" for y, _ in views] + \
             [f"mod {y} (culled)" for y, _ in views]
    sheet(row_g + row_r + row_m, cols=len(views), labels=labels).save(path)
    # overlay of the two outlines (game in red, mod in green) face-on and edge-on, to check the grip lands
    ov = []
    for y in (0, 90):
        a = np.asarray(render(gp, gn, [g["tris"]], size=size, yaw=y, bounds=B, cull=False, colors=[(1, 0, 0)], bg=(0, 0, 0), flat_shade=1))
        b = np.asarray(render(mp, mn, [r["tris"]], size=size, yaw=y, bounds=B, cull=False, colors=[(0, 1, 0)], bg=(0, 0, 0), flat_shade=1))
        ov.append(Image.fromarray(np.maximum(a, b)))
    close = [render(mp, mn, [r["tris"]], size=size, yaw=y, pitch=p_, uv=r["uv"], textures=[tex], cull=True,
                    bg=(0, 150, 0), ssaa=2, bounds=(-0.081 * h, 0.081 * h, ys.min() - 0.01 * h, ys.min() + 0.44 * h))
             for y, p_ in ((0, 0), (180, 0), (45, 15))]
    HB = (-0.081 * h, 0.081 * h, ys.min() - 0.01 * h, ys.min() + 0.44 * h)
    for y in (0, 90):     # the hilt, game red over mod green, drawn as outlines-free flat fills (overlap yellow)
        a = np.asarray(render(gp, gn, [g["tris"]], size=size, yaw=y, bounds=HB, cull=False, colors=[(1, 0, 0)], bg=(0, 0, 0), flat_shade=1))
        b = np.asarray(render(mp, mn, [r["tris"]], size=size, yaw=y, bounds=HB, cull=False, colors=[(0, 1, 0)], bg=(0, 0, 0), flat_shade=1))
        ov.append(Image.fromarray(np.maximum(a, b)))
    sheet(ov + close, cols=7, labels=["game red / mod green, face", "edge", "hilt: game red / mod green", "hilt edge-on",
                                      "hilt close, culled on green 0", "180", "45 / 15"]).save(path.replace(".png", "_close.png"))
    log("preview:", path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--preview")
    a = ap.parse_args()
    r = build(a.out)
    if a.preview:
        preview(r, a.preview)
