# Weapons: modding a character's weapon (Mavuika's claymore as the Fusion Sword, 2026-11-17)

The first weapon mod here: `MavuikaCloudyWolf/Sword`, Mavuika's signature claymore "A Thousand Blazing Suns" made
into Cloud Strife's Fusion Sword (Advent Children, assembled form). Recipe: `Tools/Builders/MavuikaCloudyWolfSword/build.py`;
output `Mods/GI/Mavuika/MavuikaCloudyWolf/Sword/`. Pictures: `Docs/Previews/MavuikaCloudyWolfSword*.png` (main sheet:
game weapon / reference model / mod in the same frame; `_close`: silhouettes game red over mod green, then the hilt
culled on green). Reference shots: `Images/GI/Mavuika/MavuikaCloudyWolf/Sword/`.

## Where the source is

- **Weapons live in `GI-Model-Importer-Assets/WeaponData/<Type>/<Stars>/<Name>/`**, but the repo stops at older
  weapons (the newest 5-star claymore there is Verdict). A Thousand Blazing Suns was NOT there: it was **dumped**.
- **Dumping it** (a game subagent with AGRemap's `Tools/GameView`): character screen -> Mavuika -> Weapons tab ->
  `dump --label MavuikaWeapon` (`FrameAnalysis-MavuikaWeapon-2026-11-17-211931`, kept). The Weapons tab today shows
  the weapon IN HER HAND, not alone; the weapon was still easy to find: it was the only stride-28 vb0 in the dump.
  Four draws use it (main pass 000019, VS `1615e2fb89012150`; three more passes of the whole character), one ib
  part, first index 0. No second (burst) mesh was found. NOT checked: whether the overworld draw has the same hashes.
- **GIMI's `genshin_3dmigoto_collect.py` picks the wrong textures for a weapon**: it sorts slot names as text, so
  `ps-t10` came before `ps-t2` and was taken as the Diffuse. The vb0 / ib text files it wrote were right; the
  textures were assembled by hand into `Tools/Builders/MavuikaCloudyWolfSword/dump/` (same layout and `hash.json`
  fields as Verdict's in the assets repo). Slots: t0 NormalMap, t1 Diffuse, t2 LightMap, t3 MetalMap.
- The MetalMap (`b0e08915`, 256, sRGB) is SHARED with Verdict: a lookup by normal, not by UV. The mod does not
  bind it, so the game's stays.

## The weapon, measured (game coordinates of the weapon; it is not skinned)

- vb0 stride 28, no blend buffer: POSITION R16G16B16A16_FLOAT (w = 1), NORMAL R8G8B8A8_SNORM, COLOR R8G8B8A8_UNORM,
  TEXCOORD R16G16_FLOAT, TEXCOORD1 R16G16_FLOAT, "TANGENT" R8G8B8A8_UNORM. ib R16_UINT in the game; the mod writes
  R32 (as GIMI's generator does). The mod's `.ini` is the generator's no-blend form: one override on the draw vb
  (`vb0 = Resource...`), the ib skip, the ib part with `ib =` and the textures.
- **"TANGENT" is not a tangent** (no relation to normals, UV tangents or position in Verdict's data, tried as
  0..1 and octahedral). GIMI's generator writes the NORMAL's bytes there for no-blend models; the mod does too.
- **uv2 differs by weapon**: on Verdict it is a planar map (exactly linear in x and z, rms 0.001); on A Thousand
  Blazing Suns it is a second unwrap (a linear fit misses by 0.2). The recipe uses the game's map when it is
  linear, otherwise a planar map of the new mesh's face (across -> u, along -> v, inside 0.02 .. 0.99).
- 5 559 vertices, 4 140 triangles; along +z from -0.483 (pommel) to 1.562 (tip); width 0.57 at the sunburst guard,
  0.27 thick there. The GRIP (longest narrow run, from points spread over the triangles) is z -0.30 .. 0.05,
  centre (0, 0, -0.125). Her hand closes just under the guard (screenshot).
- Vertex colour (1, 0.5, 0.5, a) with a = 0.5 on 62 %, lower on the rest (outline thickness).
- **Light map**: the BLADE and the sunburst guard are alpha 0, red 0, green 255: an unlit code that GLOWS by the
  diffuse alpha (the red-orange glow). The HILT and pommel are alpha 255 (lit): ornaments (254, 128, 152, 255),
  the wrapped shaft (101, 128, 50, 255). The diffuse alpha (0..255) is the glow mask. Normal map flat texel
  (128, 128, 254, 255).

## The Fusion Sword model

- Three models in the maintainer's `C:\Users\3dark\Downloads\Cloud Fusion Sword References`: a `.blend` (31 objects,
  two bolts alone 57k vertices each, no image textures), an untextured `.obj` (3.7k vertices, in centimetres), and a
  textured `.dae` (five parts: main sword and the four other blades, 13.5k vertices, 11.7k triangles, each part
  with its own 2048 albedo / metallic / roughness / normal set). **The `.dae` is the source.**
- `modkit.blender.fbx_dump` now reads `.dae`, `.obj` and `.blend` too (by extension), and records each material's
  first image texture if the file links one (the `.dae` links none: textures are matched by material name).
- In its own file the sword lies along z, grip at +z, length 2.0, grip 0.34 long.

## Placing it: the hands decide, not the lengths

- The game animates the weapon as one rigid object held at its grip; her UPPER hand closes just under the guard and
  the lower one far down the shaft (`AThousandBlazingSunsWeaponsTabCrop.jpg`). So two places matter: the guard's
  lower face and the grip's length.
- First try (grip centre on grip centre, one scale making both 2 m long): the reviewer saw the Fusion guard 2-3 cm
  over the game's grip top (her fist in the guard box) and the grip too short for the lower hand.
- Now (`hilt_map`): a turn (axis to axis, thin side to thin side), then along the axis two pieces joined at the
  GUARD'S LOWER FACE (lowest point above the grip wider than 6 cm): from the guard up the model's own size
  (`BLADE_SCALE` 1.0; its tip ends 0.2 m past the game's), below it the grip stretched (x1.10) to end 3 cm below
  the game grip's narrow run, keeping its girth. The `_close` sheet's zoomed red-over-green hilt shows it.
- Finding the grip: the width profile along the long axis from POINTS SPREAD OVER THE TRIANGLES (vertices alone left
  empty slices on long triangles), the longest run narrower than 0.35 of the median width.

## Reviewer epochs (2026-11-17; sheets: the main one and `_close`)

- **Epoch 1** (9 faults): grip short for her lower hand and the guard over her upper hand (above); the stacked blades
  read as one even grey slab; possible bloom; the guard black on one face and light grey on the other (the source
  model's own paint, kept); red grip against the concept art's black (the model's, kept); a slightly narrow and
  very thin blade (the model's); the gear disc a thin plate. Changed: the hilt map above, and a small shade step
  per blade (`PART_TINT`: main 1.0, the others 0.82-0.94).
- **Epoch 2** (7 faults): the grip now lines up with the game shaft (all yellow in the hilt overlay). New: the row of
  dark slot marks along the blade's spine "missing" and the blade 25-30 % darker than the model. Not culling (the
  same views culled, unculled and with back faces marked match): the marks are thin lines in the 2048 source maps
  and were lost when each map was shrunk to a 682 px tile, and the whole range had been scaled by 225/255 plus
  the tint. Changed: tiles of 1024 in a 2048 x 3072 atlas; brightness with a SOFT KNEE (unchanged up to 190,
  255 -> 225); tints 0.90-0.97. Kept: the guard's two colours and the red grip (the model's), no pommel spike.
  Open for the game: does her upper fist close on the game's gold collar (inside the Fusion guard box) or on the
  shaft under it?
- **Trap: `ops.save_dds` mips on a non-square texture.** 2048 x 3072 halves down to 2 x 3, and the next halving of 3
  rows gave a 2-row level where Direct3D expects 1, misplacing it. The chain now stops before a side goes odd.
- The preview sheet framed by width drew the sword at a third of its panel; reviewers could not see the blade's
  marks. Frame tall things by height.
- **Epoch 3** (7 faults, all small; "the mod and the reference differ by more than 40/255 in fewer than 70 pixels per
  view"): a light dotted seam down the grip; small tabs by the blade root missing edge-on; a dark line along the
  blade's outer edge; the blade a little darker than the model; the layers reading as one pale slab; bloom risk on
  the light gear wheel. Found and changed:
  - **The source maps' UV islands TOUCH.** The grip's red strip ends against the guard's island, whose 1-texel
    light border then lay on the grip's seam; a coverage mask counts it as covered, so a plain bleed kept it.
    `island_bleed` labels every atlas texel by UV island, trims each island by 3 texels where it meets another
    island or nothing, and regrows each island's colours only from itself.
  - **Inside-out faces cannot be told from the mesh here**: the tabs' normals agree with their winding, and the
    signed volume of an open shell depends on the origin. `orient_by_visibility` looks from 62 directions with no
    culling (points spread over the triangles BY AREA, ~4 per pixel; 12 per triangle let far faces show through
    near ones and called 10 000 triangles "seen from both sides") and turns a triangle when it is hit 6+ times and
    over 4 times as often from behind as from the front (131 turned; "more back than front" turned 2 081).
  - What was left magenta edge-on was two OPEN TUBES (168 triangles each) seen down their open ends: real openings.
    `two_sided_open` gives open islands of at most 200 triangles a reversed twin.
  - Note for reading `--mark` renders: a twin's back face lies on its original, so it can show magenta in a mark
    render (z-fight); the game culls it.
- **Epoch 4** (7 faults, mostly tone and detail). Two of them were made by epoch 3's own fixes, a pattern to expect:
  - the slots' dark outlines washed out and pale patches beside them: the per-island trim also cut where an island
    meets NOTHING, and the source paints dark outlines exactly on those borders. Now trimmed (2 texels) only where an
    island meets another island; grown outward elsewhere.
  - the side blades' tips broke edge-on: the visibility flip had turned faces on long thin blades. Flips are now
    only inside islands of at most 200 triangles; in larger ones a face seen from behind at least 30 % as often as
    from the front gets a reversed TWIN instead (212 faces: the side blades' tips are single sheets, hit about
    equally from both sides, which no flip can fix).
  - the blade 5 % darker than the model: the per-blade tint was dropped (`PART_TINT = {}`).
  Kept, noted for the game: the grip is long against the concept art (it follows her two-hand span), the guard box
  is deeper than the game's collar (a high hand may touch it), and the blade is twice the game blade's width
  (clipping with her legs and hair in idle and sprint poses to be looked at).
- **Epoch 5** (6 faults; the last epoch, by the rule): "practically identical to the reference model in all five
  views", no holes, inside-out faces, seams or z-fighting. Open:
  - WHERE HER UPPER HAND CLOSES. Epoch 1 read her photo as "just under the game's guard" (so the Fusion guard was
    moved off it); epoch 5 reads the same photo as "on the game's gold collar", which is where the Fusion guard box
    now sits (overlay y 265-335 of the hilt zoom). The renders cannot settle it: look in game at a two-handed pose.
  - Bloom risk on the near-white gear disc and the lit blade (albedo capped at 225 by the soft knee).
  - Under toon shading the stacked blades may read as one slab (the model's greys differ by a few levels).
  - Faithful to the model, noted: the gear disc reaching past the blade's back, the thin red line on the guard,
    a plain (unridged) grip.

## In game, first look (2026-11-17, a game subagent; shots `Images/GI/Mavuika/MavuikaCloudyWolf/Sword/ingame_*.png`)

- Loads with NO 3DMigoto warnings; no other mod uses the weapon's hashes; the OVERWORLD draw has the same hashes as
  the Weapons tab (the sword shows in attacks). Orientation right (edge and flat as the original's).
- **Her hands are right**: the hand nearer the blade closes on the red grip just under the guard box (a finger's
  width or less, as the original's hand sits under its gold collar), the other on the shaft. No fingers in the box.
  (Epochs 1 and 5 disagreed on this from the photo; the game settled it.)
- **SERIOUS: the whole sword, red grip included, came out GOLD-PEACH and blooming on the Weapons tab**
  (`ingame_compare_front_original_vs_mod.png`); in the night overworld a cream blade with a red grip. The game's
  MetalMap is plain grey (checked), so the tint is in the shader's constants for this weapon's lit code (alpha 255,
  specular red 254), which the mod had put on ALL of the sword. Changed, NOT seen in game yet: albedo capped at 200
  (knee 160), and four LIGHT MAP VARIANTS cycled with "]" (`LM_VARIANTS`: the game hilt's texels / low specular /
  no specular / the blade's unlit code), to be chosen by looking.
- **The guard was a hollow sleeve** (open top and bottom: "glassy", "a tray" from above): `cap_guard` closes both
  ends with flat caps.
- Read and kept: a dark red rod along the blade's back from the guard (Sword_04's own red strip in the model); red
  in the slots in one swing (her hair behind). Sprint and idle show no weapon (the claymore is put away).
- The tool's black `uidRects` box (WuWa's Terminal rectangle, applied to GIMI too) hides part of the frame in
  Genshin overworld shots; turn the camera round it.
- The subagent stopped early: someone else began driving the game. It parked the mod out of `Mods` but did not
  reload, so the game kept the sword until the next F10.

## In game, second look: the light map variants, and the effect mask (2026-11-17; `ingame2_*.png`)

- On the Weapons tab: the game hilt's texels (red 254) = gold, blooming; low specular, no specular and the unlit
  code = grey steel, within 3/255 of each other; LOW SPECULAR the best (still shaded). It is now variant 0.
- **The guard and grip stayed amber in EVERY variant.** Not the light map, not the diffuse (plain grey there):
  **the weapon's draw binds more textures than the collector names.** Frame dump draw 000019 has ps-t0..t12:
  t0-t3 normal / diffuse / light / metal maps, t4 and t12 small ramps (t12 orange: the glow's colour), t5 a pink
  gradient, t6 a swirl pattern, t7 a streak, **t8 (`d36ddf9e`, 512) an EFFECT MASK on the weapon's own UV layout**
  (olive and green shapes of its blade lines, sunburst, hilt), t9 stars, t10/t11 a noise. A new UV layout lands
  on that mask's olive areas wherever it happens to: the guard and grip lit amber. **The mod binds a black 16 x 16
  texture to ps-t8** (`EFFECT_MASK_SLOT`). Changed, NOT yet seen in game.
- Lesson: for a weapon (and probably any object with effects), list ALL `ps-t*` of the draw in the frame dump and
  look at each; any texture sampled by the object's UV must be replaced or neutralised when the UV layout changes.
- The persisted `$lightmap` is dropped from `d3dx_user.ini` while the mod is parked; it starts at 0 when loaded.

## In game, third look: the effect mask off (2026-11-17, 23:04; `ingame3_*.png`)

- No warnings. **The amber is gone**: guard black (front) and light grey (back) with its red line, grip red with
  tan caps, blade grey steel, shaded, no bloom (`ingame3_compare_original_vs_mod.png`). Black t8 broke nothing:
  the sword appears, swings and is dismissed whole; the dismiss glows gold over the whole sword exactly as the
  original does (`ingame3_dismiss_dissolve*.png`), so that effect is not t8's.
- Left: thin ORANGE lines along the blade's layer seams, the guard's and the disc's edges, and small dashes in the
  slots (the game's outline colour, or another slot sampled by UV; not traced). The blade is near-white on the
  Weapons tab's lighting, grey outdoors.
- Not seen: charged attack, skill, burst; the appear moment up close.

## The orange edge lines: four passes, different slots; and what GIMI checks (2026-11-17; `ingame4_*.png`)

- The weapon is drawn in FOUR passes sharing its ib (frame dump draws 19, 27, 63, 71), and they bind its textures in
  DIFFERENT SLOTS: draw 19 t0 normal map / t1 diffuse / t2 light map / t8 effect mask; draw 27 t0 diffuse /
  t1 light map; draws 63 / 71 t0 diffuse. Binding by slot on the ib (`ps-t1 = ...` under the ib's override) puts
  the mod's normal map where draw 27 reads a diffuse, and so on: thin orange lines along every layer step, the
  disc's arcs and the slots.
- Fourth look: the weapon's textures replaced BY HASH (`[TextureOverride...] hash = <texture> / this = ...`):
  **the orange lines were gone** (dark maroon outlines of constant width instead, as normal), but the amber came
  back on the guard, grip and in pink patches: the effect mask had been moved to a hash override too, and
  **GIMI's `d3dx.ini` checks texture hashes only in ps-t0..t3** (`[CommandListSkin]`: `checktextureoverride` on
  ps-t0..t3, vb0..2, ib). A hash override for a texture bound in t8 never fires.
- Now: t0-t3 textures (normal map, diffuse, light map) by hash; the effect mask BY SLOT (`ps-t8`) under the ib's
  override, as in the third look that removed the amber (draw 27's own t8 gets the black texture too).
- **Fifth look (2026-11-17, 23:50; `ingame5_*.png`): both gone.** No warnings; guard black with its red line (grey
  face from behind), grip red, blade grey steel with normal dark outlines on its steps, disc white-grey; nothing
  else changed. One frame while the sword appears shows the grip dark with yellow streaks, clean a moment later:
  read as the game's summon effect, not confirmed.
- Lesson: on a GIMI object drawn in several passes, replace its textures by hash wherever they sit in t0-t3, and by
  slot only for what sits above t3; check each pass's slots in the frame dump first.

## Material bands (the maintainer, 2026-11-18)

AGRemap's lesson (`Fix-Raiden-Boss/AI Agent Help/VGRemaps`): a light map's ALPHA is a MATERIAL BAND that picks a
shading ramp, its RGB a class within it, and the legend is per object, read off its own texels. This weapon's
legend, over every texel its triangles cover (not only at vertices):

| alpha | rgb | texels | on the original |
| --- | --- | --- | --- |
| 0 | (0, 255, 0) | 112 021 | the blade and sunburst: unlit; green 255 = glow (diffuse alpha drives it) |
| 254 / 255 | (254, 128, B), B 75 .. 216 rising with the diffuse's brightness | ~17 000 | its gold metal |
| 255 | (101, 128, B), B 25 .. 56 | ~9 700 | its dark red wrapped shaft (diffuse ~ (76, 40, 30)) |
| 255 | (0, 255, 0) / (0, 129, 0) | ~2 300 | small glowing / matte gold bits |

Applied (`band_lightmap`, variant 0 on "]"): the Fusion Sword's metal (its metallic map) on the metal class, the
rest on the wrap class, B from the model's roughness inside each class's range (smooth = high B). Measured on the
atlas: red cloth 94 % wrap (B ~36), black polymer 94 % wrap, tan caps and steel metal (B ~170-183). The second
look's "game texels gold" verdict came with the effect mask still on, so the metal class is tried again here.
**In game (2026-11-18, `ingame6_*.png`, side by side `ingame6_bands_vs_lowspec.png`): the copy turned the WHOLE
sword a blown-out peach, the black guard face and the ridged strip too (only the red grip held); low specular stayed
grey steel, black guard with its red line, red grip.** Both sit on the lit band (alpha 255): the BAND was right.
The class RGB was not: the original's classes are tuned to its gold, and this weapon's specular tint is gold, so any
real specular (red 254 on metal, even 101 on the wrap) paints gold on a grey diffuse. Low specular (metal
(90, 128, 60, 255), the rest (0, 128, 0, 255)) is the default again; the copy stays as variant 1 on "]".
Lesson: copy a band's ALPHA from the legend; copy its RGB only when the new material is the old one's colour.

## Cross-checking the three models (the maintainer, 2026-11-18)

"You can also use the other models to cross-validate and improve upon the sword." `measure/three_models.py` and
`measure/profiles.py` (beside the recipe) dump all three through Blender, turn each so its long axis is up and its
grip down, scale to length 2.0, and draw them side by side and as width / thickness profiles
(`Docs/Previews/MavuikaCloudyWolfSword_three_models.png`, `_profiles.png`). `fbx_dump` now also writes each
material slot's base colour (`<i>_matcol`), which is all the .blend has (no image textures).

- AGREE: the silhouette, slot column, notch and steps; mid-blade width 0.236 / 0.240 / 0.246; the guard at the same
  place; the stacked lower section's thickness.
- THE .DAE ALONE: (1) its upper blade is 0.027 thick against 0.048 (.blend) and 0.040 (.obj): the reviewers' "very
  thin edge-on"; (2) its crossguard is black on one face and on both ends, grey on the other; the .blend has it
  steel all round, the .obj one plain bar, the concept art one grey riveted bar.
- No agreement (kept as the .dae): the gear disc (white .dae, gold .blend, dark hatched art), the grip (red .dae and
  .blend, black art).
- Changed: `thicken_blade` scales the upper blade through its thickness (x1.63, to 0.044, the other two's mean)
  beyond the stacked section (found as where thickness first exceeds 1.4 x the upper blade's, from the tip), with
  a 6 cm smooth ramp; `SOURCE_PATCHES` paints the guard's black face with its grey face's texture and both black
  end faces with a plain stretch of it (rects found from the guard sleeve's own face UVs). The 4 mm rims are left.
- Reviewer epochs for this batch:
  - **Epoch 1** (6 faults): "upper blade still too thin" (read off the profiles sheet, which then showed the three
    SOURCES only: the sheet now draws the built mod too, white, read back from its buffers: mid thickness 0.049
    against 0.048 / 0.040, the .dae's 0.027); the gear disc near-white (bloom; the art draws it mid-grey) ->
    `PART_TINT` Sword_01 0.8; the red line across the guard is the .dae's alone -> a dark seam (`GUARD_SEAM`);
    guard plates read weakly at distance; no round holes on the lower blade (none of the three models has them);
    keep the blade's greys. Matches: shape, layers, tip, slots, hilt in the game's frame; no holes or z-fighting.
  - **Epoch 2** (10 faults, most of them off the profiles sheet): the mod's guard "a third shorter", its lower edge
    "narrower with a hard step", a "zig-zag" at the thickening, its tip "mirrored". Cause: the sheet scaled the MOD
    to length 2.0 like the sources, but its grip is stretched to her two-hand span, so everything shrank. The mod is
    now placed with its guard on the .dae's and guard-to-tip scaled to it (its blade is the model's own size):
    guard, widths and the .dae's steps line up, the upper blade's thickness 0.044 sits on the .blend and .obj.
    Across (left / right) is the PCA's sign, so a model can draw mirrored. Grazing renders of the thickening's start
    showed a smooth taper; the lower plate's two tones are its bevels, as on the .dae. Kept as the .dae has them:
    the ribbed side plates (bumps in the .blend's and .obj's thickness, flat in the .dae), the notched back of the
    ribbed piece, the disc as a flat plate.
  - **Epoch 3** (7 faults, all minor or moderate): "the slots are only slightly darker squares (129 against 143) and
    will vanish under toon shading; the .blend and the art draw them dark". They are windows through the outer blades
    onto the inner core (Sword_03): `PART_TINT` Sword_03 0.55 makes most of them dark (a few are the outer blade's own
    paint). Kept: the lower plate's angle (the .dae and .blend agree; the art is a sketch), the slivers in the
    through-slot (the .dae's), the flat disc (models disagree), the uncompressed textures. The reviewer measured the
    diffuse: max 184, 99 % <= 175: low bloom risk.
  - **Epoch 4** (6 faults): "the lower blade's outline follows the .obj against the .dae and .blend" and "the whole
    outline 7 px off": the profiles sheet still drew models with PCA's arbitrary left / right (the mod and the .obj
    mirrored). Now each is turned so the clipped tip's high corner is on the same side: all four outlines lie on
    one another, the mod exactly on the .dae. The gear disc still the lightest surface: Sword_01 0.65. Noted for the
    game: the lower plate's bevel strip may read as a hard dark stripe in toon shading; the ribbed column's pale
    teeth (the .dae's).
  - **Epoch 5** (8 faults; the last): "the lower angled plate is a flat dark grey without the blade's wear". It is
    part of Sword_01 with the gear disc, and the disc's whole-part tint had darkened it. Applied after it, NOT
    reviewed: `PART_BRIGHT_CAP` compresses only Sword_01's bright values (above 150, 255 -> 170): the plate is light
    and worn again (checked in the main preview), the disc near the blade's grey. Noted for the game: the guard plate
    and bevels near the bloom range; the slots' floors light at an angle (the .dae's); no rivets on the lower plate
    (none of the models has them).
- **In game (2026-11-18, 02:20; `ingame7_*.png`):** all four changes seen. The upper blade thicker edge-on
  (`ingame7_back_edge.png`), no kink; the guard grey riveted steel on both faces and the ends with a dark seam
  (`ingame7_guard_otherside.png`); the disc light grey with dark rings, no bloom (`ingame7_disc.png`); the slots a row
  of dark rectangles in the overworld (`ingame7_attack_behind1.png`). No bloom, amber, holes, or dark stripe on the
  lower plate's bevel. Read and kept: the black ribbed piece beside the blade shows more and darker (the model's own
  black part, as the art draws it; the thicker blade and the darker core show more of it). Not seen: side and
  edge-on overworld attacks, daylight (another driver reloaded the game mid-check, so the subagent stopped).
- The maintainer keeps a copy installed at `GIMI/Mods/Mavuika/MavuikaCloudyWolfSword` (2026-11-18). Refresh it by
  copying the build over it (same file names); do not also load the staging copy (same hashes).

## Open (2026-11-17)

- Variant 0 (low specular) is the one seen and approved by the game subagent; the other three can be dropped once
  the maintainer has looked. Not seen: night overworld, charged attack, skill, burst.
- The game was being driven by another session (the motorcycle's game checks) during the dump; ask before driving it.
- Textures are uncompressed RGBA8: the diffuse is 2048 x 3072 (33 MB with mips). BC7 would cut that by four.


Ei's burst sword (the Ultima Weapon, generated from pictures alone) is in the private repo:
`AI Agent Help/Private/EiBlossomPrincess/Sword.md`.
