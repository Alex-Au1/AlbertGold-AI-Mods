# Mod Building

How the first mod (`EiBlossomPrincess`, 2026-11-10, now in the PRIVATE repo) was made without a 3D editor, and what it measured.
Everything below about the game's side is from Raiden's files; nothing is confirmed in game yet.

## The loop

1. **Render the source** (`modkit.render.render`, four yaws, `cull="mark"` paints back faces magenta).
2. **Segment it.** `weld_islands` (position-welded connectivity) gives the real parts: torso, legs, arm, shoes.
   `islands` (index connectivity) splits a part further by UV island. Colour each island and render; print each
   island's bounding box, UV box and vertex groups. Pick parts in the recipe by **geometric rules** (bounding
   boxes, triangle counts), not by island number.
3. **Measure** what the new geometry must fit: cross-sections per height, an arm's axis from its weights.
4. **Decide per source part**: keep and repaint, remove, mirror, or generate.
5. **Build, render, look, adjust.** Also render vertex weights as colours.

## What the toolkit gives you

| Need | Use |
| --- | --- |
| read / write `Position` / `Blend` / `Texcoord` / `.ib` | `modkit.gimi.Mesh` |
| cut triangles out as a piece, join pieces into components | `ops.part_from_mesh`, `ops.join`, `ops.assemble` |
| a skirt, tube, cone: any grid of points | `ops.grid_surface` + `ops.new_part` (normals, tangents) |
| the other side of a limb | `ops.mirror_part` with a left/right vertex group map |
| blend weights for new geometry | `ops.knn_weights` from chosen source vertices |
| paint a kept part by **3D position** | `ops.bake_uv` (position per texel), then numpy masks |
| write a texture | `ops.save_dds` (RGBA8, DX10 header, sRGB flag, mips) |
| look | `render.render`, `render.sheet` |

## Raiden's model, measured

- Buffers: Position 40 bytes (pos, normal, tangent with w = -1), Blend 32 (4 weights, 4 group indices),
  Texcoord 20 (colour, uv, uv2). 118 vertex groups. Y up, **front is +z**, her right arm is at x < 0.
  (CHECK THE SIDE IN THE GAME: on Mavuika, 2026-11-17, the game showed +x as the character's RIGHT; "x < 0" here
  was read off `modkit.render`, which draws a mirror image of the game. See Outfit Transfer.)
  (Ei too, 2026-11-19: her fan is at +x, and in the maintainer's game screenshots the fan is at the viewer's LEFT
  from the front, i.e. on HER RIGHT. So +x is her right, as the build's `EAR_COVERED = -1` comments say, and "her
  right arm is at x < 0" above is wrong for the game. Every sheet of this mod is mirrored against the game:
  what a sheet shows at the picture's right from the front is at the picture's left in game.)
- Front faces are **counter-clockwise** (`cross(p1 - p0, p2 - p0)` points out) in 99.5% of triangles.
- Thin cloth (the tails) is single-sided in the source and its inner side shows, so the game does not cull it.
- The model stands in an A-pose; no skeleton is in a mod, so there is no way to pose it offline.
- **The draws are not what their names say.** `Head` also holds the kimono's cords, the obi ornament and the neck
  ribbon; `Dress` also holds the hair and ankle flowers; the `Body` diffuse contains a copy of the dress art.
- Her left arm does not exist under the kimono sleeve (only the hand). The right arm was mirrored for it.
  Arm groups: 65 / 67 shoulder, 66 / 68 upper arm, 88 / 111 forearm, 89 / 112 hand, fingers 72-86 / 95-109.
  Groups 12 and 13 lie on the left arm's axis but belong to the sleeve.
- Skirt chains: 25-29 and 30-34 (left tail), 35-39 and 40-44 (right), 45 / 46 front flaps, 48-51 sides, 47 pelvis.
  8 / 9 are the bust.
- Light map (read by sampling): alpha is the material code (255 skin, ~126 soft cloth, 0 dark cloth and
  stockings, 178 gold); green 128 is neutral shade; blue ~76 on cloth. Diffuse alpha is 0 except glowing emblems.
- Source textures are BC7, diffuse sRGB (DXGI 99), light map linear (98).

## Traps already hit

- **Resizing an RGBA image in Pillow premultiplies alpha**, and these textures' alpha is 0 almost everywhere:
  the whole upscaled texture came out black. Resize channel by channel.
- **"Skin" is the light map's alpha, not a colour.** `alpha > 200` is an exact skin mask; the sheer collar is
  painted on skin-coded texels, so that one part needed a colour test instead.
- Mirrored halves share UVs (both legs, both arms): paint with rules that are symmetric in x.
- Weights from nearest neighbours follow whatever is closest: the stole took the upper arms' weights and would
  swing down with them, so half its weight was put on the chest group. Predict the motion, as AGRemap's
  vertex group behaviour audit says.
- The preview's face is blank because the face is a separate draw that a mod does not carry.
- **`modkit.render` is LEFT-RIGHT MIRRORED against the game** (2026-11-18): a license plate whose text read right
  offline read backwards in game. Judge anything with a handedness (text, logos, an asymmetric decal) in game or
  in a render flipped in x. Details in [Skill Objects](../SkillObjects/CLAUDE.md).

## What the game showed (2026-11-10)

- The uncompressed RGBA8 textures, the generated tangents and vertex colour `(255, 128, 128, 128)` all work:
  outlines are clean, with thin dark lines in the deepest skirt folds.
- **Near-white blooms.** Stockings at 244 and fur at 252 came out as flat glowing white. Keep the brightest
  cloth around 225-240.
- **The Body draw textures BACK faces through `uv2`, and every Body vertex has the same `uv2`** (0.7304, 0.7059):
  one texel, the source's red kimono lining. The inside of the repainted bodice showed red until that texel was
  painted. The Dress draw has `uv2 = uv`, so its insides match its outsides.
- The mirrored arm, the kNN-weighted skirt and train, and the half-chest stole held together in the idle
  animations, climbing and a sprint. Nothing tore or spiked.
- In the character screen the first seconds after a reload play an entrance pose lit by her orb; wait about
  ten seconds before judging colours.

## The reviewer pipeline (the maintainer, 2026-11-14 to 2026-11-17)

For each batch of changes the maintainer gives: change the build; build; make comparison sheets with the reference
beside the made result; give them to a FRESH reviewer subagent with the design intent, never with what is believed
fixed; fix its fault list; repeat. The maintainer names a MODE per batch: no iteration (fix, then the maintainer
verifies in game), fast (one reviewer pass), light (up to three epochs), normal (up to five). Only then is the
maintainer asked to check. A reviewer asked to MEASURE reference and made result in the same views (counts, widths,
angles) gave what several fault lists did not; reviewers asked only for faults circle on matters of proportion.

## Two traps found on the Ei mod (2026-11-18 / 19)

- **The maintainer's loader skins only about 218,900 vertices of a mod's buffer** (the old GIMI rejects
  `override_vertex_count`): parts past it are never moved into the pose and simply do not show, with no warning.
  The last-built parts vanish first. Keep a vertex count assertion in the build.
- **Check skinned cloth against a REAL pose**: the skinning pass in a frame dump (vs `653c63ba4a73ca8b`) binds one
  3x4 float32 bone matrix per vertex group at `vs-t0`; posing the built mod with it shows what the game does. A
  made-up pose moves only the bones you think of. The 3DMigoto hash of that buffer is the same in every dump;
  compare contents, not names.

The full history of the Ei mod (every review, batch and game look) is in the private repo,
`AI Agent Help/Private/EiBlossomPrincess/CLAUDE.md`.
