"""
Cross-check the three Fusion Sword models the maintainer gave (the textured .dae the recipe uses, the .blend, the
.obj): each dumped through headless Blender, turned so its long axis is up and its grip down, scaled to length 2.0.

    python Tools/Builders/MavuikaCloudyWolfSword/measure/three_models.py <out folder>

Needs the dumps <out>/ref_dae.npz, ref_blend.npz, ref_obj.npz (made here if missing).
"""
import sys, numpy as np
sys.path.insert(0, r"E:/Computer/Games/Genshin/Repos/Repos/AlbertGold-AI-Mods/Tools/ModKit")
sys.path.insert(0, r"E:/Computer/Games/Genshin/Repos/Repos/AlbertGold-AI-Mods/Tools/Builders/MavuikaCloudyWolfSword")
import build
from modkit.render import render, sheet, load_tex
from modkit import ops
from PIL import Image
S = sys.argv[1]
import os
sys.path.insert(0, r"E:/Computer/Games/Genshin/Repos/Repos/AlbertGold-AI-Mods/Tools/ModKit")
from modkit import blender
R = r"C:/Users/3dark/Downloads/Cloud Fusion Sword References"
for tag, f in (("dae", "fusion-swordfrom-final-fantasy/source/model/model/model.dae"), ("blend", "Cloud Strifes Fusion Sword/Cloud Strife's Fusion Sword.blend"), ("obj", "ffviiac_cloudsword/Fusion Swords_Assembled.obj")):
    if not os.path.isfile(f"{S}/ref_{tag}.npz"):
        blender.fbx_dump(os.path.join(R, f), f"{S}/ref_{tag}.npz")
T = build.REF_TEX + "/"

def load(tag):
    d = np.load(f"{S}/ref_{tag}.npz")
    P, N, U, TR, COL, TEX, off = [], [], [], [], [], [], 0
    for i, n in enumerate(d['names']):
        p = d[f'{i}_pos'].astype(float); P.append(p); N.append(d[f'{i}_nrm']); U.append(d[f'{i}_uv'])
        t = d[f'{i}_tris']; TR.append(t + off)
        mc = d[f'{i}_matcol'][:, :3] if f'{i}_matcol' in d else np.full((1, 3), 0.7)
        vc = np.zeros((len(p), 3)); mat = d[f'{i}_mat']
        for k in range(len(mc)):
            vc[np.unique(t[mat == k])] = mc[k] ** (1 / 2.2)
        COL.append(vc)
        TEX.append(str(d[f'{i}_mats'][0]))
        off += len(p)
    return np.concatenate(P), np.concatenate(N), np.concatenate(U), TR, np.concatenate(COL), TEX

out = {}
for tag in ("dae", "blend", "obj"):
    P, N, U, TR, COL, TEX = load(tag)
    allt = np.concatenate(TR)
    f = build.frame(P, allt, tag)
    B = np.stack([f["across"], f["axis"], f["thin"]], 0)       # stand up: axis -> y
    q = (P - f["grip_centre"]) @ B.T
    s = 2.0 / f["length"]
    q *= s
    q[:, 1] -= q[:, 1].min()
    n = N @ B.T
    out[tag] = (q, n, U, TR, COL, TEX, allt, f)
    print(tag, "length", round(f["length"], 3), "grip", round(f["grip"][1] - f["grip"][0], 3), "-> scaled grip", round((f["grip"][1] - f["grip"][0]) * s, 3),
          "width(prof max)", round(f["prof"].max() * s, 3), "thick", round(np.ptp(q[:, 2]), 3), "verts", len(P), "tris", len(allt))
np.save(f"{S}/three_frames.npy", np.array([0]))
ims, labels = [], []
for yaw in (0, 180, 90):
    for tag in ("dae", "blend", "obj"):
        q, n, U, TR, COL, TEX, allt, f = out[tag]
        if tag == "dae":
            texs = [np.asarray(Image.open(T + m + "_albedo.jpeg").resize((1024, 1024)), np.float32) / 255 for m in TEX]
            im = render(q, n, TR, size=(260, 900), yaw=yaw, uv=U, textures=texs, cull=False, bounds=(-0.35, 0.35, -0.05, 2.05))
        else:
            im = render(q, n, [allt], size=(260, 900), yaw=yaw, colors=[COL], cull=False, bounds=(-0.35, 0.35, -0.05, 2.05))
        ims.append(im); labels.append(f"{tag} {yaw}")
art = Image.open(r"C:/Users/3dark/Downloads/Cloud Fusion Sword References/ffviiac_cloudsword/cloud_sword.jpg").convert("RGB")
w, h = art.size
crop = art.crop((int(w * 0.83), int(h * 0.5), w, int(h * 0.97))).resize((260, 900))
ims.append(crop); labels.append("concept art (assembled)")
sheet(ims, cols=10, labels=labels).save(f"{S}/three_models.png")
