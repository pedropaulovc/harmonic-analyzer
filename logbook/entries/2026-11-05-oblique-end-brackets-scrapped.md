---
date: 2026-11-05
module: M06
machine: mill
part: ch-rocker-arm-tl-oblique-end-bracket
outcome: scrapped
hours: 5.25
---

# Make the two oblique-jig end brackets

## Setup

- **Stock:** two blanks of 6061-T6511 1/2 × 1 in flat bar (OnlineMetals 1165)
  for the oblique-jig end bracket (`ch-rocker-arm-tl-oblique-end-bracket`,
  MHA-CH-06-TL-28, quantity 2). Sawn about 1/4 in over the 68.9 mm finished
  length on a 14 in Evolution metal-cutting miter saw.
- **Workholding:** the makerspace has two 4 in milling vises, a Tegara (label
  reads "440V") and a Precision Matthews with a swivel base. I used the Tegara
  instead of my 6 in vise because the parts are small. Its base has two
  removable alignment keys that are exactly the T-slot width, so lining it up
  was mostly a matter of setting it down in the slot. My 6 in vise came with
  keys too, but they're too big for these T-slots. Fixed jaw indicated to under
  0.001 in across its 4 in length.
- **Tooling:** 1/2 in 2-flute HSS end mill; generic 0.200 in cylindrical edge
  finder; height gauge with a 2 in gauge block; the drawing's two tap drills
  (#29 for the #8-32 holes, #36 for the #6-32) in a drill chuck. No centre
  drill.
- **Measuring:** Grizzly dial indicator (0.001 in graduations) on a magnetic
  base on the spindle.

## Operations

| # | operation | tool | RPM | feed | DOC | result |
|---|---|---|---|---|---|---|
| 1 | indicate fixed jaw in X | Grizzly dial indicator, mag base | — | — | — | under 0.001 in over 4 in |
| 2 | find X edge with paper | 1/2 in 2-fl HSS end mill, newspaper | 1500 | by hand | — | failed: DRO zero was off the edge |
| 3 | lay out length | height gauge, 2 in gauge block, on the mill table | — | — | — | never checked: part scrapped |
| 4 | find X edge | 0.200 in edge finder | 900 | by hand | — | found; radius sign by trial |
| 5 | face blank 1 | 1/2 in 2-fl HSS end mill | 1500 | handwheel at 0.010 in/step (meant 0.001) | 0.050 in | cutter hit blank 2 and pulled it up: **scrapped** |
| 6 | drill six holes in blank 1 | #29 and #36 jobber drills, drill chuck | 1500 | by hand | — | one hole 1/4 in short, one crooked: **scrapped** |

## Measured

| feature | nominal | tolerance | measured | instrument |
|---|---|---|---|---|
| vise fixed jaw, along X over 4 in | 0 | — | under 0.001 in | Grizzly dial indicator |
| part lift when tightening the vise | 0 | — | about 0.01 in | by eye |
| drilled hole, out of square | 0 | — | about 0.01 in | by eye |
| hole depth after drill change | through (25.40) | — | about 1/4 in short | by eye, looking underneath |

The faced part also came out of square; not measured.

## What happened

**Indicating went well this time.** The 4 in vise's alignment keys did most of
the work, and I got the fixed jaw under a thou across 4 in. I'm still working
out where to put the indicator so I can read it: the face ended up turned away
from me, and turning the spindle moves the indicator with it.

**The paper trick didn't work for me.** I tried finding the X edge with the end
mill and a strip of newspaper. I'd measured the paper with calipers a while ago
at about 3 thou. Either the paper wrapped itself around the spindle, or, when it
did catch properly, the 3 thou offset didn't match reality. With the DRO at
zero, I turned the spindle on to check, and the end mill didn't cut any chips:
it was farther from the edge than the DRO said.

**I laid out the length with a height gauge and gauge blocks,** the 2 in block
plus the gauge's dial for the rest. I know that's overkill, and I set it on
the mill table, not on a granite plate as I should have. I never got to compare
the scribed line with the DRO, because
the part was scrapped first.

**Then I switched to the edge finder** (0.200 in, at 900 rpm) and found the
edge, but I couldn't remember whether to add or subtract the radius on the DRO.
I didn't work it out; I tried it both ways until the end mill sat over the part.

**The first part was lost to the jog step.** I had both blanks in the vise, the
one I was facing and the second, still rough-cut, so the jaw would clamp
evenly. That was my plan. I was facing at 1500 rpm, 0.050 in deep, and the
handwheel step was supposed to be 0.001 in. It was on 0.010 in, ten times
coarser, and I forgot to turn it down. The cutter ran into the second blank
and pulled it up out of the jaws. Nothing was damaged except that blank, which
was scrapped. I've since set up macros in CNCjs, so I won't use the jog
control for actual cutting or facing.

**Then I drilled the part that was still good, and scrapped it too.** I tried
all six holes at 1500 rpm in the drill chuck, with the drawing's two tap-drill
sizes, and it went wrong several ways at once:

- I didn't know how to zero Z. I lowered the quill and turned the spindle by
  hand until I could feel the drill touching the part. I still don't know
  whether paper or something else is the right way.
- I forgot to centre-drill.
- The part wasn't on parallels or squared up in the vise, and I forgot to put a
  round rod against the moving jaw. It crept up about 0.01 in as I
  tightened the vise. I didn't have a dead-blow hammer to tap it down; I've
  bought one since (Tate Tools, 28 oz).
- I changed drills for the second size and forgot to re-zero Z. The hole came
  up about 1/4 in short; I saw that it hadn't come through when I looked
  underneath.
- One hole came out crooked, about 0.01 in by eye.

**What I'll do differently is everything I forgot:** tap the part down, know
which way to apply the edge-finder radius before I start, read up on zeroing Z,
and centre-drill first.

The 2026-10-30 advice was for the base bar, so none of it was tried here.

**The drawing does more work than the part needs.** Four #8-32 holes just to
screw the end block to the base bar is excessive. If the holes were tapped from
both ends, two holes could also hold the pillow block on top. That's two tapped
holes, one tap and one drill size instead of six through holes and two drill
sizes:
[#2287](https://github.com/pedropaulovc/harmonic-analyzer/issues/2287).

## Cost

- Time: 5.25 h
  - Setup 2 h.
  - Layout 0.75 h.
  - Cutting under 1 h, though I had to stop and think before each step.
  - Drilling 1.5 h.
- Material: two blanks used, two scrapped.
- Tooling: nothing broken.
- Bought: Tate Tools 28 oz dead-blow hammer.

## Open

- Make both end brackets again.
- Rework the end-bracket hole pattern:
  [#2287](https://github.com/pedropaulovc/harmonic-analyzer/issues/2287).
- Add the makerspace's 4 in vises, the Grizzly indicator, the edge finder and
  the dead-blow hammer to the shop inventory:
  [#2288](https://github.com/pedropaulovc/harmonic-analyzer/issues/2288).

## Follows up to

- Module: [`../curriculum/m06-mill-i-tramming-squaring-edge-finding.md`](../curriculum/m06-mill-i-tramming-squaring-edge-finding.md)
  (indicating, edge finding, facing); drilling under
  [`../curriculum/m08-hole-patterns-reaming-and-tapping.md`](../curriculum/m08-hole-patterns-reaming-and-tapping.md);
  layout under
  [`../curriculum/m01-measurement-and-layout.md`](../curriculum/m01-measurement-and-layout.md).
- Part: [`cad/config/parts/ch-rocker-arm-tl-oblique-end-bracket.yaml`](../../cad/config/parts/ch-rocker-arm-tl-oblique-end-bracket.yaml)
- Previous session: [2026-10-30](2026-10-30-pendant-and-roughing-base-bar-to-length.md)

## Photos

Contact sheet:
[`book/figures/hand/oblique-end-bracket-first-attempt-contact-sheet.jpg`](../../book/figures/hand/oblique-end-bracket-first-attempt-contact-sheet.jpg)
(1: the indicator on the jaw; 2: the vise on its keys; 3: height-gauge layout;
4–6: the facing crash).

Raw media, in OneDrive `Imagens/Imagens da Câmera/2026/11/`:

- `20261105_012746000_iOS.MOV`: indicating the vise jaw (22 s).
- `20261105_012814773_iOS.HEIC`: the indicator set up on the vise.
- `20261105_013132000_iOS.MOV`: paper edge-finding (16 min; paper caught at
  06:13).
- `20261105_015029000_iOS.MOV`: layout, edge finder, facing and the crash
  (33 min; crash at 28:03).
- `Temp/Seattle Makers 2.m4a`: my spoken answers to the interview.
