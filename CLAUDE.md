# CLAUDE.md

**AlbertGold AI Mods** — an experiment in how far a Claude agent can go as an actual *modder*: mods for
3DMigoto-based loaders (GIMI first) whose meshes and textures are **made by code**. No modelling by hand: since 2026-11-11 Blender may be used, but only run
headless from a script as a build step. Each mod is the output of a build script in this repo; the mod folders under `Mods/` are generated.

Structure and conventions follow [Anime Game Remap](https://github.com/nhok0169/Anime-Game-Remap) (AGRemap), whose
checkout and agent docs are on this machine at `E:\Computer\Games\Genshin\Repos\Repos\Fix-Raiden-Boss`. When this
repo's guides do not cover something, look there before inventing a convention, and write down what you adopt.

Detailed instructions live under [`AI Agent Help/`](AI%20Agent%20Help/README.md), split by topic. **Read the
file relevant to your task first.**

| Topic | File | Read it when you're... |
| --- | --- | --- |
| Overview | [`AI Agent Help/Overview/CLAUDE.md`](AI%20Agent%20Help/Overview/CLAUDE.md) | new to the repo: layout, where source models come from, what is generated, what is not verified yet |
| Mod Building | [`AI Agent Help/ModBuilding/CLAUDE.md`](AI%20Agent%20Help/ModBuilding/CLAUDE.md) | making or changing a mod: the `modkit` toolkit, the look-measure-build-render loop, what Raiden's model taught (buffer layout, winding, light map codes, bones), and the traps already hit |
| Game Audit | [`AI Agent Help/GameAudit/CLAUDE.md`](AI%20Agent%20Help/GameAudit/CLAUDE.md) | comparing a mod with its reference in the game, in epochs with a game agent (paused by the maintainer on 2026-11-10; the process and its brief are kept) |
| Blender | [`AI Agent Help/Blender/CLAUDE.md`](AI%20Agent%20Help/Blender/CLAUDE.md) | using Blender (headless) as a build step: the cloth simulation wrapper, how to try settings quickly, where it worked (free-hanging cloth) and where it did not (fitted cloth over the bust) |
| Private mods | [`AI Agent Help/Private/`](AI%20Agent%20Help/Private/README.md) | working on a mod that is not public (Ei's `EiBlossomPrincess` and its sword; Mavuika's `MavuikaCloudyWolf` with its helmet, motorcycle and sword): this folder exists only in the PRIVATE repo, `AlbertGold-Private-AI-Mods`, a superset of this one that merges from it |

**A MOD IS BUILT, NEVER HAND-EDITED.** `Mods/<Game>/<Character>/<Mod>/` is the output of
`Tools/Builders/<Mod>/build.py`. Change the recipe and rerun it.

**LOOK BEFORE AND AFTER EVERY CHANGE.** `modkit.render` draws any mesh to a PNG from any angle in seconds. Every
geometry or texture decision in the first mod was made from a render (islands coloured, weights coloured, UV
overlays), and every build ends with a preview sheet. A clean run proves nothing.

**THE OFFLINE RENDER IS NOT THE GAME: LOOK THERE TOO (2026-11-10).** `EiBlossomPrincess` loaded with no 3DMigoto
warnings and was looked at with AGRemap's `Tools/GameView` (the game is the maintainer's, so ask first): the
character screen from four sides, plus climbing and sprinting in the overworld. The game showed two things no
render did: near-white colours bloom out, and the Body draw textures back faces from one fixed texel. Both are
in [Mod Building](AI%20Agent%20Help/ModBuilding/CLAUDE.md). Not yet looked at: daylight, combat and burst
animations, a plain walk on open ground.

**RECORD WHAT YOU LEARN (the maintainer, 2026-11-11).** As in AGRemap: this file stays a short map, and every
lesson goes into the topic file it belongs to under `AI Agent Help/` (a new folder with its own `CLAUDE.md` for a
new topic, plus a row in the table above). Reference pictures and the maintainer's fault screenshots live in
`Images/<Game>/<Character>/<Mod>/` and are cited by file name.

**USE THE TOOLS THE MACHINE HAS (the maintainer, 2026-11-11).** If the computer has Blender or another
programmable 3D or CAD tool, note that it is there and count it among your options: do not limit a solution to
this repo's own toolkit when such a tool does the job better. It still runs from a script as a build step, never by
hand. What is installed and what it has been used for is in [Blender](AI%20Agent%20Help/Blender/CLAUDE.md).

**EVERY BATCH GOES THROUGH REVIEWER EPOCHS (the maintainer, 2026-11-14).** For each batch of changes the maintainer
gives: change, build, make comparison sheets with the reference models beside the made result, hand them to a fresh
reviewer subagent that is not told what is believed fixed, fix its fault list, and repeat until it finds nothing or
FIVE epochs have passed (ten at first; five since 2026-11-15: "these audits are becoming very long"). Only then is the maintainer asked to check. In-game checks are done by a game subagent too.
How, and the fault lists so far, are in [Mod Building](AI%20Agent%20Help/ModBuilding/CLAUDE.md).

Commit and push only when asked.
