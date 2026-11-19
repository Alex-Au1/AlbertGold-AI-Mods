# Overview

## Layout

```
Mods/<Game>/<Character>/<Mod>/     generated mod folders (drop one into the loader's Mods folder)
Tools/ModKit/modkit/               the toolkit: no mod-specific logic
    gimi.py                        Mesh: load / save GIMI buffers, connected islands
    ops.py                         parts, parametric surfaces, mirroring, weight transfer, UV baking, .dds writer
    render.py                      software rasteriser -> PNG, contact sheets
    blender.py                     Blender without a window: cloth_drape, fbx_dump (an .fbx as arrays)
Tools/ModKit/view.py               render a BUILT mod folder: any angle, zoom, one draw alone, holes on green
Tools/Builders/<Mod>/build.py      one recipe per mod; writes the mod folder and a preview
Docs/Previews/                     the last preview sheets of each mod
AI Agent Help/                     these notes
```

## Where a mod starts from

A character's own model as an **identity mod**: AGIDMGen's pre-generated `Mods/GI/<Name>/` at
`E:\Computer\Games\Genshin\Repos\Repos\Anime-Game-Identity-Mod-Generator`. It has every buffer, index buffer,
texture and the `.ini` with today's hashes. A recipe reads it (`--src`), never modifies it.

## Running a build

```
python Tools/Builders/EiBlossomPrincess/build.py --preview Docs/Previews/EiBlossomPrincess.png
```

Python 3.9 with numpy and Pillow; nothing to install. About 30 s. The preview flag also writes `*_top.png`
(upper-body close-up).

## Mods so far

| Mod | Character | State |
| --- | --- | --- |
| `EiBlossomPrincess` (and its `Sword`) | Raiden Shogun (GI) | moved to the PRIVATE repo on 2026-11-19, see `AI Agent Help/Private/` there |
| `MavuikaCloudyWolf` | Mavuika (GI) | built 2026-11-15 from an outside `.fbx` (Cloud Strife's Advent Children outfit), see [Outfit Transfer](../OutfitTransfer/CLAUDE.md); needs Blender and the maintainer's download at `E:\Downloads\FFVII Ever Crisis - Cloud (Advent Children)`; seen in game eight times by game subagents (2026-11-15 and 11-17): loads clean, correct side, clean throat and zip; small dark marks on open pieces and a stiff coat in a run are open |
| `MavuikaCloudyWolf/Motorcycle` | Mavuika's bike (GI skill object) | built 2026-11-17 as Cloud's Fenrir from the maintainer's FFXIV "SDS Fenrir" `.stl` (`C:\Users\3dark\Downloads\SDS Fenrir - Final Fantasy 7 _ XIV - 3227878`), see [Skill Objects](../SkillObjects/CLAUDE.md); recipe `Tools/Builders/MavuikaCloudyWolfMotorcycle/build.py`; five reviewer epochs and four game looks (2026-11-17): loads, rides, steers without tearing, glow fixed; the red shape while steering is the game's own beast-head effect; open: wheel spin not seen |
| `MavuikaCloudyWolf/Sword` | Mavuika's claymore A Thousand Blazing Suns (GI weapon) | built 2026-11-17 as Cloud's Fusion Sword (Advent Children, assembled) from the maintainer's textured `.dae` (`C:\Users\3dark\Downloads\Cloud Fusion Sword References`), see [Weapons](../Weapons/CLAUDE.md); recipe `Tools/Builders/MavuikaCloudyWolfSword/build.py`; the weapon was dumped from the game (`dump/` beside the recipe); five reviewer epochs and five game looks (2026-11-17), then cross-checked against the maintainer's other two models (2026-11-18: thicker upper blade, grey guard; five more epochs and a game look): loads clean, her hands on the grip, grey steel and red grip, normal outlines (low-specular light map; the weapon's t0-t3 textures replaced by hash, its effect mask in ps-t8 by slot) |

## Not done / open

- `EiBlossomPrincess` in daylight, in combat and on a plain walk has not been looked at.
- Testing in game: copy the mod folder to a staging folder on the importer's drive, `mods GIMI park E1` (the
  maintainer's loaded Raiden mod, which collides), `mods GIMI load <mod> --from <staging>`, `reload --mod`, and
  undo both moves at the end. GameView's own guide has the rest.
- Textures are written as uncompressed RGBA8 (22 MB each at 2048). BC7 through AGRemap's `TextureFile` would
  cut that to about a quarter; not wired in.
- The mod folder is not committed, and its binaries would want Git LFS as in AGIDMGen.
