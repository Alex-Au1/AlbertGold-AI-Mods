"""
MavuikaCloudyWolf / Motorcycle: Mavuika's bike (GI skill object "MavuikasBike") turned into Cloud Strife's Fenrir.

    python Tools/Builders/MavuikaCloudyWolfMotorcycle/build.py [--preview Docs/Previews/MavuikaCloudyWolfMotorcycle.png]

The SHAPE is read from a 3D-print model of the FFXIV "SDS Fenrir" mount that the maintainer downloaded (an ASCII
.stl, ~10k triangles, no UVs; NOT stored in this repo). Everything else is made here:

1. The game's bike is read from GI-Model-Importer-Assets (SkillData/MavuikasBike): its hashes, its vertex groups
   (bones) and the places Mavuika's riding pose needs: the two axles, the seat, the two grips.
2. MAP: the Fenrir is moved onto those places. Each wheel goes rigidly onto the game's axle at the game's radius
   (the wheels spin round their bones, so their centres must be the bones' centres). The rest goes through one
   smooth map: z so that the axles land on the axles, y so that the rear axle lands (then a linear lift for the
   front one), and the top of the bike round the seat is raised so the seat is where she sits.
3. HANDLEBAR: made here (tubes and grips) so the grips are exactly where her hands are in the game's own bike.
4. NORMALS: smooth within each part, split at creases.
5. WEIGHTS: the game bike's bones are rigid (one bone per vertex, 99.98 %): wheels on the wheel bones, the made
   handlebar on the handlebar bone, every other part on ONE bone, the majority of its nearest game vertices among
   body / rear swing arm / front cowl.
6. TEXTURE: a new atlas of material swatches (black paint, gunmetal, chrome, rubber, leather). UVs pick a swatch
   by part and a place in it by the vertex normal (a painted reflection, read the same way from every side), so
   no unwrap is needed. Light map texels per material are the game's own (sampled from its tyre, dark metal and
   bright metal), the normal map is the game's flat value.
"""

import argparse
import json
import os
import re
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO, "Tools", "ModKit"))

from modkit.gimi import Mesh, load_dump, weld_islands  # noqa: E402
from modkit import ops  # noqa: E402
from modkit.render import render, sheet  # noqa: E402

ASSETS = r"E:\Computer\Games\Genshin\Repos\Repos\GI-Model-Importer-Assets\SkillData\MavuikasBike"
STL = r"C:\Users\3dark\Downloads\SDS Fenrir - Final Fantasy 7 _ XIV - 3227878\files\SDS_Fenrir.stl"
OUT = os.path.join(REPO, "Mods", "GI", "Mavuika", "MavuikaCloudyWolf", "Motorcycle")
NAME = "MavuikasBike"
MODNAME = "MavuikaCloudyWolfMotorcycle"
TEX = 1024

# ---- the game bike's bones (measured 2026-11-17 from the dump: weighted boxes per group; front is +z) ----
VG_BODY, VG_FRONT_WHEEL, VG_REAR_WHEEL, VG_BAR, VG_SWING, VG_COWL = 6, 12, 13, 9, 14, 15
VG_ALLOWED = (VG_BODY, VG_SWING, VG_COWL)   # bones a Fenrir part may ride (side panels 0-5, forks 7/8 left out)
COWL_Z0 = 0.17         # the game's front cowl bone (15) covers z 0.175 .. 1.41

SEAT_Y = 0.96          # the game bike's seat top (z -0.5 .. -0.3, |x| < 0.2), where her pelvis rests
SEAT_Z = (-0.62, -0.22)  # where the seat is raised, game z
SEAT_FADE = 0.18
SEAT_LIFT = 0          # off since epoch 3: the lift sheared the tank's layered parts; a deep made saddle fills the dip
SX_OF_SY = 0.92        # the Fenrir a little narrower than tall: the game bike is 1.09 m wide


def log(*a):
    print(*a, flush=True)


# ------------------------------------------------------------------------------------------------ reading

def load_game():
    """the game's bike: whole vertex pool, the two draws' triangles, hashes and textures"""
    hj = json.load(open(os.path.join(ASSETS, "hash.json")))[0]
    comps = hj["object_classifications"]
    d = {}
    for c in comps:
        vb = [f for f in os.listdir(ASSETS) if f.startswith(NAME + c + "-vb0=")][0]
        ib = [f for f in os.listdir(ASSETS) if f.startswith(NAME + c + "-ib=")][0]
        a = load_dump(os.path.join(ASSETS, vb), os.path.join(ASSETS, ib))
        d[c] = a["tris"]
    a["vg"] = a["vg"].astype(np.int32)
    tex = {k: np.asarray(Image.open(os.path.join(ASSETS, f"{NAME}Head{k}.dds")).convert("RGBA"))
           for k in ("Diffuse", "LightMap", "NormalMap")}
    return a, d, hj, tex


def load_stl(path):
    txt = open(path).read()
    v = np.array(re.findall(r"vertex\s+(\S+)\s+(\S+)\s+(\S+)", txt), np.float64)
    q = np.round(v / 1e-3).astype(np.int64)
    u, inv = np.unique(q, axis=0, return_inverse=True)
    P = u * 1e-3
    T = inv.reshape(-1, 3)
    T = T[(T[:, 0] != T[:, 1]) & (T[:, 1] != T[:, 2]) & (T[:, 0] != T[:, 2])]
    lab = weld_islands(P, T)
    return P, T, lab


# ------------------------------------------------------------------------------------------------ measuring

def game_landmarks(g):
    pos, dom = g["pos"], g["vg"][:, 0]
    L = {}
    for name, grp in (("front", VG_FRONT_WHEEL), ("rear", VG_REAR_WHEEL)):
        p = pos[dom == grp]
        lo, hi = p.min(0), p.max(0)
        L[name] = np.array([0.0, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2])
        L[name + "_r"] = (hi[1] - lo[1]) / 2
        L[name + "_w"] = hi[0] - lo[0]
    L["ground"] = pos[:, 1].min()
    # grips: the handlebar bone's vertices out beyond |x| 0.26, a cylinder each side (PCA axis)
    bar = pos[dom == VG_BAR]
    for side, sgn in (("gripL", 1), ("gripR", -1)):
        q = bar[bar[:, 0] * sgn > 0.26]
        c = q.mean(0)
        _, _, vt = np.linalg.svd(q - c)
        ax = vt[0] * np.sign(vt[0][0] * sgn)
        t = (q - c) @ ax
        r = np.linalg.norm((q - c) - np.outer(t, ax), axis=1)
        L[side] = dict(c=c, ax=ax, t0=t.min(), t1=t.max(), r=np.percentile(r, 60))
    return L


def fenrir_wheels(P, T, lab):
    """the two wheel islands: round in the side view (y extent ~ z extent), narrow in x, at the two ends"""
    out = {}
    for i in np.unique(lab[T[:, 0]]):
        p = P[lab == i]
        lo, hi = p.min(0), p.max(0)
        ey, ez, ex = hi[1] - lo[1], hi[2] - lo[2], hi[0] - lo[0]
        if ey > 8 and abs(ey - ez) < 0.6 and ex < 7 and abs(lo[0] + hi[0]) < 0.2:
            c = (lo + hi) / 2
            out[i] = dict(c=np.array([0.0, c[1], c[2]]), r=ey / 2, hw=ex / 2)
    ks = sorted(out, key=lambda i: out[i]["c"][2])
    assert len(ks) == 2, f"expected two wheels, found {len(ks)}"
    return dict(rear=(ks[0], out[ks[0]]), front=(ks[1], out[ks[1]]))


class KNN:
    """brute-force nearest neighbours in chunks (no scipy on this machine)"""
    def __init__(self, pts):
        self.p = np.asarray(pts, np.float64)

    def query(self, x, k=1):
        x = np.asarray(x, np.float64)
        idx = np.empty((len(x), k), np.int64)
        dist = np.empty((len(x), k))
        for a in range(0, len(x), 512):
            d = ((x[a:a + 512, None, :] - self.p[None]) ** 2).sum(-1)
            j = np.argpartition(d, k - 1, axis=1)[:, :k] if k < d.shape[1] else np.argsort(d, 1)
            dd = np.take_along_axis(d, j, 1)
            o = np.argsort(dd, 1)
            idx[a:a + 512] = np.take_along_axis(j, o, 1)
            dist[a:a + 512] = np.sqrt(np.take_along_axis(dd, o, 1))
        if k == 1:
            return dist[:, 0], idx[:, 0]
        return dist, idx


# ------------------------------------------------------------------------------------------------ the map

def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def make_map(P, T, lab, W, L):
    """Fenrir coordinates -> game coordinates; returns the mapped positions and the wheel membership"""
    (ri, rw), (fi, fw) = W["rear"], W["front"]
    ground_f = P[:, 1].min()
    SZ = (L["front"][2] - L["rear"][2]) / (fw["c"][2] - rw["c"][2])
    SY = (L["rear"][1] - L["ground"]) / (rw["c"][1] - ground_f)
    SX = SY * SX_OF_SY
    log(f"map: SZ {SZ:.4f}  SY {SY:.4f}  SX {SX:.4f}")

    def body(p):
        q = np.empty_like(p)
        q[:, 0] = p[:, 0] * SX
        q[:, 2] = L["rear"][2] + (p[:, 2] - rw["c"][2]) * SZ
        q[:, 1] = L["ground"] + (p[:, 1] - ground_f) * SY
        return q

    q = body(P)
    # front axle: a lift growing linearly from the rear axle to the front one
    front_y = body(fw["c"][None])[0, 1]
    dy = L["front"][1] - front_y
    q[:, 1] += dy * np.clip((q[:, 2] - L["rear"][2]) / (L["front"][2] - L["rear"][2]), 0, 1.2)
    # the seat: raise the top of the bike round the seat window where it lies under SEAT_Y (the Fenrir's rider sits
    # in a dip behind the tank; hers sits higher): per z, lift = SEAT_Y - top, faded out at the window's ends, and
    # applied above ONE height band (a lift that followed each column's own top crumpled the seat, epoch 1), so the
    # bike below keeps its shape and the top moves up as a whole
    zs = np.arange(SEAT_Z[0] - SEAT_FADE, SEAT_Z[1] + SEAT_FADE + 1e-6, 0.03)
    tops = []
    for z0 in zs:
        c = (np.abs(q[:, 2] - z0) < 0.03) & (np.abs(q[:, 0]) < 0.12)
        tops.append(q[c, 1].max() if c.any() else SEAT_Y)
    tops = np.array(tops)
    wz_s = smoothstep(SEAT_Z[0] - SEAT_FADE, SEAT_Z[0], zs) * (1 - smoothstep(SEAT_Z[1], SEAT_Z[1] + SEAT_FADE, zs))
    lifts = np.maximum(0, SEAT_Y - 0.03 - tops) * wz_s * (SEAT_LIFT > 0)
    lifts = lifts.max() * wz_s     # one amount, faded at the window's ends
    lift_v = np.interp(q[:, 2], zs, lifts, left=0, right=0)
    y0 = tops.min() - 0.40
    q[:, 1] += lift_v * smoothstep(y0, y0 + 0.28, q[:, 1])
    log(f"seat: top in the window {tops.min():.3f} .. {tops.max():.3f}; raised up to {lift_v.max():.3f}")

    # wheels (and whatever lies wholly inside a wheel: hubs, caps) go rigidly onto the game's axles
    wheel_of = np.full(len(P), -1)
    hugs = []
    for key, (wi, w) in (("rear", W["rear"]), ("front", W["front"])):
        k = L[key + "_r"] / w["r"]
        for i in np.unique(lab[T[:, 0]]):
            p = P[lab == i]
            d = np.hypot(p[:, 1] - w["c"][1], p[:, 2] - w["c"][2])
            inside = d.max() < w["r"] * 0.98 and np.abs(p[:, 0]).max() < w["hw"] * 1.25
            # a fender hugs the tyre: centred over it (|x| within 1.3 half-widths), never inside 0.8 r, mostly within
            # 1.3 r (the front one reaches 1.8 r at its mount). It takes the wheel's map (or the larger front wheel
            # swallowed it, epoch 1) but not the wheel's bone
            hug = d.min() > w["r"] * 0.8 and np.median(d) < w["r"] * 1.3 and d.max() < w["r"] * 2.0 and                 np.abs(p[:, 0]).max() < w["hw"] * 1.3
            if i == wi or inside or hug:
                sel = lab == i
                q[sel] = L[key] + (P[sel] - w["c"]) * k
                if i == wi or inside:
                    wheel_of[sel] = 0 if key == "rear" else 1
                else:
                    log(f"  part {i} hugs the {key} wheel: wheel map, body bone")
                    hugs.append(i)
        log(f"wheel {key}: Fenrir r {w['r']:.2f} -> {L[key + '_r']:.3f} (scale {k:.4f})")
    return q, wheel_of, hugs


# ------------------------------------------------------------------------------------------------ handlebar

def tube(p0, p1, r, n=12, caps=True):
    """a cylinder from p0 to p1 (positions, triangles; counter-clockwise outward)"""
    ax = p1 - p0
    ax = ax / np.linalg.norm(ax)
    u = np.cross(ax, [0, 1, 0] if abs(ax[1]) < 0.9 else [1, 0, 0])
    u /= np.linalg.norm(u)
    v = np.cross(ax, u)
    th = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring = np.cos(th)[:, None] * u + np.sin(th)[:, None] * v
    pos = np.concatenate([p0 + r * ring, p1 + r * ring])
    tris = []
    for i in range(n):
        j = (i + 1) % n
        tris += [[i, n + i, n + j], [i, n + j, j]]
    if caps:
        c0, c1 = len(pos), len(pos) + 1
        pos = np.concatenate([pos, [p0, p1]])
        for i in range(n):
            j = (i + 1) % n
            tris += [[c0, j, i], [c1, n + i, n + j]]
    tris = np.array(tris)
    # orient every triangle outward from the tube's middle (sides and caps alike; the caps were inside-out, epoch 1)
    cen = (p0 + p1) / 2
    f = pos[tris]
    fn = np.cross(f[:, 1] - f[:, 0], f[:, 2] - f[:, 0])
    bad = (fn * (f.mean(1) - cen)).sum(1) < 0
    tris[bad] = tris[bad][:, ::-1]
    return pos, tris


# The game STEERS the handlebar (bone 9), the cowl (15), the forks (7, 8) and the front wheel (12) by one rotation
# about a raked axis through the front axle, leaning back 33 degrees from vertical. Measured from the bone matrices
# of the skinning pass (vs 653c63ba4a73ca8b, its t0 holds 16 bones x 3x4 floats) in the maintainer's steering dump
# FrameAnalysis-2026-11-17-221506: bones 9/15/7/8/12 relative to the body (6) turn about (0, -0.838, 0.546), and that
# line passes through the front axle. Anything on the handlebar bone must meet the body ON this axis, or it swings out
# of it when she steers (the first riser feet stood 18 cm behind the axis and floated, the maintainer's
# FloatingSteering.png, 2026-11-18).
STEER_DIR = np.array([0.0, 0.838, -0.546]) / np.linalg.norm([0.0, 0.838, -0.546])     # upwards along the axis
STEER_BONES = (VG_BAR, VG_COWL, 7, 8, VG_FRONT_WHEEL)


def steer_point(L, s):
    """the point on the steering axis s metres (along it) above the front axle"""
    return L["front"] + STEER_DIR * s


def handlebar(L, q, T):
    """grips exactly where the game's are; risers from them to a top clamp on a steering column that is coaxial with
    the game's steering axis, so the joint with the body stays put when the bar turns"""
    parts = []
    # where the axis leaves the Fenrir's body: the highest body point within 6 cm of the axis line
    rel = q - L["front"]
    s_ = rel @ STEER_DIR
    perp = np.linalg.norm(rel - np.outer(s_, STEER_DIR), axis=1)
    s_top = s_[perp < 0.06].max()
    gy = min(L["gripL"]["c"][1], L["gripR"]["c"][1])
    s_clamp = min(s_top + 0.06, (gy - 0.06 - L["front"][1]) / STEER_DIR[1])
    C = steer_point(L, s_clamp)
    log("steering axis leaves the body at", steer_point(L, s_top).round(3), "top clamp at", C.round(3))
    # the column: round and on the axis, sunk 15 cm into the body, so turning it changes nothing where it enters
    parts.append(("gunmetal",) + tube(steer_point(L, s_top - 0.15), C + STEER_DIR * 0.03, 0.05, 20))
    # the top clamp: a block across the column, in body paint
    parts.append(("paint",) + tube(C - [0.15, 0, 0], C + [0.15, 0, 0], 0.035, 14))
    for side in ("gripL", "gripR"):
        g = L[side]
        a, b = g["c"] + g["ax"] * g["t0"], g["c"] + g["ax"] * g["t1"]
        inner, outer = (a, b) if abs(a[0]) < abs(b[0]) else (b, a)
        parts.append(("rubber",) + tube(inner + (outer - inner) * 0.05, outer, g["r"] * 1.05, 14))
        # the bar: from the grip's inner end in and down to the clamp's end
        r = g["r"] * 0.7
        end = C + [np.sign(inner[0]) * 0.12, 0.0, 0.0]
        mid = np.array([np.sign(inner[0]) * 0.15, inner[1] - 0.02, (inner[2] + end[2]) / 2])
        parts.append(("gunmetal",) + tube(inner + (inner - mid) / np.linalg.norm(inner - mid) * 0.03, mid, r, 10))
        parts.append(("gunmetal",) + tube(mid, end, r * 1.15, 10))
        # (no brake levers: 6 mm tubes read as stray slivers under the grips, reviewer 2026-11-18)
    return parts


def tip_ring(c, n, r, n_seg=20):
    """an open bright ring on an exhaust mouth: outer wall, inner wall (facing in) and a lip facing out along n"""
    parts = []
    a, b = c - n * 0.015, c + n * 0.03
    po, to = tube(a, b, r * 1.12, n_seg, caps=False)
    pi, ti = tube(a, b, r * 0.92, n_seg, caps=False)
    parts.append(("tip", po, to))
    parts.append(("tip", pi, ti[:, ::-1]))           # the inner wall faces in
    u = np.cross(n, [0, 1, 0] if abs(n[1]) < 0.9 else [1, 0, 0])
    u /= np.linalg.norm(u)
    v = np.cross(n, u)
    ang = np.linspace(0, 2 * np.pi, n_seg, endpoint=False)
    circ = np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v
    lp = np.concatenate([b + circ * r * 1.12, b + circ * r * 0.92])
    j = np.arange(n_seg)
    k = (j + 1) % n_seg
    lt = np.concatenate([np.c_[j, k, j + n_seg], np.c_[k, k + n_seg, j + n_seg]])
    ln = np.cross(lp[lt[:, 1]] - lp[lt[:, 0]], lp[lt[:, 2]] - lp[lt[:, 0]])
    lt[(ln @ n) < 0] = lt[(ln @ n) < 0][:, ::-1]
    parts.append(("tip", lp, lt))
    # a dark (glowing) disc just inside the ring, so the mouth reads as a hole (1 cm down it was hidden: the
    # maintainer saw the holes "the same colour as the exhaust", 2026-11-18)
    dp = np.concatenate([[b - n * 0.008], b - n * 0.008 + circ * r * 0.93])
    dt = np.c_[np.zeros(n_seg, int), j + 1, k + 1]
    dn = np.cross(dp[dt[:, 1]] - dp[dt[:, 0]], dp[dt[:, 2]] - dp[dt[:, 0]])
    dt[(dn @ n) < 0] = dt[(dn @ n) < 0][:, ::-1]
    # mapped RADIALLY across the hole swatch (centre to centre, rim to 46 % out), so the skill's fire burst painted
    # there shows; every corner reading one texel made it "a plain orange" (the maintainer, 2026-11-18)
    su, sv, ss = swatch_rect(MATS["hole"][0])
    # each disc turns (and every other one mirrors) the burst, so the four do not read as one stamp (epoch 2)
    key_ = int(abs(c[0]) * 1000 + abs(c[1]) * 100) % 360
    rot, mir = np.radians(key_), -1 if key_ % 2 else 1
    duv = np.concatenate([[[0.5, 0.5]], 0.5 + 0.46 * np.c_[np.cos(mir * ang + rot), np.sin(mir * ang + rot)]])
    parts.append(("hole", dp, dt, np.c_[su + duv[:, 0] * ss, sv + duv[:, 1] * ss]))
    return parts


def fire_burst(px):
    """the skill's exhaust fire, after Mavuika's own (FireBikeDesign.png: mostly WHITE-GOLD, angular flame strokes,
    hollow chevron outlines and jagged streaks that point ONE way, orange to red only at the edges).
    History: smooth rays and a zig-zag crown read as a flower (epoch 1); radial blades read as a pinwheel / turbine
    with too much plain orange (epochs 2-3). So it is no longer radial: flames rise "up" the swatch (each hole turns
    it differently), white-gold through the middle"""
    from PIL import ImageDraw, ImageFilter
    s = px * 2                                                  # drawn at 2x, then reduced (smooth edges)
    y, x = np.mgrid[-1:1:s * 1j, -1:1:s * 1j]                   # y -1 is the top of the swatch
    r = np.clip(np.hypot(x, y), 0, 1)
    # hot through the middle and low, red only at the rim
    heat = np.clip(1.0 - r ** 1.6 + 0.15 * (y + 0.2), 0, 1)
    # IN GAME the glow multiplies the diffuse and CLIPS: white-gold and gold-orange both came out one flat
    # orange-yellow, the strokes invisible (audit 8, 04_skillon_leftrear34_closeup_x2_flat_orange_no_pattern.png),
    # while the tail's yellow-orange bars on its red lens survived. So the ground is DARK red-orange (it lands on red
    # and orange once multiplied) and only the strokes are bright enough to reach yellow-white
    # (a darker ground, so the strokes would survive the glow's clipping, was tried and REVERTED: the maintainer
    # found it "looks worse", 2026-11-18; the brighter fire below is the one kept)
    stops = [(0.0, (150, 30, 8)), (0.18, (214, 70, 16)), (0.38, (250, 140, 36)), (0.6, (255, 206, 90)),
             (0.82, (255, 238, 170)), (1.0, (255, 248, 222))]
    hs = np.array([s_[0] for s_ in stops])
    col = np.stack([np.interp(heat, hs, [s_[1][c] for s_ in stops]) for c in range(3)], -1)
    fill_ = Image.new("L", (s, s), 0)
    line_ = Image.new("L", (s, s), 0)
    d, dl = ImageDraw.Draw(fill_), ImageDraw.Draw(line_)

    def P(u, v):                                                # swatch units, -1..1, v up = -1
        return ((u + 1) / 2 * s, (v + 1) / 2 * s)
    rng = np.random.default_rng(5)
    # jagged flame tongues rising from the bottom, leaning a little right
    for u0 in (-0.62, -0.3, 0.0, 0.3, 0.6):
        h = rng.uniform(1.0, 1.5)
        w = rng.uniform(0.16, 0.24)
        lean = rng.uniform(0.05, 0.25)
        tip = (u0 + lean, 0.9 - h * 1.25)
        d.polygon([P(u0 - w, 0.95), P(u0 - w * 0.35, 0.95 - h * 0.45), P(u0 - w * 0.9 + lean * 0.4, 0.95 - h * 0.6),
                   P(*tip), P(u0 + w * 0.5 + lean * 0.6, 0.95 - h * 0.55), P(u0 + w * 0.15, 0.95 - h * 0.35),
                   P(u0 + w, 0.95)], fill=255)
    # hollow chevrons pointing up (the bike's "^" strokes), stacked, open
    width = max(3, s // 60)
    for (cu, cv, sz) in ((-0.35, -0.2, 0.30), (0.25, -0.45, 0.26), (0.05, 0.25, 0.34), (0.5, 0.1, 0.22)):
        dl.line([P(cu - sz, cv + sz * 0.7), P(cu, cv - sz * 0.5), P(cu + sz * 0.9, cv + sz * 0.6)], fill=255,
                width=width, joint="curve")
    # thin jagged streaks shooting up
    for k in range(6):
        u0 = rng.uniform(-0.8, 0.8)
        pts_ = [P(u0, 0.7)]
        for j in range(4):
            pts_.append(P(u0 + rng.uniform(-0.08, 0.12) * (j + 1) * 0.6, 0.7 - (j + 1) * 0.35))
        dl.line(pts_, fill=200, width=max(2, s // 110))
    glow = Image.merge("L", [Image.fromarray(np.maximum(np.asarray(fill_), np.asarray(line_)))]).filter(
        ImageFilter.GaussianBlur(s * 0.03))
    st = np.asarray(fill_, float)[..., None] / 255
    ln = np.asarray(line_, float)[..., None] / 255
    gl = np.asarray(glow, float)[..., None] / 255
    col = col + (np.array([255, 196, 80]) - col) * np.clip(gl * 1.5, 0, 1) * 0.7         # gold glow round strokes
    col = col + (np.array([255, 246, 214]) - col) * st * 0.9                              # white-gold tongues
    col = col + (np.array([255, 252, 236]) - col) * ln                                    # bright stroke lines
    rim = np.clip((r - 0.86) / 0.14, 0, 1)[..., None]                                     # deep red only at the rim
    col = col + (np.array([150, 30, 8]) - col) * rim * 0.85
    img = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)).resize((px, px), Image.LANCZOS)
    return np.asarray(img)


def face_patch(tri_face, tri_all, off=0.005, shrink=0.96, nu=13, nv=9):    # 0.88 left a wide dark frame (epoch 2)
    """a grid laid over a FOLDED face (the left can's back): rays along the face's mean normal, rows as wide as
    `shrink` of the face there, each point lifted `off` above the part. Returns pos, tris, grid uv (0..1)"""
    e1, e2 = tri_face[:, 1] - tri_face[:, 0], tri_face[:, 2] - tri_face[:, 0]
    nn = np.cross(e1, e2)
    nw = nn.sum(0)
    nw /= np.linalg.norm(nw)
    c = tri_face.reshape(-1, 3).mean(0)
    u = np.cross([0.0, 1.0, 0.0], nw)
    u /= np.linalg.norm(u)
    v = np.cross(nw, u)
    pts = tri_face.reshape(-1, 3) - c
    pu, pv = pts @ u, pts @ v
    vs = np.linspace(pv.min() + 0.004, pv.max() - 0.004, nv) * shrink
    rows, ok = [], True
    for vv in vs:
        us = np.linspace(pu.min(), pu.max(), 61)
        hit = [np.isfinite(ray_hits(c + u * uu + v * vv + nw * 0.5, -nw, tri_face).min()) for uu in us]
        if not any(hit):
            ok = False
            break
        hu = us[np.nonzero(hit)[0]]
        mid, half = (hu.min() + hu.max()) / 2, (hu.max() - hu.min()) / 2 * shrink
        row = []
        for uu in np.linspace(mid - half, mid + half, nu):
            o = c + u * uu + v * vv + nw * 0.5
            t = ray_hits(o, -nw, tri_all).min()
            row.append(o - nw * t + nw * off if np.isfinite(t) else [np.nan] * 3)
        row = np.array(row, float)
        bad = ~np.isfinite(row[:, 0])
        if bad.all():
            ok = False
            break
        for k in range(3):
            row[bad, k] = np.interp(np.nonzero(bad)[0], np.nonzero(~bad)[0], row[~bad, k])
        rows.append(row)
    if not ok:
        return None
    P = np.array(rows).reshape(-1, 3)
    tris = []
    for rr in range(nv - 1):
        for cc in range(nu - 1):
            i0 = rr * nu + cc
            tris += [[i0, i0 + 1, i0 + nu], [i0 + 1, i0 + nu + 1, i0 + nu]]
    tris = np.array(tris)
    fn = np.cross(P[tris[:, 1]] - P[tris[:, 0]], P[tris[:, 2]] - P[tris[:, 0]])
    tris[(fn @ nw) < 0] = tris[(fn @ nw) < 0][:, ::-1]
    gu, gv = np.meshgrid(np.linspace(0, 1, nu), np.linspace(0, 1, nv))
    return P, tris, np.c_[gu.ravel(), 1 - gv.ravel()]


def ray_hits(o, d, tri):
    """distances along d (Moller-Trumbore) from o to each triangle in tri (n, 3, 3); inf where missed"""
    e1, e2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    pv = np.cross(d, e2)
    det = (e1 * pv).sum(1)
    ok = np.abs(det) > 1e-12
    inv = np.where(ok, 1 / np.where(ok, det, 1), 0)
    tv = o - tri[:, 0]
    u = (tv * pv).sum(1) * inv
    qv = np.cross(tv, e1)
    v = (qv @ d) * inv
    t = (qv * e2).sum(1) * inv
    hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0)
    return np.where(hit, t, np.inf)


def surface_patch(tri, ys, frac, off, nx=13, z0=-2.0):
    """a grid laid on the back of a body part (rays forward along +z from behind): rows at heights ys, each as wide
    as frac of the part there, lifted off the surface by off. None where a row misses"""
    d = np.array([0.0, 0.0, 1.0])
    rows = []
    for y in ys:
        xs = np.linspace(0, 0.3, 61)
        hit = [np.isfinite(ray_hits(np.array([x, y, z0]), d, tri).min()) and
               np.isfinite(ray_hits(np.array([-x, y, z0]), d, tri).min()) for x in xs]
        hw = xs[np.nonzero(hit)[0].max()] * frac if any(hit) else 0
        if hw <= 0:
            return None
        row = []
        for x in np.linspace(-hw, hw, nx):
            t = ray_hits(np.array([x, y, z0]), d, tri).min()
            row.append([x, y, z0 + t - off])
        row = np.array(row)
        # a ray through a small hole in the surface missed: that point went to infinity and drew a dark stick across
        # the lens. Take the nearest hits along the row instead
        bad = ~np.isfinite(row[:, 2])
        if bad.all():
            return None
        if bad.any():
            row[bad, 2] = np.interp(np.nonzero(bad)[0], np.nonzero(~bad)[0], row[~bad, 2])
        # a thin rod of the source model runs diagonally over the hump's back and showed through the lens between
        # the grid's points: each row is flat at the rearmost point found by 41 rays across it (curved only top to
        # bottom), so nothing of the body is in front of it
        dense = [ray_hits(np.array([x, y, z0]), d, tri).min() for x in np.linspace(-hw, hw, 41)]
        dense = [t for t in dense if np.isfinite(t)]
        row[:, 2] = min(row[:, 2].min(), z0 + min(dense) - off)
        rows.append(row)
    P = np.array(rows).reshape(-1, 3)
    tris = []
    for r in range(len(ys) - 1):
        for c in range(nx - 1):
            i0 = r * nx + c
            tris += [[i0, i0 + 1, i0 + nx], [i0 + 1, i0 + nx + 1, i0 + nx]]
    tris = np.array(tris)
    fn = np.cross(P[tris[:, 1]] - P[tris[:, 0]], P[tris[:, 2]] - P[tris[:, 0]])
    tris[fn[:, 2] > 0] = tris[fn[:, 2] > 0][:, ::-1]     # facing back (-z)
    return P, tris


FRONT_LIFT_ON = False   # OFF (the maintainer, HeadLightFrontCrooked.png, 2026-11-18): the 16.5 cm ramp lift tipped
                        # the nose up, crooked; "restore the original shape". The fender fit alone keeps it clear
FRONT_CLEAR = 0.06      # metres between the front tyre's top and the body over it
FRONT_RAMP = (0.42, 0.62)   # the lift ramps in over this z (the handlebar column is at z 0.39, the grips at 0.32)


def lift_front(q, P, T, lab, bone_v, L):
    """The nose cleared the front tyre by only ~2 cm, and the game's suspension lifts the front wheel up to 1.6 cm
    (bone 12 in the steering dump), so the tyre showed through the nose (the maintainer, BikeClip.png, 2026-11-18).
    Lift the body's front (body bone, not the long arms that hold the hub) by a ramp in z alone, so layered parts
    move together (a lift by height crumpled the tank, epoch 3), enough for FRONT_CLEAR over the tyre"""
    lift_ok = bone_v == VG_BODY
    for i in np.unique(lab[T[:, 0]]):
        p = P[lab == i]
        if np.ptp(p[:, 2]) > 20 and abs(p[:, 0].mean()) > 3:
            lift_ok[lab == i] = False                     # the long front arms
    ax, R = L["front"], L["front_r"]
    rel = q - ax
    over = lift_ok & (np.abs(rel[:, 0]) < L["front_w"] / 2 + 0.03) & (np.abs(rel[:, 2]) < R) & (rel[:, 1] > 0.2)
    top = np.sqrt(np.maximum(R ** 2 - rel[:, 2] ** 2, 0))
    need = np.where(over, FRONT_CLEAR - (rel[:, 1] - top), 0).max()
    need = max(need, 0.0)
    # the ramp starts at z 0.42 on the centre line to keep the handlebar column (z 0.39, x 0) seated; off the centre
    # it starts FRONT_RAMP_SIDE earlier, so the nose's flanks over the fender lift too (they came within 1.1 cm of
    # it at 25 degrees of steering, round 3 epoch 3)
    side = smoothstep(0.06, 0.12, np.abs(q[:, 0])) * FRONT_RAMP_SIDE
    ramp = smoothstep(FRONT_RAMP[0] - side, FRONT_RAMP[1] - side, q[:, 2])
    # ...and over the FRONT FENDER, which turns with the wheel (BikeClip2.png: the nose met the fender's top). Per
    # 2 cm (x, z) cell, the fender's highest point at rest and steered +-25 degrees; every body point over the wheel
    # that is above, or a little into, that top must clear it by NOSE_OVER_FENDER once lifted (the ramp's weight at
    # its z counts: a point where the ramp barely lifts cannot be helped by more lift and is reported instead)
    cow = bone_v == VG_COWL
    if cow.any():
        cell = 0.02
        tops = {}
        for deg in (0, -15, 15, -25, 25):
            a = np.radians(deg)
            r_ = q[cow] - ax
            cp = r_ * np.cos(a) + np.cross(STEER_DIR, r_) * np.sin(a) + np.outer(r_ @ STEER_DIR, STEER_DIR) * (1 - np.cos(a)) + ax
            for kx, kz, y in zip(np.floor(cp[:, 0] / cell).astype(int), np.floor(cp[:, 2] / cell).astype(int), cp[:, 1]):
                if y > tops.get((kx, kz), -9):
                    tops[(kx, kz)] = y
        stuck = 0
        for i in np.where(lift_ok & (rel[:, 1] > 0.25))[0]:
            key = (int(np.floor(q[i, 0] / cell)), int(np.floor(q[i, 2] / cell)))
            if key not in tops or q[i, 1] < tops[key] - 0.08:
                continue
            short = tops[key] + NOSE_OVER_FENDER - q[i, 1]
            if short <= 0:
                continue
            if ramp[i] < 0.3:
                stuck += 1
                continue
            need = max(need, short / ramp[i])
        if stuck:
            log(f"front lift: {stuck} body points over the fender sit where the ramp barely lifts (z < ~0.5)")
    # room for the headlight on the nose's face (the maintainer: "raise the bike more"): with only the clearance,
    # the nose sat ~3 cm over the fender's crest and a 15 cm lamp kept clear of the steered fender rose above the
    # nose's top, a barrel on a thin line (round 3 epoch 1)
    need = min(need + NOSE_LAMP_ROOM, FRONT_LIFT_MAX)
    out = q.copy()
    out[:, 1] += need * ramp * lift_ok
    log(f"front lifted by {need:.3f} m (ramp over z {FRONT_RAMP[0]}..{FRONT_RAMP[1]}) for {FRONT_CLEAR} m over the tyre"
        f" and {NOSE_OVER_FENDER} m over the fender (steered +-25)")
    return out


UNDER_GAP = 0.04        # (3 cm read as touching in the at-rest section, epoch 1) metres the nose's underside keeps over the fender (swept) and over the tyre (lifted 1.6 cm)
UNDER_H = 0.08          # the squeeze reaches this far above the clearance floor; higher, the body is untouched
UNDER_DEEP = 0.12       # body points further than this below the floor are beside the wheel, not over it


def dent_underside(q, P, T, lab, bone_v, L):
    """Clear the front wheel WITHOUT changing the bike's outside (the maintainer, HeadLightFrontCrooked.png,
    2026-11-18: the ramp lift tipped the nose up, crooked). Per 2 cm (x, z) column over the wheel: a floor = the
    highest of the fender (swept +-25 degrees of steering) and the tyre (swept, lifted 1.6 cm by the suspension), plus
    UNDER_GAP. Body points from the deepest one under the floor up to UNDER_H over it are squeezed into [floor,
    floor + UNDER_H], so the nose's underside is hollowed and its top, 20-30 cm higher, does not move"""
    lift_ok = bone_v == VG_BODY
    for i in np.unique(lab[T[:, 0]]):
        p = P[lab == i]
        if np.ptp(p[:, 2]) > 20 and abs(p[:, 0].mean()) > 3:
            lift_ok[lab == i] = False                     # the long front arms (they hold the hub)
    ax, R, hw = L["front"], L["front_r"], L["front_w"] / 2
    cell = 0.02
    # the tyre's surface as points (a band of circles), and the fender's points
    th = np.linspace(0, np.pi, 90)
    xs = np.linspace(-hw, hw, 9)
    tyre = np.array([[x, ax[1] + 0.016 + R * np.sin(t), ax[2] + R * np.cos(t)] for x in xs for t in th])
    pts = np.concatenate([q[bone_v == VG_COWL], tyre])
    floor = {}
    for deg in (0, -10, 10, -15, 15, -20, 20, -25, 25):
        a = np.radians(deg)
        r_ = pts - ax
        cp = r_ * np.cos(a) + np.cross(STEER_DIR, r_) * np.sin(a) + np.outer(r_ @ STEER_DIR, STEER_DIR) * (1 - np.cos(a)) + ax
        for kx, kz, y in zip(np.floor(cp[:, 0] / cell).astype(int), np.floor(cp[:, 2] / cell).astype(int), cp[:, 1]):
            if y > floor.get((kx, kz), -9):
                floor[(kx, kz)] = y
    # widen by one cell (a vertex at a cell's edge meets the next cell's top)
    fl = dict(floor)
    for (kx, kz), y in floor.items():
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                k_ = (kx + dx, kz + dz)
                fl[k_] = max(fl.get(k_, -9), y)
    idx = np.where(lift_ok & (q[:, 1] > ax[1] + 0.2))[0]
    keys = list(zip(np.floor(q[idx, 0] / cell).astype(int), np.floor(q[idx, 2] / cell).astype(int)))
    F = np.array([fl.get(k_, -9) + UNDER_GAP for k_ in keys])
    has = F > 0
    depth = {}
    for k_, y, f_, h in zip(keys, q[idx, 1], F, has):
        if h and f_ - UNDER_DEEP < y < f_:
            depth[k_] = max(depth.get(k_, 0.0), f_ - y)
    # smooth the depth over neighbouring columns (a max under a Gaussian), so the dent has no steps
    D = {}
    for (kx, kz), dd in depth.items():
        for dx in range(-3, 4):
            for dz in range(-3, 4):
                k_ = (kx + dx, kz + dz)
                D[k_] = max(D.get(k_, 0.0), dd * np.exp(-0.5 * (dx * dx + dz * dz) / 1.5 ** 2))
    out = q.copy()
    moved = 0
    for j, (i, k_, f_, h) in enumerate(zip(idx, keys, F, has)):
        d_ = D.get(k_, 0.0)
        y = q[i, 1]
        if not h or d_ <= 0 or not (f_ - d_ - 1e-9 <= y <= f_ + UNDER_H):
            continue
        out[i, 1] = f_ + (y - (f_ - d_)) * UNDER_H / (UNDER_H + d_)
        moved += 1
    log(f"nose underside: {moved} body points squeezed up, the deepest {max(depth.values(), default=0):.3f} m under "
        f"the floor ({UNDER_GAP} m over the swept fender and tyre)")
    return out


NOSE_OVER_FENDER = 0.03     # metres between the body and the front fender's top, at rest and steered (5 cm was
                            # tried: the lift rose to 23 cm and the true 3D gaps did not change, their closest
                            # points sit where the ramp barely lifts; reverted)
FRONT_LIFT_MAX = 0.25       # the most the front is lifted
FRONT_RAMP_SIDE = 0.08      # how much earlier (in z) the lift ramp starts away from the centre line
NOSE_LAMP_ROOM = 0.10       # extra lift, so the nose's face is tall enough to carry the headlight over the fender


FENDER_CLEAR = 0.025    # metres between the front tyre and the fender pieces that turn with it (1.2 cm read as
                        # the fender sitting on the tyre, round 2 epoch 6)


def fit_front_fenders(q, T, lab, bone_v, L):
    """The front fender pieces (on the steering cowl bone, so they turn with the wheel) dipped up to 3.2 cm INTO the
    tyre, at its front and over its crown (reviewer epoch 1, after the body was lifted). Each such piece is grown
    radially round the axle (y, z) by ONE factor, keeping its shape, until its innermost point in the tyre's band
    clears it by FENDER_CLEAR"""
    # Epoch 3 of the first round: one factor for the whole piece made the main fender 16.5 % bigger, an oversized
    # slab head-on. Now the push is LOCAL: per 4-degree sector round the axle, the most any vertex of the piece in
    # the tyre's band needs, smoothed over neighbouring sectors, applied radially to every vertex of the piece in
    # that sector (inner and outer skins together, so the piece keeps its thickness)
    # Round 2 epoch 4: per piece, the main fender (pushed up to 6 cm) and the thin pieces lying on it (pushed < 5 mm)
    # parted into a doubled skin with a step. ONE field now, from all the cowl pieces together, moves them all
    ax, R, hw = L["front"], L["front_r"], L["front_w"] / 2
    out = q.copy()
    nb = 90
    sel = np.where(bone_v == VG_COWL)[0]
    rel = q[sel] - ax
    d = np.hypot(rel[:, 1], rel[:, 2])
    th = np.arctan2(rel[:, 1], rel[:, 2])
    b = ((th + np.pi) / (2 * np.pi) * nb).astype(int) % nb
    band = (np.abs(rel[:, 0]) < hw + 0.01) & (d > 0.8 * R) & (d < R + FENDER_CLEAR)
    if not band.any():
        return out
    need = np.zeros(nb)
    np.maximum.at(need, b[band], R + FENDER_CLEAR - d[band])
    k_ = np.exp(-0.5 * (np.arange(-4, 5) / 1.8) ** 2)
    sm = np.zeros(nb)
    for o, kk in zip(range(-4, 5), k_):
        sm = np.maximum(sm, np.roll(need, o) * kk / k_.max())
    push = sm[b] * (d > 0.5 * R)                         # radially out, not the hub-side bits
    out[sel, 1:] = ax[1:] + rel[:, 1:] * ((d + push) / np.maximum(d, 1e-6))[:, None]
    log(f"front fender (all cowl pieces, one field): pushed out by up to {need.max():.3f} m where it dipped in")
    # LOWER AT THE BACK (the maintainer, BikeClip2.png, 2026-11-18): under the nose the fender is a thick shroud
    # standing ~10 cm over the tyre, and the nose met its top. Angle round the axle from the front (0) over the top
    # (90) to the back (180): past FENDER_TAIL[0], blending in by FENDER_TAIL[1], each point's height over the
    # tyre's clearance line is scaled down to FENDER_TAIL[2], so the rear of the shroud hugs the tyre and a gap opens
    # under the nose. (Swinging the rear arc forward instead lifted bulky far pieces onto the top: dropped)
    rel = out[sel] - ax
    d = np.hypot(rel[:, 1], rel[:, 2])
    phi = np.degrees(np.arctan2(rel[:, 1], rel[:, 2]))
    wgt = smoothstep(FENDER_TAIL[0], FENDER_TAIL[1], phi) * (d > R + FENDER_CLEAR)
    if wgt.any():
        base = R + FENDER_CLEAR
        d2 = d - wgt * (d - base) * (1 - FENDER_TAIL[2])
        out[sel, 1:] = ax[1:] + rel[:, 1:] * (d2 / np.maximum(d, 1e-6))[:, None]
        log(f"front fender: its rear (past {FENDER_TAIL[0]:.0f} deg) lowered toward the tyre, by up to "
            f"{(d - d2).max():.3f} m")
    # ...and SHORTER: lowered, its trailing end hugged the tyre right in front of the engine's front, 2 cm from the
    # body (a true 3D measure, round 3 epoch 3). Past FENDER_END[0] the arc is drawn forward to end at
    # FENDER_END[1]. Done after the lowering, so the end stays close to the tyre (done before it, it swung bulky
    # far pieces up onto the top)
    rel = out[sel] - ax
    d = np.hypot(rel[:, 1], rel[:, 2])
    phi = np.degrees(np.arctan2(rel[:, 1], rel[:, 2]))
    tail = (phi > FENDER_END[0]) & (d > 0.5 * R)
    if tail.any() and phi[tail].max() > FENDER_END[1]:
        pmax = phi[tail].max()
        s_ = (FENDER_END[1] - FENDER_END[0]) / (pmax - FENDER_END[0])
        p2 = np.radians(np.where(tail, FENDER_END[0] + (phi - FENDER_END[0]) * s_, phi))
        out[sel, 1] = np.where(tail, ax[1] + d * np.sin(p2), out[sel, 1])
        out[sel, 2] = np.where(tail, ax[2] + d * np.cos(p2), out[sel, 2])
        log(f"front fender: its end drawn forward from {pmax:.0f} to {FENDER_END[1]:.0f} deg round the axle")
    return out


FENDER_END = (118.0, 130.0)     # (from 100, to soften a bend at the end, it swung pieces up under the nose: the
                                # gap fell to 1.4 cm; round 4 epoch 3, reverted) (138 left the nose's flanks 2.2 cm off its tip in the side section, with the
                                # original nose back; epoch 2, 2026-11-18) degrees round the front axle: where the shortening starts, where the fender ends
                                # (an end at 152 sat under the headstock's underside, 0.9 cm off when steered: the
                                # body there is only ~6 cm outside the tyre, no room for a fender)


FENDER_TAIL = (-110.0, 120.0, 0.15)  # (from -60 the front tip bent at a corner, epoch 2)  # (95..115 read as a DENT in the fender where it meets the nose, in game,
                                    # DentedWheel.png, 2026-11-18; from 20 the unlowered front stayed a thick lump
                                    # with a step, epoch 1: now the whole arch comes down smoothly) degrees round the front axle where the lowering starts and is full; the share
                                    # of the height over the tyre's clearance line that is kept (0.35 left body
                                    # slivers 0.2-2 cm over its rear slope, epoch 1)


def lamp_at(tri, y0, z_fallback, where):
    """the lamp itself, centred at height y0 in front of the surface `tri`: seated in front of the furthest-forward
    point of that surface over the WHOLE lens (a chin piece below the centre once cut a notch into the lens, round 1
    epoch 1), out on a housing (flush, it vanished from the side, epoch 3), a bright bezel, a slightly domed lens"""
    n = np.array([0.0, -0.08, 1.0])
    n /= np.linalg.norm(n)
    zs = []
    for a_ in np.linspace(0, 2 * np.pi, 16, endpoint=False):
        for rr in (0.0, 0.5, 1.0):
            t = ray_hits(np.array([HEAD_R * 1.15 * rr * np.cos(a_), y0 + HEAD_R * 1.15 * rr * np.sin(a_), 3.0]),
                         np.array([0.0, 0.0, -1.0]), tri).min()
            if np.isfinite(t):
                zs.append(3.0 - t)
    z0 = max(zs) if zs else z_fallback
    c = np.array([0.0, y0, z0 + HEAD_OUT])
    # the housing: a deep bucket from well inside the body out to the lens, wider than the lens (a 10 cm stub read
    # as a lamp on a thin stalk, epoch 1)
    # (on top of the nose at r 5.5 cm, 18 cm deep read as a long can from the side: 10 cm, 2026-11-18)
    parts = [("gunmetal",) + tube(c - n * (HEAD_OUT + 0.08), c, HEAD_R * 1.22, 24)]
    po, to = tube(c - n * 0.004, c + n * 0.012, HEAD_R * 1.26, 24, caps=False)      # the bezel
    parts.append(("tip", po, to))
    u = np.cross(n, [0, 1, 0])
    u /= np.linalg.norm(u)
    v = np.cross(n, u)
    ang = np.linspace(0, 2 * np.pi, 24, endpoint=False)
    circ = np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v
    lp = np.concatenate([[c + n * 0.016], c + n * 0.006 + circ * HEAD_R])
    j = np.arange(24)
    lt = np.c_[np.zeros(24, int), j + 1, (j + 1) % 24 + 1]
    ln = np.cross(lp[lt[:, 1]] - lp[lt[:, 0]], lp[lt[:, 2]] - lp[lt[:, 0]])
    lt[(ln @ n) < 0] = lt[(ln @ n) < 0][:, ::-1]
    su, sv, ss = swatch_rect(MATS["plate"][0])
    hu, hv, hs = HEAD_UV                                 # the lamp's square in the plate swatch (swatch units)
    luv = np.concatenate([[[hu, hv]], np.c_[hu + hs * 0.46 * np.cos(ang), hv + hs * 0.46 * np.sin(ang)]])
    parts.append(("lens", lp, lt, np.c_[su + luv[:, 0] * ss, sv + luv[:, 1] * ss]))   # (normals set in build)
    # a MOUNT: on top of the nose the housing overhung air, "a can hung off the nose" (the maintainer's ask for the
    # lamp ON TOP, 2026-11-18; epoch 1). Two struts from the housing's underside down onto the nose, and a cross bar
    for t_ in (0.035, 0.085):
        top_ = c - n * t_ + np.array([0.0, -HEAD_R * 1.1, 0.0])
        h_ = ray_hits(top_ + [0, 0.02, 0], np.array([0.0, -1.0, 0.0]), tri).min()
        if np.isfinite(h_) and h_ < 0.4:
            bot_ = top_ + [0, 0.02 - h_ - 0.02, 0]
            for sx in (-0.045, 0.045):
                parts.append(("gunmetal",) + tube(top_ + [sx, 0.01, 0], bot_ + [sx, 0, 0], 0.014, 10))
            parts.append(("gunmetal",) + tube(top_ + [-0.06, -0.01, 0], top_ + [0.06, -0.01, 0], 0.016, 10))
    log(f"headlight {where} at {c.round(3)}, r {HEAD_R}")
    return parts


def headlight(q, T, mat, bone_v, L):
    """a round headlight (the maintainer, 2026-11-18), pale glass with the skill off and lit warm white with it.
    Returns (bone, parts): on the nose cowl (body bone) where the Fenrir reference carries its light, if the window
    between the front fender's top and the handlebar clamp holds it; else on the front fender (the steering cowl
    bone, so it turns with the wheel).
    History: on the nose under a fender grown 16.5 % it sat up under the clamp, small and perched (epoch 2); on the
    fender it read as a decal on a mudguard (epoch 3); with the fender pushed out only where it dipped into the tyre
    the nose window opened"""
    f = q[T]
    cen = f.mean(1)
    nose = np.isin(mat, ["paint", "gunmetal", "panel"]) & (np.abs(cen[:, 0]) < 0.15) & (cen[:, 2] > 0.45) & \
        (bone_v[T[:, 0]] == VG_BODY)
    cowl_all = (bone_v[T[:, 0]] == VG_COWL) & (np.abs(cen[:, 0]) < 0.15)
    clamp_y = min(L["gripL"]["c"][1], L["gripR"]["c"][1]) - 0.06
    nb = None
    for y in np.linspace(0.75, 1.3, 56):                  # (the nose now stands higher: the front is lifted)
        t = ray_hits(np.array([0.0, y, 3.0]), np.array([0.0, 0.0, -1.0]), f[nose]).min()
        if np.isfinite(t) and (nb is None or 3.0 - t > nb[1]):
            nb = (y, 3.0 - t)
    if nb is not None:
        # the maintainer asked for it ON THE NOSE (2026-11-18), so the handlebar clamp no longer limits it (the bar
        # is 30 cm behind the lamp; from the front the two may overlap, they do not touch): the nose's furthest
        # forward point, kept a lamp's radius plus 1.5 cm above the fender's top there
        # the fender's top near the lamp, swept through +-25 degrees of steering (at rest only, the steered fender
        # rose to the lamp's rim, epoch 1)
        fender_top = 0.0
        ax_ = L["front"]
        for deg in (0, -15, 15, -25, 25):
            a = np.radians(deg)
            r_ = f[cowl_all].reshape(-1, 3) - ax_
            cp = r_ * np.cos(a) + np.cross(STEER_DIR, r_) * np.sin(a) + np.outer(r_ @ STEER_DIR, STEER_DIR) * (1 - np.cos(a)) + ax_
            near = (np.abs(cp[:, 2] - nb[1]) < 0.15) & (np.abs(cp[:, 0]) < HEAD_R * 1.3)
            if near.any():
                fender_top = max(fender_top, cp[near, 1].max())
        y0 = max(nb[0], fender_top + HEAD_R * 1.25 + 0.03)
        if y0 > nb[0] + 0.02:
            log(f"headlight: raised {y0 - nb[0]:.3f} m above the nose's furthest-forward height to clear the fender")
        return VG_BODY, lamp_at(f[nose], y0, nb[1], f"on the nose (fender top {fender_top:.3f}, clamp {clamp_y:.3f})")
    cowl = cowl_all & (cen[:, 2] > 0.6)
    tri = f[cowl]
    best = None
    for y in np.linspace(0.55, 1.0, 46):
        t = ray_hits(np.array([0.0, y, 3.0]), np.array([0.0, 0.0, -1.0]), tri).min()
        if np.isfinite(t) and (best is None or 3.0 - t > best[1]):
            best = (y, 3.0 - t)
    if best is None:
        log("headlight: no front fender found")
        return VG_COWL, []
    fr = tri[tri[..., 2].mean(1) > best[1] - 0.25]
    return VG_COWL, lamp_at(tri, min(best[0], fr[..., 1].max() - HEAD_R * 1.3), best[1], "on the front fender")


HEAD_R = 0.055                                          # the headlight's radius (6 cm read small on the fender, epoch
                                                        # 2; 7.5 cm on top of the nose "a bit too large", the
                                                        # maintainer, 2026-11-18)
HEAD_OUT = 0.02                                         # how far the lens stands out from the body (4 cm on the
                                                        # nose read as a can stuck on the front, round 3 epoch 2)
HEAD_UV = (0.5, 0.115, 0.2)                             # its square in the plate swatch: centre u, v and size


def rear_details(q, T, lab, mat):
    """the maintainer asked for details at the back (2026-11-18): bright tip rings on the exhaust mouths and a red
    tail light. Returns (material, pos, tris) like handlebar()"""
    parts = []
    tl = lab[T[:, 0]]
    f = q[T]
    fn = np.cross(f[:, 1] - f[:, 0], f[:, 2] - f[:, 0])
    ar = np.linalg.norm(fn, axis=1) / 2
    fn /= 2 * ar[:, None] + 1e-15
    # mouths: the "hole" faces, one per part, behind z -1.05, up to 7 cm across (a wider one is a can's shoulder
    # round two tips: its ring circled both). The upper right can (z -1.13) was left bare by a -1.2 limit
    # (MotorcyleBack.png, the maintainer, 2026-11-18)
    mouths = []
    for i in np.unique(tl[mat == "hole"]):
        s = (mat == "hole") & (tl == i)
        p = q[np.unique(T[s])]
        c = p.mean(0)
        n = (fn[s] * ar[s, None]).sum(0)
        n /= np.linalg.norm(n)
        r = max(np.ptp(p[:, 0]), np.ptp(p[:, 1])) / 2
        if c[2] > -1.05 or r > 0.07:
            continue
        mouths.append((c, n, r))
    for c, n, r in mouths:
        parts += tip_ring(c, n, r)
    # the left can is one box with no round mouth: two pipes out of its rear end, side by side, each with a ring
    chrome_parts = [i for i in np.unique(tl[mat == "chrome"]) if q[lab == i, 0].mean() < -0.1]
    if chrome_parts:
        # its back: the area centre of its back-facing triangles; each pipe sits where a ray from behind meets it
        # (the can's long axis ends in a narrow top corner: pipes there came out 1 cm wide)
        i = max(chrome_parts, key=lambda k: (tl == k).sum())
        sb = (tl == i) & (fn[:, 2] < -0.5)
        cen_b = (f[sb].mean(1) * ar[sb, None]).sum(0) / ar[sb].sum()
        tri_i = f[tl == i]
        back = np.array([0.0, 0.25, -1.0])
        back /= np.linalg.norm(back)                   # out of the back, tipped up a little, as the right cans
        for dx in (-0.045, 0.045):
            o = np.array([cen_b[0] + dx, cen_b[1], -2.0])
            t = ray_hits(o, np.array([0.0, 0.0, 1.0]), tri_i).min()
            if not np.isfinite(t):
                continue
            hit = o + [0, 0, t]
            parts.append(("chrome",) + tube(hit - back * 0.05, hit + back * 0.05, 0.032, 16, caps=False))
            parts += tip_ring(hit + back * 0.05, back, 0.032)
            log(f"left can: a pipe at {hit.round(3)}")
        # its big back face burns with the skill (the maintainer's red circle, ExhaustGlow.png): a PANEL laid over
        # it. Lighting the can's own triangles showed a crease line across the folded face and spilled onto its
        # bevel (reviewer, epoch 1); the panel hides both and gives the fire a clean grid to map onto
        face = (tl == i) & (fn[:, 2] < -0.5) & (f.mean(1)[:, 1] > LEFT_CAN_FACE_Y)
        fp = face_patch(f[face], tri_i)
        if fp is not None:
            su, sv, ss = swatch_rect(MATS["hole"][0])
            parts.append(("hole", fp[0], fp[1], np.c_[su + (0.04 + 0.92 * fp[2][:, 0]) * ss,
                                                      sv + (0.04 + 0.92 * fp[2][:, 1]) * ss]))
            log(f"left can: a burning panel of {len(fp[1])} triangles over its back face")
    log(f"exhaust tip rings: {len(mouths)}", [m[0].round(3).tolist() for m in mouths])
    # tail light: an integrated LED lens fitted to the rounded back of the tail hump (the maintainer's green circle,
    # MotorcyleBack.png), as real bikes set the light into the tail cowl, following its taper: a black frame, the red
    # lens inside it, a brighter LED strip across the lens
    hump = [i for i in np.unique(tl) if (mat[tl == i] == "paint").all()
            and abs(q[lab == i, 0].mean()) < 0.05 and q[lab == i, 2].mean() < -0.6 and q[lab == i, 1].max() > 1.0]
    # fitted to EVERY part there, not the hump alone (a thin strip of another part stood out through the lens)
    near = (np.abs(f.mean(1)[:, 0]) < 0.2) & (f.mean(1)[:, 2] < -0.8) & (f.mean(1)[:, 1] > 0.9) & \
        np.isin(mat, ["paint", "gunmetal", "steel", "fins", "panel"])
    tri = f[near | np.isin(tl, hump)]
    frame = surface_patch(tri, np.linspace(0.955, 1.085, 6), 0.86, 0.003)
    lens = surface_patch(tri, np.linspace(0.97, 1.07, 5), 0.74, 0.006)
    # three LED rows, each narrower as the hump tapers (one stripe read as a flat sticker, reviewer 2026-11-18)
    leds = [surface_patch(tri, np.linspace(y0_, y0_ + 0.01, 2), w_, 0.008)
            for y0_, w_ in ((0.985, 0.64), (1.013, 0.60), (1.041, 0.54))]
    for m, sp in [("rubber", frame), ("glow", lens)] + [("led", l_) for l_ in leds]:
        if sp is not None:
            parts.append((m,) + sp)
    # license plate "MAV 999" under the tail light, upright, on a black bracket back to the body
    cy = 0.955 - 0.015 - PLATE_H / 2
    body_t = f[(np.abs(f.mean(1)[:, 0]) < 0.25) & (f.mean(1)[:, 2] < -0.7) & (mat != "rubber")]
    zs = []
    for x in np.linspace(-PLATE_W / 2 - 0.01, PLATE_W / 2 + 0.01, 31):     # dense: a thin rod crossed a sparse grid
        for y in np.linspace(cy - PLATE_H / 2 - 0.01, cy + PLATE_H / 2 + 0.01, 17):
            t = ray_hits(np.array([x, y, -2.0]), np.array([0.0, 0.0, 1.0]), body_t).min()
            if np.isfinite(t):
                zs.append(-2.0 + t)
    if zs:
        zp = min(zs) - 0.012
        zb = float(np.median(zs)) + 0.01
        hx, hy = PLATE_W / 2, PLATE_H / 2
        pp = np.array([[hx, cy + hy, zp], [-hx, cy + hy, zp], [hx, cy - hy, zp], [-hx, cy - hy, zp]])
        pt_ = np.array([[0, 1, 2], [1, 3, 2]])
        fnp = np.cross(pp[pt_[:, 1]] - pp[pt_[:, 0]], pp[pt_[:, 2]] - pp[pt_[:, 0]])
        pt_[fnp[:, 2] > 0] = pt_[fnp[:, 2] > 0][:, ::-1]           # facing back
        su, sv, ss = swatch_rect(MATS["plate"][0])
        # u runs from -x to +x. IN GAME, seen from behind, the bike's +x is on the viewer's RIGHT: the first build
        # had u the other way, which read correctly in modkit.render and MIRRORED in game (the maintainer,
        # 2026-11-18). The offline render is left-right mirrored against the game: text reads backwards there
        puv = np.array([[su + ss, sv + PLATE_ROW / TEX], [su, sv + PLATE_ROW / TEX],
                        [su + ss, sv + (PLATE_ROW + PLATE_PX) / TEX], [su, sv + (PLATE_ROW + PLATE_PX) / TEX]])
        inset = np.array([[-0.002, 0.002], [0.002, 0.002], [-0.002, -0.002], [0.002, -0.002]])
        parts.append(("plate", pp, pt_, puv + inset))
        # the bracket: a black box behind the plate, a little larger, reaching the body
        lo_ = np.array([-hx - 0.008, cy - hy - 0.008, zp + 0.001])
        hi_ = np.array([hx + 0.008, cy + hy + 0.008, max(zb, zp + 0.02)])
        bp = np.array([[x, y, z] for x in (lo_[0], hi_[0]) for y in (lo_[1], hi_[1]) for z in (lo_[2], hi_[2])])
        bt = np.array([[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1], [2, 3, 7], [2, 7, 6],
                       [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]])
        bc = bp.mean(0)
        bn = np.cross(bp[bt[:, 1]] - bp[bt[:, 0]], bp[bt[:, 2]] - bp[bt[:, 0]])
        flip = (bn * (bp[bt].mean(1) - bc)).sum(1) < 0
        bt[flip] = bt[flip][:, ::-1]
        parts.append(("rubber", bp, bt))
        log(f"license plate '{PLATE_TEXT}' at y {cy:.3f}, z {zp:.3f}; bracket back to z {hi_[2]:.3f}")
    log("tail light: hump parts", hump, "lens", None if lens is None else (lens[0].min(0).round(3), lens[0].max(0).round(3)))
    return parts


SEAT_DEPTH = 0.30      # the saddle's sides reach down to the Fenrir's dip (its top there is 0.74 .. 0.8)


def saddle(q, L, nz=24, nx=17):
    """a padded seat over the seat window: flat-topped, rounded sides sinking into the body, its ends dipping into
    the tank in front and the rear hump behind. Top just over SEAT_Y (the body there is lifted to SEAT_Y - 0.03 so
    the two never share a surface)"""
    z0, z1 = SEAT_Z[0] - 0.06, SEAT_Z[1] + 0.04
    t = np.linspace(0, 1, nz)
    z = z0 + (z1 - z0) * t
    wid = 0.19 - 0.06 * t                         # wider behind (her seat), narrower at the tank
    end = np.minimum(1, np.minimum(t / 0.12, (1 - t) / 0.12))
    top = SEAT_Y + 0.012 - 0.07 * (1 - smoothstep(0, 1, end))
    ph = np.linspace(-np.pi / 2, np.pi / 2, nx)
    sx = np.sign(np.sin(ph)) * np.abs(np.sin(ph)) ** 0.55
    sy = np.abs(np.cos(ph)) ** 0.35
    pos = np.zeros((nz, nx, 3))
    pos[..., 0] = wid[:, None] * sx[None]
    depth = SEAT_DEPTH
    pos[..., 1] = (top - depth)[:, None] + depth * sy[None]
    pos[..., 2] = z[:, None]
    pos = pos.reshape(-1, 3)
    tris = []
    for a in range(nz - 1):
        for b in range(nx - 1):
            i0, i1, i2, i3 = a * nx + b, a * nx + b + 1, (a + 1) * nx + b, (a + 1) * nx + b + 1
            tris += [[i0, i2, i1], [i1, i2, i3]]
    tris = np.array(tris)
    f = pos[tris]
    fn = np.cross(f[:, 1] - f[:, 0], f[:, 2] - f[:, 0])
    if fn[:, 1].sum() < 0:
        tris = tris[:, ::-1]
    return pos, tris


# ------------------------------------------------------------------------------------------------ normals

def crease_corner_normals(P, T, angle=60.0):
    """per corner: the area-weighted normal of the faces at that vertex within `angle` of this face"""
    f = P[T]
    fn = np.cross(f[:, 1] - f[:, 0], f[:, 2] - f[:, 0])
    fu = fn / (np.linalg.norm(fn, axis=1, keepdims=True) + 1e-15)
    inc = [[] for _ in range(len(P))]
    for t in range(len(T)):
        for k in range(3):
            inc[T[t, k]].append(t)
    cosl = np.cos(np.radians(angle))
    out = np.zeros((len(T), 3, 3))
    for v, faces in enumerate(inc):
        if not faces:
            continue
        faces = np.array(faces)
        d = fu[faces] @ fu[faces].T
        acc = (d > cosl).astype(np.float64) @ fn[faces]
        acc /= np.linalg.norm(acc, axis=1, keepdims=True) + 1e-15
        for row, t in enumerate(faces):
            k = np.where(T[t] == v)[0][0]
            out[t, k] = acc[row]
    return out


# ------------------------------------------------------------------------------------------------ texture

# material -> (swatch index, base colour (top), base colour (bottom), light map class: rubber / paint / dark / metal)
MATS = {
    "paint":    (0, (140, 146, 170), (30, 34, 52), "paint"),   # navy-black gloss (lifted: the game showed pure black)
    "gunmetal": (1, (64, 67, 76), (14, 15, 18), "dark"),       # fenders, risers, hubs: dark steel (game: read light grey)
    "chrome":   (2, (124, 120, 100), (20, 20, 22), "metal"),   # less red (game: read maroon / leather)   # blackened steel exhausts, brass only in the light
    "rubber":   (3, (40, 40, 42), (16, 16, 17), "rubber"),
    "leather":  (4, (70, 56, 48), (24, 20, 18), "rubber"),   # dark brown-black, matte: apart from the paint
    "rim":      (5, (150, 152, 158), (70, 72, 78), "metal"),
    "bronze":   (7, (118, 96, 70), (34, 28, 22), "metal"),    # darker, browner (game: read as flat tan)   # the worn bronze lower rail (warmer, not olive)
    "steel":    (8, (118, 120, 128), (32, 33, 37), "metal"),   # mechanics: gunmetal mid-tone
    # exhaust mouths (the maintainer, 2026-11-18): near-black, so they read as holes. With the glow class in the
    # main textures they burned RED even parked (the maintainer and audit 7, 02_parked_rear_day_closeup.png); now
    # the main pass has no glow there and only the Nightsoul EFFECT pass sees them glowing orange (FX_* below)
    "hole":     (9, (16, 12, 12), (6, 5, 5), "rubber"),
    "fins":     (10, (150, 152, 160), (22, 23, 27), "metal"),  # the engine: dark steel fins, bright edges
    "plate":    (15, (192, 192, 184), (192, 192, 184), "dark"),  # the license plate; its swatch is painted below
    # the tail light OFF (skill off): a dim red lens, no glow class; lit in the skill-on set (TAIL_ON_*, LED_ON_*)
    "led":      (14, (66, 14, 12), (52, 10, 9), "paint"),       # the LED rows, off: as dark as the lens (stripes
                                                                # showed through "off", reviewer epoch 1)
    "tip":      (13, (182, 180, 172), (22, 22, 25), "metal"),  # exhaust tip rings: chrome contrast (the rim grey read
                                                                # as flat pale matte rings in game, audit 6)
    "silver":   (11, (170, 172, 180), (70, 72, 80), "metal"),  # the tank's side pipes (the maintainer, 2026-11-18);
                                                                # a plain gradient: the horizon curve left them dark
    "panel":    (12, (98, 101, 110), (30, 31, 35), "dark"),    # the front arms' lower half: grey, not the navy paint
    "glow":     (6, (70, 15, 13), (48, 9, 8), "paint"),       # the red tail lens, off
}
SW = 4  # swatches per row (256 px each)


def swatch_rect(i):
    s = 1.0 / SW
    return (i % SW) * s, (i // SW) * s, s


def paint_atlas(lm_src, flat_normal):
    D = np.zeros((TEX, TEX, 4), np.uint8)
    LM = np.zeros((TEX, TEX, 4), np.uint8)
    N = np.tile(np.array(flat_normal, np.uint8), (TEX, TEX, 1))
    px = TEX // SW
    rng = np.random.default_rng(7)
    for name, (i, top, bot, lmk) in MATS.items():
        u0, v0, _ = swatch_rect(i)
        x0, y0 = int(u0 * TEX), int(v0 * TEX)
        # v inside the swatch: 0 = normal pointing up (sky), 1 = down (ground); u: across (normal x/z)
        t = np.linspace(0, 1, px)[:, None]
        top_a, bot_a = np.array(top, np.float64), np.array(bot, np.float64)
        if name in ("chrome", "bronze", "tip"):
            # a horizon: bright sky, a dark band just under the horizon, warm ground light. On the exhaust the sky is
            # held to 45 %: the left can is a BOX, and its flat lid (all normals up) read in game as a pale grey
            # panel in a dark rim (audit 6, 15_riding_rearcowl_flat_grey_panel_day.png)
            sky = 0.45 if name == "chrome" else 1.0
            k = np.where(t < 0.48, 0.12 + (sky - 0.12) * np.clip(1 - t / 0.22, 0, 1) ** 2, np.where(t < 0.56, 0.04, 0.10 + 0.10 * (t - 0.56)))
            col = bot_a + (top_a - bot_a) * k
        elif name == "paint":
            k = 0.18 * np.clip(1 - t * 1.4, 0, 1) + 0.95 * np.exp(-((t - 0.30) / 0.035) ** 2)
            col = bot_a + (top_a - bot_a) * np.clip(k, 0, 1)
        else:
            col = bot_a + (top_a - bot_a) * (1 - t)
        img = np.repeat(col[:, None, :], px, 1)
        if name == "fins":
            # this swatch is read by HEIGHT (v) across the engine: 9 dark grooves between bright fins
            mid = (top_a + bot_a) / 2
            ph = (t[:, 0] * 9) % 1.0
            shade = (0.75 + 0.25 * np.cos(ph * np.pi))[:, None, None]
            edge = (ph < 0.12)[:, None, None]
            img = np.where((ph > 0.62)[:, None, None], bot_a * 0.6,
                           np.where(edge, top_a, mid * shade)) * np.ones((1, px, 1))
        img += rng.normal(0, 1.2, img.shape)          # a little grain, so flat areas are not dead
        D[y0:y0 + px, x0:x0 + px, :3] = np.clip(img, 0, 255).astype(np.uint8)
        LM[y0:y0 + px, x0:x0 + px] = lm_src[lmk]
    # the license plate (the maintainer, 2026-11-18: "MAV 999"): a band PLATE_PX tall in the plate swatch, kept under
    # ~200 (near-white blooms in game), black text and a thin dark border
    u0, v0, _ = swatch_rect(MATS["plate"][0])
    x0, y0 = int(u0 * TEX), int(v0 * TEX) + PLATE_ROW
    img = Image.new("RGB", (px, PLATE_PX), MATS["plate"][1])
    from PIL import ImageDraw, ImageFont
    dr = ImageDraw.Draw(img)
    dr.rectangle([2, 2, px - 3, PLATE_PX - 3], outline=(30, 30, 34), width=5)
    # the maintainer's details (2026-11-18): blue text, the place ("Natlan") small along the top, four bolt holes
    blue = (28, 58, 150)

    def fit(text, w, h, bold=True):
        f_ = ImageFont.load_default()
        for size in range(90, 8, -1):
            try:
                f_ = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf", size)
            except OSError:
                return f_
            b_ = dr.textbbox((0, 0), text, font=f_)
            if b_[2] - b_[0] <= w and b_[3] - b_[1] <= h:
                return f_
        return f_

    def put(text, font, cy_):
        b_ = dr.textbbox((0, 0), text, font=font)
        dr.text(((px - (b_[2] - b_[0])) / 2 - b_[0], cy_ - (b_[3] - b_[1]) / 2 - b_[1]), text, fill=blue, font=font)
    put(PLATE_PLACE, fit(PLATE_PLACE, px * 0.40, PLATE_PX * 0.15, bold=False), PLATE_PX * 0.17)
    # "MAV", a tiny blue MORA coin, "999" (the maintainer, 2026-11-18). The coin is a simple made emblem: a ring, a
    # thin inner ring and a four-pointed star, not the game's art
    left_, right_ = PLATE_TEXT.split(" ", 1)
    fnt = fit(left_ + "      " + right_, px * 0.80, PLATE_PX * 0.44)
    bl, br = dr.textbbox((0, 0), left_, font=fnt), dr.textbbox((0, 0), right_, font=fnt)
    cap = max(bl[3] - bl[1], br[3] - br[1])
    coin = cap * 0.8                               # the symbol's size against the letters' height (0.62 read tiny)
    gap = cap * 0.22
    wl, wr = bl[2] - bl[0], br[2] - br[0]
    x_ = (px - (wl + gap + coin + gap + wr)) / 2
    cy_ = PLATE_PX * 0.52
    dr.text((x_ - bl[0], cy_ - cap / 2 - bl[1]), left_, fill=blue, font=fnt)
    dr.text((x_ + wl + 2 * gap + coin - br[0], cy_ - cap / 2 - br[1]), right_, fill=blue, font=fnt)
    ccx = x_ + wl + gap + coin / 2
    # the mora symbol is a TRIQUETRA (the maintainer: "the 3 leaf symbol", not a coin): three pointed leaves, each
    # where two of three circles overlap (circles of radius r, centres r apart on a triangle round the middle), drawn
    # as blue outlines at 8x and scaled down so the thin strokes stay smooth
    big = 400
    yy, xx = np.mgrid[0:big, 0:big] - big / 2 + 0.5
    rr = big * 0.37                                # circle radius; the leaves' tips reach 1.155 r from the middle
    dd = rr / np.sqrt(3)
    cs = [(dd * np.cos(np.radians(90 + 120 * k)), dd * np.sin(np.radians(90 + 120 * k))) for k in range(3)]
    dist = [np.hypot(xx - cx, yy - cy) for cx, cy in cs]
    t_ = big * 0.09                                # stroke width
    ink = np.zeros((big, big), bool)
    for i_, j_ in ((0, 1), (1, 2), (2, 0)):
        lens = (dist[i_] < rr) & (dist[j_] < rr)
        inner = (dist[i_] < rr - t_) & (dist[j_] < rr - t_)
        ink |= lens & ~inner
    sz = max(8, int(round(coin * 1.25)))           # the symbol's box; its leaves span ~1.0 of it
    alpha = Image.fromarray((ink * 255).astype(np.uint8)).resize((sz, sz), Image.LANCZOS)
    img.paste(Image.new("RGB", (sz, sz), blue), (int(round(ccx - sz / 2)), int(round(cy_ - sz / 2))), alpha)
    put(PLATE_MOTTO, fit(PLATE_MOTTO, px * 0.56, PLATE_PX * 0.13, bold=False), PLATE_PX * 0.85)
    for hx_ in (0.07, 0.93):                    # bolt holes: a dark hole in a lighter rim, near each corner
        for hy_ in (0.17, 0.83):
            cx_, cy2 = hx_ * px, hy_ * PLATE_PX
            dr.ellipse([cx_ - 6, cy2 - 6, cx_ + 6, cy2 + 6], fill=(150, 150, 146))
            dr.ellipse([cx_ - 3.5, cy2 - 3.5, cx_ + 3.5, cy2 + 3.5], fill=(26, 26, 30))
    D[y0:y0 + PLATE_PX, x0:x0 + px, :3] = np.asarray(img)
    paint_lamp(D, HEAD_OFF_CORE, HEAD_OFF_EDGE)        # the headlight's lens, unlit glass
    D[..., 3] = 0
    return D, LM, N


HEAD_OFF_CORE, HEAD_OFF_EDGE = (92, 100, 114), (40, 44, 52)      # the headlight off: dark glass (a pale glass read as
                                                                 # a dimmer lamp beside the lit one, round 3 epoch 3)
HEAD_ON_CORE, HEAD_ON_EDGE = (255, 255, 255), (255, 255, 255)    # lit with the skill: WHITE (the maintainer: a
                                                                 # white-to-gold lens read ORANGE in game once the
                                                                 # glow multiplied it, 2026-11-18)


def lamp_slices():
    su, sv, ss = swatch_rect(MATS["plate"][0])
    hu, hv, hs = HEAD_UV
    x0, y0 = int((su + (hu - hs / 2) * ss) * TEX), int((sv + (hv - hs / 2) * ss) * TEX)
    n = int(hs * ss * TEX)
    return slice(y0, y0 + n), slice(x0, x0 + n)


def paint_lamp(D, core, edge, rings=True):
    """the headlight's square: a radial gradient from core to edge"""
    ys, xs = lamp_slices()
    n = ys.stop - ys.start
    y, x = np.mgrid[-1:1:n * 1j, -1:1:n * 1j]
    r = np.clip(np.hypot(x, y), 0, 1)[..., None]
    col = np.array(core, float) + (np.array(edge, float) - core) * r ** 1.5
    # faint concentric reflector rings, so the lens is not a featureless disc (epoch 1); a few % darker only. Not on
    # the lit lens: there they dimmed the white (2026-11-18)
    if rings:
        col *= (1 - 0.07 * (np.cos(r * np.pi * 7) > 0.6))
    D[ys, xs, :3] = np.clip(col, 0, 255).astype(np.uint8)


FX_PS = "4795b16ca8d1207c"              # the bike's Nightsoul effect pixel shader (frame dumps, 2026-11-17)
FX_SKILL_TEX = "892554c9"               # the game's effect texture at the Nightsoul shader's t0 with the skill on
LEFT_CAN_FACE_Y = 0.93                  # the left can's back face burns above this (its two pipes sit at y 0.89)
TAIL_ON_TOP, TAIL_ON_BOT = (238, 40, 28), (200, 20, 14)     # the tail lens, lit (skill on)
LED_ON_TOP, LED_ON_BOT = (255, 168, 108), (255, 128, 78)    # its LED rows, lit: hot orange-red over the red lens (epoch 3: cream read as paint)

PLATE_TEXT = "MAV 999"
PLATE_PLACE = "Natlan"
PLATE_MOTTO = "The Fire Nation"         # small along the bottom (the maintainer, 2026-11-18)
PLATE_W, PLATE_H = 0.19, 0.10           # metres (a motorcycle plate's proportions)
PLATE_PX = int(256 * PLATE_H / PLATE_W)  # its band in the 256 px swatch
PLATE_ROW = (256 - PLATE_PX) // 2


def corner_uv(mat, n):
    """swatch by material, place in it by the normal (v from n.y, u from the horizontal direction)"""
    u0, v0, s = swatch_rect(MATS[mat][0])
    m = 0.04 * s
    v = (1 - n[:, 1]) / 2
    u = 0.5 + 0.5 * np.arctan2(n[:, 0], n[:, 2] + 1e-9) / np.pi
    return np.stack([u0 + m + u * (s - 2 * m), v0 + m + v * (s - 2 * m)], 1)


# ------------------------------------------------------------------------------------------------ materials

def classify(P, T, lab, q, wheel_of, W, L, hugs=()):
    """material per triangle, by part and place"""
    tl = lab[T[:, 0]]
    mat = np.array(["paint"] * len(T), dtype=object)
    cen_f = P[T].mean(1)
    cen = q[T].mean(1)
    ntri = np.bincount(tl, minlength=lab.max() + 1)
    exhaust = []
    zr = W["rear"][1]["c"][2]
    for i in np.unique(tl):
        p = P[lab == i]
        lo, hi = p.min(0), p.max(0)
        c = (lo + hi) / 2
        sel = tl == i
        if wheel_of[lab == i][0] >= 0:
            continue        # wheels are painted below
        if i in hugs and ntri[i] >= 40:
            qi = q[lab == i]
            if qi[:, 2].mean() < 0 and qi[:, 1].max() > 0.85:
                # the rear box that rises to the tail hump: its big flat back read as a light grey slab round the
                # tail light in game (audit 6, 04_..._rearcowl_grey_day.png): body paint, like the hump
                mat[sel] = "paint"
                continue
            mat[sel] = "gunmetal"      # fenders: apart from the black tyre (in paint they read as a second tyre, epoch 4)
            continue
        # exhaust cans and pipes: behind the seat, standing up beside / over the rear wheel
        if c[2] < zr + 14 and hi[1] > 0.5 and abs(c[0]) > 1.5 and ntri[i] < 400:
            mat[sel] = "chrome"
            exhaust.append(i)
        # the lower frame (the toothed rail under the front arm, the rear swing arm): worn bronze-grey metal, as on
        # the FFXIV mount. Before the arms' rule, which took the rail too (epoch 3)
        elif hi[1] < 0.5 and hi[2] - lo[2] > 12:
            mat[sel] = "bronze"
        # the long front arms (the biggest mirrored pair, reaching from the front hub back past mid-bike): paint
        elif hi[2] - lo[2] > 20 and abs(c[0]) > 3:
            mat[sel] = "paint"
        # under the tank and seat: engine and mechanics, light steel
        elif c[1] < -1.0 or ntri[i] < 40:
            mat[sel] = "steel"
    # the tank's flanks (the maintainer, PartsSameColour.png, 2026-11-18: all one black): the ribbed pipes along each
    # side are SILVER on the reference, the cavity behind them dark gunmetal; the long front arms are navy above and
    # a grey panel along their lower half
    for i in np.unique(tl):
        sel = tl == i
        if mat[sel][0] != "paint" or ntri[i] >= 200:
            continue
        c = q[lab == i].mean(0)
        if 0.10 < abs(c[0]) < 0.20 and 0.74 < c[1] < 0.90 and 0.15 < c[2] < 0.30:
            mat[sel] = "silver"
        elif abs(c[0]) < 0.15 and 0.62 < c[1] < 0.74 and 0.20 < c[2] < 0.32:
            mat[sel] = "gunmetal"
    for i in np.unique(tl):
        p = P[lab == i]
        if (mat[tl == i] == "paint").all() and np.ptp(p[:, 2]) > 20 and abs(p[:, 0].mean()) > 3:
            sel = np.where(tl == i)[0]
            zc, yc = cen[sel, 2], cen[sel, 1]
            qa = q[lab == i]
            # the arm's height at each triangle's z (5 cm slices), lower 60 % -> panel (45 % left only the bottom edge)
            lo_ = np.array([qa[np.abs(qa[:, 2] - z) < 0.05, 1].min() for z in zc])
            hi_ = np.array([qa[np.abs(qa[:, 2] - z) < 0.05, 1].max() for z in zc])
            low = (yc - lo_) / np.maximum(hi_ - lo_, 1e-3) < 0.60
            mat[sel[low]] = "panel"
    # the engine block between the wheels, low: decided PER PART by the share of its triangles in the box (a test
    # per triangle cut the STL's long thin triangles into a row of saw-teeth, epoch 2)
    eng = (np.abs(cen[:, 0]) < 0.22) & (cen[:, 1] < 0.62) & (cen[:, 2] > -0.75) & (cen[:, 2] < 0.15) & (wheel_of[T[:, 0]] < 0)
    engine = []
    for i in np.unique(tl):
        sel = tl == i
        if eng[sel].mean() > 0.5 and mat[sel][0] in ("paint", "steel") and i not in hugs:
            mat[sel] = "fins"
            engine.append(i)
    # wheels: lathe meshes (32-vertex rings). The tyre starts at the ring where the side wall bulges out widest
    # between 0.5 and 0.75 of the radius; a triangle is tyre when ALL its corners are on or outside that ring
    # (a test on centres cut the coarse triangles into a saw-tooth star)
    for key, wid in (("rear", 0), ("front", 1)):
        wi, w = W[key]
        s = wheel_of[T[:, 0]] == wid
        dv = np.hypot(P[:, 1] - w["c"][1], P[:, 2] - w["c"][2]) / w["r"]
        ring = (lab == wi) & (dv > 0.5) & (dv < 0.75)
        thr = dv[ring][np.argmax(np.abs(P[ring, 0]))] - 0.005
        tyre = dv[T].min(1) >= thr
        mat[s & tyre] = "rubber"
        # the front wheel's inner part is a big side cover on the SDS model, a dark ring on the reference (in light
        # rim grey it read as a second, fatter tyre, epochs 4 and 5); the rear keeps a light rim
        mat[s & ~tyre] = "rim" if key == "rear" else "gunmetal"
        mat[s & (dv[T].max(1) <= 0.34)] = "gunmetal"     # the hub (rings at 0.24 and 0.32 r): a dark centre
        log(f"wheel {key}: tyre from {thr:.3f} r")
    f = q[T]
    fn = np.cross(f[:, 1] - f[:, 0], f[:, 2] - f[:, 0])
    fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-15
    # (the seat is a made saddle, not painted triangles: those alternated brown and grey, epoch 2)
    # rear light: back-facing triangles at the very tail, high
    tail = (fn[:, 2] < -0.6) & (cen[:, 2] < L["rear"][2] - 0.05) & (cen[:, 1] > 0.75) & (np.abs(cen[:, 0]) < 0.12) & (mat == "paint")
    mat[tail] = "glow"
    # exhaust mouths: in each can, the faces looking back (n.z < -0.5) in its rearmost 15 % (a fixed -0.8 caught
    # only some triangles of a fanned end: white teardrops with a black triangle, epoch 3)
    for i in exhaust:
        sel = tl == i
        zz = q[lab == i, 2]
        cut = zz.min() + 0.15 * np.ptp(zz)
        mat[sel & (fn[:, 2] < -0.5) & (cen[:, 2] < cut)] = "hole"
    return mat, exhaust, engine


# ------------------------------------------------------------------------------------------------ build

def build(out=OUT, stl=STL):
    g, gtris, hj, gtex = load_game()
    L = game_landmarks(g)
    log("game axles", L["rear"].round(3), L["front"].round(3), "r", round(L["rear_r"], 3), round(L["front_r"], 3))
    log("grips", L["gripL"]["c"].round(3), L["gripR"]["c"].round(3))

    P, T, lab = load_stl(stl)
    # winding: counter-clockwise outward (signed volume of the whole model)
    f = P[T]
    vol = np.einsum("ij,ij->i", f[:, 0], np.cross(f[:, 1], f[:, 2])).sum() / 6
    if vol < 0:
        T = T[:, ::-1].copy()
    log(f"Fenrir: {len(P)} vertices, {len(T)} triangles, signed volume {vol:+.1f}")
    W = fenrir_wheels(P, T, lab)
    q, wheel_of, hugs = make_map(P, T, lab, W, L)
    mat, exhaust, engine = classify(P, T, lab, q, wheel_of, W, L, hugs)
    # the exhausts keep the Fenrir's own height-to-length (the body's vertical stretch made them tower, epoch 1):
    # squash by SZ / SY about ONE base per side, with every small part whose centre is in that side's exhaust box
    # (each part about its own base left the tip rings floating off their cans, epoch 2)
    sq = (L["front"][2] - L["rear"][2]) / (W["front"][1]["c"][2] - W["rear"][1]["c"][2])
    sy_ = (L["rear"][1] - L["ground"]) / (W["rear"][1]["c"][1] - P[:, 1].min())
    tl_ = lab[T[:, 0]]
    for sgn in (-1, 1):
        ex = [i for i in exhaust if np.sign(P[lab == i, 0].mean()) == sgn]
        if not ex:
            continue
        box_lo = np.min([P[lab == i].min(0) for i in ex], 0) - 0.3
        box_hi = np.max([P[lab == i].max(0) for i in ex], 0) + 0.3
        base = min(q[lab == i, 1].min() for i in ex)
        for i in np.unique(tl_):
            if wheel_of[lab == i][0] >= 0:
                continue
            c = P[lab == i].mean(0)
            if i in ex or (np.all(c > box_lo) and np.all(c < box_hi) and (lab == i).sum() < 80):
                sel = lab == i
                q[sel, 1] = base + (q[sel, 1] - base) * (sq / sy_)

    global UV2_NOGLOW
    UV2_NOGLOW = np.median(g["uv2"][g["vg"][:, 0] == VG_REAR_WHEEL], 0).astype(np.float32)
    log("uv2 for every vertex (the original rear tyre's, no glow):", UV2_NOGLOW.round(4))
    # ---- bones per part ----
    gpos = g["pos"]
    gdom = g["vg"][:, 0]
    allowed = np.isin(gdom, VG_ALLOWED)
    tree = KNN(gpos[allowed])
    gd = gdom[allowed]
    bone_v = np.full(len(P), VG_BODY)
    for i in np.unique(lab[T[:, 0]]):
        sel = np.where(lab == i)[0]
        if wheel_of[sel[0]] >= 0:
            bone_v[sel] = VG_REAR_WHEEL if wheel_of[sel[0]] == 0 else VG_FRONT_WHEEL
            continue
        _, nn = tree.query(q[sel], k=4)
        votes = np.bincount(gd[nn].ravel(), minlength=20)
        # the front cowl bone may turn with the steering: only parts wholly ahead of where that bone starts ride it
        # (the Fenrir's long front arms reach back to mid-bike and stay on the body, as hub-centre steering does)
        # the front fender hugs the steering wheel: it turns with the front (the game's own fender is on the cowl
        # bone); no other part rides the cowl (a lone fragment did, epoch 2)
        dfw = np.hypot(q[sel, 1] - L["front"][1], q[sel, 2] - L["front"][2]) / L["front_r"]
        long_arm = np.ptp(P[sel, 2]) > 20      # the front arms and rails: blended below, never wholly on the cowl
        if not long_arm and ((i in hugs and q[sel, 2].mean() > 0) or np.median(dfw) < 1.3):
            bone_v[sel] = VG_COWL       # fenders and covers round the front wheel (epoch 3: a cover stayed behind)
            continue
        votes[VG_COWL] = 0
        bone_v[sel] = int(np.argmax(votes)) if votes.sum() else VG_BODY    # (an empty vote fell to bone 0, a side panel)
    # the long front arms hold the front hub: their front ends blend onto the cowl bone over the last 45 cm, so if
    # the front turns the arm bends with it instead of the wheel cutting through it (epoch 3)
    steer_v = np.zeros(len(P))
    for i in np.unique(lab[T[:, 0]]):
        sel = np.where(lab == i)[0]
        p = P[sel]
        if bone_v[sel[0]] == VG_BODY and np.ptp(p[:, 2]) > 20 and abs(p[:, 0].mean()) > 3:
            steer_v[sel] = smoothstep(L["front"][2] - 0.25, L["front"][2] - 0.08, q[sel, 2])   # the hub end only
    q = fit_front_fenders(q, T, lab, bone_v, L)       # first: the lift is sized from the fitted fender's top
    if FRONT_LIFT_ON:
        q = lift_front(q, P, T, lab, bone_v, L)
    else:
        q = dent_underside(q, P, T, lab, bone_v, L)
    # uv2: the game's own second UV at the nearest game vertex (keeps whatever it masks where it was)
    tree_all = KNN(gpos)
    _, nn_all = tree_all.query(q, k=1)
    # uv2 is where the game's shader reads its GLOW mask (the original bike's flame decals). Copied from the nearest
    # game vertex it drew those decals over the Fenrir as glowing orange zig-zags (game audit, 2026-11-17). Every
    # vertex now reads ONE uv2: the original rear tyre's, which does not glow
    uv2_v = np.tile(UV2_NOGLOW, (len(P), 1))

    # ---- which exhaust faces burn with the skill (the maintainer, ExhaustGlow.png, 2026-11-18) ----
    # the source's own mouth faces glowed as stray patches round the right cans (green circles): they go back to
    # exhaust metal, the made tips with their discs are the mouths. rear_details still finds the mouths by them.
    # The left can's big back face (red circle) burns through a panel made in rear_details
    mat_mouths = mat.copy()
    mat[mat == "hole"] = "chrome"

    # ---- corners -> vertices ----
    cn = crease_corner_normals(q, T)
    corners_v = T.reshape(-1)
    corners_n = cn.reshape(-1, 3)
    corners_m = np.repeat(mat, 3)
    uv = np.zeros((len(corners_v), 2))
    for m in MATS:
        s = corners_m == m
        if s.any():
            uv[s] = corner_uv(m, corners_n[s])
    # the engine reads the fins swatch by HEIGHT across the whole engine (linear, no wrap: the stripes are painted)
    fin_c = np.repeat(np.isin(lab[T[:, 0]], engine), 3)
    if fin_c.any():
        yy = q[corners_v[fin_c], 1]
        _, v0, sw_ = swatch_rect(MATS["fins"][0])
        uv[fin_c, 1] = v0 + 0.04 * sw_ + (yy - yy.min()) / (np.ptp(yy) + 1e-9) * sw_ * 0.92
    # the burning can face reads the hole swatch PLANAR (x, y over its own box, centred), so the fire burst shows
    hole_c = corners_m == "hole"
    if hole_c.any():
        pp_ = q[corners_v[hole_c]][:, :2]
        cen_ = (pp_.min(0) + pp_.max(0)) / 2
        ext_ = np.ptp(pp_, 0).max() / 2 + 1e-9
        su, sv, ss = swatch_rect(MATS["hole"][0])
        rel_ = (pp_ - cen_) / ext_ * 0.46
        uv[hole_c] = np.c_[su + (0.5 + rel_[:, 0]) * ss, sv + (0.5 - rel_[:, 1]) * ss]
    key = np.c_[corners_v, np.round(corners_n * 200), np.round(uv * 4096)].astype(np.int64)
    uk, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    nv = len(uk)
    first = np.zeros(nv, np.int64)
    first[inv[::-1]] = np.arange(len(inv))[::-1]
    vsrc = corners_v[first]
    part = dict(pos=q[vsrc].astype(np.float32), nrm=corners_n[first].astype(np.float32),
                uv=uv[first].astype(np.float32), uv2=uv2_v[vsrc].astype(np.float32),
                tris=inv.reshape(-1, 3))
    bone = bone_v[vsrc]
    steer = steer_v[vsrc]

    # ---- the made handlebar ----
    hparts = []
    for m, hp, ht in handlebar(L, q, T):
        hn = ops.compute_normals(hp.astype(np.float32), ht)
        hparts.append(dict(pos=hp.astype(np.float32), nrm=hn, uv=corner_uv(m, hn).astype(np.float32),
                           uv2=np.tile(UV2_NOGLOW, (len(hp), 1)).astype(np.float32), tris=ht))

    # ---- the made rear details (exhaust tip rings, tail light): body bone ----
    dparts = []
    hl_bone, hl_parts = headlight(q, T, mat, bone_v, L)
    made = [(VG_BODY, p_) for p_ in rear_details(q, T, lab, mat_mouths)] + \
           [(hl_bone, p_) for p_ in hl_parts]     # the headlight: the body's nose, or the turning fender
    for bone_, (m, dp, dt, *duv) in made:
        dn = ops.compute_normals(dp.astype(np.float32), dt)
        if m == "lens":
            # the headlight's lens faces forward, where the game's light rarely falls, so the lit white read dim
            # (the maintainer: "make the white brighter", 2026-11-18). It cannot glow (the game tints glow orange),
            # so its normals face the SKY instead: shaded like a top surface, the brightest a lit surface gets
            dn = np.tile(np.array([0.0, 0.94, 0.34], np.float32), (len(dp), 1))
        dparts.append(dict(pos=dp.astype(np.float32), nrm=dn,
                           uv=(duv[0] if duv else corner_uv(m, dn)).astype(np.float32),
                           uv2=np.tile(UV2_NOGLOW, (len(dp), 1)).astype(np.float32), tris=dt, bone=bone_))

    sp, st = saddle(q, L)
    sn = ops.compute_normals(sp.astype(np.float32), st)
    saddle_part = dict(pos=sp.astype(np.float32), nrm=sn, uv=corner_uv("leather", sn).astype(np.float32),
                       uv2=np.tile(UV2_NOGLOW, (len(sp), 1)).astype(np.float32), tris=st)
    allp = [part] + hparts + dparts + [saddle_part]
    pos = np.concatenate([a["pos"] for a in allp])
    nrm = np.concatenate([a["nrm"] for a in allp])
    uvs = np.concatenate([a["uv"] for a in allp])
    uv2 = np.concatenate([a["uv2"] for a in allp])
    off, tl = 0, []
    for a in allp:
        tl.append(a["tris"] + off)
        off += len(a["pos"])
    tris = np.concatenate(tl)
    bones = np.concatenate([bone] + [np.full(len(a["pos"]), VG_BAR) for a in hparts] +
                           [np.full(len(a["pos"]), a["bone"]) for a in dparts] + [np.full(len(sp), VG_BODY)])
    n = len(pos)
    steer_all = np.concatenate([steer, np.zeros(n - len(steer))])
    w = np.zeros((n, 4), np.float32)
    w[:, 0] = 1 - steer_all
    w[:, 1] = steer_all
    vg = np.zeros((n, 4), np.int32)
    vg[:, 0] = bones
    vg[:, 1] = np.where(steer_all > 0, VG_COWL, 0)
    col = np.tile(np.array([255, 128, 128, 128], np.uint8), (n, 1))
    tan = ops.compute_tangents(pos, nrm, uvs, tris)
    body_ib = np.zeros((1, 3), np.int64)    # the Body draw (the glowing rear emblems) draws nothing
    mesh = Mesh(pos, nrm, tan, w, vg, col, uvs, uv2, {"Head": tris, "Body": body_ib})
    log(f"mod: {n} vertices, {len(tris)} triangles; bones {dict(zip(*np.unique(bones, return_counts=True)))}")

    # ---- textures ----
    gl, guv, gvg = gtex["LightMap"], g["uv"], g["vg"][:, 0]

    # The light map's ALPHA is a material BAND (it picks the shading ramp) and its RGB a material class; both are
    # read off the bike's OWN texels at its own vertices, by what each covers (AGRemap's lesson: a band legend is
    # per object, read it from the identity model). The bike's legend (measured 2026-11-17):
    #   band 0,   rgb (68, 0, 128)    tyres (outer 40 % of the radius) and the rubber grips; nothing else
    #   band 134, rgb (255, 0, 165)   painted bodywork and painted rims
    #   band 134, rgb (136, 0, 120)   dark grey metal
    #   band 134, rgb (255, 170, 204) gold and silver trims: the METAL class (green 170)
    # (the first builds took group medians: the paint got the dark-metal class, chrome and steel the paint class)
    gd_ = gtex["Diffuse"].astype(int)
    pxy = np.clip((guv * (TEX - 1)).astype(int), 0, TEX - 1)
    vl, vd = gl[pxy[:, 1], pxy[:, 0]].astype(int), gd_[pxy[:, 1], pxy[:, 0], :3]
    near = lambda b: np.abs(vl[:, 3] - b) <= 4

    def lm_class(sel, what):
        assert sel.sum() > 50, what
        return np.median(vl[sel], 0).astype(np.uint8)
    lm_src = {
        "rubber": lm_class(near(0) & np.isin(gvg, [VG_REAR_WHEEL, VG_FRONT_WHEEL]), "tyres"),
        "paint": lm_class(near(134) & (vd[:, 0] > 90) & (vd[:, 0] > vd[:, 1] * 1.6), "red paint"),
        "dark": lm_class(near(134) & (vd.max(1) < 70) & (np.ptp(vd, 1) < 20), "dark metal"),
        "metal": lm_class(near(134) & (((vd[:, 0] > 150) & (vd[:, 1] > 100) & (vd[:, 2] < 90)) | (vd.min(1) > 150)),
                          "gold and silver"),
    }
    # ...but the metal class's GREEN (170) is a GLOW mask: it is what lights the original's gold trims and decal
    # lines in the Nightsoul state, and on this mod it lit the exhausts and engine bright orange (in game,
    # 2026-11-17). Keep its band and blue, drop the glow
    # ...except on the tail light, the one place that should light up (red, from its diffuse; 2026-11-18)
    lm_src["glow"] = lm_src["metal"].copy()
    lm_src["metal"] = lm_src["metal"].copy()
    lm_src["metal"][1] = 0
    nm = gtex["NormalMap"].reshape(-1, 4)
    vals, cnt = np.unique(nm, axis=0, return_counts=True)
    flat = vals[np.argmax(cnt)]
    log("light map texels", {k: v.tolist() for k, v in lm_src.items()}, "flat normal", flat.tolist())
    D, LM, N = paint_atlas(lm_src, flat)
    # the textures the Nightsoul EFFECT pass gets (ps 4795b16ca8d1207c; see write_ini): the same, except the exhaust
    # holes, which are Mavuika's orange fire with the glow class, so they burn when that pass draws and stay dark
    # in the main pass (an experiment: which pass made the parked red glow is not known, 2026-11-18)
    # SKILL-ON texture set (picked while the flag is up, see write_ini). Diffuse alpha stays 0 everywhere: alpha 255
    # blacked a surface out in the Nightsoul pass (dump FrameAnalysis-2026-11-18-050049, draw 107)
    D_fx, LM_fx = D.copy(), LM.copy()
    hpx = TEX // SW

    def swatch_px(m):
        u0_, v0_, _ = swatch_rect(MATS[m][0])
        return slice(int(v0_ * TEX), int(v0_ * TEX) + hpx), slice(int(u0_ * TEX), int(u0_ * TEX) + hpx)
    # the exhaust holes: the fire burst, glowing
    D_fx[swatch_px("hole") + (slice(0, 3),)] = fire_burst(hpx)
    LM_fx[swatch_px("hole")] = lm_src["glow"]
    # the tail light: lit, bright, glowing (off and dim in the plain set; the maintainer, 2026-11-18)
    for m, top, bot in (("glow", TAIL_ON_TOP, TAIL_ON_BOT), ("led", LED_ON_TOP, LED_ON_BOT)):
        tcol = np.linspace(0, 1, hpx)[:, None]
        g_ = np.array(top, float) + (np.array(bot, float) - top) * tcol
        D_fx[swatch_px(m) + (slice(0, 3),)] = np.repeat(g_[:, None, :], hpx, 1).astype(np.uint8)
        LM_fx[swatch_px(m)] = lm_src["glow"]
    # the headlight: lit white (dark glass in the plain set). NOT the glow class: the game tints the glow, and even
    # a pure white lens glowed ORANGE with a red rim (HeadLightFrontCrooked.png, 2026-11-18). A plain near-white
    # surface blooms out white in game instead (ModBuilding: "near-white blooms"), so the lit lamp is white with the
    # metal class, its glow green 0
    paint_lamp(D_fx, HEAD_ON_CORE, HEAD_ON_EDGE, rings=False)
    LM_fx[lamp_slices()] = lm_src["metal"]

    # ---- write ----
    os.makedirs(out, exist_ok=True)
    for f_ in os.listdir(out):
        if f_.startswith(NAME) or f_.endswith(".ini"):
            os.remove(os.path.join(out, f_))
    mesh.save(out, NAME, tex_stride=20)
    # one texture set: the Body draw draws nothing and binds the Head's files
    ops.save_dds(os.path.join(out, f"{NAME}HeadDiffuse.dds"), D, srgb=True)
    ops.save_dds(os.path.join(out, f"{NAME}HeadLightMap.dds"), LM, srgb=False)
    ops.save_dds(os.path.join(out, f"{NAME}HeadNormalMap.dds"), N, srgb=False)
    ops.save_dds(os.path.join(out, f"{NAME}FXDiffuse.dds"), D_fx, srgb=True)
    ops.save_dds(os.path.join(out, f"{NAME}FXLightMap.dds"), LM_fx, srgb=False)
    write_ini(out, hj, n)
    mesh.tex = D
    log("wrote", out)
    return mesh, dict(P=P, T=T, q=q, g=g, gtris=gtris, gtex=gtex, L=L, mat=mat)


def write_ini(out, hj, n):
    first = dict(zip(hj["object_classifications"], hj["object_indexes"]))
    s = [f"; {MODNAME}: Mavuika's bike as Cloud Strife's Fenrir (Final Fantasy VII Advent Children)",
         "; Built by Tools/Builders/MavuikaCloudyWolfMotorcycle/build.py (AlbertGold AI Mods). Do not edit by hand.",
         "; Hashes from GI-Model-Importer-Assets/SkillData/MavuikasBike/hash.json.", ""]
    s += [f"[TextureOverride{NAME}Position]", f"hash = {hj['position_vb']}", f"vb0 = Resource{NAME}Position", ""]
    s += [f"[TextureOverride{NAME}Blend]", f"hash = {hj['blend_vb']}", f"vb1 = Resource{NAME}Blend",
          "handling = skip", f"draw = {n},0", ""]
    s += [f"[TextureOverride{NAME}Texcoord]", f"hash = {hj['texcoord_vb']}", f"vb1 = Resource{NAME}Texcoord", ""]
    s += [f"[TextureOverride{NAME}VertexLimitRaise]", f"hash = {hj['draw_vb']}", ""]
    s += [f"[TextureOverride{NAME}IB]", f"hash = {hj['ib']}", "handling = skip", "drawindexed = auto", ""]
    for c in ("Head", "Body"):
        # The textures are swapped BY HASH (sections below) in every slot of every shader the bike draws with:
        # 3DMigoto applies a by-hash `this =` only in slots someone runs `checktextureoverride` on, and nothing did
        # for the bike's effect shader (a dump while riding showed the ORIGINAL diffuse and light map still at
        # t5 / t6 there). Per-slot `ps-t0..2` lines are gone too: in the effect shader t0 is the diffuse, not the
        # normal map, and t1 a flame noise.
        s += [f"[TextureOverride{NAME}{c}]", f"hash = {hj['ib']}", f"match_first_index = {first[c]}",
              f"ib = Resource{NAME}{c}IB"]
        s += [f"checktextureoverride = ps-t{k}" for k in range(9)]
        # in the Nightsoul effect pass only: the textures whose exhaust holes burn (the maintainer, 2026-11-18)
        s += ["run = CommandList\\global\\ORFix\\ORFix", ""]
    # SKILL-ON SWITCH (the maintainer, 2026-11-18: exhaust holes black, burning only with her skill). The bike is
    # drawn in up to five passes a frame; what shows (glow included) is the MAIN pass (ps d2d910688a4b3625 /
    # b2043833b7d3b2ef), drawn FIRST. The Nightsoul shader (ps 4795b16ca8d1207c) draws it only while the skill
    # state is on, and AFTER the main pass, and swapping its textures changed nothing visible (riding dump
    # FrameAnalysis-2026-11-18-050049: its colour target showed the main pass's black holes). So that shader only
    # raises a flag; [Present] carries the flag into the next frame; the textures swapped BY HASH below pick the
    # glowing-hole set while it is up
    s += ["[Constants]", "global $ns_flag = 0", "global $ns_active = 0", ""]
    s += ["[Present]", "$ns_active = $ns_flag", "$ns_flag = 0", ""]
    # ...but that shader ALSO draws while she is idle (the holes burned idle too, the maintainer). With the skill on,
    # its t0 holds the game's effect texture 892554c9 (both skill-on dumps: 2026-11-17-221506 and 2026-11-18-050049);
    # in the first dump of the bike (2026-11-17-195222) t0 was the bike's own diffuse. The flag waits for that texture
    # The flag is raised by that texture's OWN section, run by the `checktextureoverride = ps-t0` of the bike's draw
    # sections (the mechanism the by-hash swaps already rely on). A `ps-t0 == filter_index` test in a ShaderOverride
    # never fired (the maintainer: no glow with the skill, 2026-11-18). It is only bound to a bike draw in the
    # skill's Nightsoul pass, so no other object can raise the flag
    s += ["; the game's Nightsoul effect texture: checked at t0 of the bike's Nightsoul draw while the skill is on",
          f"[TextureOverride{NAME}NightsoulEffectTex]", f"hash = {FX_SKILL_TEX}", "$ns_flag = 1", ""]
    # The bike also draws in an EFFECT pass (the Nightsoul shader: draws 123/124 in a frame dump) that binds the
    # bike's diffuse again at t0 / t5 and its light map at t6. Overriding by slot left the ORIGINAL diffuse there,
    # and its alpha (the original's glow mask) lit up through the Fenrir's UVs as lava blotches (game audits 1-2,
    # 2026-11-17). So the original textures are also replaced BY HASH, in whatever slot any shader binds them.
    kinds = {k: h for k, _, h in hj["texture_hashes"][0]}
    s += ["; the original textures, replaced wherever any shader binds them (the Nightsoul effect pass too)"]
    for k in ("Diffuse", "LightMap", "NormalMap"):
        s += [f"[TextureOverride{NAME}{k}ByHash]", f"hash = {kinds[k]}"]
        if k in ("Diffuse", "LightMap"):      # the skill-on set: exhaust holes in orange fire with the glow class
            s += ["if $ns_active == 1", f"  this = Resource{NAME}FX{k}", "else", f"  this = Resource{NAME}Head{k}",
                  "endif", ""]
        else:
            s += [f"this = Resource{NAME}Head{k}", ""]
    s += [f"[Resource{NAME}Position]", "type = Buffer", "stride = 40", f"filename = {NAME}Position.buf", ""]
    s += [f"[Resource{NAME}Blend]", "type = Buffer", "stride = 32", f"filename = {NAME}Blend.buf", ""]
    s += [f"[Resource{NAME}Texcoord]", "type = Buffer", "stride = 20", f"filename = {NAME}Texcoord.buf", ""]
    for c in ("Head", "Body"):
        s += [f"[Resource{NAME}{c}IB]", "type = Buffer", "format = DXGI_FORMAT_R32_UINT", f"filename = {NAME}{c}.ib", ""]
    for k in ("NormalMap", "Diffuse", "LightMap"):
        s += [f"[Resource{NAME}Head{k}]", f"filename = {NAME}Head{k}.dds", ""]
    for k in ("Diffuse", "LightMap"):
        s += [f"[Resource{NAME}FX{k}]", f"filename = {NAME}FX{k}.dds", ""]
    with open(os.path.join(out, f"{MODNAME}.ini"), "w", newline="\r\n") as fh:
        fh.write("\n".join(s))


# ------------------------------------------------------------------------------------------------ looking

def game_scene(dbg):
    g, gt = dbg["g"], dbg["gtris"]
    tex = dbg["gtex"]["Diffuse"].astype(np.float32) / 255
    return g["pos"], g["nrm"], g["uv"], [gt["Head"], gt["Body"]], [tex, tex]


def preview(mesh, dbg, path):
    yaws = (0, 45, 90, 135, 180, 270)
    B = (-1.75, 1.75, -0.12, 1.45)
    gp, gn, gu, gt, gx = game_scene(dbg)
    tex = mesh.tex.astype(np.float32) / 255
    rows = []
    # the reference: the Fenrir model as read (mapped onto the game's bike), plain grey
    q, T = dbg["q"], dbg["T"]
    qn = ops.compute_normals(q.astype(np.float32), T)
    rows += [render(q, qn, [T], size=(520, 300), yaw=y, bounds=B, cull=False) for y in yaws]
    rows += [render(mesh.pos, mesh.nrm, [mesh.comps["Head"]], size=(520, 300), yaw=y, uv=mesh.uv, textures=[tex],
                    bounds=B, cull=False) for y in yaws]
    rows += [render(gp, gn, gt, size=(520, 300), yaw=y, uv=gu, textures=gx, bounds=B, cull=False) for y in yaws]
    labels = [f"Fenrir model (shape source) {y}" for y in yaws] + [f"mod {y}" for y in yaws] + \
             [f"game bike (her pose fits this) {y}" for y in yaws]
    sheet(rows, cols=len(yaws), labels=labels).save(path)
    pal = np.random.RandomState(5).rand(32, 3) * 0.6 + 0.2
    for b_, c_ in ((VG_BODY, (0.6, 0.6, 0.62)), (VG_BAR, (1.0, 0.9, 0.1)), (VG_FRONT_WHEEL, (0.1, 0.8, 0.9)),
                   (VG_REAR_WHEEL, (0.95, 0.3, 0.8)), (VG_SWING, (1.0, 0.5, 0.1)), (VG_COWL, (0.2, 0.85, 0.2))):
        pal[b_] = c_
    col = (pal[mesh.vg] * mesh.w[:, :, None]).sum(1)
    gcol = pal[dbg["g"]["vg"][:, 0]]
    wv = [render(mesh.pos, mesh.nrm, [mesh.comps["Head"]], size=(520, 300), yaw=y, colors=[col], bounds=B, cull=False)
          for y in (90, 0, 180)]
    wv += [render(gp, gn, gt, size=(520, 300), yaw=y, colors=[gcol, gcol], bounds=B, cull=False) for y in (90, 0, 180)]
    sheet(wv, cols=3, labels=["mod bones 90 (grey body, yellow handlebar, orange swing arm, green cowl", "cyan front wheel, magenta rear wheel)", "180", "game bones 90", "0", "180"]).save(path.replace(".png", "_bones.png"))
    close = [render(mesh.pos, mesh.nrm, [mesh.comps["Head"]], size=(1000, 560), yaw=y, pitch=pt, uv=mesh.uv,
                    textures=[tex], bounds=B, cull=True, bg=(0, 150, 0), ssaa=2) for y, pt in ((60, 12), (300, 12), (0, 30))]
    sheet(close, cols=3, labels=["mod 60 (culled, holes show green)", "300", "front, from above"]).save(path.replace(".png", "_close.png"))
    # review sheet: the Fenrir model at its OWN proportions (one uniform scale) above the mod, same views
    P = dbg["P"]
    k = (dbg["L"]["front"][2] - dbg["L"]["rear"][2]) / (P[:, 2].max() - P[:, 2].min()) * 1.18
    R = (P - [0, P[:, 1].min(), (P[:, 2].max() + P[:, 2].min()) / 2]) * k + [0, -0.04, -0.1]
    Rn = ops.compute_normals(R.astype(np.float32), T)
    views = ((90, 5), (60, 15), (300, 15), (0, 25), (180, 20))
    rv = [render(R, Rn, [T], size=(720, 420), yaw=y, pitch=pt, bounds=B, cull=False, ssaa=2) for y, pt in views]
    mv = [render(mesh.pos, mesh.nrm, [mesh.comps["Head"]], size=(720, 420), yaw=y, pitch=pt, uv=mesh.uv,
                 textures=[tex], bounds=B, cull=True, ssaa=2) for y, pt in views]
    sheet(rv + mv, cols=len(views), labels=[f"reference: Fenrir model, own proportions, yaw {y}" for y, _ in views] +
          [f"mod, yaw {y}" for y, _ in views]).save(path.replace(".png", "_review.png"))
    # steered: the steering bones turned about the game's axis, as the game does (the mod above, the game's own bike
    # below, which shows the axis is right: its bar must stay on its cowl)
    L = dbg["L"]

    def steer(p, vg, w, deg):
        a = np.radians(deg)
        k = STEER_DIR
        rel = p - L["front"]
        rot = rel * np.cos(a) + np.cross(k, rel) * np.sin(a) + np.outer(rel @ k, k) * (1 - np.cos(a))
        ws = (np.isin(vg, STEER_BONES) * w).sum(1)[:, None]
        return (p + ws * (rot - rel)).astype(np.float32)
    gvg, gw = dbg["g"]["vg"], dbg["g"]["w"]
    sv = []
    for deg, y, pt in ((25, 30, 20), (-25, 30, 20), (25, 330, 20), (-25, 330, 20)):
        mp = steer(mesh.pos, mesh.vg, mesh.w, deg)
        sv.append(render(mp, ops.compute_normals(mp, mesh.comps["Head"]), [mesh.comps["Head"]], size=(720, 420),
                         yaw=y, pitch=pt, uv=mesh.uv, textures=[tex], bounds=(-0.8, 0.8, 0.3, 1.35), cull=True,
                         bg=(0, 150, 0), ssaa=2))
    for deg, y, pt in ((25, 30, 20), (-25, 30, 20)):
        gpp = steer(gp, gvg, gw, deg)
        sv.append(render(gpp, gn, gt, size=(720, 420), yaw=y, pitch=pt, uv=gu, textures=gx,
                         bounds=(-0.8, 0.8, 0.3, 1.35), cull=False, ssaa=2))
    sheet(sv, cols=2, labels=["mod steered +25, yaw 30", "mod steered -25, yaw 30", "mod +25, yaw 330",
                              "mod -25, yaw 330", "game bike steered +25 (axis check)", "game bike -25"]
          ).save(path.replace(".png", "_steer.png"))
    log("preview:", path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--stl", default=STL)
    ap.add_argument("--preview")
    a = ap.parse_args()
    mesh, dbg = build(a.out, a.stl)
    if a.preview:
        preview(mesh, dbg, a.preview)
