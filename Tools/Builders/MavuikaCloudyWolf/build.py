"""
MavuikaCloudyWolf: Mavuika (GI) in Cloud Strife's Advent Children outfit.

    python Tools/Builders/MavuikaCloudyWolf/build.py [--preview Docs/Previews/MavuikaCloudyWolf.png]

The outfit's mesh and textures are READ from a model the maintainer downloaded (FFVII Ever Crisis, an .fbx and
.tga files; not stored in this repo) and fitted to Mavuika by this recipe:

1. Blender (headless) turns the .fbx into arrays (``modkit.blender.fbx_dump``), cached in the temp folder.
2. RETARGET: Cloud's outfit is moved from his rest pose and proportions to hers. Limbs go bone by bone
   (shoulder -> elbow -> wrist, hip -> knee -> ankle: a rotation, a length scale and a thickness scale per bone,
   blended with Cloud's own bone weights); the torso goes through one smooth map (height landmarks, width).
3. TORSO FIT: the outline of his base layer (knit top + trousers) and of her torso are measured as radius per
   height and angle; every torso vertex moves radially by the difference, so the top takes her figure and
   everything worn over it (straps, holster, coat top) keeps its distance from it.
4. WEIGHTS: her vertex groups, looked up from her own model's nearest vertices, limb by limb.
5. Her own model keeps: neck and head skin, ears, earrings, eye pieces, forearms and (already gloved) hands.
   Her hair and face are the game's (this mod does not touch those buffers).
"""

import argparse
import os
import shutil
import sys
import tempfile

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO, "Tools", "ModKit"))

from modkit.gimi import Mesh, POS_DTYPE, TEX12_DTYPE, weld_islands  # noqa: E402
from modkit import ops, blender  # noqa: E402
from modkit.render import render, sheet  # noqa: E402

SRC = r"E:\Computer\Games\Genshin\Repos\Repos\Anime-Game-Identity-Mod-Generator\Mods\GI\Mavuika"
CLOUD = r"E:\Downloads\FFVII Ever Crisis - Cloud (Advent Children)\Raw Files\Model"
# the outfit is one part of MavuikaCloudyWolf beside Motorcycle and Sword (their own builders), as in the game's
# Mods\Mavuika folder
OUT = os.path.join(REPO, "Mods", "GI", "Mavuika", "MavuikaCloudyWolf", "Mavuika")
NAME = "MavuikaBody"
COMPS = ("Head", "Body", "Dress")
G = 92                      # her vertex groups
SC = 100.0                  # the fbx is in centimetres-as-metres
GROUND = -0.035             # her soles (she stands on heels; the model's lowest point is -0.039)

# ---- her vertex groups (measured: weighted centres and boxes per group, 2026-11-15) ----
VG_T = [23, 32, 90, 91, 67, 44, 46, 69, 0, 1, 2, 3, 6, 7, 41, 43, 4, 5]     # pelvis .. head, clavicles, bust, seat
VG_ARM = {"L": [40, 38, 86, 14, 27], "R": [39, 37, 63, 13, 26]}             # upper arm, its twist, forearm
VG_HAND = {"L": [87] + list(range(70, 85)), "R": [64] + list(range(47, 62))}
VG_LEG = {"L": [36, 88, 68, 85, 89, 20, 34], "R": [35, 65, 45, 62, 66, 19, 33]}
VG_FOOT = {"L": (85, 89), "R": (62, 66)}
VG_CLAV = {"L": 69, "R": 46}
VG_ACC = [8, 21, 22, 42, 9, 10, 11, 12, 15, 16, 17, 18, 28, 29, 30, 31, 24, 25]   # ornaments, cuffs, heel spikes

# ---- her joints, left side (x > 0); the right side is the mirror. From weight overlaps and limb ring centres ----
SH_M = np.array([0.125, 1.410, 0.000])
EL_M = np.array([0.239, 1.215, -0.005])
WR_M = np.array([0.375, 1.035, -0.005])
HIP_Y, KNEE_Y, ANK_Y = 0.975, 0.565, 0.105
NECK_M_Y, COLLAR_M_Y = 1.483, 1.528          # base of her neck; where the turtleneck's top edge goes (under her chin)
ARM_RADIAL, LEG_RADIAL, HAND_SCALE, FOOT_XZ = 0.80, 0.95, 0.85, 0.88
TORSO_CLEAR = 0.006
TWIN_GAP = 0.0015
# how each piece's inside is made: "none" (the bare back face), "flip" (a copy with normals turned inward) or "keep"
# (a copy lit like the outside). MCW_INNER=exp builds the 2026-11-15 experiment: one of each, to look at in the game.
# RESULT (game audit 3): "none" everywhere. The game textures a bare back face like its front (the coat's inside
# was "leather like the outside"), while every inner copy, with normals flipped or kept, showed as black slabs and
# saw-teeth: a copy's faces are wound inward, and the game's outline pass (back faces pushed out, drawn black)
# then draws the copy's OUTWARD side black over the cloth.
INNER = dict(coat="none", sleeve="none", warmer="none", collar="none", holster="none")
if os.environ.get("MCW_INNER") == "exp":
    INNER = dict(coat="none", sleeve="keep", warmer="keep", collar="none", holster="flip")
COAT_PELVIS = 0.45           # share of the pelvis in the coat's weights behind her
PAULDRON_ARM = 1.0
FOREARM_RADIAL = 0.92        # warmer and bell sleeve: at 0.80 her own forearm stood through the warmer as flat black
HOLSTER_WIDTH = 0.90         # his back harness is as wide as his back; hers is narrower
ARMHOLE_R = 0.062
ARMHOLE_T = -0.018           # where along her upper arm (m from the shoulder joint) the top ends
# the outline's width (vertex colour alpha). MCW_OUTLINE=0 builds the outfit with NO outline: the test of whether
# the black marks left on the coat are the outline pass (they go) or the main pass (they stay).
OUTLINE_A = int(os.environ.get("MCW_OUTLINE", "100"))
RIGID_DIAG = 0.12            # buckles, studs, the wolf emblem: moved as rigid pieces


def log(*a):
    print(*a, flush=True)


# ------------------------------------------------------------------------------------------------ sources

def load_mavuika():
    m = Mesh.load(SRC, NAME, COMPS, tex_stride=12)
    m.dense = ops.dense_weights(m.w, m.vg, G)
    m.dom = m.dense.argmax(1)
    return m


def load_cloud():
    cache = os.path.join(tempfile.gettempdir(), "modkit_cache", "cloud_ac.npz")
    fbx = os.path.join(CLOUD, "Cloud Strife (Advent Children).fbx")
    if not os.path.isfile(cache) or os.path.getmtime(cache) < os.path.getmtime(fbx):
        log("reading the fbx through Blender ...")
        blender.fbx_dump(fbx, cache)
    d = np.load(cache)
    names = list(d["names"])
    bones = [str(b) for b in d["bones"]]
    out = {"bones": bones, "parent": d["bone_parent"], "head": d["bone_head"] * SC}
    for nm in ("body_geo", "skin_geo"):
        i = names.index(nm)
        pos, nrm, tris = d[f"{i}_pos"].astype(np.float64) * SC, d[f"{i}_nrm"].astype(np.float64), d[f"{i}_tris"].astype(np.int64)
        fn = np.cross(pos[tris[:, 1]] - pos[tris[:, 0]], pos[tris[:, 2]] - pos[tris[:, 0]])
        bad = (fn * nrm[tris].sum(1)).sum(1) < 0
        # 195 of his triangles wind against their own vertex normals. They were re-wound in epoch 1 (to clear
        # "back faces" in the offline render); they are LEFT AS HE HAS THEM since 2026-11-17: his game culls by
        # winding, so his winding is the outward one, and a triangle wound inward is drawn black by this game's
        # outline pass (what the inner copies taught).
        log("%s: %d of %d triangles wind against their normals (left as they are)" % (nm, bad.sum(), len(tris)))
        out[nm] = dict(pos=pos, nrm=nrm,
                       uv=d[f"{i}_uv"], tris=tris,
                       dense=ops.dense_weights(d[f"{i}_w"], d[f"{i}_vg"], len(bones)))
    return out


# ------------------------------------------------------------------------------------------------ retarget

KEYS = {"left_arm": "LAu", "left_forearm": "LAf", "left_hand": "LH", "left_upleg": "LLu", "left_leg": "LLl",
        "left_foot": "LF", "right_arm": "RAu", "right_forearm": "RAf", "right_hand": "RH", "right_upleg": "RLu",
        "right_leg": "RLl", "right_foot": "RF"}
XF = ["T", "LAu", "LAf", "LH", "LLu", "LLl", "LF", "RAu", "RAf", "RH", "RLu", "RLl", "RF"]


def bone_xform_class(cloud):
    """each Cloud bone -> the transform it rides (its nearest ancestor among KEYS, else the torso map)"""
    bones, parent = cloud["bones"], cloud["parent"]
    out = []
    for i in range(len(bones)):
        j = i
        while j >= 0 and bones[j] not in KEYS:
            j = parent[j]
        out.append(XF.index(KEYS[bones[j]]) if j >= 0 else 0)
    return np.array(out)


def rot_between(a, b):
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    v, c = np.cross(a, b), float(a @ b)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1 + c)


def seg(hc, tc, hm, tm, radial):
    """the map that takes Cloud's bone hc -> tc onto hers hm -> tm: v' = A v + b"""
    dc, dm = tc - hc, tm - hm
    lc, lm = np.linalg.norm(dc), np.linalg.norm(dm)
    dc = dc / lc
    A = rot_between(dc, dm) @ (radial * np.eye(3) + (lm / lc - radial) * np.outer(dc, dc))
    return A, hm - A @ hc


def leg_joints(mav):
    """her left leg's axis from ring centres of the suit's leg"""
    used = np.zeros(mav.n, bool)
    used[np.unique(mav.comps["Dress"])] = True
    m = used & np.isin(mav.dom, VG_LEG["L"]) & (mav.pos[:, 0] > 0.005)

    def ring(y0, y1):
        p = mav.pos[m & (mav.pos[:, 1] > y0) & (mav.pos[:, 1] < y1)]
        return (p.min(0) + p.max(0)) / 2
    th, kn, an = ring(0.80, 0.86), ring(0.54, 0.59), ring(0.16, 0.22)
    hip = np.array([th[0] + (th[0] - kn[0]) * 0.5, HIP_Y, th[2] + (th[2] - kn[2]) * 0.5])
    return hip, np.array([kn[0], KNEE_Y, kn[2]]), np.array([an[0], ANK_Y, an[2]])


class Retarget:
    def __init__(self, cloud, mav):
        H = {b: cloud["head"][i] for i, b in enumerate(cloud["bones"])}
        hip, knee, ank = leg_joints(mav)
        log("her left leg joints: hip %s knee %s ankle %s" % (hip.round(3), knee.round(3), ank.round(3)))
        self.cls = bone_xform_class(cloud)
        mir = np.array([-1.0, 1.0, 1.0])
        # torso map: x * sx(y), fy(y), z * SZ + dz(y); made to carry Cloud's shoulder and hip joints onto hers
        self.ys_c = np.array([0.0, H["left_upleg"][1], H["left_arm"][1], H["neck"][1], H["head"][1], H["head"][1] + 0.2])
        self.ys_m = np.array([GROUND, HIP_Y, SH_M[1], NECK_M_Y, COLLAR_M_Y, COLLAR_M_Y + 0.2])
        self.SZ = 0.90
        sx_hip, sx_sh = hip[0] / H["left_upleg"][0], SH_M[0] / H["left_arm"][0]
        dz_hip, dz_sh = hip[2] - self.SZ * H["left_upleg"][2], SH_M[2] - self.SZ * H["left_arm"][2]
        self.kx = (self.ys_c[1:3], np.array([sx_hip, sx_sh]))
        self.kz = (self.ys_c[1:3], np.array([dz_hip, dz_sh]))
        log("torso map: width x%.3f at the hips, x%.3f at the shoulders; forward %.3f / %.3f m" % (sx_hip, sx_sh, dz_hip, dz_sh))
        fy = (ank[1] - GROUND) / H["left_foot"][1]
        self.A, self.b = {}, {}
        for s, sgn in (("L", 1.0), ("R", -1.0)):
            side = "left" if s == "L" else "right"
            f = (lambda v: v) if s == "L" else (lambda v: v * mir)
            self.A[s + "Au"], self.b[s + "Au"] = seg(H[side + "_arm"], H[side + "_forearm"], f(SH_M), f(EL_M), ARM_RADIAL)
            self.A[s + "Af"], self.b[s + "Af"] = seg(H[side + "_forearm"], H[side + "_hand"], f(EL_M), f(WR_M), FOREARM_RADIAL)
            Ah = self.A[s + "Af"] / np.cbrt(abs(np.linalg.det(self.A[s + "Af"]))) * HAND_SCALE
            self.A[s + "H"], self.b[s + "H"] = Ah, f(WR_M) - Ah @ H[side + "_hand"]
            self.A[s + "Lu"], self.b[s + "Lu"] = seg(H[side + "_upleg"], H[side + "_leg"], f(hip), f(knee), LEG_RADIAL)
            self.A[s + "Ll"], self.b[s + "Ll"] = seg(H[side + "_leg"], H[side + "_foot"], f(knee), f(ank), LEG_RADIAL)
            Af = np.diag([FOOT_XZ, fy, FOOT_XZ])
            self.A[s + "F"], self.b[s + "F"] = Af, f(ank) - Af @ H[side + "_foot"]

    def torso(self, p):
        y = p[:, 1]
        sx = np.interp(y, *self.kx)
        dz = np.interp(y, *self.kz)
        return np.stack([p[:, 0] * sx, np.interp(y, self.ys_c, self.ys_m), p[:, 2] * self.SZ + dz], 1)

    def torso_normal(self, p, n):
        y = p[:, 1]
        k = np.searchsorted(self.ys_c, y).clip(1, len(self.ys_c) - 1)
        dy = (self.ys_m[k] - self.ys_m[k - 1]) / (self.ys_c[k] - self.ys_c[k - 1])
        return n / np.stack([np.interp(y, *self.kx), dy, np.full(len(y), self.SZ)], 1)

    def apply(self, part, armor=None):
        """part: pos, nrm, dense (Cloud bone weights). Returns new pos, nrm and the (n, 13) transform-class masses"""
        mass = np.zeros((len(part["pos"]), len(XF)))
        for k in range(len(XF)):
            mass[:, k] = part["dense"][:, self.cls == k].sum(1)
        mass /= mass.sum(1, keepdims=True)
        if armor is not None:
            # the pauldron is rigid on his clavicle, but her arms hang lower than his: its outer half follows the
            # upper arm, or it stands off the sleeve as a flap
            f = (armor * ((part["pos"][:, 0] - 0.07) / 0.13).clip(0, 1) * PAULDRON_ARM)
            mass[:, XF.index("LAu")] += mass[:, 0] * f
            mass[:, 0] *= 1 - f
        pos = mass[:, :1] * self.torso(part["pos"])
        nrm = mass[:, :1] * self.torso_normal(part["pos"], part["nrm"])
        for k, name in enumerate(XF[1:], 1):
            A, b = self.A[name], self.b[name]
            pos += mass[:, k:k + 1] * (part["pos"] @ A.T + b)
            nrm += mass[:, k:k + 1] * (part["nrm"] @ np.linalg.inv(A))
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
        return pos, nrm, mass


# ------------------------------------------------------------------------------------------------ torso fit

AX = (0.0, 0.01)                            # the vertical axis both outlines are measured round
FIT_YS = np.arange(0.86, 1.565, 0.01)
FIT_TH = np.linspace(-np.pi, np.pi, 96, endpoint=False)


def _fill_smooth(D, sig=1.6):
    D = D.copy()
    for _ in range(200):
        bad = np.isnan(D)
        if not bad.any():
            break
        acc, cnt = np.zeros_like(D), np.zeros_like(D)
        for sh, ax in ((1, 1), (-1, 1), (1, 0), (-1, 0)):
            r = np.roll(D, sh, ax)
            if ax == 0:                      # heights do not wrap
                if sh == 1:
                    r[0] = np.nan
                else:
                    r[-1] = np.nan
            ok = ~np.isnan(r)
            acc[ok] += r[ok]
            cnt += ok
        take = bad & (cnt > 0)
        D[take] = acc[take] / cnt[take]
    k = np.exp(-0.5 * (np.arange(-5, 6) / sig) ** 2)
    k /= k.sum()
    Dp = np.concatenate([D[:, -5:], D, D[:, :5]], 1)
    D = np.stack([np.convolve(r, k, "valid") for r in Dp])
    Dp = np.concatenate([np.repeat(D[:1], 5, 0), D, np.repeat(D[-1:], 5, 0)], 0)
    return np.stack([np.convolve(c, k, "valid") for c in Dp.T], 1)


def torso_field(base_pos, base_tris, mav):
    """how far, per height and angle, Cloud's base layer must move radially to lie on her torso"""
    Rc = ops.radial_envelope(base_pos, base_tris, AX[0], AX[1], FIT_YS, FIT_TH)
    ok = np.isin(mav.dom, VG_T + VG_LEG["L"][:1] + VG_LEG["R"][:1])
    tris = np.concatenate([mav.comps["Body"], mav.comps["Dress"]])
    tris = tris[ok[tris].all(1)]
    Rm = ops.radial_envelope(mav.pos.astype(np.float64), tris, AX[0], AX[1], FIT_YS, FIT_TH)
    top = np.searchsorted(FIT_YS, 1.50)
    Rm[top:] = Rm[top - 1]                   # above her neck comes her jaw: the collar stays a neck-wide tube
    Rm = Rm + (0.001 * ((FIT_YS - 1.46) / 0.04).clip(0, 1))[:, None]     # a looser collar round her neck
    D = _fill_smooth(Rm + TORSO_CLEAR - Rc).clip(-0.10, 0.10)
    log("torso fit: his base layer moves %.1f .. %.1f cm (mean %.1f)" % (100 * D.min(), 100 * D.max(), 100 * D.mean()))
    return D, _fill_smooth(Rm, 1.0), _fill_smooth(Rc, 1.0)


def apply_field(pos, D, amount):
    dx, dz = pos[:, 0] - AX[0], pos[:, 2] - AX[1]
    r = np.hypot(dx, dz)
    th = np.arctan2(dx, dz)
    fy = ((pos[:, 1] - FIT_YS[0]) / 0.01).clip(0, len(FIT_YS) - 1.001)
    ft = ((th + np.pi) / (2 * np.pi) * len(FIT_TH)) % len(FIT_TH)
    y0, t0 = fy.astype(int), ft.astype(int)
    y1, t1 = y0 + 1, (t0 + 1) % len(FIT_TH)
    a, b = fy - y0, ft - t0
    d = (D[y0, t0] * (1 - a) * (1 - b) + D[y1, t0] * a * (1 - b) + D[y0, t1] * (1 - a) * b + D[y1, t1] * a * b)
    ramp = ((pos[:, 1] - 0.86) / 0.09).clip(0, 1)
    k = ((r + d * amount * ramp) / np.maximum(r, 1e-4)).clip(0.3, 3.0)
    out = pos.copy()
    out[:, 0], out[:, 2] = AX[0] + dx * k, AX[1] + dz * k
    return out


def clear_over(pos, body_pos, body_nrm, margin, reach=0.05):
    """push points that lie under (or closer than margin above) the body's nearest vertex out along its normal"""
    moved = 0
    for s in range(0, len(pos), 1024):
        d = np.linalg.norm(pos[s:s + 1024, None] - body_pos[None], axis=2)
        j = d.argmin(1)
        h = ((pos[s:s + 1024] - body_pos[j]) * body_nrm[j]).sum(1)
        lift = (margin - h).clip(0, None) * (d.min(1) < reach)
        pos[s:s + 1024] += lift[:, None] * body_nrm[j]
        moved += int((lift > 0).sum())
    return moved


# ------------------------------------------------------------------------------------------------ weights

def cloud_weight_classes(cloud):
    """Cloud bone -> the class its weight is re-looked-up in on her"""
    out = []
    bones, parent = cloud["bones"], cloud["parent"]
    for i, b in enumerate(bones):
        chain = []
        j = i
        while j >= 0:
            chain.append(bones[j])
            j = parent[j]
        side = "L" if any(c.startswith("left_") or "_left_" in c for c in chain[:1]) else \
               "R" if any(c.startswith("right_") or "_right_" in c for c in chain[:1]) else None
        if side is None:
            side = "L" if any(c in ("left_arm", "left_upleg") for c in chain) else \
                   "R" if any(c in ("right_arm", "right_upleg") for c in chain) else None
        if "skirt" in b:
            c = "SK"
        elif "armor" in b:
            c = "CLAV" + "L"
        elif any(c in ("left_toe", "right_toe") for c in chain):
            c = "TOE" + side
        elif any(c in ("left_foot", "right_foot") for c in chain):
            c = "FOOT" + side
        elif any(c in ("left_arm", "right_arm") for c in chain):
            c = "ARM" + side
        elif any(c in ("left_upleg", "right_upleg") for c in chain):
            c = "LEG" + side
        else:
            c = "T"
        out.append(c)
    return out


def her_sources(mav, hand_verts):
    """her vertices that weights may be looked up from, per class: body-hugging surfaces only, no ornaments"""
    used = np.zeros(mav.n, bool)
    used[np.unique(np.concatenate([mav.comps["Body"], mav.comps["Dress"]]))] = True
    used[hand_verts] = True
    used &= ~np.isin(mav.dom, VG_ACC)
    src = {"T": used & np.isin(mav.dom, VG_T)}
    for s in "LR":
        src["ARM" + s] = used & np.isin(mav.dom, VG_ARM[s])
        # no feet: a coat hem or trouser hem near a boot must not tip with the foot (boots take the foot groups
        # directly from Cloud's own foot bones)
        src["LEG" + s] = used & np.isin(mav.dom, [g for g in VG_LEG[s] if g not in VG_FOOT[s]])
    # the coat's weight sources: torso and THIGHS only (the first two groups of each leg). With the shins in, a run
    # pulled the coat back to her trailing foot as a nearly level slab (game audit 6).
    for s in "LR":
        src["THIGH" + s] = used & np.isin(mav.dom, VG_LEG[s][:2])
    src["SK"] = src["T"] | src["THIGHL"]
    return src


def transfer_weights(pos, cpos, cdense, cloud, mav, src):
    classes = cloud_weight_classes(cloud)
    names = sorted(set(classes))
    mass = {c: cdense[:, [i for i, k in enumerate(classes) if k == c]].sum(1) for c in names}
    tot = sum(mass.values())
    out = np.zeros((len(pos), G), np.float32)
    for c in names:
        m = mass[c] / tot
        sel = m > 1e-4
        if not sel.any():
            continue
        if c.startswith("FOOT"):
            out[sel, VG_FOOT[c[-1]][0]] += m[sel]
        elif c.startswith("TOE"):
            out[sel, VG_FOOT[c[-1]][1]] += m[sel]
        elif c.startswith("CLAV"):
            f = ((cpos[sel, 0] - 0.07) / 0.13).clip(0, 1) * 0.7
            out[sel, VG_CLAV[c[-1]]] += m[sel] * (1 - f)
            s = src["ARM" + c[-1]]
            w, g = ops.knn_weights(mav.pos[s], mav.w[s], mav.vg[s], pos[sel].astype(np.float32), k=6, n_groups=G)
            out[sel] += ops.dense_weights(w, g, G) * (m[sel] * f)[:, None]
        else:
            s = src[c]
            w, g = ops.knn_weights(mav.pos[s], mav.w[s], mav.vg[s], pos[sel].astype(np.float32), k=6, n_groups=G)
            wd = ops.dense_weights(w, g, G)
            if c == "SK":
                # THE COAT (the maintainer, 2026-11-15: "the back cape part is tied to mavuika's left leg, so when
                # she moves, that bottom leg cape part becomes stretched since her stance widened"). Nearest
                # neighbours gave the whole back panel to whichever leg was nearer, mostly the left. Now the share
                # of the RIGHT leg grows across her (none at x +0.10, half at her middle, all at x -0.10; the right
                # leg is looked up at the mirrored place so heights match), and behind her 45% of the weight is
                # the pelvis itself, so the back hangs from her hips and only leans with the legs.
                q = pos[sel].astype(np.float32)
                sr = src["T"] | src["THIGHR"]
                w2, g2 = ops.knn_weights(mav.pos[sr], mav.w[sr], mav.vg[sr], q * np.array([-1, 1, 1], np.float32), k=6, n_groups=G)
                share_r = ((0.10 - q[:, 0]) / 0.20).clip(0, 1)[:, None]
                wd = wd * (1 - share_r) + ops.dense_weights(w2, g2, G) * share_r
                back = (((0.02 - q[:, 2]) / 0.06).clip(0, 1) * COAT_PELVIS)[:, None]
                wd = wd * (1 - back)
                wd[:, VG_T[0]] += back[:, 0]
            out[sel] += wd * m[sel, None]
    return ops.top4(out)


# ------------------------------------------------------------------------------------------------ parts

def cloud_part(geo, pos, nrm, tmask, w, vg, uv=None):
    tris = geo["tris"][tmask]
    used, inv = np.unique(tris, return_inverse=True)
    p = ops.new_part(pos[used], inv.reshape(-1, 3), geo["uv"][used] if uv is None else np.tile(uv, (len(used), 1)))
    p["nrm"] = nrm[used].astype(np.float32)
    p["tan"] = ops.compute_tangents(p["pos"], p["nrm"], p["uv"], p["tris"])
    p["w"], p["vg"] = w[used], vg[used]
    return p


def twin(p, gap=TWIN_GAP, keep_normals=False):
    """
    the inside of single-sided cloth: a copy just under it, wound the other way. keep_normals leaves the copy the
    OUTSIDE's normals (so it is lit like the outside) instead of turning them inward.
    """
    q = {k: v.copy() for k, v in p.items()}
    sm = {"pos": p["pos"], "nrm": ops.compute_normals(p["pos"], p["tris"])}
    ops.weld_normals(sm, tol=1e-4)
    q["pos"] = (p["pos"] - gap * sm["nrm"]).astype(np.float32)
    q["nrm"] = p["nrm"].copy() if keep_normals else -p["nrm"]
    q["tris"] = p["tris"][:, ::-1].copy()
    q["tan"] = ops.compute_tangents(q["pos"], q["nrm"], q["uv"], q["tris"])
    return q


def skin_texel(mav, lm, df, verts):
    """the UV of the plainest skin texel among the given vertices of her Body texture"""
    best, buv = 1e9, None
    S = df.shape[0]
    for v in verts:
        x, y = int(mav.uv[v, 0] * S), int(mav.uv[v, 1] * S)
        if not (6 <= x < S - 6 and 6 <= y < S - 6):
            continue
        if lm[y - 5:y + 6, x - 5:x + 6, 3].min() < 240:
            continue
        var = df[y - 5:y + 6, x - 5:x + 6, :3].reshape(-1, 3).astype(float).std(0).sum()
        if var < best:
            best, buv = var, ((x + 0.5) / S, (y + 0.5) / S)
    return np.array(buv, np.float32)


# ------------------------------------------------------------------------------------------------ textures

def make_textures(out, head_part, neck_part):
    df = np.asarray(Image.open(os.path.join(CLOUD, "tex_ch001_019_body_AAAT.tga")).convert("RGBA")).astype(np.float32)
    mr = np.asarray(Image.open(os.path.join(CLOUD, "tex_ch001_019_body_MROX.tga")).convert("RGBA")).astype(np.float32)
    # his leather is near black (about 35 of 255). In the game its shadow side came out as flat pure black with a
    # ruler-straight edge: lifted (gamma 0.70) so the shade ramp has something to darken.
    rgb = 255 * ((df[..., :3] / 255) ** 0.70) * 1.05
    dif = np.zeros(df.shape, np.uint8)
    dif[..., :3] = rgb.clip(0, 235)
    ops.save_dds(os.path.join(out, NAME + "DressDiffuse.dds"), dif, srgb=True)
    metal, rough, occ = mr[..., 0] / 255, mr[..., 1] / 255, mr[..., 2] / 255
    lm = np.zeros(df.shape, np.uint8)
    # her suit's own light map texel is (204, 89, 20, 176): the Dress draw's black leather. Matt cloth gets less of r.
    # In the game r 50..200 made trousers and coat shine like patent leather, and g well under 128 put whole panels
    # in permanent shade. Now matt (r, b low; metal keeps its shine) and g near neutral.
    # (metal at r 225 / b 135 made his black inner collar band flash gold under her chin: three audits took it
    # for a pendant of her old outfit. Metal is told by its silver diffuse; the light map only hints at it.)
    lm[..., 0] = (25 + 25 * (1 - rough) + 50 * metal).clip(0, 255)
    lm[..., 1] = (128 * (0.90 + 0.10 * occ)).clip(0, 255)
    lm[..., 2] = (5 + 30 * metal).clip(0, 255)
    lm[..., 3] = 176
    ops.save_dds(os.path.join(out, NAME + "DressLightMap.dds"), lm, srgb=False)
    nm = np.zeros((256, 256, 4), np.uint8)
    nm[:] = (128, 128, 128, 118)                                 # flat; b and a as her own map's commonest texel
    ops.save_dds(os.path.join(out, NAME + "DressNormalMap.dds"), nm, srgb=False)
    for c in ("Head", "Body"):
        shutil.copyfile(os.path.join(SRC, f"{NAME}{c}NormalMap.dds"), os.path.join(out, f"{NAME}{c}NormalMap.dds"))
    tex = {}
    for c in ("Head", "Body"):
        d_ = np.asarray(Image.open(os.path.join(SRC, f"{NAME}{c}Diffuse.dds")).convert("RGBA")).copy()
        l_ = np.asarray(Image.open(os.path.join(SRC, f"{NAME}{c}LightMap.dds")).convert("RGBA")).copy()
        if c == "Head":
            paint_long_gloves(d_, l_, head_part)
        else:
            # paint_neck is NOT run any more: each widening of it made the "gold piece at her throat" in the game
            # bigger (audit 1: a small triangle; audit 2, after its threshold was lowered: an ornament filling the
            # V). Her neck below the jaw reads the plain skin texel instead, like the bare arm, which the game
            # showed in the right tone. The Body textures are the game's own, untouched.
            for k in ("Diffuse", "LightMap"):
                shutil.copyfile(os.path.join(SRC, f"{NAME}{c}{k}.dds"), os.path.join(out, f"{NAME}{c}{k}.dds"))
            tex[c] = d_
            continue
        ops.save_dds(os.path.join(out, f"{NAME}{c}Diffuse.dds"), d_, srgb=True)
        ops.save_dds(os.path.join(out, f"{NAME}{c}LightMap.dds"), l_, srgb=False)
        tex[c] = d_
    return dif, tex


def paint_long_gloves(dif, lm, head_part):
    """her forearms' bare skin (and the pale wristband) become the glove's own black leather: long gloves"""
    S = dif.shape[0]
    hands = np.isin(head_part["vg"][:, 0], VG_HAND["L"] + VG_HAND["R"] + VG_ARM["L"] + VG_ARM["R"] + [17, 18])   # 17 / 18: her bracelets
    t = head_part["tris"][hands[head_part["tris"]].all(1)]
    mask, _ = ops.bake_uv(head_part["uv"], t, S, {})
    lum = dif[..., :3].astype(float).mean(2)
    glove = mask & (lm[..., 3] < 100) & (lum < 90)
    fore = np.isin(head_part["vg"][:, 0], VG_ARM["L"] + VG_ARM["R"] + [17, 18])
    fmask, _ = ops.bake_uv(head_part["uv"], head_part["tris"][fore[head_part["tris"]].any(1)], S, {})
    gold = (dif[..., 0].astype(int) - dif[..., 2] > 40) & (lum > 90)
    skin = ops.dilate(mask & ((lm[..., 3] > 200) | (lum > 150) | (fmask & ~gold & (lum > 70))), 3) & ops.dilate(mask, 3)
    dif[skin, :3] = np.median(dif[glove][:, :3], 0)
    lm[skin] = np.median(lm[glove], 0)
    log("long gloves: %d skin texels of her forearms painted as glove leather %s" % (skin.sum(), np.median(dif[glove][:, :3], 0)))


def paint_neck(dif, lm, neck_part):
    """the choker's shadow and outline, painted into her neck's skin, are painted out"""
    S = dif.shape[0]
    mask, at = ops.bake_uv(neck_part["uv"], neck_part["tris"], S, {"pos": neck_part["pos"]})
    low = mask & (at["pos"][..., 1] < 1.515)
    rgb = dif[..., :3].astype(float)
    ref = np.median(rgb[low], 0)
    off = np.abs(rgb - ref).sum(2) > 20
    lmref = np.median(lm[low & ~off], 0)
    bad = ops.dilate(low & (off | (np.abs(lm.astype(float) - lmref).sum(2) > 60)), 2)
    region = ops.dilate(low, 4)
    bad = (bad & region) | (region & ~mask)
    dif[..., :3] = ops.inpaint(rgb, ~bad, need=region).round().clip(0, 255).astype(np.uint8)
    lm[bad] = lmref.astype(np.uint8)
    log("neck: %d texels painted back to plain skin" % (bad & mask).sum())


INI = """; MavuikaCloudyWolf: Mavuika in Cloud Strife's Advent Children outfit
; Built by Tools/Builders/MavuikaCloudyWolf/build.py (AlbertGold AI Mods). Do not edit by hand.
; Her hair and face are the game's own: this mod only replaces the body buffers.

[TextureOverrideMavuikaBodyPosition]
hash = 80b13a2f
vb0 = ResourceMavuikaBodyPosition

[TextureOverrideMavuikaBodyBlend]
hash = 00088f8d
vb1 = ResourceMavuikaBodyBlend
handling = skip
draw = {n},0

[TextureOverrideMavuikaBodyTexcoord]
hash = 3af262c1
vb1 = ResourceMavuikaBodyTexcoord

[TextureOverrideMavuikaBodyVertexLimitRaise]
hash = 00323c91

[TextureOverrideMavuikaBodyIB]
hash = 43f8af29
handling = skip
drawindexed = auto

[TextureOverrideMavuikaBodyHead]
hash = 43f8af29
match_first_index = 0
ib = ResourceMavuikaBodyHeadIB
ps-t0 = ResourceMavuikaBodyHeadNormalMap
ps-t1 = ResourceMavuikaBodyHeadDiffuse
ps-t2 = ResourceMavuikaBodyHeadLightMap
run = CommandList\\global\\ORFix\\ORFix

[TextureOverrideMavuikaBodyBody]
hash = 43f8af29
match_first_index = 16914
ib = ResourceMavuikaBodyBodyIB
ps-t0 = ResourceMavuikaBodyBodyNormalMap
ps-t1 = ResourceMavuikaBodyBodyDiffuse
ps-t2 = ResourceMavuikaBodyBodyLightMap
run = CommandList\\global\\ORFix\\ORFix

[TextureOverrideMavuikaBodyDress]
hash = 43f8af29
match_first_index = 42618
ib = ResourceMavuikaBodyDressIB
ps-t0 = ResourceMavuikaBodyDressNormalMap
ps-t1 = ResourceMavuikaBodyDressDiffuse
ps-t2 = ResourceMavuikaBodyDressLightMap
run = CommandList\\global\\ORFix\\ORFix

[ResourceMavuikaBodyPosition]
type = Buffer
stride = 40
filename = MavuikaBodyPosition.buf

[ResourceMavuikaBodyBlend]
type = Buffer
stride = 32
filename = MavuikaBodyBlend.buf

[ResourceMavuikaBodyTexcoord]
type = Buffer
stride = 12
filename = MavuikaBodyTexcoord.buf
"""


FX_INI = """
; The game's own effects mask for Mavuika (GI-Model-Importer-Assets: component "NatlanFX", texture "Shadow"), which
; the shader reads through the model's UVs. On this outfit's UV layout its shapes showed as black marks.
[TextureOverrideMavuikaNatlanFX]
hash = b6b1dc80
this = ResourceMavuikaNatlanFXBlank

[ResourceMavuikaNatlanFXBlank]
filename = MavuikaNatlanFXBlank.dds
"""


def write_ini(out, n):
    blank = np.zeros((64, 64, 4), np.uint8)
    blank[..., 3] = 255
    ops.save_dds(os.path.join(out, "MavuikaNatlanFXBlank.dds"), blank, srgb=False)
    s = INI.format(n=n) + FX_INI
    for c in COMPS:
        s += f"\n[Resource{NAME}{c}IB]\ntype = Buffer\nformat = DXGI_FORMAT_R32_UINT\nfilename = {NAME}{c}.ib\n"
    for c in COMPS:
        for k in ("NormalMap", "Diffuse", "LightMap"):
            s += f"\n[Resource{NAME}{c}{k}]\nfilename = {NAME}{c}{k}.dds\n"
    with open(os.path.join(out, "MavuikaCloudyWolf.ini"), "w", newline="\r\n") as f:
        f.write(s)


# ------------------------------------------------------------------------------------------------ build

def island_info(geo, cloud, tol=1e-4):
    lab = weld_islands(geo["pos"], geo["tris"], tol)
    tl = lab[geo["tris"][:, 0]]
    info = []
    for l in range(lab.max() + 1):
        m = lab == l
        p = geo["pos"][m]
        dom = cloud["bones"][int(geo["dense"][m].sum(0).argmax())]
        info.append(dict(id=l, tris=int((tl == l).sum()), dom=dom, lo=p.min(0), hi=p.max(0),
                         diag=float(np.linalg.norm(p.max(0) - p.min(0)))))
    return lab, tl, info


def open_islands(geo, lab, tl, tol=1e-4):
    """islands with a free edge: single-sided cloth whose back can be seen"""
    _, wi = np.unique(np.round(geo["pos"] / tol).astype(np.int64), axis=0, return_inverse=True)
    t = wi.reshape(-1)[geo["tris"]]
    e = np.sort(np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]]), axis=1)
    owner = np.tile(tl, 3)
    _, inv, cnt = np.unique(e, axis=0, return_inverse=True, return_counts=True)
    return set(np.unique(owner[cnt[inv.reshape(-1)] == 1]).tolist())


def tuck_under(pos, mask, cover_pos, cover_nrm, margin, reach=0.03, skip=None):
    """
    move the masked points to at least margin UNDER the cover's nearest vertex (skin that must not show through).
    skip: cover vertices on the cover's free edge; a point nearest to one of those is beside the cover, not under it
    """
    idx = np.nonzero(mask)[0]
    d = np.linalg.norm(pos[idx, None] - cover_pos[None], axis=2)
    j = d.argmin(1)
    h = ((pos[idx] - cover_pos[j]) * cover_nrm[j]).sum(1)
    sink = (h + margin).clip(0, None) * (d.min(1) < reach)
    if skip is not None:
        # nearest to an edge vertex: under the cover only if nearly straight below / above it, else beside it
        lateral = np.sqrt((d.min(1) ** 2 - h ** 2).clip(0, None))
        sink = sink * (~skip[j] | ((lateral < 0.012) & (h < 0.015)))
    pos[idx] -= sink[:, None] * cover_nrm[j]
    return int((sink > 0).sum())


VG_SWAP = [(40, 39), (38, 37), (86, 63), (14, 13), (27, 26), (87, 64), (36, 35), (88, 65), (68, 45), (85, 62), (89, 66),
           (20, 19), (34, 33), (69, 46), (0, 2), (1, 3), (4, 5), (6, 7), (9, 10), (11, 12), (15, 16), (17, 18),
           (24, 25), (28, 29), (30, 31)] + [(70 + i, 47 + i) for i in range(15)]


def mirror_mesh(m):
    """mirror a Mesh across x = 0 in place: positions, normals, tangents, winding, and left / right vertex groups"""
    lut = np.arange(G)
    for a, b in VG_SWAP:
        lut[a], lut[b] = b, a
    for arr in (m.pos, m.nrm, m.tan):
        arr[:, 0] *= -1
    m.vg = np.where(m.w > 0, lut[m.vg], 0).astype(np.int32)
    m.comps = {k: v[:, ::-1].copy() for k, v in m.comps.items()}
    return m


def make_throat_patch(neck_part, suv):
    """
    HER MODEL HAS NO SKIN UNDER HER CHOKER: between the bottom of her neck's skin and the top of her chest's there
    is a band-shaped hole across the base of her throat, which her choker covered. With the choker gone one looked
    through it at the inside of the top's back (the "gold / black band" of every game audit). This makes the
    missing skin: a strip on her skin's own outline (radius per height and angle round her neck's axis, the hole
    bridged by interpolation), 2 mm under it so her own skin covers its edges, with her neck's weights.
    """
    ax, az = 0.0, 0.015
    ys = np.arange(1.405, 1.512, 0.0075)
    th = np.radians(np.linspace(-85, 85, 35))
    R = ops.radial_envelope(neck_part["pos"].astype(np.float64), neck_part["tris"], ax, az, ys, th)
    holes = int(np.isnan(R).sum())
    for j in range(R.shape[1]):                       # bridge each angle's gap along the height
        col = R[:, j]
        ok = ~np.isnan(col)
        if ok.sum() >= 2:
            R[:, j] = np.interp(ys, ys[ok], col[ok])
    for i in range(R.shape[0]):                       # and what is still missing, along the angle
        row = R[i]
        ok = ~np.isnan(row)
        R[i] = np.interp(th, th[ok], row[ok]) if ok.any() else 0.045
    k = np.array([0.25, 0.5, 0.25])
    R = np.stack([np.convolve(np.pad(r, 1, mode="edge"), k, "valid") for r in R]) - 0.002
    P = np.stack([ax + R * np.sin(th)[None], np.repeat(ys[::-1, None], len(th), 1) * 0 + ys[:, None], az + R * np.cos(th)[None]], 2)
    pos, tris, _ = ops.grid_surface(P.astype(np.float32), (0, 0, 1, 1))
    part = ops.new_part(pos, tris, np.tile(suv, (len(pos), 1)))
    out_dir = np.stack([np.sin(th)[None].repeat(len(ys), 0).ravel(), np.zeros(len(pos)), np.cos(th)[None].repeat(len(ys), 0).ravel()], 1)
    if (part["nrm"] * out_dir).sum(1).mean() < 0:
        part["tris"] = part["tris"][:, ::-1].copy()
        part["nrm"] = ops.compute_normals(part["pos"], part["tris"])
    part["tan"] = ops.compute_tangents(part["pos"], part["nrm"], part["uv"], part["tris"])
    part["w"], part["vg"] = ops.knn_weights(neck_part["pos"], neck_part["w"], neck_part["vg"], part["pos"], k=6, n_groups=G)
    log("throat: %d of %d outline samples were hole; a %d-triangle skin strip bridges it" % (holes, R.size, len(part["tris"])))
    return part


VIEW_YAWS = range(0, 360, 45)
VIEW_PITCHES = (0, 25, -20)


def seen_sides(pos, tris, size=480):
    """
    per triangle, how many pixels of it a viewer outside her sees from its FRONT and from its BACK, summed over
    24 views (8 yaws x 3 pitches, orthographic, z-buffered against every triangle given)
    """
    from modkit.render import view_matrix
    front = np.zeros(len(tris))
    back = np.zeros(len(tris))
    for yaw in VIEW_YAWS:
        for pitch in VIEW_PITCHES:
            R = view_matrix(yaw, pitch)
            vp = pos @ R.T
            mn, mx = vp[:, :2].min(0), vp[:, :2].max(0)
            sc = (size - 8) / max(mx - mn)
            sx = (vp[:, 0] - mn[0]) * sc + 4
            sy = size - ((vp[:, 1] - mn[1]) * sc + 4)
            zb = np.full((size, size), -1e9)
            idb = np.full((size, size), -1)
            bk = np.zeros((size, size), bool)
            for ti, (a, b, c) in enumerate(tris):
                ax, ay, bx, by, cx, cy = sx[a], sy[a], sx[b], sy[b], sx[c], sy[c]
                area = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)
                if area == 0:
                    continue
                x0, x1 = max(int(min(ax, bx, cx)), 0), min(int(max(ax, bx, cx)) + 1, size - 1)
                y0, y1 = max(int(min(ay, by, cy)), 0), min(int(max(ay, by, cy)) + 1, size - 1)
                if x0 > x1 or y0 > y1:
                    continue
                X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
                w0 = ((bx - X) * (cy - Y) - (cx - X) * (by - Y)) / area
                w1 = ((cx - X) * (ay - Y) - (ax - X) * (cy - Y)) / area
                w2 = 1 - w0 - w1
                msk = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
                z = w0 * vp[a, 2] + w1 * vp[b, 2] + w2 * vp[c, 2]
                sub = zb[y0:y1 + 1, x0:x1 + 1]
                msk &= z > sub
                sub[msk] = z[msk]
                idb[y0:y1 + 1, x0:x1 + 1][msk] = ti
                bk[y0:y1 + 1, x0:x1 + 1][msk] = area > 0      # screen y is flipped: positive area = back face
            ok = idb >= 0
            np.add.at(front, idb[ok & ~bk], 1)
            np.add.at(back, idb[ok & bk], 1)
    return front, back


def face_the_viewer(mesh, first_dress):
    """
    THIS GAME SHADES A BACK FACE BLACK (or gold, by the light); his drew both sides. Every outfit triangle that
    viewers outside her see mostly from its back is turned round, with the normals of vertices that mostly belong
    to turned triangles. Measured, not guessed: two rules by direction (from her body's axis; from each holster
    plate's middle) turned 22 islands for no change and 791 triangles for worse (2026-11-18).
    """
    allt = np.concatenate([mesh.comps[c] for c in COMPS]).astype(np.int64)
    front, back = seen_sides(mesh.pos.astype(np.float64), allt)
    dsel = np.arange(len(allt)) >= first_dress
    turn = dsel & (back > 2 * front) & (back >= 3)
    both = dsel & (back >= 3) & (front >= 3) & ~turn
    dt = mesh.comps["Dress"].astype(np.int64)
    k = turn[first_dress:]
    dt[k] = dt[k][:, ::-1]
    mesh.comps["Dress"] = dt.astype(np.uint32)
    cnt_t = np.zeros(mesh.n)
    cnt_a = np.zeros(mesh.n)
    np.add.at(cnt_t, dt[k].reshape(-1), 1)
    np.add.at(cnt_a, dt.reshape(-1), 1)
    fv = (cnt_t > 0) & (cnt_t >= 0.5 * cnt_a)
    mesh.nrm[fv] *= -1
    log("faces turned to the viewer: %d triangles (%.0f back-face px before), %d vertex normals; %d triangles are seen "
        "from both sides (%.0f px of back)" % (k.sum(), back[turn].sum(), fv.sum(), both.sum(), back[both].sum()))
    return mesh


def build(out=OUT):
    # THE GAME IS LEFT-HANDED: +x is HER RIGHT (game audit 5: the sleeve, on Cloud's left arm, was on her right arm
    # in every game shot; modkit's renderer shows +x at screen right from the front, as a right-handed viewer
    # would, so no offline sheet showed it). His .fbx is right-handed (his left arm at +x). The recipe below was
    # written with "+x = her left" throughout. So: she is mirrored on the way in, everything is built in that
    # mirrored world unchanged, and the finished mesh is mirrored back on the way out. Her own pieces come out
    # exactly as they went in; his outfit comes out on the correct side.
    mav, cloud = load_mavuika(), load_cloud()
    mirror_mesh(mav)
    mav.dense = ops.dense_weights(mav.w, mav.vg, G)
    mav.dom = mav.dense.argmax(1)
    rt = Retarget(cloud, mav)
    body, skin = cloud["body_geo"], cloud["skin_geo"]

    # ---- which of Cloud's pieces are worn
    lab, tl, info = island_info(body, cloud)
    drop, role = set(), {}
    for i in info:
        if i["dom"] in ("head",) or (i["diag"] < 0.035 and i["tris"] > 400):
            drop.add(i["id"])                       # his earring; finger rings collapsed to a point
        elif i["dom"].endswith("_hand") or "_hand_" in i["dom"]:
            drop.add(i["id"])                       # his gloved hands: she keeps her own gloved hands
    big = sorted((i for i in info if i["id"] not in drop), key=lambda i: -i["tris"])
    role["pants"] = big[0]["id"]
    role["top"] = max((i for i in big if i["dom"].startswith("spine") and i["hi"][1] > 1.55), key=lambda i: i["tris"])["id"]
    role["coat"] = max((i for i in big if i["hi"][1] - i["lo"][1] > 0.9 and i["id"] != role["pants"]), key=lambda i: i["tris"])["id"]
    role["sleeve"] = max((i for i in big if i["dom"].startswith("sub_left_arm") or i["dom"] == "left_forearm"), key=lambda i: i["tris"])["id"]
    role["warmer"] = max((i for i in big if "right_forearm" in i["dom"]), key=lambda i: i["tris"])["id"]
    role["pauldron"] = max((i for i in big if "armor" in i["dom"]), key=lambda i: i["diag"])["id"]     # the leather cap, not the emblem (more triangles)
    for i in big:
        log("   piece %3d: %4d tris, %-24s y %.2f .. %.2f, x %.2f .. %.2f" % (i["id"], i["tris"], i["dom"], i["lo"][1], i["hi"][1], i["lo"][0], i["hi"][0]))
    log("Cloud's pieces: %d kept, %d dropped; roles %s" % (len(info) - len(drop), len(drop), role))
    keep_t = ~np.isin(tl, list(drop))
    # his bell sleeve's mouth is closed by a lining disc with the hand through it. With her arm bent it showed as
    # a lid as wide as her torso with her hand lying on it (game audit). Faces across the forearm's axis near the
    # cuff go; the bell is an open tube with an inner copy.
    H = {b: cloud["head"][i] for i, b in enumerate(cloud["bones"])}
    fa = H["left_hand"] - H["left_forearm"]
    fl = np.linalg.norm(fa)
    fa = fa / fl
    tp = body["pos"][body["tris"]]
    fn = np.cross(tp[:, 1] - tp[:, 0], tp[:, 2] - tp[:, 0])
    fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-12
    along_f = ((tp.mean(1) - H["left_forearm"]) @ fa) / fl
    lid = (tl == role["sleeve"]) & (np.abs(fn @ fa) > 0.75) & (along_f > 0.5)
    keep_t &= ~lid
    log("sleeve: %d lining-disc triangles removed from the bell's mouth" % lid.sum())

    # ---- retarget, then fit the torso
    wclass = cloud_weight_classes(cloud)
    armor = body["dense"][:, [i for i, c in enumerate(wclass) if c == "CLAVL"]].sum(1) / body["dense"].sum(1)
    bpos, bnrm, bmass = rt.apply(body, armor)
    # his small black inner collar band, at her throat: plain black in one light, flashing gold in her hair's fire
    # (taken for a pendant of her old outfit by three audits). Small pieces that end up wholly inside the collar's
    # opening are left out; her own throat shows there.
    throat = set()
    for i in info:
        if i["id"] in drop or i["tris"] > 160:
            continue
        q = bpos[lab == i["id"]]
        if (np.abs(q[:, 0]).max() < 0.075) and (q[:, 1].min() > 1.34) and (1.45 < q[:, 1].max() < 1.56) and (q[:, 2].min() > 0.0):
            throat.add(i["id"])
            log("   throat piece dropped: island %d, %d tris, y %.3f .. %.3f, z %.3f .. %.3f" % (
                i["id"], i["tris"], q[:, 1].min(), q[:, 1].max(), q[:, 2].min(), q[:, 2].max()))
    keep_t &= ~np.isin(tl, list(throat))
    spos, snrm, smass = rt.apply(skin)
    base = np.isin(tl, [role["top"], role["pants"]])
    D, Rm, Rc = torso_field(bpos, body["tris"][base], mav)
    torso_cols = [i for i, c in enumerate(wclass) if c in ("T", "SK", "CLAVL")]
    b_amt = body["dense"][:, torso_cols].sum(1) / body["dense"].sum(1)
    s_amt = skin["dense"][:, torso_cols].sum(1) / skin["dense"].sum(1)
    bpos = apply_field(bpos, D, b_amt)
    spos = apply_field(spos, D, s_amt)

    holder = body["dense"][:, [i for i, b in enumerate(cloud["bones"]) if "holder" in b]].sum(1) / body["dense"].sum(1)
    bpos[:, 0] *= 1 - holder * (1 - HOLSTER_WIDTH)

    # ---- her own pieces
    hlab = weld_islands(mav.pos, mav.comps["Head"])
    htl = hlab[mav.comps["Head"][:, 0]]
    keep_h = np.zeros(len(htl), bool)
    hand_v = np.zeros(mav.n, bool)
    for l in range(hlab.max() + 1):
        m = hlab == l
        d = np.bincount(mav.dom[m], minlength=G).argmax()
        if d in (64, 87):
            keep_h |= htl == l
            hand_v |= m
        elif d in (11, 12, 15, 16) or (d == 44 and m.sum() < 40):
            keep_h |= htl == l                      # earrings, eye pieces
    head_part = ops.part_from_mesh(mav, mav.comps["Head"][keep_h])
    lm_b = np.asarray(Image.open(os.path.join(SRC, NAME + "BodyLightMap.dds")).convert("RGBA"))
    df_b = np.asarray(Image.open(os.path.join(SRC, NAME + "BodyDiffuse.dds")).convert("RGBA"))
    px = np.clip((mav.uv * lm_b.shape[0]).astype(int), 0, lm_b.shape[0] - 1)
    is_skin = lm_b[px[:, 1], px[:, 0], 3] > 200
    bt = mav.comps["Body"]
    cen = mav.pos[bt].mean(1)
    # neck and head only, plus the strip the open zip shows. Her chest skin further out poked through the knit top
    # between its vertices (a pale notch at the armhole).
    # (y > 1.43 kept her shoulder tops too: the top was pushed off them into torn-looking tabs beside the collar)
    # The strip under the neck was 5 cm either side of her middle: narrower than the collar's opening, so beside it
    # one looked INTO the hollow top (two lobes either side of her neck, black, or gold when her lit hair was
    # behind: the "pendant" of four game audits). It is 8.5 cm either side now, front only.
    # (8.5 cm all the way down poked through the knit at the side of her chest: wide only from y 1.42 up.)
    # WHICH triangles are her skin: by ISLAND (index-connected piece of the Body draw that is mostly skin-coded), not
    # triangle by triangle. The skin under her choker is not skin-coded in the light map (the choker's shadow is
    # painted there), so "all three vertices skin-coded" left a band-shaped HOLE across the base of her throat:
    # through it the inside of the top's back showed, black or gold by the light. That was the "pendant" of every
    # game audit; the Body draw alone, back faces marked, on green, shows the hole in one render.
    from modkit.gimi import islands as _islands
    lab_i = _islands(bt, mav.n)
    ti = lab_i[bt[:, 0]]
    # (no size limit: "> 50 vertices" dropped her EARS, four pieces of 29 and 47 vertices, 2026-11-17; the
    # maintainer saw it in game)
    skin_isl = [l for l in range(lab_i.max() + 1) if (lab_i == l).any() and is_skin[lab_i == l].mean() > 0.6]
    on_skin = np.isin(ti, skin_isl)
    log("her skin: %d index-islands of the Body draw, %d triangles (%d of them not skin-coded in the light map)" % (
        len(skin_isl), on_skin.sum(), (on_skin & ~is_skin[bt].all(1)).sum()))
    keep_b = on_skin & ((cen[:, 1] > 1.47) | ((cen[:, 1] > 1.42) & (np.abs(cen[:, 0]) < 0.085) & (cen[:, 2] > 0))
                        | ((cen[:, 1] > 1.36) & (np.abs(cen[:, 0]) < 0.05)))
    neck_part = ops.part_from_mesh(mav, bt[keep_b])
    log("her own: %d head-draw triangles (hands, earrings, eyes), %d neck / head skin triangles" % (keep_h.sum(), keep_b.sum()))

    # ---- the outfit must clear what she keeps: forearms / hands under the warmer and the sleeve, neck under the collar
    hv = np.nonzero(hand_v)[0]
    fore = np.isin(np.array(XF)[bmass.argmax(1)], ["LAf", "RAf", "LH", "RH"])
    n1 = clear_over_idx(bpos, fore, mav.pos[hv], mav.nrm[hv], 0.004, reach=0.012)   # near her arm only: with 5 cm the bell sleeve was kinked
    # her forearm UNDER the warmer is sunk 6 mm along its normals (none on the hand, fading in over the wrist):
    # with her wrist bent (the bike's grips) it stood through the warmer as dark grey quads, her forearm being
    # painted in the glove's leather (game audits 8 and 9)
    wv = np.unique(body["tris"][tl == role["warmer"]])
    hw = ops.dense_weights(head_part["w"], head_part["vg"], G)
    hand_share = hw[:, VG_HAND["L"] + VG_HAND["R"]].sum(1)
    near = np.zeros(len(head_part["pos"]), bool)
    for s0 in range(0, len(head_part["pos"]), 2048):
        d = np.linalg.norm(head_part["pos"][s0:s0 + 2048, None] - bpos[wv][None], axis=2).min(1)
        near[s0:s0 + 2048] = d < 0.03
    sink = near * (1 - hand_share).clip(0, 1) * 0.006
    head_part["pos"] = (head_part["pos"] - head_part["nrm"] * sink[:, None]).astype(np.float32)
    log("forearm under the warmer: %d vertices sunk up to 6 mm" % (sink > 0.0005).sum())
    nk = neck_part["src"]
    topv = np.zeros(len(bpos), bool)
    topv[np.unique(body["tris"][tl == role["top"]])] = True
    n2 = clear_over_idx(bpos, topv, mav.pos[nk], mav.nrm[nk], 0.004, reach=0.015)
    tv = np.nonzero(topv)[0]
    # his arm's skin fits his top's armhole in HIS pose. Skin near the top goes where the top went (the nearest top
    # vertex's own move), or the two part: the skin's cap lay over the knit behind the armhole and at the bust.
    d0 = np.linalg.norm(skin["pos"][:, None] - body["pos"][tv][None], axis=2)
    j0 = d0.argmin(1)
    k0 = ((0.05 - d0.min(1)) / 0.03).clip(0, 1)[:, None]
    spos = spos * (1 - k0) + k0 * (skin["pos"] + bpos[tv][j0] - body["pos"][tv][j0])
    log("arm skin: %d of %d vertices carried with the top" % ((k0 > 0).sum(), len(spos)))
    tt = body["tris"][tl == role["top"]]
    e = np.sort(np.concatenate([tt[:, [0, 1]], tt[:, [1, 2]], tt[:, [2, 0]]]), axis=1)
    ue, cnt = np.unique(e, axis=0, return_counts=True)
    edge_v = np.zeros(len(bpos), bool)
    edge_v[ue[cnt == 1].reshape(-1)] = True
    edge_v = edge_v[tv]
    n3 = 0      # (tucking and pinning skin under the top are gone: that skin is the knit side panel now, and both
                # moves crumpled it into a frill at the armhole)
    # skin that his own top covers in his own pose (nearest top vertex is inside the cloth, not on its edge, and
    # the skin is under it) is pinned 1.2 cm under that same top vertex here. The skin mesh is coarse (3 cm
    # triangles): triangles that cross the armhole's edge then dive under it instead of lying on the knit.
    hc = ((skin["pos"] - body["pos"][tv][j0]) * body["nrm"][tv][j0]).sum(1)
    covered = (~edge_v[j0]) & (d0.min(1) < 0.04) & (hc < 0.004)
    del covered
    log("clearance: %d forearm-wear vertices and %d top vertices pushed off her skin; %d arm-skin vertices tucked under the top" % (n1, n2, n3))

    # ---- the pauldron's outer part lies ON the sleeve (6 mm off it): riding the arm's map it still stood out as a shelf
    pa = np.zeros(len(bpos), bool)
    pa[np.unique(body["tris"][tl == role["pauldron"]])] = True
    sv = np.unique(body["tris"][tl == role["sleeve"]])
    pi = np.nonzero(pa)[0]
    d = np.linalg.norm(bpos[pi, None] - bpos[sv][None], axis=2)
    nn = np.argsort(d, axis=1)[:, :4]
    ww = 1.0 / (np.take_along_axis(d, nn, 1) + 1e-3)
    ww /= ww.sum(1, keepdims=True)
    tgt = ((bpos[sv][nn] + 0.006 * bnrm[sv][nn]) * ww[:, :, None]).sum(1)
    fo = ((body["pos"][pi, 0] - 0.13) / 0.08).clip(0, 1)[:, None]
    log("pauldron: outer part moved %.1f cm on average onto the sleeve" % (100 * (np.linalg.norm(tgt - bpos[pi], axis=1) * fo[:, 0]).sum() / max(fo.sum(), 1e-9)))
    bpos[pi] = bpos[pi] * (1 - fo) + tgt * fo

    # ---- small hard pieces keep their shape: one rotation, size and shift each, fitted to where the maps took them
    nr = 0
    for i in info:
        if i["id"] in drop or i["diag"] > RIGID_DIAG:
            continue
        m = lab == i["id"]
        X, Y = body["pos"][m], bpos[m]
        xc, yc = X.mean(0), Y.mean(0)
        U, S, Vt = np.linalg.svd((X - xc).T @ (Y - yc))
        dd = np.sign(np.linalg.det(U @ Vt))
        R = (U * [1, 1, dd]) @ Vt                      # row vectors: (X - xc) @ R ~ (Y - yc)
        k = (S * [1, 1, dd]).sum() / ((X - xc) ** 2).sum()
        bpos[m] = k * (X - xc) @ R + yc
        bnrm[m] = body["nrm"][m] @ R
        nr += 1
    log("rigid pieces: %d small islands moved without distortion" % nr)

    # ---- BACK FACES SEEN FROM OUTSIDE (found 2026-11-17 by marking back faces in the game's view: magenta sat
    # exactly on the "black slits beside the zip", the collar-edge slit and the "gold / black band at her throat").
    # His knit top has faces wound toward the body: the inner collar band across the throat and the undersides of
    # the zip placket's folds. His game lights both sides; this one shades a back face black, or gold, by the
    # light. Triangles of the top above the waist whose face points toward her body's axis are turned to face out.
    tp = bpos[body["tris"]]
    c0 = tp.mean(1)
    # the top, and every small piece in the collar's opening (his inner collar band is its own island)
    tt_mask = keep_t & ((tl == role["top"]) | ((np.abs(c0[:, 0]) < 0.10) & (c0[:, 1] > 1.36) & (c0[:, 1] < 1.56) & (c0[:, 2] > 0.02)))
    fn = np.cross(tp[:, 1] - tp[:, 0], tp[:, 2] - tp[:, 0])
    fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-12
    cen_t = tp.mean(1)
    rad = np.stack([cen_t[:, 0] - AX[0], np.zeros(len(cen_t)), cen_t[:, 2] - AX[1]], 1)
    rad /= np.linalg.norm(rad, axis=1, keepdims=True) + 1e-12
    # in the collar's opening one looks from the front AND from above: there "outward" is out-and-up (his inner
    # collar band is a flat ring facing down; its upper side was the gold / black band)
    in_open = (np.abs(cen_t[:, 0]) < 0.10) & (cen_t[:, 1] > 1.40) & (cen_t[:, 1] < 1.56) & (tl != role["top"])
    out_dir = np.where(in_open[:, None], rad * 0.6 + np.array([0.0, 0.8, 0.0]), rad)
    inward = tt_mask & ((fn * out_dir).sum(1) < -0.10) & (cen_t[:, 1] > 1.20) & (cen_t[:, 2] > 0.0)
    body["tris"][inward] = body["tris"][inward][:, ::-1]
    cnt_in = np.zeros(len(bpos)); cnt_all = np.zeros(len(bpos))
    np.add.at(cnt_in, body["tris"][inward].reshape(-1), 1)
    np.add.at(cnt_all, body["tris"][tt_mask].reshape(-1), 1)
    flipv = (cnt_in > 0) & (cnt_in >= 0.5 * cnt_all)
    bnrm[flipv] *= -1
    log("top: %d inward-facing triangles at the front turned outward (%d vertex normals with them)" % (inward.sum(), flipv.sum()))

    # ---- cut-outs: his atlas is see-through (alpha < 128) at stud plates, strap holes and the zip's teeth; his game
    # cuts them away, this one draws them as solid light squares. Triangles that lie mostly on such texels go.
    alpha = np.asarray(Image.open(os.path.join(CLOUD, "tex_ch001_019_body_AAAT.tga")).convert("RGBA"))[..., 3]
    A_ = alpha.shape[0]
    uvt = body["uv"][body["tris"]]
    hits = np.zeros(len(uvt))
    for smp in [uvt.mean(1)] + [uvt[:, k] * 0.6 + uvt.mean(1) * 0.4 for k in range(3)]:
        q = np.clip((smp * A_).astype(int), 0, A_ - 1)
        hits += alpha[q[:, 1], q[:, 0]] < 128
    cut_t = hits >= 2
    keep_t &= ~cut_t
    log("cut-out triangles dropped: %d" % (cut_t & keep_t | cut_t).sum())

    # ---- weights
    src = her_sources(mav, hv)
    bw, bg = transfer_weights(bpos, body["pos"], body["dense"], cloud, mav, src)
    # ---- whatever lies ON the coat (the straps and buckles down its front, rings, the belt's lower edge) takes the
    # COAT's weights at that place: weighted from the torso while the panel under it followed her thigh, the two
    # parted in a pose and black slots and squares showed between them (the slot under the lower buckle standing,
    # squares on the panel in the bike pose; game audits 7 to 9; in the rest pose there is nothing there).
    cv = np.unique(body["tris"][tl == role["coat"]])
    # the coat's weights, smoothed over its own surface (12 rounds of averaging with welded neighbours): from
    # nearest neighbours its top had jumps of up to 2 between neighbouring vertices where pelvis, spine and both
    # thighs meet (median 0.48 per edge, the trousers 0.16), and in the bike pose those triangles folded over and
    # showed black squares on the front panel (game audit 10). Its hem keeps its own (legs) weights more.
    _, wi = np.unique(np.round(bpos[cv] / 1e-4).astype(np.int64), axis=0, return_inverse=True)
    wi = wi.reshape(-1)
    loc = np.full(len(bpos), -1)
    loc[cv] = np.arange(len(cv))
    ct = loc[body["tris"][tl == role["coat"]]]
    e = np.concatenate([ct[:, [0, 1]], ct[:, [1, 2]], ct[:, [2, 0]]])
    e = wi[e]
    dn = ops.dense_weights(bw[cv], bg[cv], G).astype(np.float64)
    nw = int(wi.max()) + 1
    acc0 = np.zeros((nw, G))
    np.add.at(acc0, wi, dn)
    acc0 /= np.bincount(wi, minlength=nw)[:, None]
    keep_share = ((1.0 - bpos[cv][:, 1]) / 0.4).clip(0, 1)            # 0 at the waist .. 1 from 0.6 m down
    ks = np.zeros(nw)
    np.maximum.at(ks, wi, keep_share)
    cur = acc0.copy()
    deg = np.bincount(np.concatenate([e[:, 0], e[:, 1]]), minlength=nw)[:, None] + 1e-9
    for _ in range(12):
        nb = np.zeros_like(cur)
        np.add.at(nb, e[:, 0], cur[e[:, 1]])
        np.add.at(nb, e[:, 1], cur[e[:, 0]])
        cur = 0.5 * cur + 0.5 * nb / deg
        cur = cur * (1 - ks[:, None]) + acc0 * ks[:, None]
    sw, sg = ops.top4(cur[wi].astype(np.float32))
    jb = lambda W_: np.maximum.reduce([np.abs(W_[ct[:, a]] - W_[ct[:, b]]).sum(1) for a, b in ((0, 1), (1, 2), (2, 0))])
    before = jb(dn)
    bw[cv], bg[cv] = sw, sg
    after = jb(ops.dense_weights(sw, sg, G))
    log("coat weights smoothed: jump per edge median %.2f -> %.2f, triangles over 1.2: %d -> %d" % (
        np.median(before), np.median(after), (before > 1.2).sum(), (after > 1.2).sum()))
    not_on = np.zeros(len(bpos), bool)
    for k_ in ("coat", "pants", "sleeve", "warmer", "top"):
        not_on[np.unique(body["tris"][tl == role[k_]])] = True
    cand = np.nonzero(~not_on & (bpos[:, 1] < 1.15))[0]
    on_coat = []
    for s0 in range(0, len(cand), 2048):
        d = np.linalg.norm(bpos[cand[s0:s0 + 2048], None] - bpos[cv][None], axis=2).min(1)
        on_coat.append(cand[s0:s0 + 2048][d < 0.015])
    on_coat = np.concatenate(on_coat) if on_coat else np.zeros(0, int)
    if len(on_coat):
        cw, cg = ops.knn_weights(bpos[cv].astype(np.float32), bw[cv], bg[cv], bpos[on_coat].astype(np.float32), k=4, n_groups=G)
        bw[on_coat], bg[on_coat] = cw, cg
    log("on the coat: %d vertices of straps / buckles take the coat's weights" % len(on_coat))
    sw, sg = transfer_weights(spos, skin["pos"], skin["dense"], cloud, mav, src)

    # ---- parts
    # THE GAME DRAWS BACK FACES, BLACK (game audit, 2026-11-15). An inner copy 0.5 mm under EVERY open piece fought
    # its original for depth: trouser legs, sleeve and knit broke into black and grey shards. Inner copies now go
    # only where an inside is really looked into (coat, bell sleeve, warmer, the collar, the holster's open panels),
    # 1.5 mm under along SMOOTHED normals (along the split normals a copy crosses its original at every hard edge).
    opened = {role["coat"], role["sleeve"], role["warmer"]}
    opened |= {i["id"] for i in info if "holder" in i["dom"]} & (open_islands(body, lab, tl) - drop)   # holster panels: their backs show from her side
    collar = (tl == role["top"]) & (bpos[body["tris"]][:, :, 1].min(1) > 1.44)
    holster = np.isin(tl, list(opened - {role["coat"], role["sleeve"], role["warmer"]}))
    pieces = {"coat": tl == role["coat"], "sleeve": tl == role["sleeve"], "warmer": tl == role["warmer"],
              "collar": collar, "holster": holster}
    two_sided = np.zeros(len(tl), bool)
    for m_ in pieces.values():
        two_sided |= m_
    outfit = [cloud_part(body, bpos, bnrm, keep_t & ~two_sided, bw, bg)]
    for k_, m_ in pieces.items():
        p = cloud_part(body, bpos, bnrm, keep_t & m_, bw, bg)
        outfit.append(p)
        if INNER[k_] != "none":
            outfit.append(twin(p, keep_normals=INNER[k_] == "keep"))
    log("inner copies: %s" % INNER)
    slab, stl, sinfo = island_info(skin, cloud)
    arm = max((i for i in sinfo if "right_arm" in i["dom"]), key=lambda i: i["tris"])["id"]
    suv = skin_texel(mav, lm_b, df_b, neck_part["src"])
    arm_part = cloud_part(skin, spos, snrm, stl == arm, sw, sg, uv=suv)
    # THE ARMHOLE. His top's armhole is cut for his arm, raised 43 degrees; on her lowered arm it gapes down the
    # side of her bust, and the coarse skin under it drew its edge as angles. The skin mesh is cut by a plane
    # across her arm at the shoulder joint: outside it stays bare arm, inside it becomes knit (a side panel in
    # the Dress draw), so the armhole is a clean ring round her arm.
    sh = SH_M * [-1, 1, 1]
    ax = (EL_M - SH_M) * [-1, 1, 1]
    ax = ax / np.linalg.norm(ax)
    def along(q):
        # bare arm = past the plane AND within the arm's own thickness of its axis (her flank under the armpit is
        # past the plane too, and stayed bare as an angular patch)
        t = (q - sh) @ ax
        r = np.linalg.norm((q - sh) - t[:, None] * ax, axis=1)
        return np.minimum(t - ARMHOLE_T, ARMHOLE_R - r)
    panel = ops.clip_part(arm_part, lambda q: -along(q))
    arm_part = ops.clip_part(arm_part, along)
    # 3 mm under where it was, easing to nothing at the cut: under the real top it hides (two knit surfaces at
    # one depth would flicker), in the armhole it shows
    panel["pos"] = (panel["pos"] - panel["nrm"] * (0.003 * (-along(panel["pos"]) / 0.02).clip(0, 1))[:, None]).astype(np.float32)
    # ribs run down the flank and on outward over the shoulder's top (v follows height, then distance outward)
    pv = (panel["pos"][:, 1] - 1.33) + (panel["pos"][:, 0] + 0.10)
    panel["uv"] = np.stack([0.56 + 0.5 * panel["pos"][:, 2], 0.70 - 0.5 * pv], 1).astype(np.float32)
    panel["uv2"] = panel["uv"].copy()
    panel["tan"] = ops.compute_tangents(panel["pos"], panel["nrm"], panel["uv"], panel["tris"])
    outfit.append(panel)
    log("armhole: %d skin triangles stay bare arm, %d became the top's side panel" % (len(arm_part["tris"]), len(panel["tris"])))
    log("skin texel for the bare arm: uv %s" % suv.round(4))

    # the strip of her chest the zip's V shows still carried her pendant's paint (five offline epochs and the game
    # all saw it): everything of the kept skin below the neck's base reads the plain skin texel
    sunk = neck_part["pos"][:, 1] < 1.47
    neck_part["pos"][sunk] -= 0.005 * neck_part["nrm"][sunk]
    low_skin = neck_part["pos"][:, 1] < 1.515
    neck_part["uv"][low_skin] = suv
    throat_part = make_throat_patch(neck_part, suv)
    mesh = ops.assemble({"Head": head_part, "Body": [neck_part, arm_part, throat_part], "Dress": outfit})
    # vertex colour alpha is the outline's width. Full width (128) on thin layered pieces pushed black outline
    # shells through the layer above them (small black squares on the coat); round the collar's opening the far
    # side's shell showed as black triangles beside her face. The outfit gets a thinner line, the collar none.
    mesh.col[:] = (255, 128, 128, OUTLINE_A)
    dn = len(head_part["pos"]) + len(neck_part["pos"]) + len(arm_part["pos"])
    collar_v = np.zeros(mesh.n, bool)
    collar_v[dn:] = mesh.pos[dn:, 1] > 1.43
    collar_v &= (np.abs(mesh.pos[:, 0]) < 0.085) & (mesh.pos[:, 2] > -0.02)
    mesh.col[collar_v, 3] = 0
    hn = len(head_part["pos"]) + len(neck_part["pos"])
    mesh.col[:hn] = np.concatenate([head_part["col"], neck_part["col"]])
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        if os.path.isfile(os.path.join(out, f)):
            os.remove(os.path.join(out, f))
    face_the_viewer(mesh, len(mesh.comps["Head"]) + len(mesh.comps["Body"]))
    mirror_mesh(mesh)                       # back to the game's handedness
    mesh.save(out, NAME, tex_stride=12)
    dif, tex = make_textures(out, head_part, neck_part)
    mesh.tex = tex
    write_ini(out, mesh.n)
    wsum = mesh.w.sum(1)
    log("built %s: %d vertices; triangles %s; weight sums %.4f .. %.4f" % (
        out, mesh.n, {c: len(t) for c, t in mesh.comps.items()}, wsum.min(), wsum.max()))
    return mesh, mav, dif, dict(D=D, Rm=Rm, Rc=Rc)


def clear_over_idx(pos, mask, body_pos, body_nrm, margin, reach=0.05):
    idx = np.nonzero(mask)[0]
    sub = pos[idx].copy()
    n = clear_over(sub, body_pos.astype(np.float64), body_nrm.astype(np.float64), margin, reach)
    pos[idx] = sub
    return n


# ------------------------------------------------------------------------------------------------ looking

def _tex(path):
    return np.asarray(Image.open(path).convert("RGBA"), np.float32) / 255


def scene(mesh, dif, hair=True):
    """the built mod plus the game's own hair, as render() inputs"""
    pos, nrm, uv = [mesh.pos], [mesh.nrm], [mesh.uv]
    tris = [mesh.comps[c] for c in COMPS]
    tex = [mesh.tex["Head"].astype(np.float32) / 255, mesh.tex["Body"].astype(np.float32) / 255, dif.astype(np.float32) / 255]
    if hair:
        hp = np.fromfile(os.path.join(SRC, "MavuikaHairPosition.buf"), POS_DTYPE)
        ht = np.fromfile(os.path.join(SRC, "MavuikaHairTexcoord.buf"), TEX12_DTYPE)
        pos.append(hp["pos"]); nrm.append(hp["nrm"]); uv.append(ht["uv"])
        tris.append(np.fromfile(os.path.join(SRC, "MavuikaHairHead.ib"), "<u4").reshape(-1, 3) + mesh.n)
        tex.append(_tex(os.path.join(SRC, "MavuikaHairHeadDiffuse.dds")))
    return np.concatenate(pos), np.concatenate(nrm), np.concatenate(uv), tris, tex


def reference(yaws, size, bounds=None, ssaa=1):
    """Cloud's own model (outfit and bare skin, no head) from the same sides"""
    cloud = load_cloud()
    b, s = cloud["body_geo"], cloud["skin_geo"]
    pos = np.concatenate([b["pos"], s["pos"]]).astype(np.float32)
    nrm = np.concatenate([b["nrm"], s["nrm"]]).astype(np.float32)
    uv = np.concatenate([b["uv"], s["uv"]])
    t = _tex(os.path.join(CLOUD, "tex_ch001_019_body_AAAT.tga"))
    return [render(pos, nrm, [b["tris"], s["tris"] + len(b["pos"])], size=size, yaw=y, uv=uv, textures=[t, t],
                   cull=False, bounds=bounds, ssaa=ssaa) for y in yaws]


def grender(*a, yaw=0, **k):
    """render as the GAME shows it (left-handed: +x is her right): the view from the mirrored side, mirrored"""
    from PIL import ImageOps
    return ImageOps.mirror(render(*a, yaw=(360 - yaw) % 360, **k))


def preview(mesh, dif, path):
    yaws = (0, 45, 90, 180, 270, 315)
    P, N, U, T, X = scene(mesh, dif, hair=True)
    full = [grender(P, N, T, size=(420, 860), yaw=y, uv=U, textures=X, cull=False, bounds=(-0.62, 0.62, -0.08, 1.9)) for y in yaws]
    P, N, U, T, X = scene(mesh, dif, hair=False)
    bare = [grender(P, N, T, size=(420, 860), yaw=y, uv=U, textures=X, cull=False, bounds=(-0.62, 0.62, -0.08, 1.9)) for y in yaws]
    ref = reference(yaws, (420, 860), bounds=(-0.70, 0.70, -0.08, 1.9))
    refdir = os.path.join(REPO, "Images", "GI", "Mavuika", "MavuikaCloudyWolf")
    os.makedirs(refdir, exist_ok=True)
    sheet(ref, labels=[f"Ever Crisis model {y}" for y in yaws]).save(os.path.join(refdir, "Reference_EverCrisisModel.png"))
    sheet(ref + bare + full, cols=len(yaws),
          labels=[f"Cloud (reference) {y}" for y in yaws] + [f"mod, hair hidden {y}" for y in yaws] + [f"mod {y}" for y in yaws]).save(path)
    GREEN = (0, 170, 0)     # close-ups hide back faces, as a culling shader would: a hole shows green
    top = [grender(P, N, T, size=(640, 640), yaw=y, uv=U, textures=X, cull=True, bg=GREEN, bounds=(-0.42, 0.42, 0.95, 1.68), ssaa=2)
           for y in (0, 90, 180, 270)]
    rtop = reference((0, 90, 180, 270), (640, 640), bounds=(-0.45, 0.45, 1.0, 1.75), ssaa=2)
    sheet(rtop + top, cols=4).save(path.replace(".png", "_top.png"))
    legs = [grender(P, N, T, size=(520, 800), yaw=y, uv=U, textures=X, cull=True, bg=GREEN, bounds=(-0.45, 0.45, -0.08, 1.15), ssaa=2)
            for y in (0, 90, 180, 270)]
    rlegs = reference((0, 90, 180, 270), (520, 800), bounds=(-0.45, 0.45, -0.05, 1.2), ssaa=2)
    sheet(rlegs + legs, cols=4).save(path.replace(".png", "_legs.png"))
    pal = np.random.RandomState(3).rand(G, 3) * 0.8 + 0.2
    col = (pal[mesh.vg] * mesh.w[:, :, None]).sum(1)
    wv = [grender(mesh.pos, mesh.nrm, [np.concatenate([mesh.comps[c] for c in COMPS])], size=(520, 900), yaw=y,
                 colors=[col], cull=False) for y in (0, 90, 180, 270)]
    sheet(wv, labels=["blend weights by group colour", 90, 180, 270]).save(path.replace(".png", "_weights.png"))
    log("preview:", path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--preview")
    a = ap.parse_args()
    mesh, mav, dif, dbg = build(a.out)
    if a.preview:
        preview(mesh, dif, a.preview)
