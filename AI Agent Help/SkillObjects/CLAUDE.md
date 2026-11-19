# Skill objects: modding a thing a character summons (Mavuika's bike, 2026-11-17)

The first mod here that is not a character: `MavuikaCloudyWolf/Motorcycle`, Mavuika's bike (her skill object) made
into Cloud Strife's Fenrir. Recipe: `Tools/Builders/MavuikaCloudyWolfMotorcycle/build.py`; output
`Mods/GI/Mavuika/MavuikaCloudyWolf/Motorcycle/`. Pictures: `Testing/Acceptance/Previews/MavuikaCloudyWolfMotorcycle*.png`
(`_review` = reference model over the mod, same views; `_close` = culled on green; `_bones` = bone per vertex,
mod over game). References: `Images/GI/Mavuika/MavuikaCloudyWolf/Motorcycle/`.

## Where the source is

- **Skill objects live in `GI-Model-Importer-Assets/SkillData/<Name>/`**, not `PlayerCharacterData`. The bike is
  `SkillData/MavuikasBike`: one component, draws `Head` (11 248 triangles: the whole bike) and `Body` (944: the two
  glowing emblems at the back), one shared texture set (1024, BC7). It is not in AGIDMGen's pre-generated `Mods/`.
- **AGIDMGen still makes its identity mod**: `GIMIIdentityModGenerator().generate(<SkillData folder>, <out>,
  name="MavuikasBike")` (with `AGIDMGen/api/src/py` on `sys.path`). The dump is the older single-vb0 kind
  (stride 92: position, normal, tangent, blend, colour, uv, uv2) and the generator splits it into Position 40 /
  Blend 32 / Texcoord 20. The recipe does not need it: `modkit.gimi.load_dump` reads the dump text directly and
  the `.ini` is written from `hash.json`.
- **Trap: a Windows Python given a Git Bash path** (`/c/Users/...`) writes to `C:\c\Users\...`. Pass `C:/...`.
  (A stray `C:\c\` from this was left for the maintainer to delete; the shell refused to remove it.)
- **Hashes are not yet confirmed in today's game** (the assets repo's dump may be older). Check in game.

## The bike, measured (game coordinates: Y up, front +Z, metres)

- 14 247 vertices; 16 bones; **99.98 % of vertices ride exactly one bone** (rigid parts), so a new part needs one
  bone per part, not blended weights.
- Bones: 6 body; 12 front wheel, 13 rear wheel (each exactly the wheel); 9 handlebar with grips; 10 dash;
  14 rear swing arm; 15 front cowl and fender (z 0.175 .. 1.41); 7 / 8 the front fork legs; 11 a front piece over
  the wheel; 0-5 the big side panels in mirrored pairs (whether these move in game is not known yet).
- Axles: rear (0, 0.367, -1.019), front (0, 0.367, 0.825); wheel radius 0.411; ground -0.044.
- Seat top ~0.96 at z -0.5 .. -0.3 (the lowest top between the rear hump and the tank); tank top 1.18 at z 0;
  grips: centres (+-0.347, 1.090, 0.318), cylinders found by PCA on bone 9's vertices beyond |x| 0.26.
- **Light map = material band (alpha) + material class (RGB)**, AGRemap's lesson ("a GIMI lightmap's alpha is a
  material band", "a band legend is per object": `Fix-Raiden-Boss/AI Agent Help/VGRemaps` and `CreatingRemaps`).
  The bike's legend, read off its own texels at its own vertices (2026-11-17):

  | alpha | rgb | on the original |
  | --- | --- | --- |
  | 0 | (68, 0, 128) | tyres (outer 40 % of the radius) and the rubber grips, nothing else |
  | 134 | (255, 0, 165) | painted bodywork, painted rims, the handlebar's metal |
  | 134 | (136, 0, 120) | dark grey metal |
  | 135 | (255, 170, 204) | gold and silver trims: the METAL class (green 170) |

  132-138 is ONE band (BC7 spreads it; the gold sits at 135). Green is 0 except on metal.
  The mod maps: paint and the tail light -> paint; gunmetal -> dark; chrome exhausts, steel, engine fins, rim,
  bronze -> metal; rubber, leather (no original equivalent: the soft class, as the grips) and the exhaust mouths ->
  band 0. The first builds took GROUP medians instead (the swing arm's texel for "dark", the handlebar's for
  "bright"): the right bands, but the black paint on the dark-metal class and every bright metal on the paint class.
  Changed 2026-11-17 at the maintainer's request.
  **IN GAME the metal class GLOWED**: the exhausts and engine lit bright orange-red even idle (a GameView shot,
  `20261117-231421-085_g0`). Its GREEN (170) is a GLOW mask (green marks exactly the original's glowing gold trims and
  decal lines). The mod's metal is now (255, 0, 204, 135): the metal band and blue, no glow. A class copied whole
  carries every channel's meaning, glow included.
- Vertex colour (255, 128, 128, 128) on 86 % of vertices.

## An outside model with no UVs (the Fenrir .stl)

- The maintainer's model is a 3D-print `.stl` of the FFXIV "SDS Fenrir" mount: ASCII, 10 111 triangles, no UVs,
  facets with zero normals, Y up, front +Z, in printer millimetres (49.6 long). Weld at 1e-3 and the parts come out
  as closed islands (wheels are lathe meshes of 32-vertex rings).
- **Rider-fixed places decide the map, not the model's proportions.** Her riding animation is the game's: the
  wheels spin round bones 12 / 13, so each wheel must sit exactly on the game axle at the game radius (moved
  rigidly, own scale); the rest maps z so axle lands on axle, y so the rear axle lands, a linear lift for the
  front axle, and the top round the seat raised to the game's seat height. The result is ~26 % taller for its
  length than the Fenrir; that is the price of her pose.
- **Grips are made, not moved**: tubes and rubber grips exactly on the game's grip cylinders, bars down to the
  tank.
- **Texture without an unwrap**: each material is a 256 px swatch in a 1024 atlas, and a corner's UV is the
  swatch plus a place chosen by its normal (v from n.y, u from the heading): a painted reflection (chrome's
  horizon line) that reads the same from every side, with no seams to hide. Normals are smoothed within 42
  degrees and split at creases, and a vertex is split wherever material or normal differ.
- **Tyre vs rim on coarse lathe meshes**: by RING, not by triangle centre. The tyre starts at the ring where the
  side wall is widest between 0.5 and 0.75 of the radius; a triangle is tyre when all three corners are on or
  outside it. The centre test cut a saw-tooth star round both rims.
- Bones per part: wheels and anything wholly inside a wheel on the wheel bone, the made handlebar on 9, every
  other part on ONE bone by majority of its nearest game vertices among 6 / 14 / 15; 15 (the cowl, which may
  steer) only for parts wholly ahead of z 0.17, so the long front arms stay on the body.
- The Body draw (glowing emblems) is given one degenerate triangle: it draws nothing.

## Reviewer epochs, first batch (2026-11-17; sheets `_review`, `_close`, the main sheet, `_bones`)

- **Epoch 1** (11 faults). Materials did not read (everything one dark blue-grey, no engine visible); the
  seat/tank top crumpled with a fin at the join; the left rear exhaust a flat blade; exhausts towering over the
  handlebar; the long front arms on the cowl bone (would swing if it steers); the front tyre "doubled"; patchy rims;
  the front fender MISSING; exhaust mouths flat; grips read as chrome; faceted paint.
  Causes found and changes: the front wheel is scaled 18 % more than the body map, so it SWALLOWED its fender ->
  parts hugging a wheel (never inside 0.8 r, median under 1.3 r, centred) take the wheel's map but the body's bone;
  the seat lift followed each column's own top -> one lift amount above one height band; the exhausts got the
  body's 26 % vertical stretch -> each squashed back by SZ / SY about its base; the tube caps were inside-out
  (magenta in `view.py --mark`) -> every triangle wound outward on its own; new materials: bronze-grey lower frame,
  light steel under the tank, dark exhaust mouths, brown-black leather, lighter gunmetal; creases at 60 degrees.
  No part of the STL is inside-out (all signed volumes positive), though many have a few open edges.
- **Epoch 2** (11 faults). Saw-tooth spikes of light grey on black under the seat and brown/grey triangles
  alternating on the seat back: materials chosen PER TRIANGLE (engine box, up-facing seat) on the STL's long thin
  triangles. Changed: materials are decided PER PART (a part is engine when over half its triangles are in the
  engine box); the seat is a MADE saddle (a flat-topped, round-sided grid just above SEAT_Y, ends dipping into the
  tank and the rear hump; the body under it is lifted to SEAT_Y - 0.03 so they never share a surface).
  Exhaust tip rings floated off their cans: each part had been squashed about its own base -> one base per side,
  and every small part centred in that side's exhaust box squashed with them. The swing arm's bronze read as
  cardboard -> greyer; chrome's horizon band softened (black / white blocking). The engine got painted fins: a
  swatch read by HEIGHT across the engine (linear v, the stripes are in the texture). The front fender now rides
  the cowl bone (turns with the front), nothing else does. TRAP: zeroing a bone's votes and taking argmax of an
  all-zero vote gave bone 0 (a side panel) -> fall back to the body.
- **Epoch 3** (10 faults). The tank still crumpled; the reviewer saw that the MAPPED source was already lumpy,
  so the damage was the map's: the seat lift raised everything above one height while the parts lying under and
  on the tank (hoses, ribs, covers) sat across that band, so they slid against each other. **The lift is off
  (`SEAT_LIFT = 0`)**: the made saddle is 30 cm deep and fills the Fenrir's dip up to her seat height instead.
  Also: the toothed rail was black because the arms' rule matched it first (rules reordered, it is bronze-grey);
  everything read black or near-white -> darker steel and fins, exhausts in worn brass-gunmetal as in the FFXIV
  render; exhaust mouths per can (faces looking back in its rearmost 15 %); every short part whose median distance
  from the front axle is under 1.3 r rides the cowl (a cover hugging the tyre stayed on the body), and the long
  front arms and rails BLEND onto the cowl over their last 45 cm to the hub (they hold the hub; if the front turns
  they bend with it). The bones sheet now has fixed colours and a legend (two bones had looked alike).
- **Epoch 4** (11 faults, mostly materials). Paint read as flat slate grey, one mass with the steel; exhausts
  beige "cardboard" and the brightest thing on the bike; the front fender read as a second tyre; the bronze rail
  and the engine fins barely read; blank rims; the arms' 45 cm weight gradient read as "will bend"; bare risers
  read as antennae. Changed: paint navy-black with ONE sharp highlight band in its swatch (glossy, not grey);
  exhausts dark gunmetal with brass only in the light; steel and fins brighter (fins to 182: still under the
  ~225 where colours bloom); a stronger bronze; fenders gunmetal; the hub (rings inside 0.34 r) dark; the arms
  blend onto the cowl only over the last 17 cm; a paint clamp block at each riser's base.
  Not changed (the source's own shapes): the horn-shaped rear pieces, the tail hump's height.
- **Epoch 5** (9 faults; the early stop). Nearly all VALUES: exhausts still tan, engine and fins pale, the front
  wheel's side cover light grey (it is the front wheel island's inner part, which got the rim colour), the rail
  olive, no gunmetal mid-tone. Applied after it, NOT reviewed (the fifth epoch is the last): darker gunmetal
  (fenders, hubs, risers), blackened-steel exhausts with a thin brass highlight, gunmetal mechanics, dark fins with
  bright edges, a warmer bronze, the front wheel's inner part gunmetal. Disagreement kept open: epoch 3 asked the
  front arms to follow the steering at the hub, epoch 5 asked them rigid on the body; they blend over their last
  17 cm. Whether the game steers bone 15 at all is not known.

## The first game look (2026-11-17, a game subagent; `Testing/Acceptance/Previews/audit_MavuikaCloudyWolfMotorcycle_2026-11-17/`)

- **The mod shows**: the hashes from the assets repo are today's (also proven by a frame dump already on disk,
  `GIMI/FrameAnalysis-MavuikaBike-2026-11-17-195222`: ib `9bec497f`). No red bodywork is left. `cmp1` is the
  original (F9) above the mod.
- **THE WHOLE BIKE GLOWED with orange zig-zags and blotches** that follow the ORIGINAL bike's flame decals, not the
  Fenrir's panels (`crop_back.png`, `crop_q1.png`). The bike's shader reads a glow mask through **uv2
  (TEXCOORD1)**; the recipe had copied each vertex's uv2 from the nearest game vertex, so it drew the old decals
  over the new shape in pieces. Not the extra textures: the draw also binds t3 `b0e08915` (a shading ramp, 256),
  t4 `3470cc74` (BC6H) and t5 `8b904bb1` (a generic flame noise), and none is a decal. Changed: every vertex reads
  ONE uv2, the original rear tyre's median (0.8075, 0.4265), which does not glow. The same trick as the Body draw's
  one-texel lining in the first mod. CHANGED, NOT YET SEEN IN GAME.
- Paint read as pure black (about 15-25) -> its base lifted to (30, 34, 52); the front fender read light grey
  (90-110) -> gunmetal darkened. The saddle is hidden under her coat and hips from every angle shot (expected).
- The game's own effects (the golden wing fin, chevrons, light blades, sparks) stay where the original's fins were,
  30-50 cm above and outboard of the Fenrir's tail: they are effects, not the mesh.
- Weak: her near hand looked about 10-15 cm inboard of its grip. Not settled.
- Not seen: riding (the first burst drove up a cliff and she fell; during the second the game showed Eula's
  character screen, which the agent had not opened, so it STOPPED as the rules say); wheel spin; steering.

## The second game look, and what the glow REALLY was (2026-11-17; `audit2_MavuikaCloudyWolfMotorcycle_2026-11-17/`)

- With one uv2 everywhere **the glow was unchanged**: lava blotches over the tank, fenders, arms and exhausts, strong
  while riding (the Nightsoul state), weaker when idle. The uv2 diagnosis was WRONG (kept anyway: harmless).
- The blotches were STRETCHED along surfaces, as a texture read through this mod's normal-based UVs looks. In the
  maintainer's frame dump the bike draws twice per frame: the main shader (t0 normal, t1 diffuse, t2 light map)
  AND an **effect pass** (draws 123/124, ps `4795b16ca8d1207c`) that binds the DIFFUSE at t0 and t5, the LIGHT MAP
  at t6 and a flame noise (`8b904bb1`) at t1 / t7. The `.ini`'s per-slot `ps-t0..2` lines (right for the main
  shader) put the wrong textures in that pass and left the ORIGINAL diffuse at t5, whose alpha is the original's
  glow mask (the decal lines and orange patches; its light map's green marks the silver decal lines).
- **Change: the three original textures are replaced BY HASH as well** (`[TextureOverride...ByHash]`, `hash =
  040624ff / 52b74fb4 / 60f282a6`, `this = <our texture>`), so every shader that binds them gets this mod's,
  whose diffuse alpha is 0. Checked: those sections parse in `d3d11_log.txt`.
- LESSON: for an object with an EFFECT state, look at every draw of its ib in a frame dump (`ls | grep ib=<hash>`
  and each draw's `ps-t*` files) before deciding what a texture slot is. `ps-tN = ...` lines only cover the shader
  they were written for; replacing a texture by hash covers all of them.
- Also from this look: in the idle animation she sits on the bike and the paint reads navy-black; no tearing in
  four short rides with steering; wheels and the steering front hidden by tall grass.

## The third game look and a dump of the MODDED bike: the by-hash swap never fired (2026-11-17)

- Audit 3 (`audit3_MavuikaCloudyWolfMotorcycle_2026-11-17/`): the glow unchanged after the by-hash sections.
  Two fixes had been guesses from a dump of the ORIGINAL bike; the maintainer allowed a dump of the modded one while
  riding: `GIMI/FrameAnalysis-FenrirModRiding-2026-11-17-214513` (16.7 GB, 534 draws).
- **A modded draw is not filed under the original ib hash** (`ib=9bec497f` finds nothing: the file names carry the
  bound buffer's hash). Find the object by its SHADER hashes instead (here vs `1cbd80e442c32196` main,
  `0242e309e62d76ba` effect).
- In the effect draws (165 / 166, ps `4795b16ca8d1207c`) t5 was still the ORIGINAL 1024 BC7 diffuse (alpha mean 12.9:
  the glow mask) and t6 the original light map. **3DMigoto applies a by-hash `this =` only in slots that something
  runs `checktextureoverride` on**; GIMI does it for character shaders (why the outfit's NatlanFX blank worked), and
  nothing did for the bike's effect shader.
- Change: each draw section runs `checktextureoverride = ps-t0` .. `ps-t8`, and the per-slot `ps-t0..2` lines are
  gone (in the effect shader t0 is the diffuse and t1 a flame noise; the per-slot lines had put the normal map and
  the diffuse there). CHANGED, NOT YET SEEN IN GAME: the maintainer was playing when it was ready.
- LESSON (the memory "no fixed claim without seeing the fault"): two "fixes" were reported as changes, not verified,
  and both failed in game. The dump of the MODDED object answered in one look what two guesses had not.

## The fourth game look: the glow is GONE; a steering afterimage (2026-11-17; `audit4_MavuikaCloudyWolfMotorcycle_2026-11-17/`)

- **VERIFIED IN GAME**: with `checktextureoverride` on t0-t8 and the textures swapped by hash, no orange lava
  idle (day and night) or riding straight (`idle_day_crop.png`, `ride_mount_side_crop.png`): navy-black gloss, dark
  fender, finned engine, bronze rail. No new faults from the texture change (no tints, black faces or lost
  outlines).
- NEW, only while STEERING: a see-through red-orange copy of the ORIGINAL bike over the front half, with the
  original's pointed nose past the Fenrir's fender and an arc over the handlebar (`steer_ghost_night_crop.png`).
  Likely a separate afterimage draw of the original mesh (another ib or shader) that the mod does not override.
  Next: a frame dump while holding A during a ride, find that draw, skip it or feed it the Fenrir's buffers.
- Exhausts read dull brown-black (minor). Wheels spinning: still not seen (grass).

## A dump while steering, MISSED (2026-11-17)

- `GIMI/FrameAnalysis-FenrirModSteering-2026-11-17-220720` (10.6 GB) has NO draw of the bike (no vb `4fa81127`, no
  bike shader). The turn was held with `key w+a --hold 4000` started in the background and `dump` sent 1.2 s later;
  GameView's helper most likely ran them ONE AFTER THE OTHER, so F8 came after the turn and the ride had ended.
  To catch a state that lasts seconds: put the held key and F8 in ONE `do` sequence? (`do` has no key-down either);
  better, ask the maintainer to hold the turn and press F8 themself, or bind the dump to a moment the state lasts
  (the idle afterimage, if there is one).
- The maintainer was playing right after it (the game had moved to another region): stopped there.

## The steering "afterimage" is the GAME'S effect, not the bike (the maintainer's dump, 2026-11-17)

- The maintainer held a turn and pressed F8 (`GIMI/FrameAnalysis-2026-11-17-221506`). Every draw of the bike in that
  frame (162/163 main, 172/173 effect, 190/195, 357-372 later passes) uses THIS mod's 10 258 vertices: the
  original mesh is not drawn. While steering, the effect pass also binds an effect texture `892554c9` (512 px) at
  t0 / t2, which is the game's, not a bike texture.
- The "red copy of the original bike with a pointed nose and an arc over the handlebar" is **draw 342**: an effect
  mesh of 204 vertices shaped as a BEAST'S HEAD (eye holes, a toothed snout, an arched crown), 1.5 x 1.1 x 2.5 m,
  drawn over the front of the bike when it turns. It shares its vertex and index buffers (vb `911ff708`, ib
  `9ccbfb88`) with the game's other particles (sparks 337, a trail 345, petals 335), so it cannot be skipped by
  hash without hiding those too. **Decided: left as the game's effect**, like the golden wing fin and chevrons.
- HOW it was found: list the frame's draws whose vb0 POSITION box is bike-sized (a script over every
  `*-vb0*.txt`), then render each candidate with `modkit.render`. Draw 171 (3 917 vertices) looked likely and was
  her HAIR; the render settled it in seconds.
- `o0` of a draw here is a NORMALS buffer (the game renders deferred; the image is upside down): a before / after
  diff of `o0` cannot show colour.

## Open (2026-11-17)

- Glow fixed and seen in game (above); the steering "afterimage" is the game's beast-head effect (kept). Open: wheel spin (bone 15 steers and 14 barely moves: see "The steering axis" below); the Body draw's glowing emblems are gone (one degenerate triangle).
- The front fender shroud reads light grey from the side; the source's horn-shaped rear pieces and the tall tail
  hump are kept as the model has them.
- Textures are uncompressed RGBA8 (5.6 MB each at 1024), one set shared by both draws.

## The fifth game look: materials by the bike's legend, no glow (2026-11-17; `audit5_MavuikaCloudyWolfMotorcycle_2026-11-17/`)

- With metal = (255, 0, 204, 135): **no glow on the body, idle or riding** (`idle_rear_crop.png` at the angle of
  the glowing `g0` shot). Paint glossy with sharp highlights; engine fins read as metal ("better"); tyres, rim good.
- Looks, not codes: the bronze swing arm read flat tan, the fenders flat light grey, the exhausts maroon. Diffuse
  only changed: bronze (118, 96, 70) / (34, 28, 22), gunmetal (64, 67, 76) / (14, 15, 18), exhausts (124, 120, 100) /
  (20, 20, 22). Seen once after, in daylight from her left (`after_colour_tweak_day_left.png`, taken by the
  building agent): fenders dark, no glow. The bronze arm (her right side) not looked at since.

## The steering axis, measured: the handlebar floated (2026-11-18)

- Fault (the maintainer, `FloatingSteering.png`): while steering, the riser clamp blocks lifted off the tank. The
  risers ended on the BODY 18 cm behind and 9 cm beside the axis the game turns the bar about, so they swung out.
- **Bone matrices are in the dump**: the character skinning pass (vs `653c63ba4a73ca8b`) binds the bones at
  `vs-t0` as 3x4 float32 rows, one per bone (the bike's: 16 x 48 = 768 bytes, draw 4 of
  `FrameAnalysis-2026-11-17-221506`). Each bone relative to the body, `inv(M6) @ Mi`, gives its motion:
  - bones 9 (handlebar), 15 (cowl), 7, 8 (forks) and 12 (front wheel) turn by ONE rotation about the axis
    (0, 0.838, -0.546) (raked 33 degrees back), which passes through the front axle. So bone 15 DOES steer.
  - 12 also spins about x (the wheel turning); 14 (swing arm) barely moves; the side panels 0-5 swing 43 degrees about
    x through (0, 0.42, -0.59): they fold, which is why the mod leaves them empty.
- Fix (in the recipe): a steering COLUMN coaxial with that axis (sunk 15 cm into the body, so its joint with the
  body is unchanged by a turn), a top clamp across it, and the risers end on the clamp. Rule: anything on a steering
  bone must meet a body-bone part on the axis, or be wholly in front of it.
- The preview `_steer.png` turns the steering bones by +-25 degrees about the axis, for the mod and for the game's
  own bike (the axis check: its cowl and bar stay on the frame). Not yet seen in game.
- A reviewer then saw the steered grips "sinking into" the fixed tank in quarter views. A smooth dent pressed into
  the tank under the bar's sweep only crumpled its top, and close side renders with and without it showed the grips
  pass OVER and BESIDE the tank, never inside. The dent was removed. Lesson: settle "buried?" with a close render
  from the side, not a 3/4 view, before reshaping the body; and a test needs a control (the first burial test read
  zero with and without the dent, so it proved nothing).

## Rear details and two colours (the maintainer, 2026-11-18)

- Asked for: details at the exhausts and a red tail light; then (`PartsSameColour.png`) the tank's side pipes
  silver and the front arms' lower half a different grey, as on the FFXIV reference.
- `rear_details()` adds bright steel tip rings on the cans' mouths (the "hole" faces behind z -1.2, mouths wider
  than 6.5 cm skipped: that one was the can's shoulder round both tips) and a red bar light across the tail hump's
  back at y 0.95. Only one side's cans have round mouths; the other can is one angular block, left without rings.
- The tail light's light-map texel is the bike's METAL class WITH its green 170 kept (`lm_src["glow"]`): green is
  the glow mask, so it should light red in the Nightsoul state (not yet seen in game).
- Silver (11) for the three ribbed pipes per side (parts picked by their centre box), gunmetal for the cavity
  behind them, "panel" grey (12) for the lower 60 % of each long front arm (per 5 cm slice). The chrome "horizon"
  curve made the pipes dark on side-facing normals; silver uses a plain bright gradient (toned to 170 at the top
  after a reviewer called 192 near-white).
- One light reviewer pass (the maintainer: "for epochs, just use light iteration"). Fixed from it: the silver
  tone, the tail light narrowed to +-4.5 cm and sunk 3 cm. Left, as older design or not asked: the panel line on
  the arms is ragged (the STL's long triangles), the brown seat and bronze swing arm, a grey sheet under the tail, the
  left exhaust a black block with a hook, the stem cylinder above the cowl, the front fender reading as a second tyre.

## The sixth game look (2026-11-18; `audit6_MavuikaCloudyWolfMotorcycle_2026-11-18/`)

- **VERIFIED IN GAME**: steering left and right, the handlebar stays attached; nothing floats (05, 08-10, 13, 14).
  The tank pipes read silver and the arms' lower panel grey, apart from the body (01, 05, 16). The tail light shows
  red parked and riding, day and dusk, a slight glow, no excess bloom (02, 06, 16).
- How the agent captured mid-turn: a separate non-elevated script grabbed the screen while the helper's `do` held
  the keys; holding F9 in the same key chord shows the vanilla bike in the same frame (13, 14).
- Faults, and what was done:
  - A light grey flat slab round the tail light (04, 15): the rear fender box that rises to the hump, in gunmetal;
    its large flat back caught the sky like the fenders once did. Now body paint (rule: a rear hug part reaching
    above y 0.85). Not looked at in game since.
  - Exhaust tips read as flat pale matte rings: they now have their own "tip" swatch, chrome horizon with strong
    contrast. The exhaust chrome's sky is held to 45 %, so the box-shaped left can's flat lid cannot go pale.
    Not looked at in game since.
  - The inside grip may sink into the tank at full lock (unconfirmed: motion blur, her fist covers it). The offline
    check at +-25 degrees showed clearance, so the game may turn further. Open.
  - While riding, the game's own effects (a yellow lozenge on the front, the original's spiked wheel ornament, a
    reddish streak) lie over the bike and make it read maroon; the vanilla bike shows them too. Kept.

## Rear: tail lens, every exhaust end, a license plate (the maintainer, 2026-11-18, `MotorcyleBack.png`)

- **Orientation of `modkit.render` on this bike: yaw 180 looks at the BACK, yaw 0 at the front.** Several sheets
  this day were drawn at the wrong end first; label the first render of a session by what it shows.
- Tail light: real bikes set an integrated lens into the tail cowl, following its taper (searched: a tail-lamp
  patent, TST Industries, Eagle Lights). Made as `surface_patch()`: rows laid on the hump's back by rays from
  behind (`ray_hits`, Moller-Trumbore), each row as wide as 74 % of the hump there. A black frame (86 %), the red
  "glow" lens, a brighter "led" strip. Two faults found by looking and fixed:
  - A ray through a small hole put a grid point at infinity and drew a dark stick. Misses are now filled from the
    row's other hits.
  - A thin diagonal ROD of the source model crosses the hump's back and showed between the grid's points. Each row
    is now flat at the rearmost of 41 rays across it, so no body is in front. The plate needed the same treatment:
    dense rays (31 x 17).
- Exhausts: rings on every round mouth behind z -1.05 (the upper right can was skipped by a -1.2 limit), each with
  a dark disc inside. The left can is a box with no mouth: two pipes with rings come out of its back, where rays
  from behind meet it. Its long axis ends in a narrow top corner, and pipes put there first came out 1 cm wide.
- License plate: a 19 x 10 cm quad upright under the lens, on a black bracket box back to the body. Its texture
  is painted into the spare swatch 15 by PIL (`PLATE_TEXT` "MAV 999" in blue, "Natlan" small above, "The Fire
  Nation" small below, four bolt holes, plate grey 192, kept under 200 against bloom).
- **TEXT READ MIRRORED IN GAME (the maintainer looked, 2026-11-18) while `modkit.render` showed it right: the
  offline render is LEFT-RIGHT MIRRORED against the game.** u now runs from -x to +x (seen from behind in game,
  +x is on the viewer's right), and the offline render shows the plate backwards. Anything with a handedness
  (text, logos, an asymmetric decal) must be judged in game, or in a render flipped in x.
- After one light reviewer pass: the tail lens got three LED rows (one stripe read as a flat sticker). Left as
  noted: the plate has no hanger or plate light, the right twin tips are shallow from straight behind, magenta
  slivers (back faces) at the rear fender's edges, the hook pipe and the bronze arm seen from the side.
- Built, reloaded with no warnings. The mirrored plate fix is not yet seen in game.
- Exhaust holes (the maintainer: they read "the same colour as the exhaust"; and "glow red when her skill is
  active"): the dark disc sat 1 cm down the pipe and was hidden, so it now sits just inside the ring. The "hole"
  material is near-black with the GLOW light-map class (metal class, green 170 kept). The glow is the game's own
  Nightsoul mask: it lit the navy paint orange earlier, so its colour is the game's fire, not the diffuse, and it
  was stronger riding than idle. The bike only exists while her skill is up, so "dark when off" is seen only as
  the weaker idle glow. NOT yet seen in game: whether it burns red-orange, and whether it is stronger with the
  skill's riding state.
- **Seen in game (the maintainer, and audit 7 `02_parked_rear_day_closeup.png`): the glow-class holes burned
  bright RED even parked, like the tail light**, with a dark near-black diffuse under them. So this glow's colour
  does NOT come from the diffuse, and it does not wait for the skill state. The plate reads the right way round.
- Experiment now built (the maintainer wants "orange like Mavuika's fire", only with the skill):
  - The main pass holes have no glow (light map class rubber).
  - The Nightsoul EFFECT pass (`[ShaderOverride...NightsoulFX] hash = 4795b16ca8d1207c`, `filter_index = 4795`)
    gets its own textures through `if ps == 4795` in the draw sections: `FXDiffuse` with orange-fire holes, and
    `FXLightMap` with the glow class on the holes. Parsed with no warnings (1 ShaderOverride).
  - Seen by the maintainer: parked, the holes are BLACK (good). With the skill on they STAYED black, so the light
    map's glow class did nothing in the effect pass.
  - Next try, built: the effect pass's glow is the DIFFUSE ALPHA (the original's alpha made the lava blotches
    there, audits 1-2), so `FXDiffuse` has alpha 255 on the hole swatch and 0 elsewhere. Not seen yet.
  - Seen by the maintainer: still black with the skill on.
  - **A mistake found in the old riding dump:** the effect draws (172/173 of `FrameAnalysis-2026-11-17-221506`)
    bind the GAME's effect texture `892554c9` at t0 / t2, flame noise `8b904bb1` at t1 / t7, the bike's diffuse
    at t5 and its light map at t6. The first two tries also set t0 to the bike's diffuse, which (if the condition
    fired) replaced the effect texture and may have killed the glow. Now only t5 / t6 are swapped.
  - The pass is now recognised by `if ps == 4795 || $fx_pass == 1`. `$fx_pass` is a `[Constants]` global that
    the ShaderOverride sets (and resets with `post`), in case `ps ==` is not a test this 3DMigoto supports.
    Parsed with no warnings. Not seen yet.
  - Still black. **The maintainer's dump while riding with the skill (`FrameAnalysis-2026-11-18-050049`)
    settled it:**
    - The swap WORKS: the Nightsoul draws (106 Body, 107 Head) have the FX textures at t5 (holes orange
      248, 135, 41) and t6 (holes on the glow class). Draws are found by `*ps=4795b16ca8d1207c*`, and a mod
      resource has no hash in the file name: read its texels at a known swatch to tell which one is bound.
    - **That pass is not an overlay: it is the bike's G-BUFFER pass in the Nightsoul state** (deferred). o0 is
      normals, o1 colour, o2 material, and **o4 an EMISSION MASK**: the tail light and her hair are white there.
    - **Diffuse ALPHA 255 made the holes BLACK in o1 and 0 in o4**, so alpha is not a glow mask in this shader
      (the "lava from the original's alpha" was a wrong reading). The tail light (alpha 0, glow class) glows.
  - Now: the FX holes are made like the tail light (alpha 0, glow class), with orange diffuse. Untested: tries 1
    and 2 were spoiled by the t0 override and by alpha 255. Open: does the emission take the diffuse colour (the
    holes burned RED in the main pass over a near-black diffuse, so maybe not)?
  - How to read a G-buffer dump: crop the bike from o1 and o4 and flip them vertically (the targets are stored
    upside down).
  - Still black with alpha 0. **All the bike's draws in that frame** (find them by `*-vb0=4fa81127-*`): 96 / 97
    MAIN (ps `d2d910688a4b3625` / `b2043833b7d3b2ef`: diffuse at t1 and t5, light map at t0 / t2 / t6), then
    106 / 107 Nightsoul, then 128 / 134, 288 / 292, 299 / 303. **The Nightsoul pass comes AFTER the main pass
    and its holes in o1 are the main pass's (11, 7, 8)**, so it does not overwrite there. What shows, glow
    included, is the MAIN pass, which is why the glow class there burned even parked.
  - **Now: a skill-on switch.** The Nightsoul ShaderOverride only sets `$ns_flag = 1`. `[Present]` carries it into
    `$ns_active` for the next frame and clears it. The by-hash diffuse and light map sections pick the FX set
    (holes orange, glow class) `if $ns_active == 1`, else the plain set. Parsed with no warnings. Not seen.
    If the holes then glow parked too, the Nightsoul shader also draws while parked. If they glow red, the main
    pass's glow colour is not the diffuse.
  - **Seen by the maintainer: the holes glow ORANGE**, so the main pass's glow takes the diffuse colour. Why the
    first try (near-black diffuse, glow class) burned red is still unexplained. **But they also glowed while she
    was IDLE without the skill: the Nightsoul shader draws when idle too.**
  - Now the flag waits for a texture. The Nightsoul shader's t0 held the game's effect texture `892554c9` in
    both skill-on dumps (2026-11-17-221506 and 2026-11-18-050049), and the bike's own diffuse `040624ff` in the
    first dump of the bike (2026-11-17-195222; her state then was not recorded). So `[TextureOverride...
    NightsoulEffectTex] hash = 892554c9, filter_index = 892554`, and the ShaderOverride runs `if ps-t0 ==
    892554` → `$ns_flag = 1`. Parsed with no warnings, but **it NEVER fired: no glow with the skill on** (the
    maintainer). Do not use `ps-tN == filter_index` in a ShaderOverride here.
  - Now: the effect texture's own section raises the flag (`[TextureOverride...NightsoulEffectTex] hash =
    892554c9`, `$ns_flag = 1`). It is run by the `checktextureoverride = ps-t0` that the bike's draw sections do
    in every bike draw, the same route the working by-hash swaps take. No ShaderOverride is left.
  - **WORKS (the maintainer, 2026-11-18): holes black idle, orange with the skill.** Lessons:
    - The visible bike (glow included) is the MAIN pass; the Nightsoul pass draws after it and does not show.
    - The glow class in the main pass glows in the DIFFUSE's colour. Set it per state through a second texture
      set that the by-hash sections pick by a flag.
    - Skill state: the game's effect texture `892554c9` bound to a bike draw. Raise the flag from that
      texture's own TextureOverride, reached by the draw sections' `checktextureoverride`, and carry it to the
      next frame in `[Present]`. A ShaderOverride `ps-t0 ==` test never fired, and the Nightsoul shader alone
      draws while idle too.

## Skill-on looks (the maintainer, 2026-11-18, `ExhaustGlow.png`, `FireBikeDesign.png`)

- Which faces burn: the source model's own mouth faces glowed as stray patches round the right cans (green
  circles), so they are exhaust metal again; `rear_details` still finds the mouths from a copy of the materials
  (`mat_mouths`). The left can's big back face (red circle) burns: its back-facing triangles above y 0.93.
- Tail light: OFF in the plain set (dim red lens and LED rows, light map class paint) and lit in the skill-on
  set (bright, glow class), through the same switch.
- **"A plain orange": every corner of a hole disc read ONE texel (UV by normal), so no pattern could show.** The
  discs now map radially across the hole swatch, and the can face planar over its own box. The skill-on swatch
  is `fire_burst()`: a white-gold core, five curling rays, a zig-zag crown of flame tips, deep red at the rim,
  after Mavuika's flame strokes. The plain set's hole swatch stays near-black.
- Sheet: `Testing/Acceptance/Previews/MavuikaCloudyWolfMotorcycle_skill_off_on.png` (offline: mirrored, no bloom).
- **Three reviewer epochs (the maintainer: "light iterations, 3 epochs")**:
  - Epoch 1: the burst read as a FLOWER on the holes and cracked lava on the can face; a crease line and bevel
    spill on the can face; the tail lit vs off too alike.
    The can face is now a PANEL (`face_patch()`): rays along the face's mean normal (its triangles tilt 45 to 64
    degrees off it: a fold, hence the line), 96 % of its outline, 5 mm off. It hides the crease, cannot spill,
    and gives the fire a grid to map onto.
  - Epoch 2: a PINWHEEL, the same stamp everywhere, mostly plain orange. Each disc now turns its UVs (and every
    other one mirrors them) by a key from its position.
  - Epoch 3: still a pinwheel / turbine, too little white-gold; cream LED bars read as paint. **A RADIAL design
    reads as a pinwheel whatever its strokes.** `fire_burst` is now DIRECTIONAL: mostly white-gold through the
    middle, jagged tongues and open chevrons and streaks rising one way, red only at the rim. Lit LED rows are hot
    orange-red over the red lens.
  - Left as minor: the off can face is flat black; the oval opening's pattern is slightly stretched; a sliver
    under the tail housing (older).
- Installed and reloaded with no warnings.

## The eighth game look: the fire pattern is LOST to clipping (2026-11-18; `audit8_MavuikaCloudyWolfMotorcycle_2026-11-18/`)

- Seen at night in the DPS trial arena:
  - The tail light works: dim with no bars idle (09), lit with orange-red bars on a red lens with the skill (02, 04).
  - Idle holes and can face are dark. Nothing else glows.
- **But the fire pattern did not show: the holes and the can face were one flat orange-yellow with a red rim**
  (04, at about 60 px per opening). The tail's bars survived because they differ in HUE from the lens.
- **Reading: the glow multiplies the diffuse and clips per channel.** White-gold (255, 246, 214) and gold-orange
  (255, 196, 90) land on the same orange-yellow. Three offline reviewer epochs could not see this: the offline
  render has no glow.
- Change: the fire's ground is DARK (64, 10, 3 to 168, 74, 18), so it lands on red and orange once multiplied;
  only the strokes are bright. A stand-in (x2.6 and clip) shows white strokes on red-orange. **Rule for a glowing
  texture here: carry the pattern in brightness, keep the ground under about 40 % of white, and check it through
  a multiply-and-clip preview, not the plain render.** Not seen in game yet.
- **REVERTED by the maintainer ("looks worse")**: the bright fire is back. Taste won over the clipping reading;
  the flat orange in game stays a known limit.

## The front: clipping into the tyre, a headlight (the maintainer, `BikeClip.png`, 2026-11-18; 6 epochs)

- Cause, measured:
  - The nose cleared the tyre's top by only ~2 cm.
  - **The game's suspension lifts the front wheel up to 1.6 cm**: the axle under bone 12 in the steering dump,
    found by multiplying the axle by `inv(M6) @ M12` from the skinning pass's `vs-t0`.
  - The front fender pieces (steering cowl bone) dipped up to 4.8 cm INTO the tyre. They turn with the wheel, so
    steering never showed it.
- `lift_front()`:
  - Raises the body bone (not the long arms that hold the hub) by a ramp in z alone (0.42 to 0.62, ahead of the
    column at 0.39), by 4.1 cm, for 6 cm over the tyre.
  - Applied to the mapped Fenrir `q` before anything is built from it.
- `fit_front_fenders()`: what was learnt in order.
  1. One factor per piece made the main fender 16.5 % bigger, an oversized slab.
  2. A local push per 4-degree sector round the axle, done per piece, parted layered pieces into a doubled skin.
  3. Kept: ONE smoothed field from all cowl pieces, applied to all of them. Clearance 2.5 cm (1.2 cm read as
     touching).
- Headlight: `headlight()` / `lamp_at()`, r 7.5 cm, standing out 4 cm on a housing, with a bezel and a domed lens.
  Pale glass with the skill off; with it on, a hot white centre to a gold rim with the glow class, in the band
  above the plate in swatch 15.
  - Placement history:
    1. The nose, under a grown fender: up under the handlebar clamp, small and perched.
    2. The fender, flush: a decal.
    3. Now: the nose cowl if the window between the fender's top and the clamp holds it (it misses by 1.7 cm),
       otherwise **the front fender on the steering cowl bone, so it turns with the wheel**, like a fork lamp.
  - Made parts can now take a bone of their own (`made` list in `build`).
- Sections: a slab of world space cuts a turned wheel and fender in different places, which read as steps and
  contacts. Draw a steered section in the WHEEL's frame: turn the whole steered bike back by the steering angle.
- Left as found by the reviewers:
  - The fender's two-lobe front with a centre crease, a ragged front flap, and its bulk (the source model's).
  - The lamp is low and reads as a fog lamp from some angles.
  - Brackets of the body near the fender's top at the headstock may touch it when steered: not proven, look in
    game.
  - The lit lamp looks flat offline (no bloom).
- Built and reloaded with no warnings. Not seen in game.

## The front, round 2: the nose met the FENDER, a headlight on the nose (the maintainer, `BikeClip2.png`; 5 epochs)

- **The second clip was nose against FENDER, not tyre.** The first round's fender push raised its top up to 7 cm
  under the nose. Measured by a script that turns the fender through +-25 degrees of steering (the fender turns
  with the wheel, the nose does not).
- **Measure a gap in 3D, not vertically.** Per-cell "body over fender" checks missed flanks BEHIND the fender's
  rising back edge and parts deeper than a filter allowed. The final check: the nearest fender vertex to each body
  vertex (KNN), with the fender swept through steering and the long arms (they hold the hub) left out.
- What worked, in `fit_front_fenders` then `lift_front` (that order: the lift is sized from the fitted fender):
  1. Push the fender out of the tyre (one field for all its pieces).
  2. LOWER its rear toward the tyre past 95 degrees round the axle, keeping 15 % of its height over the clearance
     line. The shroud stood ~10 cm over the tyre under the nose.
  3. SHORTEN it: past 120 degrees the arc is drawn forward to end at 138.
     - Done before the lowering, this swung bulky far pieces onto the top.
     - Ending at 152, it sat under the headstock, 0.9 cm off.
  4. Lift the body's front for 6 cm over the tyre and 3 cm over the steered fender, plus `NOSE_LAMP_ROOM` 10 cm
     so the nose's face can carry the lamp. 16.5 cm in all. The lift ramp starts 8 cm earlier off the centre line
     (`FRONT_RAMP_SIDE`), so the nose's flanks lift while the column at x 0 stays seated.
  - Result (3D): 4.8 cm at rest, 3.7 at 15 degrees, 3.0 at 25.
  - A 5 cm margin was tried: the lift rose to 23 cm and the gaps did not change, because their closest points sit
    where the ramp barely lifts. Reverted.
- Headlight on the NOSE (body bone), as asked. The handlebar clamp no longer limits it, and it is kept clear of
  the fender swept through steering.
  - Lit: WHITE (255 to 238, 244, 255) with faint reflector rings. A white-to-gold lens read orange in game.
  - Off: dark glass.
  - Deep housing, the lens 2 cm proud.
- Left by the reviewers:
  - The lamp reads as a can on the nose from the side; the source's swept nose tip is under it.
  - The fender is faceted and lumpy (the source model's).
  - The front views show no daylight between the fender and the nose, though the 3D gap is >= 3 cm.
  - The brown left exhaust, the black flame housing when off, crumples behind the bars (older).
- Installed (files copied). The in-game reload waits for the maintainer's go-ahead (game use is announced first).

## The front, round 3: the original nose back, the lamp on top (the maintainer, `HeadLightFrontCrooked.png`; 3 epochs)

- In game, round 2 looked CROOKED: the 16.5 cm ramp lift tipped the nose up. Also, the white lamp glowed ORANGE with
  a red rim. The maintainer asked to restore the original shape and put the lamp on top. Later: "a bit too large".
- **Lift off (`FRONT_LIFT_ON = False`); `dent_underside()` instead.**
  - It hollows the nose's UNDERSIDE only.
  - The floor, per 2 cm (x, z) column, is the highest of two things, plus `UNDER_GAP` (4 cm):
    - the fender, swept through +-25 degrees of steering;
    - the tyre, lifted 1.6 cm and swept.
  - Body points from the deepest one under the floor up to 8 cm above it are squeezed into [floor, floor + 8 cm]. The
    depth is smoothed over neighbouring columns.
  - The nose is ~30 cm thick over the tyre, so its top and outline do not move.
  - Gaps (3D, KNN): body-fender >= 4.1 cm and body-tyre >= 4.7 cm at every steer angle. In the side section's flattened
    slice, the closest is 3.2 cm.
  - The fender's end was drawn to 130 degrees (it was 138): its tip came 2.2 cm from the nose's flanks in the section.
  - From the front, a dark V under the lamp is that clearance (rays: before the dent they hit the fender's front
    there). It is not a hole in the nose.
- **The lamp no longer uses the glow class.**
  - The game tints the glow, so pure white came out orange with a red rim.
  - The lit lamp is now white with the metal class (glow green 0), counting on near-white blooming white in game.
    Not seen yet.
- The lamp is now r 5.5 cm with a 10 cm housing (18 cm read as a long can). It sits on two struts and a cross bar
  down to the nose (`lamp_at`). It is raised 9 cm above the nose's furthest-forward point, at y 0.97.
- **TRAP: stale sheets.** `build.py` writes the main, steer, close and review sheets only with `--preview <path>`.
  The front and skill sheets come from scratch scripts. Epoch 1 reviewed a sheet from the morning. Check the
  sheets' timestamps before handing them to a reviewer.
- Left by the reviewers (the source model's, or not proven):
  - the fender's ragged leading edge;
  - crumpled nose panels;
  - a thin rod by the fork;
  - "too little clearance" read from the sections (measured >= 4 cm in 3D);
  - from the front, the lamp seems to hang under the bar.

## The front, round 4: the fender DENT, a brighter lamp (the maintainer, `DentedWheel.png`, 2026-11-18)

- **In game, the fender's lowering read as a DENT** where the fender passes under the nose. Lowering only the rear
  half over 95 to 115 degrees round the axle bends the arch there.
- The fix lowers the WHOLE arch smoothly: `FENDER_TAIL` (-110, 120, 0.15).
  - Starting the blend at 20 degrees left the unlowered front a thick lump with a step (epoch 1).
  - Starting at -60 left a corner at the tip (epoch 2).
  - The fender is now one arch of even thickness, low over the tyre: "lower the rim".
- 3D gaps after the change: body-fender >= 2.8 cm at 25 degrees of steering, >= 4.1 cm at rest; body-tyre >= 4.4 cm.
- Lamp brightness:
  - The glow class cannot be used, because the game tints the glow orange.
  - The lit lens is all 255 with no reflector rings.
  - **Its NORMALS face the sky** (0, 0.94, 0.34), so the game shades it like a top surface, the brightest a lit
    surface gets. It is a made part named "lens", with normals set in `build`.
  - Not seen in game.
- Left by the reviewers: from the front the fender is a wide flat shield, and a flat grey slab when steered; its
  lower front edge is faceted (all the source model's). A small nub by the fork strut under the nose.
- Epoch 3 still saw a bend where the fender ends under the nose. Starting the shortening at 100 degrees (not 118)
  swung pieces up under the nose, and the gap fell to 1.4 cm, so it was reverted. Three epochs in all.

## License plate: a mora coin (the maintainer, 2026-11-18, "fast iteration")

- Between "MAV" and "999" sits a small blue mora symbol, drawn by `paint_atlas`.
  - A first made coin (disc, ring, star) was wrong. The maintainer: not a coin, "the 3 leaf symbol".
  - The mora's symbol is a TRIQUETRA (Genshin wiki, "Symbols in Teyvat"). It is drawn from geometry, not copied.
  - Three circles of radius r, with centres r apart on a triangle, overlap in pairs into three pointed leaves, one
    pointing up.
  - Their outlines (stroke 9 % of the canvas) are made at 400 px and scaled down to 1.0 of the letters' height.
- The two halves are drawn apart round it, sized from "MAV      999".
- Checked by a crop of the diffuse: `Testing/Acceptance/Previews/MavuikaCloudyWolfMotorcycle_plate.png`, made through
  `modkit.render.load_tex`. modkit has no DDS loader in `ops`.
- No reviewer epochs (fast iteration).

- The agent's mid-ride capture script was `a8grab.py` in that session's scratchpad (may be cleared). It holds
  frames in memory and saves them after the run (about 8 s per PNG), and the game minimises when `do` returns.

## Hiding a skill object's accessory: Mavuika's riding helmet (2026-11-18)

- `MavuikaCloudyWolf/Helmet` hides the helmet she wears while riding (hold E in game to ride). Recipe:
  `Tools/Builders/MavuikaCloudyWolfHelmet/build.py`; output, where the maintainer asked for it,
  `Images/GI/Mavuika/MavuikaCloudyWolf/Helmet/MavuikaCloudyWolfHelmet.ini`; preview
  `Testing/Acceptance/Previews/MavuikaCloudyWolfHelmet.png`. Built once, no reviewer epochs (the maintainer: "do no iterations").
- **Not in the assets repo** (neither `SkillData` nor Mavuika's `hash.json`). No new dump was needed: the riding
  dumps already on disk have it (`FrameAnalysis-2026-11-17-221506` and `FenrirModRiding-...214513`, same hashes).
- HOW it was found: the character skinning pass (vs `653c63ba4a73ca8b`, the first draws of the frame) lists every
  skinned object by its position vb; a scatter of each one's POSITION named them in one look (her body, a riding
  HAIR of 3 917 vertices with a ponytail, the bike, the helmet, a tiny 3 628-vertex object). The helmet's vb1
  vertex count (2 343) then finds its main draws, and those give the ib.
- The helmet: position vb `862f9f72`, blend vb `93ca98ae`, texcoord vb `2c54dd38`, **ib `8f86c652`** in two parts:
  first index 0 (6 636 indices, the shell with two swept ear fins; five passes) and 6636 (84 indices, the VISOR,
  drawn alone later, draw 353).
- The mod is one section: `[TextureOverrideMavuikaHelmetIB] hash = 8f86c652, handling = skip`, which skips every
  draw binding that ib (both parts, every pass); parsed with no warnings.
- **VERIFIED IN GAME (2026-11-18, a game subagent)**: while riding, the shell, fins and visor are gone from front,
  back and both sides, nothing left floating; with F9 the helmet is there (`ingame_ride_compare_front.png`,
  `ingame_ride_compare_back_head.png` in the Helmet images folder). Under it the game draws its own RIDING HAIR
  (glowing near-white yellow, swept back with a small topknot, no bangs): closed, no holes, but it blooms at night
  and is a plain style; the game's, not the mod's. A ride lasts ~3-4 s after holding E; standing beside the parked
  bike she wears no helmet even unmodded, so only frames ON the bike test this.
- Seen in passing, not the helmet's: her raised forearm crosses her face from the side (the Fenrir's handlebar
  height), and her bare arm reads flat pale pink (the outfit mod).
