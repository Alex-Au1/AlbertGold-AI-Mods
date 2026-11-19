# Outfit Transfer: wearing a model that is not a 3DMigoto dump

How `MavuikaCloudyWolf` (2026-11-15) put Cloud Strife's Advent Children outfit, read from an `.fbx` the maintainer
downloaded (FFVII Ever Crisis; the model is NOT stored in this repo), on Mavuika. Recipe:
`Tools/Builders/MavuikaCloudyWolf/build.py`. Seen in the game the same day by a game subagent (its section below).

Pictures: `Testing/Acceptance/Previews/MavuikaCloudyWolf.png` (reference row, mod without hair, mod), `_top.png`, `_legs.png`
(reference above, mod below, back faces magenta), `_weights.png`. The reference renders alone are in
`Images/GI/Mavuika/MavuikaCloudyWolf/Reference_EverCrisisModel.png`.

## Can an outside model be read? Yes, through Blender

- `modkit.blender.fbx_dump(fbx, out_npz)` runs `Tools/ModKit/blender/fbx_dump.py` in Blender 3.6 without a window
  and returns arrays in the mod's coordinates (Y up, front +Z): per mesh object positions, normals, UVs (v flipped
  to the .dds convention), triangles, material slots, the four heaviest bone weights, and the armature's bones
  (names, parents, rest positions). About 20 s; the recipe caches the result in the temp folder.
- **The unit is the file's.** This model came out 100 times too small (1.6 cm tall): `SC = 100`.
- **Winding and handedness matched ours** after Blender's Z-up to Y-up rotation: 96% of triangles counter-clockwise,
  his left arm at x > 0 like hers. Check with one textured render before anything else.
- The `.tga` textures open in Pillow. `AAAT` is albedo, `MROX` metal / roughness / occlusion, `NNNX` the normal map.
- **Tiny islands with hundreds of vertices are real accessories at their real size** (his wolf earring, two finger
  rings: 600 vertices inside 2 cm). The recipe drops islands under 3.5 cm with more than 400 triangles, and
  everything weighted to his head. A size test alone dropped 47 buckles and rivets: add the triangle count.

## Mavuika's model, measured

- Buffers: Position 40, Blend 32, **Texcoord 12 (colour, one uv; no uv2)**: `Mesh.load(..., tex_stride=12)`,
  `mesh.save(..., tex_stride=12)`, `view.py --stride 12`. 92 vertex groups. Her hair is its own buffer set
  (`MavuikaHair*`): a mod that leaves those sections out keeps the game's hair, and the same goes for the face.
- Draws: `Head` = forearms and gloved hands, earrings, eye pieces, three ornaments (chest star 42, back disc 8,
  lower back 21, choker 22); `Body` = jacket, sleeves, cuffs, and ALL bare skin (neck, the head's underside with the
  ears, chest); `Dress` = the suit from bust to shoes.
- Groups: 23 pelvis, 32 / 90 spine, 91 chest, 67 neck, 44 head, 46 / 69 clavicles (right / left), 0-3 bust,
  4 / 5 seat. Arms right / left: 39 / 40 upper arm, 37 / 38 its lower half, 63 / 86 forearm, 64 / 87 hand, fingers
  47-61 / 70-84. Legs right / left: 35 / 36 thigh, 65 / 88 lower thigh and knee, 45 / 68 shin, 62 / 85 foot,
  66 / 89 toe. Ornament groups (never a weight source): 8, 21, 22, 42, 9-12, 15-18, 24 / 25 heel spikes,
  28-31 the jacket's cuffs.
- Joints, left side, from where two groups' weights overlap and from ring centres of the limbs: shoulder
  (0.125, 1.41, 0), elbow (0.239, 1.215, -0.005), wrist (0.375, 1.035, -0.005), knee y 0.565, ankle y 0.105.
  Her arms hang at 57 degrees below level, Cloud's at 43. She stands on heels: the model's lowest point is -0.039.
- Light map alpha (the material band), read per draw: Body 248 skin, 0 jacket; Dress 176 the black suit
  (texel 204, 89, 20), 0 the red trims; Head 120 gold, 72 dark, 248 skin. Vertex colour (255, 128, 128, 128)
  on nearly the whole suit.

## The fit, in the order the recipe does it

1. **Limbs bone by bone.** For each of his limb bones (upper arm, forearm, thigh, shin) one map takes his bone
   onto hers: a rotation, a scale along the bone to her length and a scale across it (arms 0.80, legs 0.90). Every
   helper bone (twist, cloth, belt bones) rides its nearest ancestor among those. Vertices blend the maps with his
   own bone weights, so elbows and knees stay joined. Feet are not rotated (her foot bone points down a heel): a
   boot is scaled, taller, so its sole stays on her ground and its ankle sits on her ankle.
2. **The torso through one smooth map** (heights by landmarks: ground, hip joint, shoulder joint, neck base, the
   collar's top under her chin; a width scale and a forward shift that carry his shoulder and hip joints exactly
   onto hers, so limbs and torso meet).
3. **Torso fit by outlines.** `ops.radial_envelope` gives radius per height and angle for his BASE LAYER (knit top
   + trousers, picked as islands) and for her torso (suit, jacket body, skin; arms and ornaments left out). The
   difference, hole-filled and smoothed, is ADDED to the radius of every torso vertex. The top takes her waist
   and bust, and everything worn over it (straps, buckles, holster, coat top) keeps its distance, because all of
   them go through the same map (the bust warp's lesson in Mod Building). Above her neck's top the field is held
   constant so the collar stays a tube under her jaw.
4. **Her own body under the outfit is removed**, except what shows: neck, head underside, ears; forearms and hands.
5. **Weights from her own model**, never from his bones' names: each vertex's weight is split by class of his
   bones (torso, left / right arm, left / right leg, coat) and each share is looked up by nearest neighbours among
   her vertices of that class only. Directly mapped: his foot / toe bones to her foot / toe groups, the pauldron
   to her left clavicle.
6. **Single-sided cloth gets an inner copy** (0.8 mm under, facing in): every island with a free edge.
7. Her skin and gloved hands stay in the Head / Body draws with her textures; the bare right arm is his arm mesh,
   reading the plainest skin texel of her Body texture; the whole outfit is the Dress draw with his atlas.

## Faults found while building (each seen in a render first)

- **The pauldron stood off as a flap.** It is rigid on his clavicle, and her arm (and the sleeve under it) hangs
  14 degrees lower. Its outer part now rides the upper arm's map (`PAULDRON_ARM`, growing with distance out from
  the neck), and its weights are split the same way.
- **A pale notch at the armhole** was her own chest skin showing BETWEEN the top's vertices (clearance per garment
  vertex is not clearance, as with the kimono). Kept skin is now the neck, the head's underside and the strip the
  open zip shows. Found by rendering the Body draw alone on green.
- **The coat's hem took her foot's weights** (seen in `_weights.png` as the foot's colour on the hem): nearest
  neighbours near a boot are foot vertices. Leg weight sources leave out feet and toes; boots get those groups
  from his own foot bones.
- **The coat's back hangs behind both legs**, so its weight source is the pelvis and BOTH legs.
- Open holster panels on her back showed their backs: the inner copy went to every open island, not four named ones.

## Reviewer epochs (early stopping is 5 epochs since 2026-11-15, the maintainer)

The reviewer gets the three sheets, the design intent and what is out of scope (no face, her own hair / ears /
earrings / gloved hands, the outfit reshaped to her figure, his arms higher than hers, hair over holster and
emblem). It is never told what was changed.

**Epoch 1 (24 faults: 3 serious).** Matches: silhouette and layering from every side, textures crisp and in place,
coat length and front edge, straps and buckles, emblem, pocket and boot detail, no body through coat or trousers.
Faults, by cause, and what was changed for epoch 2:

- *Back faces (magenta) on holster, pocket, coat edges, boots, collar.* Two causes. 195 of his triangles wind
  against their own normals (re-wound on load). And most of the magenta was the INNER COPIES themselves: a copy
  offset along split normals crosses its original at hard edges, and `cull="mark"` paints it. Those cost nothing
  in the game (same texture, or culled). **A close-up that is to show holes hides back faces and uses a green
  background** (`cull=True`): green inside the outline is a hole. `_top` and `_legs` do that now.
- *Ragged right armhole, a skin hole in the knit, skin over the knit at the bust.* All the SKIN, not the top (the
  Dress draw alone on green has a clean oval armhole). His arm skin is 348 triangles of 3 cm; it and the top went
  through different shares of the maps. Now: skin within 5 cm of his top (in his pose) takes the nearest top
  vertex's own move; skin his top covers in his pose is pinned 1.2 cm under that top vertex.
- *Grey patch at the throat*: the choker's shadow painted into her neck skin. `paint_neck` inpaints the neck
  (diffuse and light map) below y 1.505. The Body and Head diffuse / light map are written by the build now.
- *Bare wrist between warmer and glove; white wristband*: `paint_long_gloves` paints her forearm skin and her
  bracelets (groups 17 / 18, part of the hand's island) with the glove's own leather texel in both textures.
- *Wolf emblem stretched, standing off*: it sat across two maps. **Small hard pieces are moved rigidly**: every
  island under 12 cm gets one fitted rotation + size + shift (Procrustes from his pose to where the maps took it).
  111 islands (buckles, studs, emblem, rings).
- *Pauldron a stiff shelf*: its arm share goes to 1.0 and starts nearer the neck (x 0.07 to 0.20).
- *Sleeve kinked at the elbow, a flap behind the cuff*: `clear_over` (push cloth off her kept forearm) reached
  5 cm and pushed bell-sleeve vertices that were nowhere near her arm. Reach 1.2 cm.
- *Holster oversized, wings at both hips*: its width is scaled 0.80 by holster-bone weight.
- *Trousers too narrow*: the legs' thickness scale is 1.0 (was 0.9). *Collar too small*: 8 mm looser, top edge
  at y 1.552.
- Not changed: the armhole is deeper on her than on him; ribs spread over the bust; a strap end standing off her
  right flank; a lumpy outer trouser outline at pocket and knee.

**Epoch 2 (21 faults: 1 serious).** Gone since epoch 1: every back-face item, the skin hole in the knit, the bare
wrist, the grey throat patch, the stretched emblem, the kinked sleeve. No green hole inside any cloth surface.
Still serious: the right armhole ("jagged ... stair-stepped notches", "cut too deep and too far forward"). Others:
straps standing off under the bust, a strap end past her right flank, collar "pinched narrow ... very tall",
earrings through the collar, a trouser strap through the coat's back panel (the legs at 1.0 thickness), holster
jumbled and wide, pauldron's corner, waistband lip, boxy warmer cuff. Changed for epoch 3:

- **The armhole is cut for her, not kept from him.** His armhole is shaped for an arm raised 43 degrees; on hers
  it gaped down the side of her bust, and no amount of moving the 3 cm skin triangles under it made its edge
  clean (three tries: tuck, carry with the top, pin under the top). Now the arm's skin mesh is CUT
  (`ops.clip_part`) by "past a plane across her upper arm 1.8 cm inside the shoulder joint AND within 6.2 cm of
  the arm's axis": that part stays bare arm, everything else becomes knit (a side panel in the Dress draw, UVs
  laid flat into the atlas's knit area). The edge is a clean ring. The second condition matters: her flank under
  the armpit is past the plane too. General rule: when a borrowed opening does not suit her pose, cut a new edge
  with `clip_part` instead of nudging coarse geometry about under the old one.
- Kept skin is the neck above y 1.47 plus the zip's strip: her shoulder tops had been kept, and the top pushed off
  them stood up as torn tabs beside the collar. `clear_over` for the top reaches 1.5 cm.
- Collar back down (top edge y 1.528, 4 mm looser than her neck); legs' thickness 0.95.
- Told to the reviewer as accepted from epoch 3: a strap bridging taut from bust to belt, the reference's own black
  band inside the collar, the armhole ring, open holster loops.

**Epoch 3 (33 items: 1 serious, most minor).** "The fit is close to the reference from every angle and I found no
large holes." Serious: the armhole again, now as "a ragged frill ... a darker, ruffled, pleated lump": the new
knit side panel was made from skin vertices that the earlier tries had tucked and pinned under the top. Also:
ribs running sideways on the shoulder cap, a green speck at the armpit, the strap junction on the bust as a
"horn", the emblem tipped on the bust's slope, collar now "shorter and narrower" (epoch 2 said too tall), the
holster's upper straps "squeezed into a narrow bundle" (the 0.80 width), pauldron a stiff plate, a waistband rim,
trouser legs merging above the boots. Changed for epoch 4:

- **Once the hidden skin became knit, the moves that hid it had to go.** No tuck, no pin: the panel is the skin's
  own smooth shape, set 3 mm under itself (easing to 0 at the cut, so no gap opens at the arm) so the real top
  covers it without flicker. Its v follows height and then distance outward, so ribs run on over the shoulder.
  A fix layered on earlier fixes of the same spot: remove the earlier ones first and look again.
- Holster width 0.90.
- Told to the reviewer as accepted from epoch 4: the collar's size (two reviewers disagreed about it in opposite
  directions), slimmer trousers and boots, earrings touching the collar.

**Epoch 4 (12 faults: none serious).** "No large holes, no skin showing through cloth and no detached parts
found; the faults are shape and placement faults, plus a few thin slivers." The armhole is no longer on the list
as a fault of its edge (ribs on its cap run diagonally: minor). Listed: the pauldron "a stiff flat flap ... like a
shelf", the emblem lying sloped on the bust in profile, the hanging belt strap off the coat with green slivers,
a strap knot at the bust tip, a strap end off her right flank, the arm warmer "a tight tube" with leather on its
upper third only, a lumpy collar edge, a small red triangle at the throat, the holster crowded. Changed for
epoch 5:

- **The pauldron's outer part is laid ON the sleeve** (each vertex goes 6 mm off the weighted mean of its four
  nearest sleeve vertices, by a share growing outward from x 0.13 to 0.21 in his pose). Riding the arm's map alone
  never closed the gap. First try picked the wrong island: the emblem has more triangles than the leather cap.
  Pick a piece by SIZE (diagonal), not triangle count, and print which one was picked.
- **Forearm wear at full thickness** (`FOREARM_RADIAL` 1.0; the upper arm stays 0.80). At 0.80 her own forearm
  stood through the warmer; painted as glove leather it showed as "flat near-black" below a short leather cuff.
- `paint_neck`'s colour threshold 40 to 20 and up to y 1.515: the choker's soft shadow and the pendant's red
  point had passed as skin.

**Epoch 5, the last (12 faults: none serious, 1 moderate, 11 minor). STOPPED BY THE RULE, NOT CLEAN.** "I found no
serious fault. There is no green hole inside the outfit in any of the eight close-ups." The pauldron and the arm
warmer are in its "matches well" list now. Open, as it listed them:

1. (moderate) a small gold / brown pendant-shaped mark on her skin in the zip's open V: paint of her own
   outfit left in the kept chest strip (`paint_neck` stops at y 1.515 going UP; the strip below the neck is
   not inpainted at all);
2. the horizontal chest strap's end juts past her right flank as a square corner;
3. a strap tab / dark knob at the bust tip where the chest strap meets the taut vertical strap;
4. the chest buckle seen edge-on as a pale sliver on the bust; emblem ring plus buckle read long in profile;
5. the knit cap on her right shoulder meets the back panel in a step, ribs change direction there;
6. the harness strap behind the right armhole is faceted and a little off the knit;
7. a thin green sliver between the hanging buckle straps and the coat top at the left hip (yaw 90);
8. the holster's upper tabs and studs crowded, the pack a little wide for her waist;
9. a lumpy outer outline of her right trouser leg (pocket, knee);
10. trouser cuffs wide over the slimmer boots;
11. the emblem standing proud of the pauldron at 45 / 315 degrees;
12. her own front hair lock across the emblem (accepted).

What the five epochs did: 24 faults with 3 serious, then 21 / 1, 33 / 1 (a longer list of minor items), 12 / 0,
12 / 0. The armhole took three of the five. As with Ei's hair, the reviewer's count wanders; read what is NEW or
GONE.

## The first game audit (2026-11-15, a game subagent; `Testing/Acceptance/Previews/audit_MavuikaCloudyWolf_2026-11-15/`)

Loaded with no 3DMigoto warnings (23 sections). Mavuika is in the maintainer's party (slot 4); `key c` opens the
character screen on her. Her idle there is a 30 s loop (bike, stand, hand on hip, arm raised) with a moving
camera: the bent-arm poses are what the offline T-pose can never show. In daylight the silhouette matches the
offline sheet (`mcw_O_r0.png`). Skin of the bare arm matches her neck and face; emblem, buckles, zip and
stitching read; outlines thin and even; nothing glows.

**Three serious faults, none of them visible offline, and what each was:**

- **The bell sleeve's mouth was a lid** as wide as her torso with her hand lying on it
  (`crop_sleeve_bell_U_r0_r3_r1.png`). His model closes the bell with a lining disc and puts the hand through
  it; in the T-pose, seen from the side, that reads as a dark sleeve mouth. Faces across the forearm's axis in
  the cuff half of the sleeve are removed (44 triangles). **Look INTO every borrowed opening before building on
  it.**
- **Trouser legs, sleeve and knit broke into hard black and grey shards** (`crop_legs_Z_r8-r11.png`).
  **The game draws back faces, and draws them BLACK** (as on Ei's hair), so the inner copies were not harmless:
  0.5 mm under EVERY open island, offset along split normals, they crossed and fought their originals. Offline
  the same thing had shown as magenta and was explained away as "costs nothing in the game". Now only coat,
  sleeve, warmer, collar and the holster's open panels have an inner copy, 1.5 mm under along SMOOTHED normals.
  When `cull="mark"` paints something, find out what it is before deciding it does not matter.
- **The leather's shadow side was flat pure black with a ruler-straight edge, its lit side shone like patent
  leather.** The diffuse was near black (about 35 of 255, gamma 0.88) so the shade ramp had nothing left; the
  light map's g (0.6 to 1.0 of 128, from his occlusion map) put whole panels in permanent shade; its r (50 to
  200 from his roughness) is shine on this draw's band 176. Now: diffuse gamma 0.70; g 115 to 128; r 25 to 50
  and b 5 for cloth, metal keeps 225+ / 135.

Also from it: the pendant mark in the zip's V (the kept strip below y 1.47 reads the plain skin texel now);
the collar's back a wide funnel (1 mm looser than her neck, was 4); the warmer's top wider than her arm
(forearm thickness 0.92). Listed and NOT changed: the coat is a stiff cone in motion with a ragged hem and a
boot coming out behind (no cloth bones); the coat's lining shows as a brown strip between her legs from the
front; hair through the holster; a holster stud visible beside her right flank; angular bust profile.

## The second game audit (2026-11-15, a fresh game subagent; `Testing/Acceptance/Previews/audit2_MavuikaCloudyWolf_2026-11-15/`)

On the build with the changes above. NOT clean: 4 serious, and the work stopped here for the maintainer.

- **Confirmed gone in the game:** the bell's lid ("an open tube and her hand comes out; nothing caps or crosses the
  mouth"), the patent-leather shine ("nothing shines like patent leather"), the trouser legs' shards from knee to
  boot (only small black squares at a boot heel and a hip crease when seated remain). Knit, skin, hardware, hands
  and silhouette right; no see-through hole.
- **Still serious, and all one thing: every INNER COPY is flat pure black, and breaks into shards where it meets
  its original.** The coat's inside and rear panel "a wide black slab ... the full coat length" in every light;
  saw-teeth at the hip and hem that change from shot to shot; a black slab between sleeve, holster and coat;
  black triangles on the knit round the collar and the zip's V; the bell's inside; slashes on the warmer; the
  holster's tube ends. These are exactly the pieces that still have an inner copy. NOT YET KNOWN which it is: the
  copy's flipped normals put it in full shade on a dark texture, or the game shades anything facing away black.
  The next step is an experiment, not another guess: one build with NO inner copies, one with copies that keep
  the original's normals, each looked at in game on the coat's inside.
- The pendant at her throat is STILL there ("a gold pendant / ornament sits in the V under her chin, with a gold
  piece at the collar's left edge"), after the kept skin strip was moved to a plain texel. So it is not paint on
  that strip. Not yet identified: render the Head and Body draws alone, close, at the throat.
- Leather near-black with little grain in overworld daylight (fine on the character screen); the right armhole's
  edge slightly saw-toothed; the coat's hem flares wider than the reference; hair through holster and over emblem.
- Not seen: a run or sprint cycle, the coat against the legs in motion, night, combat, climbing.

**AN INCIDENT, AND A RULE FOR EVERY GAME BRIEF.** The second game agent used 6 s `hold` runs where the brief said
1 to 2 s and ran her off the edge of the Serenitea Pot realm. The party took fall damage (Mavuika at 2820 of
17332 HP, Yelan's portrait greyed out) and the game respawned her on the plaza. Nothing was clicked or spent, but
the maintainer's party was left hurt. From now on a game brief says, as a hard rule: **look at where she stands
before any movement; never hold a movement key longer than 2 s; never move toward an edge, water or enemies; after
every move take a shot and check HP; if HP drops, stop and report.** And say in the report whatever state changed.

## The third game audit: an experiment, and the maintainer's coat bug (2026-11-15; `Testing/Acceptance/Previews/audit3_MavuikaCloudyWolf_2026-11-15/`)

One build with a different treatment per piece (`MCW_INNER=exp`): coat and collar with NO inner copy, sleeve and
warmer with copies that keep the outside's normals, holster with flipped copies as before. The game agent
answered eight questions with shots; movement was limited to 1 s paired steps, and no HP was lost.

- **THE GAME TEXTURES A BARE BACK FACE LIKE ITS FRONT.** The coat's inside, with no copy: "leather like the
  outside ... slightly darker. It is not flat pure black", no shards inside. So single-sided cloth needs nothing.
  (Ei's "back faces are black" was hair in the Head draw of another character; do not carry a rule about what
  the game draws from one draw to another without looking.)
- **EVERY INNER COPY IS BLACK, whichever way its normals point** (`g3_crop_I_sleeve.png`: a saw-toothed black slab
  down the back of the sleeve; black slashes in the bell; black on the warmer and holster). A copy's triangles
  are wound inward. The likely mechanism (not proven by a frame dump): the game's outline pass draws back faces,
  pushed outward along the normal, in black; for an inward-wound copy the "back" is its OUTWARD side, so a black
  shell sits on top of the cloth. `INNER` is "none" for every piece now and `twin()` is unused.
- **The "gold pendant at her throat" was Cloud's own black inner collar band.** One agent saw it gold, the same
  agent saw it black in other shots of the same loop (`g3_crop_neck_B03_B08.png`). His MROX texture marks it
  metal, and metal was written as light map r 225 / b 135: it flashed gold in the scene's warm light. Metal's
  share of r is 50 and of b 30 now. Three audits and two offline reviewers called it a remnant of her outfit,
  and two "fixes" went into her skin texture for it. **Identify the object (render each draw alone at that spot,
  in the mod's own files) before fixing what it looks like.** `paint_neck` is not run any more; her neck below
  the jaw reads the plain skin texel.
- **The coat's back panel (the maintainer: "the back cape part is tied to mavuika's left leg, so when she moves,
  that bottom leg cape part becomes stretched since her stance widened").** Its weights came from nearest
  neighbours, mostly her left leg. Now: the right leg's share grows across her (0 at x +0.10, half at her middle,
  all at x -0.10, looked up at the mirrored place so heights match), and behind her 45% of the weight is the
  pelvis (`COAT_PELVIS`). The agent: "hangs down behind her from the hips ... not pulled sideways", "no long
  thin sheet or stretch toward one leg seen in any pose I got", the front panel follows the left leg. Its poses
  were standing, 1 s steps and the bike idle; a run or a wide combat stance was NOT seen.
- Left on the coat with no copy: a small black square on the front panel at upper-thigh height in every front
  shot, a column of small black rectangles down its left side that grows in motion, slits below the holster,
  ragged teeth on the hem mid-stride; black ragged triangles on the knit beside the zip's V. Changed for the
  next look: vertex colour alpha (the outline's width) 64 on the outfit instead of 128, and 0 round the
  collar's opening. Whether these marks are outline shells of layers underneath is a guess until that look.

## The fourth game look (2026-11-15; `Testing/Acceptance/Previews/audit4_MavuikaCloudyWolf_2026-11-15/`): FRONT VIEW ONLY

On the build with no inner copies, outline alpha 64 (0 at the collar) and the dulled metal. The agent stopped after
the front view of the character screen: the screen switched to another character and back with no input from it
(someone else was using the game), and by its rule it sent nothing more. It left the game ON THE CHARACTER SCREEN.
Sides, back and overworld were not seen, so the sleeve's back (the big black slab of audit 3) is NOT confirmed gone.

- Right from the front: no holes, no flicker, the bell's mouth with her hand in it "with nothing black or broken
  there", warmer, armhole, trousers, boots, coat hanging straight in the bike pose.
- **STILL THERE, so three of my explanations were wrong or incomplete:**
  - *The gold piece at her throat* (`crop_front_up_01_collar.png`): two gold lobes either side of her neck with a
    darker gold tab between and below them, skin through the middle. NOT the metal light map (now low), NOT the
    kept skin strip's paint (it reads a plain texel), and NOT in this mod's own files: the offline render of the
    same build shows a plain neck. Its outline matches the shape of the choker's painted shadow in her original
    Body texture. What draws it is UNKNOWN. Next: a build without the kept neck skin below y 1.50 (does the gold
    go with it?), or a frame dump of that spot.
  - *A pure-black rhombus on the coat's front panel* over her right thigh, a quarter of her palm, in every
    standing frame; a black slot below the left-hip buckle; *three black slits on the knit* (one on the collar's
    outer face on her right, two beside the zip below the V). The thinner outline did not remove them, so they
    are not outline shells of the layers underneath, or not only.
- New: "no dark game-style outline is visible on the outfit pieces" (alpha 64 is too thin, or the line is lost on
  dark leather); the leather now "flat and grey-brown ... almost no highlight", coat and trousers one tone
  (gamma 0.70 and the matt light map went too far together).

## The fifth game look (2026-11-17; `Testing/Acceptance/Previews/audit5_MavuikaCloudyWolf_2026-11-17/`): THE OUTFIT WAS MIRRORED

Same build as the fourth look. Left side, rear three-quarter and back on the character screen; then the screen
switched to another character and back by itself again and the agent stopped (second time, same pattern, during a
back-to-back burst of screenshots; the maintainer had said the game was free, so it is the tool or the game, not
a person: later briefs say to put `wait 2` between shots, re-select her and carry on).

- **THE GAME IS LEFT-HANDED: +x IS THE CHARACTER'S RIGHT.** "In game the long sleeve, pauldron and wolf emblem are
  on her anatomical RIGHT arm ... The reference renders show the opposite." Every earlier game shot shows it too
  (`audit_.../mcw_O_r0.png`: emblem at picture left with her facing the camera); two game agents and I looked at
  them for other faults and did not see it. `modkit.render` puts +x at the picture's right from the front, as a
  right-handed viewer would, so the offline sheets looked right. An `.fbx` through Blender is right-handed (his
  left arm at +x). Mod Building's "her right arm is at x < 0" for Raiden was read off the same renderer: check it
  in the game before relying on it.
  - The recipe was written "+x = her left" throughout. Fix without rewriting it: `mirror_mesh` mirrors HER on the
    way in (positions, normals, winding, and left / right vertex groups by `VG_SWAP`), everything is built in that
    mirrored world unchanged, and the finished mesh is mirrored back before saving. Her own pieces come out as
    they went in; his outfit lands on the correct side (his texture is mirrored with it: the wolf looks the other
    way).
  - The build's preview sheets use `grender` now (the view from the mirrored side, mirrored): they show what the
    game shows. `view.py` still shows the right-handed view: a mirror image of the game.
  - **For any asymmetric outfit, the first game shot answers one question before all others: which side is it on.**
- **The throat, identified at last.** In this look "a flat, pure-black horizontal band ... reads as a black
  cut-out"; in the fourth look, same build, two gold lobes either side of her neck with skin between. The kept
  strip of chest skin was 5 cm either side of her middle, narrower than the collar's opening: beside it one looked
  INTO the hollow top, black, or gold when her lit hair was behind it. The strip is 8.5 cm wide from y 1.42 up
  now (8.5 cm all the way down poked through the knit at the side of her chest). Offline this shows as green in
  the collar's opening on the culled close-up, which had been there since epoch 2 and was read as "the face is
  not drawn". Four wrong explanations came first (paint on her skin, his collar band, metal in the light map,
  an unknown draw of the game's).
- Still there: black parallelograms in a column on the coat at hip / thigh height below the bell, rhombi on the
  coat's front panel, black triangles in the holster stack, a notch at the hem. Right: the sleeve from the side
  and behind in four arm poses, the bell's mouth ("a dark leather inside with the gloved hand coming out"), the
  pauldron, the coat hanging straight, leather tone ("worn dark leather ... The coat and trousers separate").
- Offline finds while it ran: the 195 triangles re-wound in epoch 1 sit on trousers, holster, straps and boots
  (not the coat's front or the knit); re-winding is taken out (his winding is the outward one). 38 triangles of
  the built outfit are inside out after the maps (22 of them where the sleeve's top folds under the pauldron).
- For the sixth look the build has NO outline on the outfit (`MCW_OUTLINE=0`): if the black marks go, they are
  the outline pass; if they stay, they are the main pass.

## The sixth game look (2026-11-17; `Testing/Acceptance/Previews/audit6_MavuikaCloudyWolf_2026-11-17/`): a full one

Mirrored-back build, no outline on the outfit (the test), wider throat strip. Character screen from five sides
through the idle loop, overworld from four directions, two rounds of both movement pairs (a 1 s hold is a RUN).
The self-switch quirk did not occur with `wait 2` between shots. No HP lost.

- **Side: correct** (`g6_frontB08.png`, `g6_backC02.png`).
- **The black marks stayed with no outline, so they are not the outline pass.** Slot under the lower belt buckle,
  squares on the coat's front panel, a column of parallelograms on the coat's side, slits beside the zip and on
  the collar's edge, triangles in the holster stack, squares at knee and hip on the trousers in a run.
- **WHAT THEY ARE: THE GAME'S OWN EFFECTS MASK, READ THROUGH OUR UVs.** GI-Model-Importer-Assets lists a fourth
  component for Mavuika, `NatlanFX`, with one texture, "Shadow" (`MavuikaNatlanFXHeadShadow.dds`, hash
  `b6b1dc80`), for the Head / Body / Dress draws: red, green and blue shapes on black, laid out on HER suit's UVs
  (her glowing lines, cogs, triangles). The shader reads it with the mesh's UVs whatever mesh is bound. Mapped
  onto the outfit's UVs offline (one render, `flat_shade=1`), its green and blue shapes sit exactly where the
  black marks are: a green parallelogram at the hip, diamonds on the thigh, slits at the chest, blue triangles
  in the holster, green rectangles on the back of a trouser leg. It also explains the teal and red patches
  seen only while her hair is ignited. The identity mod has no section for it (an identity mod keeps her UVs).
  - The mod now replaces it: `[TextureOverrideMavuikaNatlanFX] hash = b6b1dc80 / this = Resource...Blank` with a
    64 x 64 black texture (black is the mask's own "nothing here": 87% of it). Loads with no warning.
  - **For any character: read EVERY component in the asset repo's `hash.json`, not only the ones the identity
    mod draws. A texture the game binds by itself is still read through your UVs.**
  - How it was found: the marks' places did not move across five builds that changed geometry, winding, inner
    copies and outlines, so they had to be fixed in UV space; then which texture? Five guesses before that
    (inner copies, outline shells, re-wound triangles, his alpha cut-outs, inside-out triangles) were each
    checked offline or in game and each explained only part or nothing.
- **The throat again:** a yellow / gold band with a tab in the relaxed pose, black in others, skin only from a
  three-quarter view. His atlas has 30 145 texels with alpha under 128 (light grey, not black): cut-outs his
  game draws with alpha. 42 small islands use them: the holster's square stud plates (fine as squares), and
  island 63, 24 triangles at his throat: the zip's pull, a flat plate that needs its cut-out to be a zip pull.
  Opaque, it is a light grey slab that goes yellow in the warm light and black in shade. It is dropped (small
  island wholly inside the collar's opening that reaches above y 1.45). A wider rule also took the zip's slider
  pieces at y 1.37 to 1.41: print what a drop rule drops.
- **A run:** "The coat does not hang from the hips. It is pulled with the trailing leg into a long, nearly
  horizontal slab reaching the back foot" (`g6_crop_ow_move1_b.png`). The coat's leg sources are thighs only now
  (`THIGHL` / `THIGHR`: the first two groups of each leg). Pink skin patches beside the zip in a run: the kept
  chest strip is set 5 mm under itself.
- Right: sleeve from the side and behind, bell and rim, pauldron seam, coat hang and hem standing, trousers over
  boots in a stride, holster silhouette, knit, buckles, emblem. Leather near black in daylight, coat and
  trousers one tone.

## The seventh game look (2026-11-17; `Testing/Acceptance/Previews/audit7_MavuikaCloudyWolf_2026-11-17/`), and what the marks REALLY were

Build: effects mask blanked, zip pull dropped, coat on thighs only, outline alpha 100.

- Better: the column of parallelograms on the coat's side "mostly gone", no squares on the trousers and no hem
  triangle in a run, and the coat "hangs from the hips and follows the forward (left) leg ... no longer pulled back
  to the trailing foot" (still "a wide stiff wedge", with a thin strap standing out as a line and a jagged hem).
- Unchanged: the slits beside the zip and on the collar's edge, the slot under the lower buckle, the throat piece
  (gold standing, black on the bike, yellow-green in ignite), dark triangles in the holster.
- **THE SLITS AND THE THROAT PIECE WERE BACK FACES, AND ONE RENDER SHOWED IT.** The built mod drawn in the game's
  view with `cull="mark"`: magenta sat exactly on the two slits beside the zip, the slit on the collar's edge, and
  a band with a tab across the base of her throat. **This game shades a back face by whatever its normal gives:
  leather-like on the coat's big inside, black in a fold, gold in warm light.** So a back face that can be SEEN
  from outside is a fault; `cull="mark"` in the game's view is the check, and green-background culled close-ups
  hide exactly this. Two different things made them:
  - *The slits:* his knit top has faces wound toward the body (undersides of the zip placket's folds). Triangles
    of the top above the waist, at the front, whose face points toward her body's axis are turned outward
    (winding, and the normals of vertices that mostly belong to such triangles): 97 triangles.
  - *The throat:* drawing the Body draw ALONE showed a band-shaped HOLE between the bottom of her neck's skin and
    the top of her chest's: **her model has no skin under her choker.** Through it one saw the inside of the
    top's back. Not paint, not his collar band, not metal, not hair, not a missing skin-coded triangle (selecting
    her skin by index-island changed nothing: the triangles do not exist). `make_throat_patch` builds the missing
    skin: radius per height and angle round her neck's axis from her own skin, the hole bridged by interpolation,
    2 mm under so her skin covers its edges, plain skin texel, her neck's weights. Seven game looks and five
    offline epochs had this spot on their lists; the render that settled it takes ten seconds. **When a fault
    survives two fixes, stop explaining it and draw each draw alone, back faces marked, at that spot.**
- The effects mask: blanking it removed the marks that came and went with pose and light (coat side, trousers in
  a run). It was not the cause of the static ones.
- The maintainer asked for the mod in a `Mavuika` subfolder: it is loaded from `Mods\Mavuika\MavuikaCloudyWolf`
  now (moved by hand, so GameView's journal no longer knows it: `reload --mod Mavuika` matches it; to unload, move
  the folder out by hand).

## The eighth game look (2026-11-17; `Testing/Acceptance/Previews/audit8_MavuikaCloudyWolf_2026-11-17/`)

Build with the throat patch and the top's inward faces turned out, loaded from `Mods\Mavuika\MavuikaCloudyWolf`.
Seven series through the idle loop on the character screen, four movement pairs. No HP lost, no quirk.

- **VERIFIED IN GAME: the throat** ("Bare skin only, in standing, ignite and the after-ignite pose, from the front
  and both three-quarters ... No band, piece, seam or lump": `g8_crop_throat_front_fA02_fA06.png`) and **the slits
  beside the zip** ("Gone in standing, ignite and bike poses"). The side is right, outlines on leather and knit
  are dark and thin again (alpha 100), the coat in a run "hangs from the hips and trails behind the legs ... Not
  pulled to a foot, not a rigid wedge", bell keeps its shape, coat / trousers / boots stay closed.
- **Still there (the open list below):** the slot left of the strap under the lower belt buckle; two or three
  rhombi on the coat's front panel in the bike pose; dark wedges between the holster's plates; dark quads on the
  warmer; one square on the coat's back in the overworld; a black block at the collar's front corner seen from
  her left three-quarter; a thin strap standing off the coat's front as a rod; pointed triangles at the back
  hem; a skin-coloured patch at her left armpit behind the sleeve's top; green / yellow-green flame-shaped
  patches on the pauldron during hair-ignite (they change between frames and go out with the hair: probably
  burning strands, not certain). Throat and arm are one flat peach tone, darker than her near-white face, with a
  hard step along the jaw.

## Ears, and the dark marks as back faces seen from outside (2026-11-18)

The maintainer: "fix them" (the dark marks), and "the ears on mavuika are gone".

- **The ears were dropped by my own throat fix.** Her skin was chosen by index-island of the Body draw, skin-coded
  and over 50 vertices; her ears are four pieces of 29 and 47 vertices (plus four of 3 to 5). The size limit is
  gone. A rule that chooses parts by size needs a render of what it dropped, every time it changes.
- **The repo layout moved under me:** other sessions made `Mods/GI/Mavuika/MavuikaCloudyWolf/` a folder of parts
  (`Mavuika`, `Motorcycle`, `Sword`), as in the game's `Mods\Mavuika`. This builder writes the `Mavuika` part
  now, and its clean-out deletes files only, not the sibling parts.
- **The dark marks, counted.** `seen_sides(pos, tris)` renders every triangle from 24 views outside her (8 yaws x
  3 pitches, z-buffered) and counts the pixels each shows from its front and from its back. Summed per piece,
  three holster plates showed 26 000 back-face pixels, more than everything else together; then back straps,
  the sleeve, the collar's inner edge.
  - Two rules by DIRECTION failed, measured: "face away from her body's axis", per open piece, turned 22 pieces for
    no change; "face away from each plate's middle" (the plates are sheaths, a front and a back sheet) turned
    791 triangles and made it worse, because a single strap has no middle.
  - What worked is the measurement itself: `face_the_viewer` turns every outfit triangle seen at least twice as
    much from its back as from its front (167 triangles, 13 800 back-face pixels), with the normals of vertices
    that mostly belong to turned triangles. The holster plates went from 11 400 / 8 750 / 5 800 back-face pixels
    to 330 / 240 / 710. Left: 217 triangles seen from both sides (the bell's inside, a back strap, the collar's
    inner edge), 3 200 pixels.
  - It costs about 6 minutes of the build (pure Python rasterising). Worth making faster.
- **Cut-outs:** his atlas is see-through (alpha under 128) at stud plates, strap holes and zip teeth, which his
  game cuts away; here they drew as solid light squares. Triangles lying mostly on such texels go (120).
- In the game the mod is loaded from `Mods\Mavuika\MavuikaCloudyWolf` beside the other sessions' parts; a reload
  there parses 60 sections, all clean.

## The ninth game look (2026-11-18; `Testing/Acceptance/Previews/audit9_MavuikaCloudyWolf_2026-11-18/`): partial, the game was in use

Character screen only. The agent stopped when the screen left the character menu by itself and a 3DMigoto reload
overlay appeared that it had not caused (`g9_chk3.png`: `Unrecognised entry: resource\gimi\normalmap ... = null`,
`= ref resource\gimi\... unless_null`: syntax this importer does not know, from ANOTHER mod's `.ini`; this mod's
own reload had parsed 60 sections under `Mods\Mavuika` with no warning). Mavuika was already at 8383 HP at the
start, so not from this look.

- Better: the black block at the collar's front corner is GONE (six shots, 30 to 60 degrees left); the holster's
  gaps are "mostly dark-brown shadow, with a few near-black pockets ... finger size" (were large black wedges);
  throat and zip still clean.
- Still there: the slot left of the strap under the lower belt buckle; a square and slits on the coat's front
  panel in the bike pose; dark quads on the warmer near the wrist; small black slots / a triangle at the coat's
  edges by the hip. A green-yellow dotted patch on the pauldron during hair-ignite (palm size) is reported
  again.
- Ears: not confirmed either way: her hair covered them in every pose it caught, no hole or black at either ear.
- Not seen: overworld, motion, the back hem, the holster from behind with hair lifted.

## The marks left after the back faces: pose-dependent (2026-11-18)

- Every remaining mark was looked for in the REST pose with three tests: back faces from outside (24-view count),
  triangles whose winding disagrees with their own vertex normals (764 of them, mostly on the holster's side
  pouch, none at the marks), and a close-up of the slot under the lower buckle (no back face, no hole: 0 pixels).
  Nothing is there at rest. The marks are in the POSES: standing idle, the bike, a bent wrist.
- **The slot under the lower buckle, the squares on the front panel in the bike pose, slots at the coat's hip
  edges:** straps, buckles and rings lying on the coat were weighted from her torso while the panel under them
  follows her thigh (`COAT_PELVIS`, thighs only); in a pose they part. Now every outfit vertex within 1.5 cm of the
  coat (below y 1.15, not trousers / sleeve / warmer / top) copies the coat's own weights there (the Ei lesson: a
  part that sits on cloth takes the cloth's weights).
- **Dark grey quads on the warmer near the wrist:** her own forearm (painted in the glove's leather) standing
  through the warmer when her wrist bends. Her forearm under the warmer is sunk 6 mm, none on the hand.
- A rest-pose check cannot prove either; the next game look is the check.

## The tenth game look, and the coat's weights smoothed (2026-11-18)

- `Testing/Acceptance/Previews/audit10_MavuikaCloudyWolf_2026-11-18/`: front only. Throat and zip still clean; the black square and
  slits on the coat's front panel in the BIKE pose still there, so copying the coat's weights onto the straps did
  not cure them. The look stopped when the character screen closed and reopened by itself after a drag.
- **That self-closing is a quirk, not a person.** It has happened in four looks (5, 9, 10 and the fourth), always
  after a drag on the model or a burst of shots, with the maintainer not playing. Game briefs now say: on it,
  wait, re-open the character screen with `key c` if needed, re-select her, and continue; stop only for a dialog,
  a reload overlay or HP loss.
- **The coat's weights had jumps.** Measured on the built buffers: the largest blend-weight difference along any
  edge of a triangle has a median of 0.48 on the coat (0.16 on the trousers), with 31 triangles over 1.2 at hip
  height where pelvis, spine and both thighs meet. Nearest-neighbour weights do that at a junction of groups. In a
  sitting pose such triangles fold over and show their back (black). The coat's weights are smoothed now over its
  own welded surface (12 rounds of averaging with neighbours; the hem below 0.6 m keeps its own), before the
  pieces on it copy them. Measure the same number for any new garment.

## The eleventh game look, and what the "quirk" really was (2026-11-18)

- `Testing/Acceptance/Previews/audit11_MavuikaCloudyWolf_2026-11-18/`. **Ears: present in game**, both, from the side and behind
  (`g11_crop_earL_profile.png`, `g11_crop_earR_back.png`). Throat, zip and collar corner clean from front and
  both three-quarters. Coat's back: no square under the holster. Warmer quads not seen (views not as close as
  before).
- **Still there:** the black bar and square beside the strap under the lower buckle in the BIKE pose (unchanged
  after the weights were smoothed: coat jumps over 1.2 went from 31 triangles to 0, so folding of the coat itself
  is not the cause either); the standing slot, smaller; black triangles between the holster's lower plates from
  her right. **New:** a small white "F"-shaped sliver between the two buckles in every pose: probably a hole
  left where cut-out triangles were dropped (a buckle's frame or a strap hole), showing the light piece behind.
- **THE "QUIRK" WAS OTHER SESSIONS.** The character screen closing and reopening, the character switching, the
  camera turning and 3DMigoto reloads with `Unrecognised entry: resource\gimi\... = null` warnings were other
  Claude sessions driving the same game at the same time: `ListAgents` showed "Mavuika bike to Fenrir
  motorcycle mod" and "Ei's Ultima Weapon sword mod" busy while the looks ran. The maintainer's "it's free" meant
  THEY were not playing. **Before a game look, list the peer sessions (`ListAgents`) and agree on the game with
  any that is busy; a game brief must not tell an agent to carry on through changes it did not cause.**

## The twelfth game look: the overworld at last, then another session's reload (2026-11-18)

`Testing/Acceptance/Previews/audit12_MavuikaCloudyWolf_2026-11-18/`. Four directions and walking steps (a 1 s hold is a walk from
the bike). Stopped by a 3DMigoto reload it did not cause, the same `Unrecognised entry: resource\gimi\... = null`
lines (another session's `.ini`), although the maintainer had given this session the game; the bike and sword
sessions still showed "busy". No HP lost.

- **Serious, new: walking, seen from her right, the coat's front hem is pulled toward the forward leg into a long
  pointed flap** (`g12_crop_ow_d1_rightside.png`), ragged at the hem, thin strap rods standing off it.
- A long diagonal strap stands proud of the coat as a straight rod from the waist to below the knee (front and
  left); walking from her left the coat flares like a wide skirt round both legs.
- Black slots and squares on the coat's front also STANDING in the overworld (under the lower buckle, mid-thigh,
  knee), and a black rectangle on the coat's back at thigh height (`g12_crop_ow_w1_back.png`).
- The bell, bent at her chest, reads as "a black bowl"; hanging down it is a normal open sleeve.
- From behind the coat covers her left leg and the right trouser leg shows: as in the reference (the back panel
  covers the picture-left two thirds there).

## Open / not verified

- Dark marks after `face_the_viewer` (audit 9): collar corner gone, holster much reduced; the slot under the lower
  buckle, the front panel's square in the bike pose, the warmer's quads and slots at the coat's hip edges remain:
  NOT back faces from outside by the 24-view count, so something else (next: draw those exact places alone).
  Pieces seen from both sides (bell's inside, a back strap, the collar's inner edge) are not handled.
- A thin strap of the coat's front stands out as a rod at rest and in a run; pointed triangles at the back hem;
  a skin patch at her left armpit behind the sleeve's top (the left arm has no skin under the sleeve).
- Flat peach throat and arm against her near-white face (one plain skin texel; the body stays plain).
- Flame-shaped green patches on the pauldron during hair-ignite: hair or cloth not settled.
- The coat and bell sleeve have no cloth bones. Not seen: mid-stride frames, a walk, sprint, jump, climb, combat,
  burst.
- The five offline epochs' minor items (strap end off her flank, strap knob at the bust, holster crowding, lumpy
  trouser outline, cuffs over the boots). The offline reviewers have NOT seen the builds after epoch 5.
- Her gloves keep their gold trims; her long hair passes through the holster; Cloud's sword is not part of this.
- STATE: the mod is LOADED in the maintainer's GIMI at `Mods\Mavuika\MavuikaCloudyWolf` (the maintainer asked
  for that subfolder; same files as `Mods/GI/Mavuika/MavuikaCloudyWolf` in this repo, the build audit 8 saw).
