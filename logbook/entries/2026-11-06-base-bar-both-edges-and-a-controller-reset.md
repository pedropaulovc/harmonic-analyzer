---
date: 2026-11-06
module: M06
machine: mill
part: ch-rocker-arm-tl-oblique-base-bar
outcome: partial
hours: 6
---

# Face both long edges of the base bar on the table

Continues [2026-11-05](2026-11-05-base-bar-on-the-table.md).

## Setup

- **Stock:** the base-bar blank from 2026-11-05, far edge roughed.
- **Workholding:** I redid the setup so both long edges can be faced without
  unclamping. The 1-2-3 blocks are joined with the Taytools attachment
  hardware and stand 2 in tall, staggered like a Z tetromino from Tetris. The
  same screw jack sits under the middle, with strap clamps from the Little
  Machine Shop 1268 kit.
- **Tooling:** the same 1/2 in 2-flute HSS end mill.
- **Control:** CNCjs macros on the FluidNC controller.
- **Lubrication:** Grizzly way oil in a McMaster-Carr 10085K36 oil can.

## Operations

| # | operation | tool | RPM | feed | DOC | result |
|---|---|---|---|---|---|---|
| 1 | oil every ball oiler and the ways | McMaster 10085K36 oiler, Grizzly way oil | — | — | — | done, about 10 min |
| 2 | join the 1-2-3 blocks, re-set the bar | Taytools attachment hardware | — | — | — | Z-tetromino arrangement at 2 in |
| 3 | face the front and back long edges | 1/2 in 2-fl HSS end mill | not recorded | not recorded | not recorded | both faced; 0.015 in left on the width |
| 4 | — | — | — | — | — | FluidNC controller reset mid-pass; spindle e-stopped; home lost |

## Measured

| feature | nominal | tolerance | measured | instrument |
|---|---|---|---|---|
| width left to remove | 5.50 in | — | 0.015 in over | not recorded |

## What happened

**I oiled the mill for the first time:** every ball oiler and the ways, with
Grizzly way oil from a McMaster oil can. It took about 10 minutes.

**I rebuilt the setup so the bar never leaves the table.** I joined the 1-2-3
blocks with the attachment hardware, at the 2 in height, staggered like a Z
tetromino, and faced the front and back long edges without unclamping. The
plan for the ends is to add more clamps before removing the old ones, then
face the two ends. I haven't done that yet.

**The controller restarted in the middle of a facing pass.** The machine
stopped, then the FluidNC controller started rebooting: the CNCjs console
showed its start-up messages. I hit the e-stop to stop the cut. The cut was
interrupted partway, so that pass needs finishing, but there's still 0.015 in
to come off before the 5.50 in width, so nothing was lost. I don't know the
cause. The controller lost its home position, so I'll have to re-indicate.

## Cost

- Time: 6 h. I put it as setup 1.5 h, cutting 3.5 h, about 2 h debugging the
  CNC controller and testing before cutting, plus filming and breaks. Those
  add up to more than 6 h; the 6 h total is my number.
- Material: none scrapped.
- Tooling: nothing broken.

## Open

- Re-home or re-indicate, then take the last 0.015 in off the width.
- Add clamps before removing the old ones, then face both ends.
- Find out why FluidNC reset mid-pass.
- Measure the width along the length once it's finished.

## Advice afterwards (from Claude, not yet tried)

I asked Claude for advice on finishing the width and recovering after the
controller reset. None of this has been tried at the machine yet.

- **Don't trust any coordinate from before the reset.** When FluidNC reboots,
  its machine position restarts from wherever the table is, so a work offset
  from before means nothing until the machine is homed again. If homing is
  set up and repeatable, `$H` brings the old offset back. Prove it with a
  test: re-touch the edge you zeroed on and check that the DRO reads what it
  did before (unverified against my config).
- **The surer route for 0.015 in: zero on the part again.** The bar hasn't
  moved, so the coordinates don't matter, only the edge does. Measure the
  width at both ends and the middle and write it down: actual − 5.500 =
  allowance. Touch the side of the cutter on the edge being cut (spindle off,
  turned by hand, as before) and zero Y there. Take about 0.010 in as a rough
  pass and the rest as one finish pass, each cut to an absolute Y. Measure
  between them.
- **Edge-finder sign rule.** When the finder kicks, the spindle centre is one
  radius (0.100 in for the 0.200 in finder) from the edge, on the side the
  finder is on. Set the DRO to what the spindle centre really is: the edge
  coordinate, moved 0.100 in toward the finder's side. For an edge you want to
  be zero, finding it from the −Y side means setting Y = −0.100.
- **Finding the cause of the reset.** The ESP32 inside FluidNC prints a reset
  reason in the first lines it sends after it reboots. Copy those lines from
  the CNCjs console next time: a brownout points at power or the USB cable,
  and a panic or watchdog points at firmware or noise (unverified against my
  board). Until then, run the finish pass with the spindle stop in reach, and
  keep it short enough to repeat if it's interrupted.
- **The clamp swap for the ends.** Add the new straps and snug them before
  loosening any old one, and keep at least two straps on solid support the
  whole time. Re-touch an edge after the swap rather than assuming nothing
  moved.

## Follows up to

- Module: [`../curriculum/m06-mill-i-tramming-squaring-edge-finding.md`](../curriculum/m06-mill-i-tramming-squaring-edge-finding.md)
- Part: [`cad/config/parts/ch-rocker-arm-tl-oblique-base-bar.yaml`](../../cad/config/parts/ch-rocker-arm-tl-oblique-base-bar.yaml)
- Previous session: [2026-11-05](2026-11-05-base-bar-on-the-table.md)

## Photos

Contact sheet (with 2026-11-05):
[`book/figures/hand/oblique-base-bar-table-setup-contact-sheet.jpg`](../../book/figures/hand/oblique-base-bar-table-setup-contact-sheet.jpg).

Raw media, in OneDrive `Imagens/Imagens da Câmera/2026/11/` (file names are
UTC; local times below):

- `20261107_000049240_iOS.heic`, `20261107_000053665_iOS.heic`: the joined
  1-2-3 blocks, top and front (16:00).
- `20261107_003727000_iOS.MOV`: fitting the attachment hardware to a 1-2-3
  block (16:37, 17 s).
- `20261107_013148132_iOS.HEIC`: the head (17:31).
- `20261107_013238000_iOS.MOV`: the pendant at the machine (17:32, 37 s).
- `20261107_050752441_iOS.HEIC`: the faced edge and the chips (21:07).
- `Temp/Seattle Makers 3.m4a`: my spoken answers to the interview.
