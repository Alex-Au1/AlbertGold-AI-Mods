"""
Cross-check the three Fusion Sword models the maintainer gave (the textured .dae the recipe uses, the .blend, the
.obj): each dumped through headless Blender, turned so its long axis is up and its grip down, scaled to length 2.0.

    python Tools/Builders/MavuikaCloudyWolfSword/measure/profiles.py <out folder>

Needs the dumps <out>/ref_dae.npz, ref_blend.npz, ref_obj.npz (made here if missing).
"""
import sys, numpy as np
sys.path.insert(0, r"E:/Computer/Games/Genshin/Repos/Repos/AlbertGold-AI-Mods/Tools/ModKit")
sys.path.insert(0, r"E:/Computer/Games/Genshin/Repos/Repos/AlbertGold-AI-Mods/Tools/Builders/MavuikaCloudyWolfSword")
import build
from PIL import Image, ImageDraw
S = sys.argv[1]
import os
sys.path.insert(0, r"E:/Computer/Games/Genshin/Repos/Repos/AlbertGold-AI-Mods/Tools/ModKit")
from modkit import blender
R = r"C:/Users/3dark/Downloads/Cloud Fusion Sword References"
for tag, f in (("dae", "fusion-swordfrom-final-fantasy/source/model/model/model.dae"), ("blend", "Cloud Strifes Fusion Sword/Cloud Strife's Fusion Sword.blend"), ("obj", "ffviiac_cloudsword/Fusion Swords_Assembled.obj")):
    if not os.path.isfile(f"{S}/ref_{tag}.npz"):
        blender.fbx_dump(os.path.join(R, f), f"{S}/ref_{tag}.npz")
res = {}
MOD = r"E:/Computer/Games/Genshin/Repos/Repos/AlbertGold-AI-Mods/Mods/GI/Mavuika/MavuikaCloudyWolf/Sword/"
for tag in ("dae", "blend", "obj", "MOD"):
    if tag == "MOD":                     # the built mod itself, read back from its buffers
        r = np.fromfile(MOD + "AThousandBlazingSuns.buf", np.uint8).reshape(-1, 28)
        P = r[:, 0:8].copy().view(np.float16).astype(float)[:, :3]
        T = np.fromfile(MOD + "AThousandBlazingSunsHead.ib", "<u4").reshape(-1, 3).astype(np.int64)
    else:
        d = np.load(f"{S}/ref_{tag}.npz")
        P, TR, off = [], [], 0
        for i in range(len(d['names'])):
            P.append(d[f'{i}_pos'].astype(float)); TR.append(d[f'{i}_tris'] + off); off += len(P[-1])
        P = np.concatenate(P); T = np.concatenate(TR)
    f = build.frame(P, T, tag)
    Q = build.surface_points(P, T)
    t = (Q - f["grip_centre"]) @ f["axis"]; a = (Q - f["grip_centre"]) @ f["across"]; th = (Q - f["grip_centre"]) @ f["thin"]
    if tag == "MOD":
        # the mod's grip is stretched to the game's two-hand span, so its own length is not the models' scale: put its
        # GUARD where the .dae's is and scale guard-to-tip to the .dae's (the blade keeps the model's own size)
        t0 = (f["guard"] - f["grip_centre"] @ f["axis"])
        s = (2.0 - dae_guard) / (t.max() - t0)
        t = dae_guard + (t - t0) * s; a *= s; th *= s
    else:
        s = 2.0 / f["length"]; t = (t - t.min()) * s; a *= s; th *= s
    # one left/right for all: the clipped tip's HIGH corner on +across (PCA's sign is arbitrary, so the obj and the
    # mod had been drawn mirrored, read by a reviewer as "the mod follows the obj")
    top = t > np.percentile(t, 99)
    if np.mean(a[top]) < 0:
        a = -a
    bins = np.linspace(0, 2, 81); i = np.clip(np.digitize(t, bins) - 1, 0, 79)
    lo = np.full(80, np.nan); hi = np.full(80, np.nan); tk = np.full(80, np.nan)
    for k in range(80):
        m = i == k
        if m.sum() > 5:
            lo[k], hi[k], tk[k] = a[m].min(), a[m].max(), np.ptp(th[m])
    res[tag] = (lo, hi, tk, (f["guard"] - (f["grip_centre"] @ f["axis"]) - (t.min() / s if False else 0)))
    g0 = (f["guard"] - f["butt"]) * s if tag != "MOD" else dae_guard
    if tag == "dae":
        dae_guard = g0
    print(f"{tag}: guard at {g0:.3f} of 2.0; blade root width {np.nanmax(hi[int(g0*40)+3:int(g0*40)+12]-lo[int(g0*40)+3:int(g0*40)+12]):.3f}; "
          f"mid-blade width {np.nanmedian((hi-lo)[40:55]):.3f}; mid thickness {np.nanmedian(tk[40:55]):.3f}; guard thickness {np.nanmax(tk[int(g0*40):int(g0*40)+3]):.3f}")
W, H = 600, 1000
im = Image.new("RGB", (W * 2, H), (30, 30, 34)); d = ImageDraw.Draw(im)
cols = {"dae": (255, 80, 80), "blend": (80, 255, 80), "obj": (90, 140, 255), "MOD": (255, 255, 255)}
for tag, (lo, hi, tk, _) in res.items():
    ys = H - 20 - (np.arange(80) + 0.5) / 80 * 2 * 470
    for arr, x0, sc in ((lo, W / 2, 900), (hi, W / 2, 900), (tk / 2, W * 1.5, 2500), (-tk / 2, W * 1.5, 2500)):
        pts = [(x0 + v * sc, y) for v, y in zip(arr, ys) if not np.isnan(v)]
        d.line(pts, fill=cols[tag], width=3 if tag == "MOD" else 2)
    d.text((10, 10 + 14 * list(cols).index(tag)), tag, fill=cols[tag])
d.text((W + 10, 10), "thickness (x2.8 scale)", fill=(255, 255, 255))
im.save(f"{S}/profiles.png")
