---
date: 2026-10-29
module: M06
machine: mill
part: ch-rocker-arm-tl-oblique-base-bar
outcome: partial
hours: 6.5
---

# Install the 6 in vise and start the oblique-jig base bar

## Setup

- **Stock:** 6061-T6511 flat bar, 1/2 × 6 × 72 in (OnlineMetals 1173), for the
  oblique-jig base bar (`ch-rocker-arm-tl-oblique-base-bar`, MHA-CH-06-TL-20).
  Length of the piece cut: not recorded.
- **Workholding:** Precision Matthews 6 in vise on the PM-30MV table, held down
  with T-bolts. I didn't tram the head; I trusted it was square, because I
  don't feel ready to tram a head yet. Fixed jaw indicated along X to ±12.5 µm
  (25 µm total, about 0.001 in) over the jaw's length. For the first cut the
  bar stood on edge, gripped across its 1/2 in thickness between the stock
  hard jaws, about 6 in sticking up, no parallels.
- **Tooling:** 1/2 in 2-flute HSS end mill, cutting with its bottom on the bar's
  long edge. Sawing on a miter saw (model and blade not recorded; see Open).
  Layout with Dykem, a tungsten scriber and a combination square.
- **Control:** the mill is CNC-converted. The plan was to practise manual
  milling through CNCjs, with a pendant as the handwheel and an EL400
  simulator as the DRO, so I don't have to undo the conversion.

## Operations

| # | operation | tool | RPM | feed | DOC | result |
|---|---|---|---|---|---|---|
| 1 | install vise, indicate fixed jaw in X | Mitutoyo dial indicator in an R8 collet | — | — | — | ±12.5 µm over the jaw, after 1.5 h |
| 2 | lay out the cut line | Dykem, tungsten scriber, combination square | — | — | — | line smeared: Dykem still wet |
| 3 | saw off the bar | miter saw, no lubricant | not recorded | by hand | — | cut easily; two passes left a step |
| 4 | mill long edge | 1/2 in 2-fl HSS end mill | 2500 | 10 mm/min (keyboard jog) | 0.1 mm | very clean |
| 5 | mill long edge | same | 2500 | 10 mm/min | 1 mm | very clean |
| 6 | mill long edge | same | 2500 | 10 mm/min | 2 mm | great finish, no chatter; vibration felt through the floor |

## Measured

Nothing yet. The milled edge hasn't been measured for width, squareness or
finish.

## What happened

**Installing and indicating the vise took 1.5 hours,** and the indicator was
the struggle. I started with my Mitutoyo dial gauge (1 µm graduations) on its
magnetic base stuck to the spindle. It wasn't solid or stable enough: the
readings wouldn't repeat. What fixed it was working out how to move the
indicator holder's support pin so I could grip it in a proper R8 collet.
That got the fixed jaw to ±12.5 µm end to end. The indicator reads to 1 µm,
but 25 µm is about a thou, and that's good enough for this job.

**Sawing a 72 in bar on a miter saw is awkward.** I laid out the line with
Dykem, the scriber and the square, but didn't wait for the Dykem to dry.
The square and scriber dragged it around and made a mess. Acetone cleaned
off the excess cleanly. Next time I'll let it dry first. I sawed with the
1/2 in edge down on the saw table. The bar blocked the blade's full travel,
so I had to cut in two passes, and where the passes met there's a step. Without
lubricant the aluminium cut really easily. I propped up only the long end.
The scary moment was at the end of the cut: the roughly 5½ ft offcut came
free. It didn't fall off, but it could have.

**The vise only opens to 5¾ in.** I found that out trying to clamp the piece I'd
just cut: the bar is 6 in wide, and the vise with its stock hard jaws only takes
5¾ in. I changed the drawing to make the finished bar narrower: the base bars
are now 5½ in wide ([#2079](https://github.com/pedropaulovc/harmonic-analyzer/pull/2079)).
That PR switched to buying 1/2 × 5-1/2 bar, but I've since decided to keep using
the bar I have and mill the 6 in piece down to width.

**For the first cut** I stood the bar on edge in the jaws and milled the long
edge with the bottom of the end mill, centring the cutter over the 1/2 in edge
by eye. I looked up speeds and feeds for a 1/2 in 2-flute HSS end mill on a
couple of online calculators. I'm not confident in those numbers yet, and they
were all in inches when I wanted millimetres to match the drawing. I ran 2500
rpm and jogged at 10 mm/min. I started at 0.1 mm deep, then went to 1 mm and
then 2 mm. Every pass was very clean. At 2 mm I could feel the machine
vibrating through the floor, but the finish stayed great and there was no
chatter.

**The CNCjs pendant didn't work.** I spent an hour trying to get the pendant to
push its events to CNCjs and couldn't, so I jogged from the keyboard instead.
I'll try again today. I should have tested the CNCjs integration at home with
the simulator before taking it to the shop.

## Cost

- Time: 6.5 h
  - Setup 4 h: vise install and indicating 1.5 h, pendant 1 h, layout 0.5 h,
    break 0.5 h, and oiling the vise and hunting for a wrench for the rest.
  - Sawing 0.5 h.
  - Cutting 2 h.
- Material: one piece cut from the 72 in bar; none scrapped.
- Tooling: nothing broken or worn.

## Open

- Measure the milled edge.
- Retry the CNCjs pendant.
- Reconcile the CAD and inventory with milling the owned 6 in bar to width:
  [#2083](https://github.com/pedropaulovc/harmonic-analyzer/issues/2083).
- Add the miter saw's model and blade size to the shop inventory:
  [#2084](https://github.com/pedropaulovc/harmonic-analyzer/issues/2084).

## Follows up to

- Module: [`../curriculum/m06-mill-i-tramming-squaring-edge-finding.md`](../curriculum/m06-mill-i-tramming-squaring-edge-finding.md)
  (vise indicating, first milling); layout under
  [`../curriculum/m01-measurement-and-layout.md`](../curriculum/m01-measurement-and-layout.md).
- Part: [`cad/config/parts/ch-rocker-arm-tl-oblique-base-bar.yaml`](../../cad/config/parts/ch-rocker-arm-tl-oblique-base-bar.yaml)

## Photos

Photos to be taken on 2026-10-30.
