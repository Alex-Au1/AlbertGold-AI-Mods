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
Testing/Acceptance/Previews/                     the last preview sheets of each mod
AI Agent Help/                     these notes
```

## Where a mod starts from

A character's own model as an **identity mod**: AGIDMGen's pre-generated `Mods/GI/<Name>/` at
`E:\Computer\Games\Genshin\Repos\Repos\Anime-Game-Identity-Mod-Generator`. It has every buffer, index buffer,
texture and the `.ini` with today's hashes. A recipe reads it (`--src`), never modifies it.

## Running a build

```
python Tools/Builders/EiBlossomPrincess/build.py --preview Testing/Acceptance/Previews/EiBlossomPrincess.png
```

Python 3.9 with numpy and Pillow; nothing to install. About 30 s. The preview flag also writes `*_top.png`
(upper-body close-up).

## Mods so far

| Mod | Character | State |
| --- | --- | --- |
| `EiBlossomPrincess` (and its `Sword`) | Raiden Shogun (GI) | moved to the PRIVATE repo on 2026-11-19, see `AI Agent Help/Private/` there |
| `MavuikaCloudyWolf` (and its `Helmet`, `Motorcycle`, `Sword`) | Mavuika (GI) | moved to the PRIVATE repo on 2026-11-19, see `AI Agent Help/Private/` there |

## Not done / open

- `EiBlossomPrincess` in daylight, in combat and on a plain walk has not been looked at.
- Testing in game: copy the mod folder to a staging folder on the importer's drive, `mods GIMI park E1` (the
  maintainer's loaded Raiden mod, which collides), `mods GIMI load <mod> --from <staging>`, `reload --mod`, and
  undo both moves at the end. GameView's own guide has the rest.
- Textures are written as uncompressed RGBA8 (22 MB each at 2048). BC7 through AGRemap's `TextureFile` would
  cut that to about a quarter; not wired in.
- The mod folder is not committed, and its binaries would want Git LFS as in AGIDMGen.
