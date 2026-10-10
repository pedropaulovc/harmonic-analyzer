# Gear standard: why the replica cuts 20° inch-standard teeth

## Decision

Every gear in the replica uses a standard inch diametral pitch (DP) and a 20°
pressure angle (PA). These are anachronistic for a machine of the 1890s, and we
chose them on purpose so a hobby machinist can cut nearly every gear with a stock
involute cutter instead of making cutters for an odd pitch.

| Meshing domain | Parts | Tooth system |
|---|---|---|
| Cone and cylinder train | `dt-cone-gear` T006–T120, `dt-cylinder-gear` ×20 (120T), `dt-alignment-pinion` (32T) | 48DP, PA20, spur |
| Crossed crank pair | `dt-crank-pinion` (16T, straight), `dt-crank-drive-gear` (64T, right-hand helix 13.0011°) | normal 24DP, normal PA20 |
| Paper-drive reducer | `pd-rack-pinion` (120T disc), `pd-transgear-knob-shaft` (integral 12T) | 48DP, PA20 (same cutter set as the cones) |
| Paper feed | `pd-transgear-feed-pinion` (12T), `pd-platen-rack` | 32DP, PA20 |
| Chain | crank and knob sprockets, 68 links | ANSI #25 |

The configured values live in [`../config/machine/gear_train.yaml`](../config/machine/gear_train.yaml)
and the part specs (`dt_cone_gear_spec.py`, `dt_crank_drive_gear_spec.py`,
`pd_rack_pinion_spec.py`, `pd_transgear_feed_pinion_spec.py`). This document
records why we chose them and what they change. The cutter plan that follows from
them is in [`machining-dfm.md`](./machining-dfm.md#cutter-plan).

## What the original used, and how sure we are

No source states the original's pitch or pressure angle. The previous model used
DP 49.82 and PA 14.5°, and neither value was measured:

- DP 49.82 came from one scaled measurement, a 62.2 mm cylinder-gear outside
  diameter read off a book photograph at low confidence, solved for the pitch of
  a standard 120-tooth gear: (120 + 2) / 2.449 in
  ([`../config/dimensions.yaml`](../config/dimensions.yaml), "Diametral pitch /
  module"). It reconciles a photo with a tooth count. Nobody listed 49.82 as a
  pitch.
- PA 14.5° was assumed as "period-typical; not stated anywhere" (same file,
  "Pressure angle").
- The paper drive's DP 38 and DP 30 teeth were scaled the same way.

The 14.5° assumption has good period support. Brown & Sharpe's *Practical
Treatise on Gearing* (7th edition, 1902; copyrights from 1886) builds its
involute rack with lines of pressure at 75½° to the radius, which is a 14½°
pressure angle ([archive.org scan](https://archive.org/details/treatisegear00browrich)).
Brown & Sharpe's 1904 catalogue sold involute cutters by whole-number diametral
pitch, eight cutters to a pitch (No. 1 for 135 teeth to a rack down to No. 8 for
12–13 teeth). Its list for the No. 3 gear-cutting machine runs through 36, 40
and 48 DP, the finer pitches made to order
([archive.org text](https://archive.org/stream/BrownAndSharpeMachineryAndTools1904Catalogue/Brown+and+Sharpe+Machinery+and+Tools+1904+Catalogue_djvu.txt),
catalogue pp. 262–265). A shop of the period would have cut a listed pitch, so
49.82 is best read as a measurement artefact; 48DP is itself a pitch Brown &
Sharpe offered at the time.

20° became the default much later. AGMA adopted 20° as its preferred normal
pressure angle in the early 1980s; the gains are load capacity and fewer teeth
before undercut
([Dengel, *Gear Solutions*, Sept. 2017](https://gearsolutions.com/departments/tooth-tips-under-pressure/)).
Fine-pitch inch stock gears are easy to find at 20°: Boston's
48DP 20° list includes the 120T Y48120, and SDP/SI lists 48DP 20° 32T and 120T
spurs ([Boston spur catalogue](https://www.altraliterature.com/-/media/Files/Literature/Brand/boston-gear/catalogs/p-1930-bg-sections/p-1930-bg_spur-gears.ashx),
[SDP/SI D820](https://sdp-si.com/D820/PDFS/Gears.pdf)). 14.5° cutters are still
sold ([Toolmex 14½° list](https://www.toolmex.com/catsearch/230/involute-gear-cutters-14-1-2-degree-pressure-angle/8)),
so pressure angle alone did not decide this. The tooth-count arithmetic below
did. A 20° gear cannot mesh with a 14.5° gear
([KHK](https://khkgears.net/new/gear_knowledge/gear-nomenclature/gears-with-a-pressure-angle-of-20-degrees.html)),
so the whole train changes together.

## Why 20° and standard pitches

### Stock cutters

At DP 49.82 no cutter was sold, so every form cutter would have been made in the
shop. At 48DP PA20 the ordinary eight-cutter ranges cover every cone from 12T to
120T, the 120T cylinder gears, the 32T alignment drum and the paper reducer. The
6T cone is the one gear left needing a cutter you make.

### Cutter-native teeth

A range cutter is ground to the tooth of the lowest count in its range: #8 for
12–13 teeth, #7 14–16, #6 17–20, #5 21–25, #4 26–34, #3 35–54, #2 55–134. The
model draws every form-cut gear as the gap its stock cutter makes, not as an
ideal involute for its own tooth count. The 120T cylinder gears carry the #2
form (55T reference), the 32T alignment drum the #4 form (26T), the 16T crank
pinion the #7 form (14T), and the 64T crank gear the #2 form in its normal
section. Each cone is cut by the cutter for its own range at standard depth, so
the cutter's pitch line sits on the cone's pitch circle. Its blank is the AGMA
standard outside diameter, (N + 2)/DP, floored to 0.01 mm and cut down only
where the cutter's form would stop supporting the tip. The 6T cone is cut by
DT6-FORM1, a custom ground tool with its own sheet. The two 12T paper pinions
carry the #8 form, and their hubs are shaped so the cutter runs out clear.

### How the meshes are accepted

Each mesh gets the ordinary closed-form hand checks (`standard_mesh_checks`):
contact ratio, involute interference, backlash and root clearance, computed from
the printed tip and tooth-thickness limits of each gear and the booked range of
centre distance. The check uses each gear's ideal involute, which is the usual
shop approximation for range cutters; the SolidWorks assembly interference gate
checks the real flanks.

The tolerances are ordinary ones for a hobby build of an 1898 machine. Cone
blanks are OD +0/−0.05 mm and tooth thickness ±0.075 mm, and each cone and drum
is set up for tooth cutting within 0.05 mm TIR of its finished bore
(`dt_cone_gear_spec.py`; `tolerances.yaml`, `cone_drum_oblique_mesh`). T006
keeps its own thin-only bands (thickness +0/−0.04 mm, OD +0/−0.02 mm). Close
running fits elsewhere use the ordinary H7/g6 class (`_fit_limits.py`).

The cone centre distance is not fixed. It is set at assembly, so the gate is
written for a set mesh (`cone_set_stack`, `dt_mesh_checks`,
`test_standard_mesh_checks`):

- Cones T012–T120 must reach a contact ratio of at least 1.0 at the nominal
  set centre, and show no binding and no interference at the RSS corner of the
  centre and tooth bands. Nominal ratios run from 1.05 (T012) up to about 1.19.
- T006 is the named exception. No full-depth six-tooth form reaches a contact
  ratio of 1 against the 20° 120T drum, so T006 is gated instead on its
  DT6-FORM1 relief standing at least 0.010 mm clear of every printed drum-tip
  path over the RSS centre range, with at least 0.02 mm backlash. Its contact
  ratio, 0.775 at nominal and 0.766 at the RSS corner, is reference only.
- The crank pair has a fixed centre. It must reach a contact ratio of at least
  1.0 at the nominal centre (1.088) and must not bind at any tolerance corner.
  Its open-corner ratio is reference only.

Everything else these checks print is reference (REF): the RSS-corner contact
ratios and the arithmetic worst-corner interference. Among T012–T120 only T012
overlaps at the arithmetic worst corner, by 0.322 mm. That is a fit-up note on
the assembly sheet: if T012 binds after the set, back the swing off or stone
the T012 tip.

The alignment pinion only meshes while the readout is zeroed, with the notches
set by eye. It must not bind; its contact ratio is reported, not gated.

### Setting the cone mesh

The cone set swings on a platform. The cone-lock knob, MHA-VN-013, sets and
locks the engaged mesh at assembly. The swing stop screw, MHA-VN-015, only
limits how far the set swings out when disengaged; it plays no part in the
mesh. The order, from note 4 of the drive-train assembly sheet:

1. Ease the arbor-pedestal screws to snug-loose.
2. Swing in on radial shims, cone tip to drum root, at T012 and T120, so the
   arbor lines up with the cone line. Tighten the pedestal screws.
3. Swing in until a feeler is snug between the T120 tip and the drum root, hold
   it there, and lock MHA-VN-013.
4. Do not loosen the pedestals after the set. If you do, redo both steps.

The set cannot correct a pivot that moves sideways, so the platform pivot is
reamed Ø6.350 H7 (6.350–6.365 mm) on the stock 91829A560 shoulder, and the
base's pivot seat is held ±0.05 mm from the pedestal seats, machined in one
setup.

### Undercut

A full-depth standard rack undercuts a gear with fewer than
2 / sin²α teeth: 17.1 at 20° and 31.9 at 14.5°, the usual "17 and 32"
([KHK involute profile reference](https://khkgears.net/new/gear_knowledge/gear_technical_reference/involute_gear_profile.html)).
Five cones (6T to 30T) sit below the 14.5° limit; at 20° only the 6T and 12T do.

### Contact ratio on the small cones (study)

The study that chose the standard compared ideal involute teeth, before the
cutter-native ruling. The oblique cone mesh is backed off from standard centre
distance, so the small cones ran below a contact ratio of 1 at the worst
printed tolerance corner, and the 20° train improved every one of them. Values
are the deep-edge planar screen, nominal / worst:

| Cone | DP 49.82 PA14.5 | 48DP PA20 |
|--:|--:|--:|
| 6T | 0.659 / 0.179 | 0.928 / 0.650 |
| 12T | 0.920 / 0.430 | 1.223 / 0.804 |
| 18T | 1.104 / 0.606 | 1.331 / 0.907 |
| 24T | 1.252 / 0.747 | 1.413 / 0.985 |
| 30T | 1.375 / 0.864 | 1.468 / 1.036 |
| 36T | 1.482 / 0.966 | 1.517 / 1.082 |
| 42T | 1.577 / 1.056 | 1.542 / 1.104 |

From 48T up the worst-case ratio stays between about 1.12 and 1.21 in both trains.
These are comparison values only; the built teeth are accepted as described in
[How the meshes are accepted](#how-the-meshes-are-accepted).

### Paper-drive 12T pinions (study)

As ideal teeth, both 12T paper pinions needed positive profile shift to avoid
undercut: x = +0.298 with a 0.437-module tip land at 20°, against x = +0.624
with only 0.272 module of land at 14.5°. The built pinions are cut instead with
the stock #8 form, the feed pinion with the 32DP cutter and the knob pinion with
the 48DP cutter from the cone set.

## Why not 14.5° at 48DP

We built and ran a 48DP PA14.5 train to keep the period tooth form. It failed for
two independent reasons.

1. The small cones would still need special cutters. A stock cutter is made
   for the lowest tooth count in its range. Fitted to the cone profiles, the best
   PA14.5 cutter misses the 12T flank by 0.26 mm, against a 0.06 mm backlash
   screen; the PA20 #8 cutter misses the same cone by 0.004 mm. The 12T to 36T
   cones all fail at 14.5°, so the period form would have kept five custom
   cutters plus the 6T special.

   | Cone | Cutter | Max flank error, PA14.5 | Max flank error, PA20 |
   |--:|:--:|--:|--:|
   | 12T | #8 | 0.261 mm | 0.004 mm |
   | 18T | #6 | 0.225 mm | 0.014 mm |
   | 24T | #5 | 0.164 mm | 0.043 mm |
   | 30T | #4 | 0.121 mm | 0.049 mm |
   | 36T | #3 | 0.098 mm | 0.005 mm |

2. The crank mesh fell below its floor. With the crank and post architecture
   kept, the PA14.5 cone line pushed the 16:64 crank pair to a worst-case
   contact ratio of 0.572, under the retained 0.60 floor, and the native drive
   train assembly refused to build.

The 6T is a special at either angle. At 14.5° it needs a shift of at least
x = 0.838 to keep the 120T drum tips off its base circle, against 0.649 at 20°.

## What changes visibly

The pitch change from 49.82 to 48 scales every standard diameter by +3.79%.

- Cylinder gears (120T, #2 form): OD 62.20 → 64.44 mm. Alignment drum (32T, #4
  form): OD 17.33 → 17.63 mm. Both blanks sit under the ideal 48DP tips (64.56
  and 17.99 mm) so that the whole cutter-form flank stays inside the stock
  cutter's ground profile at every tolerance corner.
- Cone incline: 12.518° → 13.001°. Cone face width: 6.8887 → 6.8756 mm. The
  7.0565 mm channel pitch is unchanged.
- Cone outside diameters follow the AGMA standard blank: 7.26 mm at 12T up to
  64.35 mm at 120T, where the #2 cutter's form caps it just under the ideal
  64.56 mm. T006 is 4.31 mm, above its AGMA 4.23 mm, so that its tip keeps a
  quarter-module land. The values are in `dt_cone_gear_spec.py`.
- Crank pair: centre distance 39.77 → 43.52 mm (+9.44%); 16T OD 17.38 → 18.87 mm;
  64T OD 65.21 → 71.04 mm. To make room the crank and the cone journals rise
  4.732 mm together, the cone pivot post grows from 86 to 94.732 mm (head 26.6 mm),
  the swing platform loses its relief pocket under the 64T, and the post
  mounting screw becomes a 4 in 1/4-20 (MSC 40923906) cut to 94.9 mm.
- Paper drive: the reducer keeps its 12:120 counts, which fit the photographed
  1898 disc best, but is cut at 48DP with the cone cutters. The disc shrinks from
  OD 81.55 mm to 64.54 mm, about 21% smaller. The change is deliberate: one
  48DP cutter set then serves the cones, the cylinder gears and the reducer.
  The 12T 32DP feed pinion runs on a purchased SDP/SI A1B12-Y324 32DP rack,
  which shortens the paper advance from 1.596 to 1.496 mm per crank turn
  (−6.25%). The chain stays ANSI #25, 68 links, on the 12T crank and 24T knob
  sprockets.
- Tooth form: a 20° tooth has a smaller base circle (0.940 of pitch diameter,
  against 0.968 at 14.5°), so its flanks are more curved and its tip narrower.
  At 48DP the whole tooth is about 1.2 mm deep, so the difference shows under a
  loupe rather than across the room.

## What it costs

- The 6T cone still needs a cutter you make. No ordinary cutter range reaches
  6 teeth. In the first 48DP study its root-to-bore web fell from 0.621 mm to
  0.354 mm, because the PA20 gap floor sits lower. The terminal journal was
  then cut to 1/32 in. With DT6-FORM1 the printed gap floor is Ø2.136 mm MIN,
  which leaves a 0.64 mm web over the largest allowed bore, against a 0.62 mm
  floor (the one named web exception).
- The 64T crank gear is a true helix. Cutting it needs a spiral-capable
  universal dividing head geared to the table leadscrew (lead 945.86 mm per
  turn). A plain or semi-universal indexing head cannot do it; the shop's
  Precision Matthews BS-0 is sold as semi-universal, while the BS-2 is sold as
  able to cut spirals
  ([BS-0](https://www.precisionmatthews.com/products/dividinghead-bs-0),
  [BS-2](https://www.precisionmatthews.com/products/dividinghead-bs-2)).
  The previous crank pair was also a crossed helical pair, so this cost is not
  new, but it is now explicit.
- The meshes are not conjugate. Drawing each gear as its cutter's form removes
  the earlier mismatch between range cutters and ideal profiles, at the price
  of some transmission error in each mesh, which the model does not quantify.
- The paper scale changes by −6.25%, as above.

## Sources

- Evidence reports from the gear-standard study (2026-10-08): 48DP PA20 cone
  study, 48DP PA14.5 cone study, all-inch drive train integration, inch paper
  drive, and the analytic mesh screen. Branches `exp/gear-std-cone-48pa20`,
  `exp/gear-std-cone-48pa145`, `exp/gear-std-inch-train` and
  `exp/gear-std-full-inch`.
- Brown & Sharpe Mfg. Co., *Practical Treatise on Gearing*, 7th ed., 1902,
  [archive.org](https://archive.org/details/treatisegear00browrich).
- Brown & Sharpe Mfg. Co., *Machinery and Tools* catalogue, 1904, involute cutter
  lists, [archive.org](https://archive.org/details/BrownAndSharpeMachineryAndTools1904Catalogue).
- Ivan Law, *Gears and Gear Cutting*, ch. 12 (`references/gears-and-gear-cutting/`):
  shop-made form cutters shaped with a button tool; the Eureka device there is
  a relieving attachment, not a way to generate the form.
- B. Dengel, "Under Pressure," *Gear Solutions*, September 2017,
  [gearsolutions.com](https://gearsolutions.com/departments/tooth-tips-under-pressure/).
- KHK, [Gears with a pressure angle of 20 degrees](https://khkgears.net/new/gear_knowledge/gear-nomenclature/gears-with-a-pressure-angle-of-20-degrees.html)
  and [involute gear profile](https://khkgears.net/new/gear_knowledge/gear_technical_reference/involute_gear_profile.html).
- C.R.Tools, [DP PA20 involute gear cutters](https://crtoolsuk.com/product/diametrical-pitch-involute-gear-cutters/);
  Newman Tools, [involute and module cutter chart](https://www.newmantools.com/cutters/gear.htm).
