# Game Audit: comparing a mod with its reference, in epochs

The maintainer's process (2026-11-10), borrowed from AGRemap's in-game audit: a **game agent** looks at the mod
in the game beside the reference pictures and reports what is still unlike the reference; the building agent
fixes that and rebuilds; the game agent looks again. One round is an **epoch**. Stop when an epoch finds nothing
material, or after **10 epochs**, whichever comes first, and then hand over what is still open.

The goal is the maintainer's: **make the outfit look like the reference outfit.** Their written feedback points
at differences; it is not a specification to satisfy word by word.

## If you are the game agent

You LOOK and REPORT. You do not fix.

**Not allowed:** git commands, running `build.py`, editing anything outside your epoch folder, GameView's
`mods` / `launch` / `dump` commands, `reload` (the building agent has already reloaded), pressing Enter in game,
clicking anything that spends or sends, saving any image that shows an account id.

**The mod:** `EiBlossomPrincess` on Raiden Shogun, installed and loaded. Its built files are in
`Mods/GI/Ei/EiBlossomPrincess/Ei`.

**The references:** `.refs/EiBlossomPrincess/`
- `user_1.png` side view (her right), `user_2.png` side view (her left), `user_3.png` back: whole outfit
- `user_4.png` close-up: sleeve end, skirt side, back bustle
- `user_5.png` three-quarter back: fur, sleeve, belt, bustle, skirt lace
- `user_6.png` close-up: neckline embroidery, necklace, belt and buckle
- `user_7.png` close-up: front hem lace, stocking tops
- `user_8.png` front three-quarter, `user_9.png` side: whole upper body and skirt
- `web_art1.jpg`, `web_art2.jpg`: the official key art (her figure is at the left of each)

**Looking at the game:** AGRemap's GameView, from `E:\Computer\Games\Genshin\Repos\Repos\Fix-Raiden-Boss\Tools\GameView`,
always with `py -3.9 main.py ...`. The elevated helper is already running. Read that repo's
`AI Agent Help/GameView/CLAUDE.md` section "Rules for driving the game" first. What has worked here:

```
py -3.9 main.py screenshot --name s0 --crop 705 0 860 630      # where am I? (view coordinates)
py -3.9 main.py do "key c; wait 12"                            # overworld -> character screen (Raiden is active)
py -3.9 main.py screenshot --name a1 --crop 520 60 480 570     # the character, full height
py -3.9 main.py do "drag 700 330 850 330; wait 1.5"            # turn her about a quarter less than 90 degrees
py -3.9 main.py do "scroll 8 --at 780 250; wait 2"             # zoom in (scroll -8 zooms out)
py -3.9 main.py key h --vk                                     # the mod's neckline toggle; press it an EVEN number of times
py -3.9 main.py do "key esc; wait 3"                           # back to the overworld when you finish
```

Shots land in `C:\Users\3dark\.claude\gameview\shots\` (the newest file with your `--name`); open them with the
Read tool. Take a screenshot first to see which screen the game is on. Wait about ten seconds after opening the
character screen (an entrance pose glows). Orange text at the top left is other mods' warnings, not this mod's.
In the overworld, `hold w 2` walks; use it for a few frames of the dress in motion from behind.

**Looking closer than the game allows:** the mod's own files, rendered offline, show texture detail at any zoom:

```
python Tools/ModKit/view.py Mods/GI/Ei/EiBlossomPrincess/Ei EiBlossomPrincess --out <png> --yaw 0 90 180 \
       --bounds -0.3 0.3 0.6 1.2 --size 700 700 --comps Body Dress --bg 0 220 0
```

(`--bounds` is x0 x1 y0 y1 in metres; she is 1.75 tall, the waist at 1.18, the skirt's hem near 0.8.)

**Compare part by part**, each against the reference picture that shows it best: overall silhouette and
proportions; fur collar; bodice and neckline embroidery; necklace; sleeves (fit, length, shape of the end, its
lace and lining); belt and buckle; skirt (length, shape of the hem, lace, embroidery, colour); the bustle at the
back; the tails; stockings; shoes; colours overall; anything broken (holes, clipping, parts crossing, stretched
or blurry texture).

**Decided by the maintainer, not differences to report:** Raiden's own face, hair, hair ornament and body; bare
shoulders with the fur as a V that shows her cleavage (the reference has fur epaulettes on a closed jacket); the
H toggle between a jacket edge over the chest and bare skin; whitish stockings; the nape tattoo. Her feet stand
3 cm above the ground under the toes, so the shoes keep a platform there.

**Return the report as your final message** (a subagent cannot write report files here; the building agent
saves it as `.refs/EiBlossomPrincess/epochs/<N>/report.md`), and copy the shots it cites into that folder:

1. `VERDICT:` `CLEAN` (nothing material left) or `OPEN`.
2. Since the last epoch (read the previous report if there is one): each earlier issue as fixed / improved /
   unchanged / worse, and any regression.
3. At most 12 issues, most visible first. For each: the part; what the reference shows (file name); what the
   mod shows (your shot's file name); and a concrete change, with numbers where you can give them (centimetres,
   fractions of a length, counts, approximate RGB). Describe shapes by what they look like in the picture, and
   say where on the body they sit.
4. What you did not manage to look at.

Report the SAME measurements every epoch for things that are a matter of degree (skirt length as a fraction of
thigh, sleeve bell width against the forearm, belt depth against the buckle, blossom size against the hand), so
progress is a number and not an impression. Be strict: the maintainer will look after you, and a difference they
find in a picture you took is one you missed.

Your final message: the report's path, the verdict, and the issues as one line each.

## If you are the building agent

- Rebuild, copy the mod into the importer's `Mods`, `reload --mod`, THEN start the epoch. Never start one on an
  unreloaded build.
- Fix mechanisms, not one number per epoch: when the report says "smaller", look at the reference yourself and
  go to what it shows.
- Re-check everything fixed in earlier epochs on the new build before starting the next one.
- After the 10th epoch, stop and hand the open list to the maintainer.

## What the first epochs taught (2026-11-10)

- Epoch 1 found twelve differences after six rounds of the maintainer's own notes had been "done": the notes
  had been satisfied one by one while the whole (a hem sweeping to a train, sleeves that show the hand) was
  never compared with the reference.
- **If a shot shows a scene the agent did not put there, the maintainer is playing: stop driving and say so.**
  Epoch 2's agent did. The building agent then fixes offline and asks before the next reload or epoch.
- Parts hung on the skirt's swinging bones fly out in idle animations (the bustle's tiers went horizontal);
  a part that should sit still goes rigidly on the pelvis (group 47).
- The agent's measurement table is what shows progress; keep its rows fixed.
