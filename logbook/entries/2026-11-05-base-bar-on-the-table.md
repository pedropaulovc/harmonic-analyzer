---
date: 2026-11-05
module: M06
machine: mill
part: ch-rocker-arm-tl-oblique-base-bar
outcome: partial
hours: 4
---

# Rough the new base-bar blank on the table

Restarts the base bar scrapped on
[2026-10-30](2026-10-30-pendant-and-roughing-base-bar-to-length.md), with that
entry's advice for op 10.

## Setup

- **Stock:** a new piece sawn from the 1/2 × 6 × 72 in 6061-T6511 bar
  (OnlineMetals 1173) on the 14 in Evolution metal-cutting miter saw, about
  0.3 in over the drawing's length. The width is the bar's full 6 in, to be
  milled to 5.50 in. The blue on one end is dried Dykem layout fluid.
- **Workholding:** flat on the PM-30MV table on all five 1-2-3 blocks I have:
  the two new Taytools blocks, and three from the makerspace that I found
  rusty and soaked overnight in Evapo-Rust (about 12 h). There's an HHIP
  3901-0076 23–30 mm screw jack under the middle, standing on one of the 1-2-3
  blocks (riser height not recorded), with strap clamps on step
  blocks from the small clamping kit (Little Machine Shop 1268). I didn't use
  the work stop.
- **Tooling:** 1/2 in 2-flute HSS end mill.
- **Control:** CNCjs with the new macros for the cutting moves, not jogging.
- **Arrived for this session:** the JB Tools order (HHIP 3900-0070 machinist's
  jack, 3900-0266 Little Giant jack screw set, 3900-2125 universal work stop,
  2 × 3901-0076 screw jacks) and the Taytools order (two 1-2-3 blocks, 2 ×
  1-2-3 block attachment hardware kits).

## Operations

| # | operation | tool | RPM | feed | DOC | result |
|---|---|---|---|---|---|---|
| 1 | saw the blank | 14 in Evolution metal miter saw | — | by hand | — | about 0.3 in over length |
| 2 | set up on the table | 1-2-3 blocks, 3901-0076 jack, straps | — | — | — | good: held for the far-edge pass |
| 3 | face the far long edge | 1/2 in 2-fl HSS end mill, CNCjs macros | 1800 | 7 in/min | 0.050 in radial; axial past the bottom of the bar by about 0.100 in (by eye) | faced |
| 4 | bumped the part while jogging | — | — | — | — | part moved visibly; touched off again with the cutter and kept facing |

## Measured

Not measured. The bump moved the part visibly; how far wasn't measured.

## What happened

**The new setup worked.** I followed the 10-30 advice for op 10, except I
didn't use the work stop. The bar sat on all five 1-2-3 blocks with the screw
jack under the middle and straps on the ends. I faced the far edge at 1800 rpm
and 7 in/min, 0.050 in radial per pass, with the bottom of the end mill about
0.100 in below the bar. I set that by eye. The cutting moves ran from the CNCjs
macros, not the jog.

**Then I bumped the part while jogging,** and it moved visibly. I didn't
measure how far. I was still roughing and had stock left to remove, so I didn't
re-indicate it: I touched off again with the cutter and carried on facing.

**The plan had a hole in it.** I meant to face one long edge on the table and
then move the bar to the vise. Then I realized that until the part is square
all round, I'd need a ground rod between the part and the moving jaw, and I
didn't have one with me. So the plan changed: do all four sides clamped on the
table (see [2026-11-06](2026-11-06-base-bar-both-edges-and-a-controller-reset.md)).

## Cost

- Time: 4 h, no split recorded.
- Material: one blank cut from the 72 in bar; none scrapped.
- Tooling: nothing broken.
- Bought: see Setup.

## Open

- Face both ends.
- Bring a ground rod for squaring in the vise. Bought afterwards: POWERTEC
  71476 hardened, ground steel dowel pins, 1/4 × 2 in, 10 pack (Amazon
  B086DCHYQK), due 2026-11-07.
- Shop inventory: mark the JB Tools and Taytools orders received (there's one
  3900-0070 jack, not two) and add the three makerspace 1-2-3 blocks:
  [#2288](https://github.com/pedropaulovc/harmonic-analyzer/issues/2288).

## Follows up to

- Module: [`../curriculum/m06-mill-i-tramming-squaring-edge-finding.md`](../curriculum/m06-mill-i-tramming-squaring-edge-finding.md)
- Part: [`cad/config/parts/ch-rocker-arm-tl-oblique-base-bar.yaml`](../../cad/config/parts/ch-rocker-arm-tl-oblique-base-bar.yaml)
- Previous session: [2026-11-04](2026-11-04-oblique-end-brackets-scrapped.md);
  advice tried from [2026-10-30](2026-10-30-pendant-and-roughing-base-bar-to-length.md#advice-afterwards-from-claude-not-yet-tried).

## Photos

Contact sheet (with 2026-11-06):
[`book/figures/hand/oblique-base-bar-table-setup-contact-sheet.jpg`](../../book/figures/hand/oblique-base-bar-table-setup-contact-sheet.jpg).

Raw media, in OneDrive `Imagens/Imagens da Câmera/2026/11/` (file names are
UTC; local times below):

- `20261106_010143460_iOS.jpg`: the Evolution saw (17:01).
- `20261106_042935654_iOS.HEIC`, `20261106_042944264_iOS.HEIC`: the table
  setup, front and angled (20:29).
- `20261106_045319000_iOS.MOV`: facing the far edge (20:53, 22 s).
- `Temp/Seattle Makers 3.m4a`: my spoken answers to the interview.
