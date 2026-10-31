---
date: 2026-10-30
module: M07
machine: mill
part: ch-rocker-arm-tl-oblique-base-bar
outcome: scrapped
hours: 5.0
---

# Get the pendant working, then rough the base bar to length

Continues [2026-10-29](2026-10-29-vise-install-and-first-cuts.md).

## Setup

- **Stock:** the 443 mm piece I sawed on 10-29 from the 1/2 × 6 in 6061-T6511
  bar, for the oblique-jig base bar (`ch-rocker-arm-tl-oblique-base-bar`,
  MHA-CH-06-TL-20). The goal was to rough the end down to the 440 mm length.
- **Workholding:** same as 10-29. The bar stood on edge in the 6 in vise's hard
  jaws, gripped across its 1/2 in thickness, about 6 in sticking up.
- **Tooling:** a 5/8 in 4-flute TiN-coated HSS end mill that was lying around,
  in a 5/8 in R8 collet. I used it instead of the plan because I was curious
  how hard I could push the machine. Tap Magic as the cutting fluid.
- **Control:** CNCjs on the laptop, the pendant as the handwheel, and the EL400
  simulator as the DRO. Spindle speed set by hand on the knob.
- **Speeds and feeds:** I asked Claude. It suggested starting side roughing at
  1700 rpm, 400 mm/min, 0.500 in axial depth and 0.060 in radial step-over,
  and full-width slotting at 1500 rpm and 230 mm/min. It said to use
  conventional milling if the machine still had backlashy lead screws.

## Operations

| # | operation | tool | RPM | feed | DOC | result |
|---|---|---|---|---|---|---|
| 1 | get the pendant talking to CNCjs | — | — | — | — | works after installing a driver |
| 2 | touch off on the bottom-right corner | side of the cutter, spindle turned by hand | — | — | — | Y travel about 5 mm short of the top-left corner |
| 3 | side-mill the end (climb, without realizing) | 5/8 in 4-fl TiN HSS | on the knob; not recorded | 400 mm/min | radial in 0.100 or 0.150 in steps; axial not recorded | chatter; needle chips |
| 4 | side-mill the end | same | 1500 | 400 mm/min | 0.150 in radial, 1 in axial | loud ringing; I backed into the cut; spindle e-stop; cutter pulled 1/4 in out of the collet; part gouged |
| 5 | full-width shallow cuts | same, reseated | 1500 | 230 mm/min | not recorded | a lot of chatter; loose arc chips |
| 6 | full-width shallow cuts | same | 1000–1200 | 230 mm/min | not recorded | acceptable |

## Measured

Nothing. I didn't remeasure the piece before cutting, and I haven't measured
the scrapped piece yet.

## What happened

**The pendant mostly works now.** Yesterday it wouldn't send its events to
CNCjs. The fix was installing a driver, which Claude sorted out. I used the
EL400 simulator only to check that it's integrated, not for any actual cuts.
What's still wrong or unclear:

- I can't tell how to switch the pendant display between work and machine
  coordinates.
- The feed rate shows in mm even in inch mode.
- The link to the microcontroller is very slow. If I jog quickly in step mode,
  the jogs queue up as G-code lines and the table keeps moving after I stop,
  in one case all the way to the end of the table. The pendant's stop button
  stops it within about a second.
- The pendant stops working when the laptop screen turns off.

Since step jogs queue up anyway, I set the step jog to 400 mm/min in the
pendant config and used it as a poor man's power feed. It worked OK. Proper
macros are the real fix.

**I deviated from the plan.** I picked up the 5/8 in 4-flute end mill to rough
the end of the bar down to length, partly to see how much the machine could
take. I followed the speeds and feeds at first, setting the RPM on the knob and
the feed in mm/min, but I don't remember the depth and step-over I started
with. Then I made several mistakes.

**I forgot how much I was supposed to rough off,** and removed too much. I
should have remeasured the piece before cutting. I also kept forgetting
whether I was taking 0.100 or 0.150 in at a time, so I was never sure the
cutter was where I thought it was.

**I was climb milling while I thought I was conventional milling.** I only
worked it out the next day at home, holding my right hand thumbs down with my
fingers playing the cutting side of the end mill.

**The axes confused me.** A positive X or Y jog moves the table toward me and
to the left. That makes sense from the end mill's point of view, but positive
Z is up. I jogged in the wrong direction many times.

**The scary one** (video 04:31–05:11). I was taking 0.150 in radial at 1 in
axial depth, 1500 rpm and 400 mm/min, and the part started ringing loudly. I
tried to back off in Y, went the wrong way, and pushed the cutter further into
the cut. That made it worse, and I hit the spindle e-stop. The force pulled
the end mill 1/4 in down out of the collet. I noticed because the uncoated
part of the shank was sticking out below the collet. The end mill looks fine,
so I reseated it and carried on. The part was gouged, and that's when I
realized it was scrapped.

**Side milling was a bad choice here.** It made a lot of chatter. Shallower,
full-width cuts at 230 mm/min went better. Spindle speed mattered: a
full-width cut that chattered a lot at 1500 rpm was acceptable at 1000 to
1200 rpm.

**Chips looked good,** breaking off cleanly: needle chips from the side
cutting and loose arc chips from the full-width cuts (chip shapes as in
[this chart](https://ars.els-cdn.com/content/image/3-s2.0-B9780444637116000077-f07-02-9780444637116.jpg)).

**I zeroed off the wrong corner.** The table can't travel far enough in Y
toward me to reach the part's top-left corner; it ran out about 5 mm short. I
should have moved the vise and re-indicated it, but I was lazy and zeroed off
the bottom-right corner instead, touching off by turning the spindle by hand
until the side of the cutter met the part. From there I was winging it.

I also kept mixing up axial and radial when reading the speeds and feeds. A
linear pattern on the EL400 would probably have made the repeated passes
easier, but I'd forgotten how to use it.

Next time: follow the plan.

## Cost

- Time: 5 h
  - Pendant 1.5 h.
  - Cutting 3 h.
  - Cleanup 0.5 h.
- Material: the 443 mm piece, scrapped. It may be reusable for another
  oblique-jig part.
- Tooling: the 5/8 in end mill pulled out of the collet under load. It looks
  fine.

## Open

- Practise jogging the machine with the DRO, and relearn the EL400 simulator,
  including its linear pattern.
- Set up proper jog macros for power feed so the serial link isn't overloaded.
- Work out the pendant's work/machine coordinate display and its feed units in
  inch mode, and why it stops when the laptop screen turns off.
- Measure the scrapped piece and check whether it can make another part of the
  oblique jig.
- Move the vise so Y can reach the part's top-left corner, then re-indicate it.

## Follows up to

- Module: [`../curriculum/m07-mill-ii-profiling-slots-workholding.md`](../curriculum/m07-mill-ii-profiling-slots-workholding.md)
- Previous session: [2026-10-29](2026-10-29-vise-install-and-first-cuts.md)
- Part: [`cad/config/parts/ch-rocker-arm-tl-oblique-base-bar.yaml`](../../cad/config/parts/ch-rocker-arm-tl-oblique-base-bar.yaml)

## Photos

- Video of the roughing, including the ringing and the e-stop at 04:31–05:11:
  `OneDrive/Imagens/Imagens da Câmera/2026/10/20261031_022544000_iOS.MOV`
  (13 min 19 s).
- The 10-29 photos haven't been taken yet.
