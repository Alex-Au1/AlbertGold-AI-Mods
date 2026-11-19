"""
Run INSIDE Blender (no window):  blender --background --factory-startup --python fbx_dump.py -- <in.fbx> <out.npz>

Reads an .fbx, .dae, .obj or .blend (any model that is NOT a 3DMigoto dump) and writes it as plain arrays in the mod's coordinates
(Y up, front +Z, the FBX's own unit scale applied by Blender's importer):

    names                       mesh object names, in order
    <i>_pos (n, 3) _nrm (n, 3) _uv (n, 2) _tris (m, 3)    one vertex per (vertex, uv, normal) corner, v flipped
    <i>_mat (m,)                material slot per triangle;  <i>_mats  slot names
    <i>_w (n, 4) _vg (n, 4)     heaviest four bone weights (indices into ``bones``)
    bones, bone_parent, bone_head (b, 3), bone_tail (b, 3)   the armature's rest pose
"""
import sys

import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
ext = argv[0].lower().rsplit(".", 1)[-1]
if ext == "blend":                      # a .blend is opened as it is
    bpy.ops.wm.open_mainfile(filepath=argv[0])
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if ext == "dae":
        bpy.ops.wm.collada_import(filepath=argv[0])
    elif ext == "obj":
        bpy.ops.wm.obj_import(filepath=argv[0], forward_axis="NEGATIVE_Z", up_axis="Y")
    else:
        bpy.ops.import_scene.fbx(filepath=argv[0])


def from_b(p):          # Blender's Z-up to the mod's Y-up (a rotation)
    p = np.asarray(p, np.float64).reshape(-1, 3)
    return np.stack([p[:, 0], p[:, 2], -p[:, 1]], 1)


out = {}
arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
bones = []
if arm:
    bones = [b.name for b in arm.data.bones]
    mw = np.array(arm.matrix_world)
    tr = lambda v: from_b((mw @ np.array([*v, 1.0]))[:3])[0]
    out["bones"] = np.array(bones)
    out["bone_parent"] = np.array([bones.index(b.parent.name) if b.parent else -1 for b in arm.data.bones])
    out["bone_head"] = np.array([tr(b.head_local) for b in arm.data.bones])
    out["bone_tail"] = np.array([tr(b.tail_local) for b in arm.data.bones])
    print("fbx_dump: armature", arm.name, len(bones), "bones")
bidx = {b: i for i, b in enumerate(bones)}

names = []
for ob in bpy.data.objects:
    if ob.type != "MESH":
        continue
    me = ob.data
    me.calc_loop_triangles()
    if hasattr(me, "calc_normals_split"):
        me.calc_normals_split()
    i = len(names)
    names.append(ob.name)
    mw = np.array(ob.matrix_world)
    co = np.array([v.co[:] for v in me.vertices])
    co = (np.c_[co, np.ones(len(co))] @ mw.T)[:, :3]
    nm3 = np.linalg.inv(mw[:3, :3]).T
    uvl = me.uv_layers.active
    lv = np.array([l.vertex_index for l in me.loops])
    ln = np.array([l.normal[:] for l in me.loops]) @ nm3.T
    luv = np.array([d.uv[:] for d in uvl.data]) if uvl else np.zeros((len(lv), 2))
    key = np.c_[lv, np.round(luv, 5), np.round(ln, 3)]
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.reshape(-1)
    tl = np.array([t.loops[:] for t in me.loop_triangles])
    out[f"{i}_pos"] = from_b(co[lv[first]]).astype(np.float32)
    n = from_b(ln[first])
    out[f"{i}_nrm"] = (n / (np.linalg.norm(n, axis=1, keepdims=True) + 1e-12)).astype(np.float32)
    uv = luv[first].copy()
    uv[:, 1] = 1 - uv[:, 1]
    out[f"{i}_uv"] = uv.astype(np.float32)
    out[f"{i}_tris"] = inv[tl]
    out[f"{i}_mat"] = np.array([t.material_index for t in me.loop_triangles])
    out[f"{i}_mats"] = np.array([s.material.name if s.material else "" for s in ob.material_slots] or [""])
    texs = []                           # first image texture each slot's node tree uses, if any
    for s in ob.material_slots:
        img = ""
        if s.material and s.material.use_nodes:
            for nd in s.material.node_tree.nodes:
                if nd.type == "TEX_IMAGE" and nd.image:
                    img = bpy.path.abspath(nd.image.filepath)
                    break
        texs.append(img)
    out[f"{i}_texs"] = np.array(texs or [""])
    cols = []                           # each slot's base colour (Principled BSDF, else the viewport colour), linear
    for s in ob.material_slots:
        c = [0.8, 0.8, 0.8, 1.0]
        m = s.material
        if m is not None:
            c = list(m.diffuse_color)
            if m.use_nodes:
                for nd in m.node_tree.nodes:
                    if nd.type == "BSDF_PRINCIPLED":
                        c = list(nd.inputs["Base Color"].default_value)
                        break
        cols.append(c)
    out[f"{i}_matcol"] = np.array(cols or [[0.8, 0.8, 0.8, 1.0]], np.float32)
    gname = {g.index: g.name for g in ob.vertex_groups}
    W = np.zeros((len(me.vertices), 4), np.float32)
    G = np.zeros((len(me.vertices), 4), np.int32)
    for v in me.vertices:
        gs = sorted(((g.weight, bidx.get(gname[g.group], -1)) for g in v.groups), reverse=True)[:4]
        gs = [g for g in gs if g[1] >= 0 and g[0] > 0]
        s = sum(g[0] for g in gs) or 1.0
        for k, (w, b) in enumerate(gs):
            W[v.index, k], G[v.index, k] = w / s, b
    out[f"{i}_w"], out[f"{i}_vg"] = W[lv[first]], G[lv[first]]
    p = out[f"{i}_pos"]
    print("fbx_dump: mesh %s: %d verts, %d tris, mats %s, box %s .. %s" % (
        ob.name, len(p), len(tl), list(out[f"{i}_mats"]), np.round(p.min(0), 3), np.round(p.max(0), 3)))
out["names"] = np.array(names)
np.savez(argv[1], **out)
print("fbx_dump: wrote", argv[1])
