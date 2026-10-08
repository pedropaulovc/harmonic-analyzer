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

At DP 49.82 there was no cutter to buy, so the plan was to
make every form cutter by the Eureka method. At 48DP PA20 the ordinary eight-cutter
ranges cover every cone from 12T to 120T, the 120T cylinder gears and the 32T
alignment drum. The 6T cone is the one gear left needing a special cutter.

### Cutter-native teeth

A range cutter is ground to the tooth of the lowest count in its range: #8 for
12–13 teeth, #7 14–16, #6 17–20, #5 21–25, #4 26–34, #3 35–54, #2 55–134. The
model draws every form-cut gear as exactly the gap its stock cutter makes, not
as an ideal involute for its own tooth count. The 120T cylinder gears carry the
#2 form (55T reference), the 32T alignment drum the #4 form (26T), the 16T
crank pinion the #7 form (14T), and the 64T crank gear the #2 form in its normal
section. Each cone carries the form of its own range, with its blank diameter
and plunge solved against the stock-form drum it meshes. The 6T cone uses a
named special single-point cutter. The two 12T paper pinions carry the #8 form,
and their hubs are shaped so the cutter runs out clear.

Gears cut this way do not mesh conjugately, so a classical contact ratio no
longer describes them. The model reports stock-form coverage instead: the 3D
union of the angular spans over which a supported contact exists, including
tip-corner and face-edge contact, divided by the tooth pitch. Coverage is
neither a contact ratio nor a loaded-contact check. Each drive mesh must also
keep contact with no gap between teeth, hand over within 0.005 mm, and hold
positive backlash at every tolerance corner (0.06–0.41 mm for the cones), and
its transmission error is charged to the existing nominal-residual budget. The
required coverage is at least 1.1 for every cone and 0.62 for the crank pair.
The alignment pinion is only meshed while the readout is zeroed, with the
notches set up by eye, so it is checked for continuity, backlash and root
clearance instead. The cone and crank meshes are crossed or oblique, so these
checks run on the 3D solids (`cad/scripts/diagnostics/oblique_cone_mesh_study.py`
and `stock_form_contact_3d.py`); a planar screen is reported alongside but does
not count. The final values are in the part specs.

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
These are comparison values only; the built teeth are checked by stock-form
coverage, as above.

### Paper-drive 12T pinions (study)

As ideal teeth, both 12T paper pinions needed positive profile shift to avoid
undercut: x = +0.298 with a 0.437-module tip land at 20°, against x = +0.624
with only 0.272 module of land at 14.5°. The built pinions are cutter-native
instead: the standard #8 gap moved along its centreline, with blank diameter
and plunge solved from that geometry.

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
- Cone outside diameters are solved per cone against the stock-form drum. The
  study's long-addendum tips (6T 4.16 mm, 120T 64.85 mm) are superseded by the
  values in `dt_cone_gear_spec.py`.
- Crank pair: centre distance 39.77 → 43.52 mm (+9.44%); 16T OD 17.38 → 19.05 mm;
  64T OD 65.21 → 71.63 mm. To make room the crank and the cone journals rise
  4.732 mm together, the cone pivot post grows from 86 to 94.732 mm (head 26.6 mm),
  the swing platform grows 7.5 mm longer with no relief pocket under the 64T, and
  the post mounting screw becomes a 4 in 1/4-20 (MSC 40923906) cut to 94.9 mm.
- Paper drive: the reducer keeps its 12:120 counts, which fit the photographed
  1898 disc best, but is cut at 48DP with the cone cutters. The disc shrinks from
  OD 81.55 mm to just under 64.6 mm, about 21% smaller. The change is deliberate: one
  48DP cutter set then serves the cones, the cylinder gears and the reducer. The
  32DP feed pinion and the purchased 32DP rack shorten the paper advance from
  1.596 to 1.496 mm per crank turn (−6.25%). The chain is 68 links
  of ANSI #25.
- Tooth form: a 20° tooth has a smaller base circle (0.940 of pitch diameter,
  against 0.968 at 14.5°), so its flanks are more curved and its tip narrower.
  At 48DP the whole tooth is about 1.2 mm deep, so the difference shows under a
  loupe rather than across the room.

## What it costs

- The 6T cone still needs a cutter you make. No ordinary cutter range reaches
  6 teeth. In the first 48DP study its root-to-bore web fell from 0.621 mm to
  0.354 mm, because the PA20 gap floor sits lower. The terminal journal was
  then cut to 1/32 in, which restores a 0.7485 mm minimum web. Its cutter is a
  named single-point fly cutter, DT6-FORM1.
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
  of a small transmission error in each mesh, which the model bounds and
  propagates to the drum and channel phase.
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
- B. Dengel, "Under Pressure," *Gear Solutions*, September 2017,
  [gearsolutions.com](https://gearsolutions.com/departments/tooth-tips-under-pressure/).
- KHK, [Gears with a pressure angle of 20 degrees](https://khkgears.net/new/gear_knowledge/gear-nomenclature/gears-with-a-pressure-angle-of-20-degrees.html)
  and [involute gear profile](https://khkgears.net/new/gear_knowledge/gear_technical_reference/involute_gear_profile.html).
- C.R.Tools, [DP PA20 involute gear cutters](https://crtoolsuk.com/product/diametrical-pitch-involute-gear-cutters/);
  Newman Tools, [involute and module cutter chart](https://www.newmantools.com/cutters/gear.htm).
