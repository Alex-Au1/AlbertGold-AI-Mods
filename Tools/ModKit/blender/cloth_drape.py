"""
Run INSIDE Blender (no window):  blender --background --python cloth_drape.py -- <in.npz> <out.npy>

Lets one piece of cloth settle on colliders under gravity and writes its vertex positions back. Topology is
untouched: vertex i in is vertex i out, so the caller keeps its own triangles, UVs and blend weights.

in.npz (the mod's coordinates: metres, Y up, front +Z):
    pos (n, 3), tris (m, 3)      the cloth, welded (no duplicate vertices)
    pin (n,)                     0 = free ... 1 = held where it is
    col_pos_<i>, col_tris_<i>    the colliders
    params                       [frames, grow, collision distance, bending stiffness, quality]
                                 grow: how much bigger than its starting shape the cloth is cut (0.04 = 4 %)
"""
import sys

import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
d = np.load(argv[0])
frames, grow, dist, bend, quality = [float(v) for v in d["params"]]


def to_b(p):       # the mod's Y-up to Blender's Z-up (a rotation: winding is kept)
    return np.stack([p[:, 0], -p[:, 2], p[:, 1]], 1)


def from_b(p):
    return np.stack([p[:, 0], p[:, 2], -p[:, 1]], 1)


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def add_mesh(name, pos, tris):
    me = bpy.data.meshes.new(name)
    me.from_pydata(to_b(pos.astype(np.float64)).tolist(), [], tris.astype(int).tolist())
    me.update()
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob


i = 0
while f"col_pos_{i}" in d:
    c = add_mesh(f"collider{i}", d[f"col_pos_{i}"], d[f"col_tris_{i}"])
    c.modifiers.new("collision", "COLLISION")
    c.collision.use = True          # modifiers.new() does not switch it on (bpy.ops.object.modifier_add does)
    print("collider", i, "collision.use =", c.collision.use)
    c.collision.thickness_outer = dist
    c.collision.thickness_inner = 0.01
    c.collision.cloth_friction = 8.0
    c.collision.damping = 0.5
    i += 1

cloth = add_mesh("cloth", d["pos"], d["tris"])
vg = cloth.vertex_groups.new(name="pin")
for vi, w in enumerate(d["pin"]):
    if w > 0.001:
        vg.add([vi], float(w), "REPLACE")
mod = cloth.modifiers.new("cloth", "CLOTH")
s = mod.settings
s.quality = int(quality)
s.mass = 0.0003                    # per vertex (kg): about 1 kg over a whole jacket. (0.02 made a 50 kg jacket that
                                   # stretched off her shoulders and through her)
s.tension_stiffness = 20
s.compression_stiffness = 20
s.shear_stiffness = 8
s.bending_stiffness = bend
s.tension_damping = 8
s.compression_damping = 8
s.shear_damping = 8
s.bending_damping = 1.0
s.air_damping = 4.0                # settles instead of swinging
s.vertex_group_mass = "pin"
s.pin_stiffness = 1.0
s.shrink_min = -grow
s.shrink_max = -grow
cs = mod.collision_settings
cs.use_collision = True
cs.distance_min = dist
cs.collision_quality = 4
cs.use_self_collision = False

scene.frame_start = 1
scene.frame_end = int(frames)
mod.point_cache.frame_start = 1
mod.point_cache.frame_end = int(frames)
for f in range(1, int(frames) + 1):
    scene.frame_set(f)
dg = bpy.context.evaluated_depsgraph_get()
me = cloth.evaluated_get(dg).data
out = np.zeros(len(me.vertices) * 3)
me.vertices.foreach_get("co", out)
out = from_b(out.reshape(-1, 3))
assert len(out) == len(d["pos"]), "the cloth's vertex count changed"
np.save(argv[1], out)
print("cloth_drape: moved by up to %.1f mm, on average %.1f mm" % (
    1000 * np.linalg.norm(out - d["pos"], axis=1).max(), 1000 * np.linalg.norm(out - d["pos"], axis=1).mean()))
