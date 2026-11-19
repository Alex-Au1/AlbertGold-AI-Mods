# Blender as a build step

The maintainer has Blender installed (2026-11-11: `C:\Program Files\Blender Foundation\Blender 3.6\blender.exe`,
3.6.14; the `Blender 4.2` folder has no blender.exe) and allowed its use. It runs without a window, so a mod is
still the output of a recipe: a part goes out as arrays, a script does one job inside Blender, arrays come back.

- `Tools/ModKit/modkit/blender.py`: `find()` (env `MODKIT_BLENDER`, else the install folder) and
  `cloth_drape(part, colliders, pin, frames, grow, dist, bend)`: lets a part settle as cloth, in place. Only
  positions change (vertex i in is vertex i out), so triangles, UVs and blend weights stay the caller's.
- `Tools/ModKit/blender/cloth_drape.py`: the script Blender runs. Converts Y-up to Blender's Z-up and back.
- `build.py` with env `EI_DUMP=<path>` saves the jacket step's inputs (`<path>0.npz` worn, `<path>1.npz` off the
  shoulders: jacket, body, kimono), so a cloth setting can be tried in about a minute instead of a whole build.

**State (updated 2026-11-11): one build uses it, for the cloth between her elbows (last section). The first trial, on the worn jacket, was not used.** `Docs/Previews/Blender_cloth_jacket_trial.png` is the best run on the
worn jacket (grow 0, 30 frames, bending 4, kimono as the only collider).

## What the trial taught

- **Mass is per vertex.** 0.02 kg on 2 500 vertices is a 50 kg jacket: it stretched off her shoulders.
  About 0.0003 is a 1 kg garment.
- **`modifiers.new("x", "COLLISION")` needs `ob.collision.use = True`** set by hand.
- **One collider under the cloth, not two stacked.** Body and kimono 5 mm apart, each with its own thickness,
  both claimed the jacket lying 5 mm over the kimono: it crumpled and went inside the kimono. Collide with the
  outermost layer under the cloth only, and keep collider thickness + cloth distance under the starting gap.
- **Hold it like a tailored garment.** Free at the shoulders, an open-fronted jacket slides off them. Pinned:
  shoulder line and collar (y > 1.36), the belt edge, the arms beyond |x| 0.17, and the open front edge softly
  (0.6, fading over 2 cm).
- **The simulation keeps the pattern it is given.** Cloth cut from her skin carries the skin's fold under each
  breast as spare cloth, and the simulation turns that into a ring of wrinkles there, whatever the stiffness or
  size. Relaxing that area first (a membrane) shrank it through the bust instead. The back and the sleeves,
  where the pattern is sound, came out well: looser, hanging, no longer skin-tight.
- Time: 30 frames at quality 10 take about 1 to 1.5 minutes for a 2 500-vertex jacket on a 5 700-vertex collider.

## Next, if it is taken further

Give the simulation a garment that was never skin: a smooth shell for the jacket's front (the old ring-built
bodice was one), joined to the body-cut shoulders and arms, then draped. Also worth trying: the cloth hanging
between her elbows (jacket position 2, today a stiff shelf from `make_drape`), which is free-hanging cloth and
the case a simulation suits best.

## Second trial: a smooth shell front, then cloth (2026-11-11)

Picture: `Docs/Previews/Blender_cloth_jacket_shell_trial.png` (rows: as built, shell, shell + cloth).

- The jacket's front was moved onto a smooth shell first (`_shell_front` in the EiBlossomPrincess recipe, see
  [Mod Building](../ModBuilding/CLAUDE.md)), so the pattern no longer carries the fold under the bust.
- **The cloth step still crumples the bust front**, from a clean taut start, with the same pins and settings as
  the best first-trial run. So the spare cloth in the pattern was not the only cause. Not proven, but the likely
  one: the collider is the kimono, itself cut from skin and pulled about over the bust (layers close together,
  a surface that crosses itself in the fold), and the cloth is pushed about by it.
- **Decision: the build uses the shell and no cloth step.** The shell alone removed the fold line; the build
  still does not need Blender.
- If cloth on the bust is tried again: collide against a clean stand-in (the shell field itself, turned into a
  mesh a few mm inside the jacket) instead of the kimono. Free-hanging cloth (the jacket between her elbows,
  skirt panels) remains the better first use of the cloth step.

## First use in a build: the cloth between her elbows (2026-11-11)

Pictures: `Docs/Previews/Blender_cloth_elbow_trial.png` (top: grow 0.30, bending 0.5; bottom: grow 0.18,
bending 4), `Docs/Previews/EiBlossomPrincess_jacket_elbows_cloth.png` (the build).

- **State: the EiBlossomPrincess build now runs Blender** (about 45 s) for the jacket's third position: the
  ring of cloth from the belt out to the fur edge (`make_drape`, a flat shelf before) settles as cloth. When
  `blender.find()` returns None the build prints so and keeps the shelf.
- **Free-hanging cloth is where the cloth step works.** A plain grid, held along two edges, with simple
  colliders well away from most of it: the first run already looked like cloth.
- Settings kept: grid 21 x 144 (9 x 96 was too coarse to fold), pinned at the belt row, the fur-edge row and
  wherever |x| > 0.24 (at her elbows the cloth is the sleeve), grow 0.18, bending 4, 60 frames, colliders =
  body, overskirt, train, bustle, belt.
- **Leave out colliders the cloth passes through at the start.** The ring crosses her forearms; with the
  jacket arms and bells as colliders it bunched into a wad at each elbow.
- **grow is slack in every direction.** 0.30 with soft bending gave a crumpled ruffle; 0.18 with bending 4
  gives broad folds. For a low-poly, flat-lit game mesh prefer few broad folds.
- `EI_DUMP=<prefix>` on the build also writes `<prefix>2.npz` (this cloth and its surroundings) for trials.
- OPEN: with the fur off (K), the cloth's outer edge near the elbows is ragged; not looked at in game; the
  folds are fixed in the mesh and will not move with her arms beyond what the blend weights do.

## Tools on this machine (2026-11-11)

The maintainer's note for every agent: when the computer has Blender or another programmable 3D / CAD tool,
keep in mind that it is available and do not limit solutions to this repo's own toolkit. Found so far: Blender
3.6.14 under `C:\Program Files\Blender Foundation\` (`modkit.blender.find()`). Look for others before deciding
that something has to be written from scratch, and add what you find here. Candidates that were NOT tried and
might have been better done in Blender: UV unwrapping of fitted cloth (the kimono's layout round her was done
by hand in the recipe), remeshing a body-cut garment, posing the armature to test weights before the game.
