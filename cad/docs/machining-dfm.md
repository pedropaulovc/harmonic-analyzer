# Machining DFM — per-part manufacturability pass (Tier-1)

> Companion to [`tolerance-gdt-assessment.md`](./tolerance-gdt-assessment.md). That doc's §6 tiers
> the parts by **tolerance/fit/GD&T** effort; this one is the **machinability** layer for the same
> Tier-1 parts — *can the machinist actually cut this, in what stock, in how many setups, and where
> will it fight back.* Generic DFM checklists ("radius internal corners", "minimize setups") are
> useless as bare bullets; every row below is attached to a **named feature with a real number** from
> the build script. Audience + toolchain per §1/§11: period **brass + steel**, on a **manual** shop
> (`cad/process/shop/inventory.toml`): the **PM-30MV mill, handwheels on all three axes read on a DRO**
> (`operation_mode = "manual_with_digital_positioning"`), the **PM-1127VF-LB lathe** and the **BS-0
> dividing head**. There is no CNC: the repeat parts get their repeatability from fixtures, stops and
> indexing.

All numbers are from the `cad/scripts/build_*.py` sources (mm). Where a part is modeled as a
**casting** but you intend to cut it from bar, that is a *substitution* — flagged, because the
geometry is casting-shaped, not milling-shaped.

The `dt-arbor-pedestal` and `dt-cone-pivot-post` inside corners take the
shop-wide **R1.0 MAX** title-block default. Their former duplicate local notes
and time-limited inside-corner exceptions have been retired; the sharp modeled
junctions and the post's separate crank-bore angularity authorization are
unchanged. The cylinder gear's native notch-phase dimension and Detail A define
its first-root position; no second general note restates that location.

## The headlines (read these first)

- **Three parts carry the whole risk. Everything else is generous.**
  1. **`dt-cone-tip-gear` (T006, MHA-DT-37)** — six leaves on a **Ø4.31 mm OD** solid, with an integral
     Ø.0625 in spigot (.71 in long, L/D about 12) to the south and an integral Ø.0625 in pivot (.25 in) to the north
     (owner decision C1 keyed, 2026-11-09, PR #1992). The single hardest part in the machine. Its
     turning route is **not selected**: the part's process text and sheet note 3 (`CENTRES OK.`) name
     centres and a steady, but no listed centre or steady rest fits a Ø.0625 stem
     ([#2468](https://github.com/pedropaulovc/harmonic-analyzer/issues/2468)). The teeth are involute
     flanks closed by a gap floor with printed diameter limits, and the floor, cut by DT6-FORM1, is
     Ø2.136 MIN / Ø2.201 MAX, the cutter running off over both stems (.011 in radial). T006 has no bore, so
     the former 0.62 mm web floor exception is gone. The thinnest cone web is now T012's 1.641 mm
     (.0646 in MIN, owner-accepted RV-03) over its reamed Ø.0625 in bore on the spigot; the T018 and T024
     webs meet the target.
     Period mitigation: the tip gears were a harder yellow metal.
  2. **`sm-summing-lever` knife edge** — the sharp top-vertex ridge of a hex trunnion that protrudes
     **21.717 mm unsupported** past each end of a casting-shaped organic lever. Delicate (nicks/rounds)
     *and* fixturing-hostile from bar. Per §6 the edge should be a **separate hardened tool-steel
     insert**, not this parent — which also removes it from this part's machining hazard.
  3. **The bonded cone tip** (owner decision C1 keyed, 2026-11-09, PR #1992) — T024 bonded with LOCTITE 638
     on round land 2 one 0.45 ±0.10 feeler off T030 (0.35–0.55 mm stack float); T018 and T012 bonded on the
     MHA-DT-37 spigot, whose end is bonded in the reamed Ø.0625 × .20 in socket in MHA-DT-04's end; land 2
     ends .025 in inside T024's bore so T018 always butts T024. Degrease, phase each bonded gear to the keyed
     stack within the compound's fixture time with the MHA-DT-03-TL-02 phasing comb (owner rulings
     2026-11-09 and 2026-11-10: one blade per gear in the tooth space beside its phase-0 tooth, T030 to
     T006), and let it cure before load; a bonded
     slip fit has nothing to adjust afterwards. The bonds cure in two rounds (#2470), each accepted on the
     comb once cured. Step 1 bonds T024 alone, its joint degreased, then T030's back face, the key's back end
     and the feeler waxed (none on the land) against its squeeze-out; once T024 has cured and the wax is
     wiped off, the comb must drop into T030 and T024. Step 2 then bonds T018, T012 and the spigot, the
     spigot held home in its blind socket until the bonds grab, and the cured comb must drop into all five
     gears. A failed round's parts come off at about 250 °C, the cured film is cleaned off every parted face,
     and the round is redone (the second from MHA-DT-38's check: the heat frees a bond there too).
     The MHA-DT-38 brass bushing is pressed on the pivot against the leaves, made to its measured bore.
     The MHA-DT-39 end screw (stock 91794A558 with a reamed Ø.0630 × .12 in pivot hole, wall to the 2A
     thread root .067 in MIN, RV-01) threads into MHA-DT-21: run it in until the shaft stops shuttling, back
     off 1/8 turn for 0.05–0.25 mm end play, then tighten the pinch screw. Ream the end-screw hole held on
     its thread so it runs true. MHA-DT-21's axis height is made to the measured MHA-DT-05 journal-axis
     height above MHA-DT-20 (matched fit, ±.003 in) so the pivot enters the end screw; tighten the block's
     hold-down with the pivot running free in MHA-DT-39. At the print-worst stack the end screw keeps 1.39D
     of full thread in the block, under rule 18's 1.5D (accepted by owner ruling 2026-11-09, dt-drive-train DT-07).
     `dt_cone_tip_air.py` owns the cone-tip air to G19 over the whole swing: the bushing, the end
     screw's proud end and MHA-DT-21's south face where it stands over G19. Use worst-case arithmetic
     over every source if it clears everywhere; otherwise use the statistical method everywhere: nominal
     air minus the arithmetic sum of `IN_SERVICE_CLEARANCES`, minus the RSS of independent printed
     manufacturing and set tolerances, minus the swing-interval arc allowance. Fastener and running
     clearances, thread centring, shaft swing in the post journal and G19 cock can all be taken up
     together; never put them in the RSS. The current calculated least air is 0.112 mm at the bushing,
     3.945 mm at the end screw and 5.094 mm at the block (`dt_cone_tip_air.require_air()`), not a measured
     clearance; `_native_cone_tip_air` checks the saved bodies against it.
     The shaft drawing (one sheet, **Shaft Controls**) dimensions each chucking
     from its own collar face (rule 11): the journal and the collar web from the
     journal-side thrust face, the land step and the tip from the
     collar's tip-side (MHA-DT-07 seat) face. The journal, web and tip station
     chain the two ends; the front-to-tip overall is a reference. The
     presentation does not prescribe a workholding arrangement.

- **The repeat families (make N identical by hand: the shop is manual, so fixtures, stops and indexing carry the repeatability):**
  | family | qty | repeat risk and route |
  |---|---|---|
  | `dt-cylinder-gear` (+ integral cam) | 20 | 120 teeth + eccentric cam + 0.4 mm index notch, all co-phased +Y — hand-repeating 20× scatters the phase. Teeth with the stock #2 cutter on the BS-0; the cam's throw and phase need an eccentric fixture that is not drawn, so the cam route is **not selected** ([#2361](https://github.com/pedropaulovc/harmonic-analyzer/issues/2361)); the notch needs a .014 in screw-slotting saw that is not yet owned (`shop-equipment.toml` `tools.cylinder-notch-saw`, [#2364](https://github.com/pedropaulovc/harmonic-analyzer/issues/2364)) |
  | `dt-cone-gear` | 19 | involute teeth cut with stock 48DP PA20 range cutters indexed on the BS-0 dividing head; T006 (`dt-cone-tip-gear`) alone needs a special cutter (see [Cutter plan](#cutter-plan)); wire-EDM = outsource alt; the cutters and arbors are not yet in the inventory ([#2356](https://github.com/pedropaulovc/harmonic-analyzer/issues/2356)) |
  | `ch-rocker-arm` / `ch-channel-lever` hubs | 20 each | the integral hubs stack face to face and set the 7.0565 channel pitch; the 19 `pivot-bushing` and 19 `lever-bushing` spacers are retired. Hub width consistency across each set is the point ([#2344](https://github.com/pedropaulovc/harmonic-analyzer/issues/2344)) |
  | `ch-rocker-arm` | 20 | strap with a pressed hub; the R800/R816 arcs are cut on the oblique jig MHA-CH-06-TL-00, by a held reference route that is not yet qualified (`cad/process/ch_rocker_arm/plan.toml`) |
  | `ch-connecting-rod` | 20 | flat outline from 1018 plate, stepped both faces, slotted fork; the outline on the manual mill is **route not selected** ([#2340](https://github.com/pedropaulovc/harmonic-analyzer/issues/2340)) |
  | `sm-knife-mount` | 2 | trivial prismatic block, 2 identical; 4140/4142 HT pre-hardened bar (28-32 HRC), no heat treatment |

- **Casting-vs-bar substitution:** `fr-rocker-arm-support` is a benign stock
  substitution; the **`sm-summing-lever` now explicitly uses a machined-from-solid
  route** in its registry. Option A simplifies its coefficient side to a uniform
  7.00 mm slab and one shared tangent rib profile, but does not turn the retained
  cylinder, counter web and delicate knife trunnions into a simple plate part.
  Plan the multi-setup workholding and cutter access for the actual solid; the
  setup count and machining clearance still need native/CAM qualification.
  - **`sm-knife-mount` material is settled:** bar stock, 4140/4142 HT pre-hardened to 28-32 HRC
    as supplied (`parts/sm-knife-mount.yaml`, owner ruling 2026-11-10 (Pedro), #2334 option B1); the
    builder keeps the generic `Plain Carbon Steel` library material for density only.

- `fr-rocker-arm-support` carries four **5/16 through clearance drills**. Four
  McMaster 92240A540 1/4-20 UNC-2A × 3/4 in hex-head screws install from the
  top into **through-tapped** UNC-2B seats in `fr-harmonic-base`. The exact
  vendor under-head washer transition still seats on the support, leaving
  **12.422 mm nominal insertion**. Insertion is not useful engagement: the
  retained casting limits full-thread overlap, and any excess shank projects
  into the underside pocket. The seat contracts account separately for the
  printed material limits, edge breaks, full thread, protrusion and bench
  clearance; there is no blind drill depth or tap-lead reserve at these seats.
  Other receivers are threaded too; the `sm-knife-mount` #10-24 bottoming hanger-bolt tap is one
  example. The 20 `dt-cone-gear`s and the 64T `dt-crank-drive-gear` transmit torque
  through a 1/16 square key on land 1 (the 64T and T030–T120, owner decision C1
  keyed, 2026-11-09, PR #1992); T024 is bonded with LOCTITE 638 on round land 2,
  and T018 and T012 on the integral spigot of `dt-cone-tip-gear` (T006), itself
  bonded in the shaft's end socket; the cylinder gears ride free on their
  stationary arbor. The gears seat against each other without spacers from the
  collar-supported 64T to T030 and from T024 to T006, one feeler-set float between.

- **`fr-harmonic-base` cross-screw seats:** the green-top height and the
  cross-screw axis are dimensioned from the same faced underside, rather than
  deriving the land through the flange, pad and deck-rise chain. With ordinary
  `.X` ±0.8 mm bands, the minimum ligament above the Ø9.0 spotface is
  `(47.8 − 0.8) − (38.1 + 0.8) − (9.0 + 0.8)/2 = 3.2 mm`.
  This changes the dimensioning scheme, not the casting or its interfaces.
  Owner ruling **2026-11-05** removed the long-reach reduced-shank #10-32 tap
  from all eight frame cross-screw paths (MHA-FR-01 here, MHA-FR-02 below):
  the near casting wall is a **#10 close clearance, Ø.206** (`DRILL TO
  SOCKET`), wide enough for a standard-shank 10-32 tap to pass and to guide
  the tube's Ø.197 match drill, and only the far wall is threaded. The shared
  contract is `fr_frame_cross_screw`. Depths still run from the spotface floor.
  Engagement counts the far wall alone, at the shortest stock screw (B18.6.3
  −.06 length), 0.7P tip loss, the most outboard printed seat, a Ø26.0 matched
  socket and the far mouth's .010 edge break: **7.50 mm (1.55D)** of full
  thread (6.87 mm, 1.42D, if a 1.5P tip loss is assumed instead), above the
  1.5D = 7.24 mm floor. The 0.7P tip is a nominal allowance, as for the swing
  stop, so MHA-FR-00 check 2 accepts each installed screw at full-form
  far-wall engagement of at least 1.5 screw diameters. The tap keeps its bottoming lead (`↧ 1.93 MIN` drill;
  the lug's past-tip guard leaves no room for a plug lead). The callout reads
  `DEPTHS FROM SPOTFACE FLOOR` / `FAR WALL ONLY 10-32 UNF`, naming the face
  the depths start from as the top frame's does, and its associative
  full-thread and minimum-drill depth tokens are unchanged.
  The native pedestal-to-pivot X/Y dimensions locate the pivot from the actual
  near pedestal axis with the existing ±0.05 mm functional band. Both carry
  one-line ABOVE `SEE NOTE 1` flags to numbered free note 1 in the B4 notes
  lane. It names the MHA-DT-02 seat, calls for drilling and tapping at assembly
  without prescribing a setup or repeating the numeric offsets, and states
  that the pivot's table X/Y are reference. Its actual native tag is resolved from the
  physical pivot station, not a fixed family letter. The generated native
  hole-table coordinates remain unchanged; that same physical row carries
  `SEE NOTE 1` in a custom NOTE column (#1744), because generated hole-table
  cells are not editable. Both the numbered note and curated view-tag layout
  follow station identity if native size families re-letter or merge.

Owner exception **RV-02**, selected **2026-10-20** and registered under
`fr-harmonic-base` in its package YAML, permits redundant default **2B** only
in the generated native hole-table **SIZE cells** on sheet 2. The cells stay
model-linked and are not rewritten; all physical Hole Wizard threads remain
class 2B. The five separate native tap callouts still omit the duplicated
class token. This presentation-only exception does not extend to other
callouts, packages, tolerances, engagement or clearance limits. The existing
reviewer and judge consume the package declaration through their standard
owner-exception mechanism; the general drawing rubric is unchanged.

The flange perimeter remains the hole table's coordinate origin, not a
specified mating seat. A layout reference alone does not justify Ra 3.2 under
drawing-guidelines rule 6, so the four flange-side roughness controls are
removed from both the native part and drawing. The deck, underside and matched
column-socket finish controls remain; neither the flange shape nor the native
hole-table origin changes.

The modeled stamped ID must read **2** in the native top projection. Its
3.5 mm artwork stays centered at machine X161.0/Z124.25 and cuts 0.3 mm deep.
The DXF generator accounts for both the Top-sketch Y/part-Z mapping and the
plan's downward-positive Z projection; the artwork is reflected in sketch Y
to avoid a reflected numeral on the actual part. This changes orientation,
not the glyph area, cut volume, location or drawing-view orientation.

The base's **18 deck seats** are through-tapped at their existing stations
and thread designations: four rocker-support, one cone-pivot, one cone-lock,
one swing-stop, four pinion-block, one spring-foot, two arbor-pedestal and four
nameplate seats. All **11 round interior islands and five rectangular pads**
formerly backing those seats are removed. The perimeter, four socket bosses,
two relieved ribs and four horizontal cross-tap lugs remain. A through tap
continues through any retained rib or other casting in its path; it is not a
clearance hole, and no underside nut is introduced. The cross taps remain
blind and retain their independent manufacturing and engagement contracts.

Owner ruling **2026-10-20** retains a **13.0 mm nominal deck skin** by making
the underside pocket **1.0 mm shallower** (37.8 mm pocket depth). The deck
top, mounting stations, hardware and existing loose tolerance scheme stay
unchanged. The controlling dimensions remain green-top height, deck rise and
pocket depth, each with the title block's `.X` ±0.8 mm band; the skin is not
silently made a directly controlled or tighter dimension. The worst-case
female full-thread depth at a skin-only seat is
`(47.8−0.8)+(3.0−0.8)−(37.8+0.8)−2×0.25 = 10.10 mm`.
That exceeds the 1/4-20 receiver's **1.5D = 9.525 mm** requirement by
**0.575 mm**, after both edge breaks. The former 12 mm skin would retain
only 9.10 mm under the same chain and was not accepted for this conversion.

The retained cross-tap lugs extend from Y26.5 to the pocket ceiling Y37.8,
where they join the green skin up to Y47.8. The unchanged cross-tap axis at
Y38.1 is 0.3 mm above that shared boundary: the lug/skin union, not the skin
alone, backs its complete thread. Lug-bottom and top-land wall checks remain
controlling; the ceiling need not be above the cross-tap axis.

The separate 49 MIN cross-drill callout has no upper depth limit. Its existing
tip/past-tip proof therefore describes the nominal native drill, not a
worst-case manufactured deep end. The finite lateral and vertical backing
checks charge the printed bands and require a continuous 2 mm envelope through
the retained lug/socket/wall union, with the socket bore and spotface entrance
treated as intended openings. No fillet credit or new depth band is assumed.

The per-station material map includes retained ribs, socket bosses, lugs,
walls and pocket fillets rather than assuming every hole crosses only the
deck skin. A maximum-radius fillet may contribute material to the nominal
model, but that optional material cannot be counted as guaranteed full thread
when the print permits a smaller radius. Native readbacks must prove the
actual cut opens through every retained material segment. Existing screws,
their top-side bearing seats and the cone knob's clamp/bare-base poses stay
unchanged; the original pivot-screw operational-retention issue is not fixed
merely by breaking its tap through the deck.

The current live stations have the following retained material. Coordinates
are machine X/Z; the source-owned station tuples, not these rounded labels,
remain authoritative. `THROUGH_SEAT_MATERIAL` records every individual seat.

| Seats | Count | Nominal metal on the hole axis | Complete-circumference nominal receiver |
|---|---:|---:|---:|
| Rocker support | 4 | 13.0 mm | 13.0 mm |
| Cone pivot, cone lock, swing stop | 1 each | 13.0 mm | 13.0 mm |
| Pinion blocks, `PINION_PIVOT_X − 8.5` | 2 | 13.0 mm | 13.0 mm |
| Pinion blocks, `PINION_PIVOT_X + 8.5` (X ≈ −4.652) | 2 | 13.0 mm | 13.0 mm |
| Spring foot | 1 | 13.0 mm | 13.0 mm |
| Arbor pedestals, including ±2 X / ±5 Z transfer envelopes | 2 | 13.0 mm | 13.0 mm |
| Nameplate | 4 | 13.0 mm | 13.0 mm |

The owner subsequently selected moving the **whole cross rib +11.0 mm in X**,
not local notches. Its 10.0 mm width, full Z span, 3.0 mm bench relief and
connection to the long rib/end walls remain unchanged. Its west/east faces
are now X6.0/X16.0. This removes the two inner block bores' former 34.8 mm
interrupted continuation down the rib; all eighteen axes and their thread
footprints now exit the 13.0 mm skin into pocket air.

The nearest #8-32 axis is X≈−4.652206 with major radius 2.083 mm.
The existing `.X` location band plus half the flange-length band bounds the
rib face by ±(0.8+0.4), independently of the ±0.8 hole-position allowance:
`6.0−(0.8+0.4)−(−4.652206+0.8+2.083) = 6.569206 mm` minimum
bare-face clearance. The implemented all-station exit gate is more conservative:
it subtracts three `(0.8+0.05)` location/rounding allowances and the 0.25 mm
edge break from the 8.569206 mm nominal gap, giving **5.769206 mm** at these
block seats, still above their 2.0 mm exit-clearance requirement.
Existing R6 MAX vertical root/end fillets are retained:
cross/long-rib patches lie at |Z|5–11, and cross-rib/end-wall patches at
|Z|119.25–125.25, far from these block stations at about Z−85.589/+87.311.
The material/clearance contracts cover every seat and pedestal transfer
envelope against the actual finite fillet patches, not an infinite rib line.
No unrequested horizontal root fillet is introduced.
These bounds describe the authored geometry, not the size or clearance of an
unmodelled foundry root; no such root allowance is qualified by this proof.

All eighteen receivers use the conservative full-form interval
**0.25–10.35 mm** below the deck at the printed limits. The current lock is
13.53 mm inside the pocket wall, and the stop is about 5.43 mm beyond the long
rib's edge; neither is backed by those structures. No current hole footprint
reaches an R6 patch, socket boss or cross-tap lug.

Receiver capacity is distinct from unchanged stock-screw limitations.
The base and assemblies share one insertion window per support/pedestal
joint rather than independently choosing stock or title-block limits.
The support window charges the ASME B18.2.1 pointed hex-cap-screw
[+0/−0.03 in length limit](https://www.portlandbolt.com/technical/faqs/bolt-length-tolerance/)
exactly as 0.762 mm, the support foot's ±0.51 mm band, and the actual
0.2778125 mm washer-bearing offset. With the harvested nominal 0.75-pitch
tip, minimum complete overlap is
`19.05−0.762−(6.35+0.51)−0.2778125−0.9525−0.25 = 9.9476875 mm`,
above 1.5D=9.525 mm; it is not the entire 10.10 mm receiver capacity.
Pedestal windows retain their existing 0.76 mm short-stock allowance and
±0.8 mm flange band. Nominal vendor tip/runout geometry is not a published
stock-tip tolerance; these calculations do not silently qualify unknown
end-form limits or replace the existing installed inspections.

The nameplate's existing **RV-03** ruling (`parts/fr-nameplate.yaml`) retains the
1/4 in brass screw and the printed **3.73 MIN** external full-form projection:
`6.35−0.508−(1.500+0.13)−0.75×0.635 = 3.73575 mm`.
That inherited calculation omits the female entrance edge break. Charging
the unchanged 0.25 mm maximum entrance loss gives **3.48575 mm** female
overlap; the conversion does not shorten it, and it must not be described as
a new 1.5D-qualified joint. The frame checks that the new receiver fully
covers the existing screw reach and records this finite overlap separately.
The pivot shoulder screw likewise retains its existing installed **4.83 mm
minimum** inspection: the harvested tail's nominal full-form interval is
`[2.3368, 9.525−0.43434]`, or **6.75386 mm**, not 9.525 mm of useful thread.
Neither inherited stock limitation is remedied by removing casting islands.
The existing [base thread audit #617](https://github.com/pedropaulovc/harmonic-analyzer/issues/617)
and [engagement audit #846](https://github.com/pedropaulovc/harmonic-analyzer/issues/846)
retain the inherited qualification questions; this geometry conversion does
not close either audit or authorize a new shortfall.

### Blind-thread DFM rule

Applied from the [thread-depth DFM walkthrough](https://www.youtube.com/watch?v=c1o3ZQY25jI)
(12:30–21:30):

- Specify the **installed engagement**, **usable full-thread depth**, and
  deeper **tap-drill depth** separately. Screw projection through a clearance
  part is not engagement, and a modeled tap-minor cylinder is not full thread.
- Ordinary steel/iron joints rarely need more than 2–3 diameters of engagement;
  1.5D is adequate here. More thread adds tapping risk without adding useful
  clamp capacity.
- A machine plug tap needs four chamfered lead threads plus one pitch of
  margin beyond the usable full threads. A bottoming tap reduces that allowance
  to one or two pitches; use it only when the design actually needs threads
  near the bottom.
- Model the tap-minor diameter, then check the **major-diameter envelope**
  against outer walls and neighboring cavities. The drill fitting does not
  prove the finished thread avoids breakout.
- About 3D is the practical machine-tapping depth ceiling. If a design demands
  full thread substantially beyond that, redesign the joint or thread-mill it
  instead of encoding an optimistic tap callout.

---

## Per-part rows

### Summing lever & knife edge (T1 — least forgiving interface)

By explicit owner decision, MHA-SM-03's two bracket receivers are conventional
blind **2-56 UNC 2B** taps fastening **MHA-MG-01**. The native callout prints
**2X Ø.070 DRILL .26** and **.195 MIN** full thread, with the concise
**FASTENS MHA-MG-01** caption. The drill diameter inherits the **+.004/0 in**
drilled-hole row and the routine two-place depth the **.XX ±.01 in** title-block
band (6.350–6.858 mm about the 6.604 mm model depth);
the native cylindrical depth is explicitly symmetric. Native usable
full-thread metadata remains **4.95 ±0.0508 mm** (±.002 in) for the screw stack.
The printed minimum is not a cutting-depth maximum. There is no additional
finished-cavity envelope or printed wall-acceptance requirement.

The owner's **2026-10-22 plate-tap relocation** makes all three rib extrusions
**5.08 mm**, printed **.20** under the two-place **±.01 in** band. Both edge ribs
retain their outer faces at **Z=±76.20 mm**; their inner caps are now
**Z=±71.12 mm**, and the middle rib remains centered on Z=0. One native
**3X .20** thickness dimension replaces the three separate thickness authorities.
The separate counter-arm leaf remains **5.08 mm**; it is not a rib extrusion.

The two receiver axes move down to local **Y=−0.7112 mm**, the nearest .001 in to the bracket's **−0.71 mm** row.
**ReceiverY0 = .128 ±.002 in (3.2512 ±0.0508 mm) below the actual coefficient top** owns that
location, not the unchanged hex centre. The matching bracket clearance holes
and installed MHA-MG-VN-53 screws move by the same delta. Their X stations,
**13.7 mm** pitch, Z stations, **3.175 mm** flange grip, bracket body/seat,
threaded-lever pose and spring interfaces do not move. The bracket's row
ordinate from its actual lower flange edge becomes **5.64 ±0.05 mm**.

The drill continues beyond the 5 mm rib into the continuous 7 mm coefficient
plate. Requiring either the full thread or pilot point to end inside the rib
is obsolete. `magnifying_bracket_joint_layout.receiver_pilot_material_wall_budget`
and `RECEIVER_PILOT_MATERIAL_WALL_MIN` instead enforce the independent
**≥.080 in (2.032 mm) pilot-only connected-material wall**. The actual-top-referenced row
cancels top-face position error; the nearest top and bottom axis floors are
**3.25−0.0508 = 3.1992 mm** and **6.858−3.25−0.0508 = 3.5572 mm**, the second
at the plate's printed **.27 in** (6.858 mm) minimum.
The printed **Ø.070 +.004/0** pilot has maximum radius **0.9398 mm**. Its
118° point and 0.3° drift over the deepest **6.858 mm** cylinder plus point
give **0.038865 mm** wander, leaving conservative top/bottom pilot walls
of approximately **2.221735 / 2.577335 mm**. The connected-plate proof takes
no helpful rib or root-fillet credit after the inner cap.

The drill lead reserve is **0.442057 mm**. Usable screw engagement
remains **3.305 mm minimum**, above **1.5D = 3.2766 mm**, and the native
full-thread metadata retains **0.0067 mm** minimum tip gap. These are
stack/design checks, not a strength or native-geometry certificate.

`sm_summing_lever_profile.receiver_pilot_wall_budget` /
`ReceiverPilotWallBudget` independently bound both longitudinal pilot walls
against `RECEIVER_PILOT_WALL_MIN`, using the actual tangent profile, printed
shape/plate limits, correlated actual-top/free-edge positions, and the printed
pilot radius plus drill wander. The independent native **PlateTopY** dimension
takes **±0.3683 mm**, the larger printed excursion of the sheet's knife-ridge
(**.404**, `.XXX`) to coefficient-top (**.10**, `.XX`) chain. **ReceiverY0**
remains **±.002 in (0.0508 mm) from the actual top**, so top/axis motion stays
correlated; the independent thickness takes its printed **.28 ±.01 in** limits
(−0.142/+0.366 mm about 7.00). The boundary test constructs
the permitted common-tangent wall independently and rejects the obsolete
half-band budget. The native trimmed-face comparison separately uses the
actual pilot radius, **TAP_DRILL_DIA/2**.

These proofs cover pilot drilling and the retained engagement stack, not
unknown physical thread-cutting geometry. The native model contains a Hole
Wizard pilot and cosmetic threads; it does not establish all finished-hole
wall thicknesses.

Native backing verification emits one `part.receiver_plate_backing` child span
with `receivers`/`boundaries` counts; knife-height dimension insertion emits one
`drawing.knife_height_location` child span with `dimensions`/`references` counts.
These operation-level spans add no per-witness spans or COM reads; the returned
settled-height check and all geometry/acceptance checks remain unchanged.

The approved option A keeps the coefficient plate's **top at local Y=+2.54 mm**
and makes the entire **X=0..44.45, Z=±76.20 mm** slab **7.00 mm** thick,
downward to **Y=−4.46 mm**. It is not a recentered 7 mm plate. The separate
counter-arm web remains **5.08 mm**, centered on Y=0. Every spring station,
the **Ø.006 RFS** pattern, the spring-neck top seat and the **MHA-CH-14 nut
underside seats** are unchanged. Only the matched bracket mounting row moves;
the #1769 bracket body and threaded-lever installation stay fixed. World spring
top remains **982.24 mm** and nut seat **975.24 mm**.
The full-width lower face eliminates the integral underside pad and its step.

View G locates the boss's upper axial face at **Y=+9.525 mm** relative to the
coefficient top at **Y=+2.54 mm**: the actual-edge native vertical dimension
measures **6.985 mm**, printed **.28** under the `.XX` ±.01 in band. Its
attachments are the boss upper rim and the actual +Z coefficient-top edge,
with projected +Y checked before annotation and attachment/value rechecked
after settling. The separate **19.05 mm** boss length and **5.08 mm** counter
web thickness remain; the web top is flush with the coefficient top.
The boss and counter web still share Y=0, and neither is located from the
asymmetric 7.00 coefficient plate's midplane.

The source-neighbour intent is **X reach 35.814 mm (1.41 in) before the worst nut
footprint at X36.449 mm**, not a claim of axial separation. Charging the
printed rib reach (**1.41 ±.01 in**, at most 36.068 mm) gives
**36.449−36.068 = 0.381 mm** geometric
X clearance. Native full-interference validation must still qualify the
rib/nut, screw-head/knife-mount and installed-neighbour clearances.

All three positive-X ribs now share the **R15.24** wrap, tangent flanks and
**R.040** transitions into the coefficient top/bottom faces at **X=35.814 mm**;
the negative-X middle-rib contour is unchanged. The title block's
**INSIDE CORNERS R.040 MAX** row controls the roots and blends; no local
callout repeats that ceiling (drawing-guidelines rule 2). The bounded native
R.040 controls and geometry guards cover the modeled profile transitions
and rib inner-cap side roots against the plate, pivot cylinder and counter
web. A fourth family, **CoefficientUndersideRootFillets**, implements the
owner's **2026-10-21 model-the-blend** decision at the moved lower
plate/cylinder junction. All four families disable tangent propagation;
the established three families retain their separate picks and added-volume
bounds. This is not a general body-fillet claim. The following unchanged
sharp junctions remain outside that proof:

- Longitudinal coefficient-plate **top**-to-pivot-cylinder junctions
  between rib caps (near X=+12.44 mm).
- Longitudinal counter-web face-to-pivot-cylinder junctions (near X=−12.44 mm).
- Boss-to-counter-web and boss-to-negative-X-middle-rib-flank junctions.
- The obtuse crease where each negative-X middle-rib tangent flank sinks
  into a counter-web face (near X=−63.75 mm).
- Knife-stub-to-end-rib shoulders.

Only these unchanged junctions retain the existing **RV-02** authorization
from **b2c8d954**: the owner's **2026-10-18 R.040 MAX** inside-corner ceiling,
now carried by the shop-wide title-block row. This is carried-forward
authorization for the listed unchanged junctions, not a new exception or a
waiver for the changed rib roots. The coefficient underside moved from
Y=−2.54 to **Y=−4.46 mm**, moving its longitudinal cylinder intersection from
X≈+12.44 to **X≈+11.89 mm**. That moved junction is excluded from this
unchanged-only RV-02 carry-forward; it now has an implemented native **R.040 MAX**
fillet contract, not an expanded sharp-corner exception.

The lower-junction picks derive from **sqrt(CylR² − BottomY²), BottomY** and
the midpoints of the actual two inboard cap intervals:
**Z=−71.20..−2.50** and **+2.50..+71.20 mm**. They are applied after the
three cap-root families, while these mid-run edges still exist. Its added
native volume must be strictly positive and no more than
**2R² × (sum of run lengths + 4R)**, including one-radius end-corner
neighbourhoods; at R = 1.016 mm the current upper bound is **292.05 mm³**. Exact six-direction
sheet-body extrema bound every new surface to the lower tangent section
plus those finite corner neighbourhoods. Both runs must contain native
**R.040 cylinders parallel to Z at the derived tangent centre**; a nonanalytic
corner patch cannot replace a missing run or evade the bounds. The new
family participates in the existing native radius/MAX-band readback, and
all four feature-envelope audits run again on the final rebuilt model.

The complete bounded lower-blend envelope is X-disjoint from both receiver
pilots, charging the printed pilot radius, drill wander, ordinary free-edge
variation and actual-axis position bands.
Its Z envelope stays inside the rib caps' finite neighbourhoods and away from
the receiver entry/body-end/knife faces; its X reach stays clear of the spring
and nut lane, outer plate edge, and its Y envelope cannot reach the top seat.
The analytic section adds material only. Receiver wall proofs therefore take
**no extra wall credit** for this blend and retain their independent pilot
and connected-material gates. **Fresh native fillet topology, corner integration,
saved-feature surfaces/radii and installed clearance verification are pending**;
the source implementation and fail-closed guards do not claim a native pass.

There is no end ledge or reference-only **(0.44)** contract: the former
pad-step scope and RV-04 ledge exception are removed. The unchanged knife
roots retain their separate local **R.020 MAX** debt (#1625); knife
material/hardness remains #1611. Neither the retained RV-02 authorization
nor the changed-rib proof claims that those unchanged junctions are modeled
with fillets or that the knife roots are manufacturable.

The screw/grip, engagement, tip-gap and bottoming-tap-lead guards are retained.
The bounded **.26 ±.01 in** drill (6.604 mm model depth) now runs into the connected coefficient
plate rather than relying on a special deep rib. Native **4.95 ±0.0508 mm**
full-thread metadata remains a screw-stack input, not a maximum imposed by the
printed **.195 MIN**. An unbounded MIN drill remains unacceptable.
`magnifying_bracket_joint_layout` owns those stacks and the independent
pilot-only material budget. The **.128 ±.002 in** actual-top row location
places both receiver axes at local **Y=−0.7112 mm**; the matched bracket holes
and screws follow it without shifting any body, seat, spring or threaded-lever pose.

The drawing retains **6 views**, reduced from 9 by removing C-C and H-H and
combining knife detail D and ridge detail E into **D at 10:1**, with the
knife dimensions, ridge **R.004 MAX** and datum A together. The rib-side/profile
R.040 ceiling comes from the title block, not a redundant local VIEW G callout.
The six views are the sheet-1 top/plan view, VIEW G, sheet-1 standard isometric,
sheet-2 VIEW F, Detail D, and the existing sheet-2 isometric reoriented to
underside rear-bottom-right **(+X,−Y,−Z)** at **1:4**. This exposes the receiver
underside without adding a seventh view; there are no sections.
The underside pictorial remains useful for the lower longitudinal blend and
reentrant rib roots; the standard top isometric does not replace it. Detail D
cannot be removed merely because the ribs are uniform: it uniquely owns the
knife envelope, ridge radius and datum. This change simplifies rib dimensions,
not the actual six-view count.
`PlateThickness@PlateProfile` remains model-owned at **7.00 mm**, printed
**.28** under the two-place ±.01 in band. Changes to wording or annotations still require
fresh native acceptance.

Datum A remains on the actual **−Z knife ridge** in Detail D. The plan's
owned theoretical-sharp centreline now uses that same stub for the anchor-X
and spring-row BASIC dimensions. The two stubs share one nominal axis, so
this does not correct the **39.85** nominal or change any numerical control;
it removes the opposite-stub association. Native acceptance must inspect
the longer dimension witnesses rather than suppressing them.

Native nominal dimension readbacks use a fixed absolute allowance of
**1e-9 m (1e-6 mm)** with no relative component, matching the builder's
native dimensional checks. This applies to the imported plate thickness
and knife-ridge radius, not their manufacturing bands.
Length globals enter the inch document with explicit `mm` units; their
equation-driven SI readbacks need not exactly equal the requested decimal
(the 7 mm native readback can be **0.006999999969999999 m**).
This numerical allowance does not enlarge a printed MAX limit or any
tolerance deviation. After capture, the thickness check still requires the
same native display/model objects and exactly unchanged full name, raw
value and tolerance metadata, even for a change smaller than that allowance;
the existing view-ownership and visible free-end witness proofs also remain.

The r6 native display includes a horizontal text leader as well as the two
thickness witnesses. The check selects exactly one horizontal witness at each
projected plate-face level, retaining the native-gap/free-end origin and
arrow-intersection proof; extra horizontal ink must join the arrow-axis
dimension line. Duplicate face-level candidates are refused. Recorded r6
tuples cover initial and settled checks without implying a regenerated
drawing has passed.

Native layout iteration moved VIEW F and its annotations clear of Detail D
while preserving the receiver coordinates, source-detail circle and owned
receiver centreline. Receiver-callout and caption placements live in the
drawing recipe rather than a second set of coordinates here.

Detail D retains the complete 10:1 knife envelope, native exterior angle arc,
outboard flank text, ridge round and datum A. The flank-text shelf sits below
the detail boundary and height dimension; its native leader clearance still
requires rendered inspection. Local witness gaps preserve their attachment
landings; the parent-view identifier must clear the screw-pattern dimensions.

Recorded historical ink and analytical replays are not after-change
acceptance. Native readbacks, audit and enlarged-sheet inspection must prove
the complete text, leaders, witnesses, source circle and isometric clearance
on both sheets, with all dimensions and six views retained, with no sections.
The r7 `19X7.06` BASIC-box left-border strike lies in whitespace
(prefix ends **284.309 mm**, border **284.6645 mm**, value begins
**285.731 mm**); the enlarged PDF is visibly unstruck, so it is unchanged.
Known edge-missing collector artifacts remain reported, not demoted.

The part authors every printed decimal place (`sm_summing_lever_spec.DRAWING_PRECISION`)
and the drawing imports them unchanged; the body-end **PlateLength** is read
back immediately after its top-view import. It prints **6.00** under the
two-place **±.01 in** band, which the receiver pilot-material budget charges at
the opposite end (`PLATE_L_DEVIATIONS`). Nominal geometry, receiver
entry-relative depths and poses are unchanged. Native precision/ink acceptance
remains pending with the layout changes above.

**Historical source-only material/gravity estimate (against #1761, b2c8d954,
at the prior 8.20 receiver depth).** The following numbers describe the earlier
rib dimensions, not the current uniform-5.00-rib design, and are not current
mass/CG acceptance values. The gross downward box is 10.080 cm³, but it overlaps the
existing cylinder and ribs. Integrating the source prism unions gives
**+5.808 cm³** for the plate
extension with the old ribs plus **+0.961 cm³** for the shared-rib reprofile:
**+6.769 cm³ net**. The signed-delta centroid is approximately
**(22.744, −3.517, −0.0777) mm**, not the final part CG or the centroid of
only the added material; some old upper-flank material is removed.
The source first moment is **∫X dV ≈153,950 mm⁴**. With explicitly
illustrative density **7.2–7.85 g/cm³**, that is about **49–53 g** and
**10.87–11.85 N·mm** of additional level-pose gravity moment. The estimate
includes the R1 in-plane rib transitions and overlap subtraction but
**excludes out-of-plane root-blend changes**. Unchanged cuts cancel only
under the retained containment/seat contracts. These are ideal-profile
estimates, not native mass/CG acceptance values.

Added +X weight **reduces the required counter-spring tension**. Its relevant
installed margin is the force above the measured **initial-tension floor**,
not catalog maximum load minus operating force and not the full catalog
force span. `solve_bank_balance` and the default error budget omit lever
gravity; neither qualifies this change. Native final mass/CG readback
(including the implemented blends), underside and full swept-clearance
qualification, and measured installed balance throughout the operating
poses remain outstanding. The opt-in
`diagnostics/diag_stock_spring_gravity.py` is an existing native gravity
probe, not evidence that it has been run for option A.

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`sm-summing-lever`** | machined-from-solid organic first-class lever; uniform 7.00 coefficient slab, retained centered 5.08 counter web | solid pivot cylinder Ø25.4×152.4 (**no bore**); 2× unchanged hex knife trunnions protruding 21.717 each end; 20× #6-32 through-taps in the 7.00 slab @ 7.0565 pitch (Ø2.705 tap drill), anchors locked by underside MHA-CH-14 jam nuts; one #10-24 tap through the Ø19.05×19.05 summation-anchor boss with its retained top jam nut; shared R15.24 tangent positive ribs, bounded R.040 MAX side roots/profile blends and a separately bounded lower longitudinal plate/cylinder blend, not general body fillets | delicate knife ridge; slender trunnions and cantilevered faces complicate workholding; small through-taps require controlled tapping; independent pilot wall guards retain the .080 in (2.032 mm) pilot floor; unchanged top-plate/cylinder, counter-web/cylinder, boss/counter-web, boss/middle-rib-flank, middle-rib-flank/counter-web and knife-stub shoulder junctions retain baseline RV-02 only; separate knife-root/tool-access debt remains | multiple setups; native/CAM route not yet qualified | **machined from solid**, per registry; preserve all spring/bracket/mount seats; evaluate hardened knife insert separately (§6) |
| **`sm-knife-mount`** | rectangular block 25.4 ±0.8 wide ×29.6×14.0 (bar/plate), 4140/4142 HT pre-hardened bar, 28-32 HRC as supplied and not heat treated, the bore and B reamed once to their printed bands (owner ruling 2026-11-10 (Pedro), #2334 option B1; supersedes the 2026-11-08 harden-less O1 ruling); **2 identical** | unchanged Ø12.00 +0.03/0 reamed through bore and pose, centre 20.616 BASIC below the top face (`BORE_CY` −5.75 from the knife-edge origin, block top +14.866, clamped to the casting underside); #10-24 UNC-2B bottoming tap on the bore axis: #25 Ø3.7973 under the title-block DRILLED HOLES +0.10/0 row, cylindrical drill depth .438 ±.002 (11.1252 ±0.0508), full thread .375 ±.005 (9.525 ±0.127); fully charged drill-point crown web 2.1060 (≥2.032), no break-in (conservative proof envelope Ø3.924, above accepted MAX Ø3.8989; point MIN 117°); one MHA-SM-VN-53 slip hole cut from the top seat to a flat floor 9.398 deep (owner ruling 2026-10-24, T+H3): datum B, a Ø.1280 ±.0007 blind flat-bottom reamed round hole 7.62 (.300) +X of the tap axis, ⊥Ø.001 to A. Owner ruling 2026-11-08 (Pedro), #2144 item 11.3 (scheme S1) deletes the −X slot (datum C) and its notch: the bore carries ⌖Ø.008 to A and B (datum C) plus a separate ∥.002 to A, and the tap is cut on the part at ⌖Ø.005 | A | B | C▷ (owner ruling 2026-11-10 (Pedro), #2334, S1 and margin option 1a; formerly spotted through MHA-FR-02's #10 hole); the bore's yaw about B is set at MHA-SM-00 by a (Ø.4720) × 8.0 in gauge bar, .0002-.0017 diametral clearance in each bore, through both mounts' bores (#2334, S2): knife rock 7.76° worst against the 5.0° floor, the far-end offset 0.0470 being the bar's .0017 diametral clearance in the largest bore plus the lever ridge's yaw from that clearance over its 159.90 minimum mouth span; bore floor and pose unchanged | hold the explicit tap/drill depth bands and accepted pilot diameter/point-angle bounds to preserve ≥2.0 crown web; all joint webs ≥2.0 at printed worst cases | 1–2 (square block, bore one axis) | manual (×2). Modified #10-24 hex-head Bolt MHA-SM-VN-52 (92314A253, cut under head at MHA-SM-00 step 4 to its hole's measured crossbar-underside-to-washer-top stack plus .351 ±.005 in (8.9154 ±0.127); 46.70 nominal, printed (1.84) as a reference) and new 18-8 SAE washer MHA-SM-VN-54 (96659A104) clamp the block to the top-frame's integral crossbar through a letter C drill Ø6.147 (.242) #10 clearance on D within ⌖ .010 | D (owner ruling 2026-11-06). Crossbar width 25.0 ±0.8, symmetric about X=−15; washer seat on the whole faced top (no SPOTFACE), 36.50 (title-block .XXX ±0.13) above faced underside. Nominal reach 8.9173, range 8.7884–9.0424; full-form engagement MIN 7.730067 ≥7.239, tip air MIN 0.3556. The bolt goes in plain, without threadlocker (coordinator ruling 2026-10-16: a doweled static clamp needs no lock). One MHA-SM-VN-53 dowel per mount (98381A473, 1/8 ×3/4) presses 11.94 to the floor of a Ø3.150 +0.013/0 blind ream in the crossbar's faced underside (0.015–0.033 interference), .300 ±.005 (7.62 ±0.127) +X of its bolt axis at the same Z and ⊥Ø0.025 (.001) to A (owner ruling 2026-11-06), pierced by a #51 (Ø1.70) knockout drilled up from its floor on the ream's axis; its proud end slips .0020–.0036 into the block's B, so the block fits one way round only (owner ruling 2026-11-08 (Pedro), #2144 item 11.3: the −X reams and their ⌖ frames are deleted). The #10 holes' ⌖ .010 | D to the bar's two-face width median datum D limits their X shift to ±0.127, retaining the Z socket station and ≥2.0 webs. The former #6 socket-head counterbore route is obsolete |

The hanger clearance hole is a **letter C drill, Ø6.147 (.242)**, under the
title block's DRILLED HOLES +0.10/0 row (Ø6.248 at most; owner ruling
2026-11-06): undersize would fail bolt float. With this maximum hole diameter and
the MHA-SM-VN-53 press reams (owner ruling 2026-10-24, T+H3; one per
station, .300 ±.005 from the bolt axis, since owner ruling 2026-11-08
(Pedro), #2144 item 11.3), the worst-case screw-to-ream web is
2.660 mm. The crossbar's sides are as cast (owner rulings B2 and B5,
2026-11-10, #2333), so the walls to them are charged at the bar's least
printed width, .99 − .03 on the faced underside: the ream keeps 2.673 mm to
the bar side (2.483 mm at its underside mouth, inside the title-block
break), and the #51 knockouts (Ø1.70, DRILLED HOLES +0.10/0) keep 3.095 mm
to the bar face and 2.954 mm to the screw hole
(`build_fr_top_frame.PIN_HOLE_SCREW_WALL`, `PIN_HOLE_BAR_WALL`,
`PIN_HOLE_MOUTH_BAR_WALL`, `KNOCKOUT_BAR_WALL`, `KNOCKOUT_SCREW_WALL`), each
over the 2.032 mm (.080) target. The ream floors print **2X FLAT BOTTOM, CORNER R.003 MAX**. The
pressed end bears only inside its ASME B18.8.2 point (Ø2.794 MIN) and
outside that corner, a 0.3157 mm (.0124) bearing land on the ream floor at
the drawn coaxiality's implied ±0.127 per axis, under the 0.4 target by owner
ruling 2026-10-27 (machinist exception RV-06). The largest end flat (Ø3.048) sits on the fillet, which
holds it at most 0.0044 mm off the floor. Each knockout is a ~15 D
run (24.94 mm from the shallowest floor to the top at the grip's far limit):
the shop drills it with a pecked **taper-length #51** (2 in flute, 3-3/4 in
overall), whose flutes clear the 36.63 mm from the underside, and removes a
dowel from the faced top with an extra-long 1/16 in pin punch or drill-rod
drift of at least **36.63 mm** reach (`HANGER_KNOCKOUT_PUNCH_REACH_MIN`).

The washer-seat grip is the model's actual driving thickness dimension
`HangerGrip@Crossbar`, **36.50 mm** (1.437) from the finished underside to the
whole faced top, except the four corner bosses that remain 4.57 mm (.18) proud.
The builder authors no band on it and section F-F imports it bare under the
title block's .XXX **±0.127 mm** band (owner ruling 2026-10-18; #290 prints
it 1.437). Both its ends are faced planes, so the casting's ±.03 does not
reach it (owner ruling B2, 2026-11-10, #2333); there is no
hanger spotface, separate floor driver or cleanup-stock offset in the model.

On the MHA-FR-02 CROSS-TAPS sheet the near casting wall is the same **#10
close clearance, Ø.206** (owner ruling 2026-11-05, `fr_frame_cross_screw`),
called out natively as `4X ⌀.206 / DRILL TO SOCKET`, and the native 10-32
hole callout's mate line states **`FAR WALL ONLY`**. Because the clearance
consumes the tap's entry rim, the tap callout
attaches to the far mouth, where the tap drill breaks into the socket, seen
through the clearance. The requirement travels with the feature, not a
detached A-A note; the Hole Wizard still owns the thread and tap-drill
depths, from the counterbore floor. Each floor is located from its own
socket axis, **.62** out (owner ruling D5, 2026-11-10, #2333: .65 before the
casting, moved in because the drafted boss barrel narrows below its top and
brings the Ø.35 mouth in with it). The fillister head sits **.041** under
the mouth's lowest point at nominal and **.0009** under it at the printed
limits with the barrel on its socket's axis
(`COUNTERBORE_PRINTED_HEAD_RECESS`); a barrel also standing its
⌖ Ø.06 | A | B off the socket can leave the head up to **.029** proud
(`COUNTERBORE_PRINTED_HEAD_STANDOUT_MAX`), a residual left to the owner in
[#2516](https://github.com/pedropaulovc/harmonic-analyzer/issues/2516).
With the floor at .62 the print-worst far-wall
engagement is **13.11 mm (2.72D)** at the 0.7P tip (**12.48 mm, 2.59D**, at
1.5P), against the 1.5D = 7.24 mm floor;
`build_fr_top_frame.TOP_CROSS_SCREW_FAR_WALL_MIN_ENGAGEMENT` proves it.

The A-A cap-recess-depth callout retains its full **MHA-FR-VN-54** skirt
mate, three qualifier rows and **16.30 +0.3/0.0 mm** band. Its native sheet
anchor is **(382, 158) mm**, 4 mm left of the former placement, with the
same boss-face and recess-floor attachments. The longer parent-scoped name
left only **0.21 mm** between the underline and border strokes at the old
anchor. The regenerated native PDF measured **4.21 mm** of border air;
subsequent native inspection must retain that gap and check the neighbouring
boss-height callouts. The **1.0 X 45 DEG CAP / GOOSENECK TOP** chamfer keeps
its original creation point and exact-vertex measurement, while its native
text-only jog moves the three rows to **(315, 174) mm**. Native inspection
found that enabling `OffsetText` re-dressed the dimension line from
**y = 153.6656 mm** to **y = 162.000 mm**, the unchanged creation-point y.
The measuring vertices and 1.0 control are unchanged; the native dimension
line's paper placement is not invariant. The text shelf is now separate
from the dimension line and witness overrun. Inspection must distinguish
the offset leader joining its own native arrow/witness widget from a
text/witness strike, and confirm clearance to the 4.5 boss-height leader.

The top-frame's live view identifiers are **H-H** (front/rear rail section),
**DETAIL J** (underside hub enlargement) and **K-K** (set-screw boss
section); DETAIL L retired with the crossbar's dowel slot.
Datum A is new: the faced underside on F-F, to which the two press reams
carry **2X ⊥Ø0.025** (.001, RV-05; owner ruling 2026-11-06). The press
reams are no datums: owner ruling 2026-11-06 retired the crossbar's datums B
and C and the ▷ modifier, and owner ruling 2026-11-08 (Pedro), #2144 item
11.3 deletes the −X reams and every ream position frame (the 2X ⌖Ø0.10
(.004) | A | D, SEP REQT pair frame with them). Datum D and A-A/E-E/F-F/VIEW G
are unchanged. Owner rulings 2026-11-10 (#2333) add datum B, the 4X socket
pattern (no relation to the retired ream datum B), on HOLES-SOCKETS, and
sheet 7, CAST-DATUMS, with the cast datum targets E1–E3, F1–F2 and G1 and
datum D's as-cast width and station. Section stations, endpoints,
profiles, orientations and scales retain the historical B/E/D placement
calibration; old B/D glyph bounds do not establish H/K glyph clearance.

Owner ruling 2026-10-24 (T+H3) retires the crossbar's dowel slot and round
slip holes, and owner ruling 2026-11-08 (Pedro), #2144 item 11.3 (scheme S1)
leaves one dowel per mount. Each knife-mount station carries one
**Ø3.150 +0.013/0 mm** (.1240 +.0005/0) blind press ream, **11.94 ±0.25 mm**
deep from the faced underside to a flat floor, into which its MHA-SM-VN-53
dowel presses to the floor; it is
pierced on its axis by a **#51 knockout** drilled up from its floor on the
ream's axis (no setup note), which exits at the faced top under the MHA-SM-VN-54 washer
(the washer keeps a continuous bearing ring inside the knockout). The ream
stands **.300 ±.005 in** (.XXX) from its bolt axis at the same Z on F-F, with
no position frame: the bolt-float stack charges exactly that band. The
former −X ream, its BASIC span and its ⌖ frame (owner ruling 2026-11-06's
BASIC 7.620 either side of D under 2X ⌖Ø0.10 | A | D, SEP REQT) are
deleted, so the block fits one way round only, and the MHA-SM-02 slot
(datum C) is gone too. The block may turn about its one dowel; a Ø.4720
gauge bar through both mounts' bores sets that turn at MHA-SM-00 step 5.
The F-F and underside-locator annotations belong to `draw_fr_top_frame`
and need native inspection (the knockout callout's leader now lands on the
front ream); the historical slot-text placements and glyph clearances do
not carry over.
The native 36.50 grip text sits on its line right of F-F's profile at
**(158, 75) mm** (`HANGER_GRIP_TEXT_XY`).
The top-frame recipe sets and reads back drawing-document wireframe curve
quality (Custom, value 100, high curve quality enabled) before creating views.
This per-drawing tessellation control is independent of the views' precise
HLR mode (`Faceted=False`); it does not change geometry, dimensions, tolerance
exceptions, crops or scales. Successful preference readback or offline tests
do not prove smooth exported ink: inspection of the resulting native drawing
and actual exported vector PDF is required.

The whole top except the four corner bosses is finished Ra 3.2 µm, and the
four boss tops are faced too, with their own native Ra 3.2 µm symbol (owner
ruling B3, 2026-11-10, #2333). The right
(west) rail alone remains flat within 0.04 so both MHA-CH-07 keeper bores
align. The finished underside and knife-mount pose remain unchanged.

The casting's flange corner crops and convex edge breaks are judged at the
print's limits, not on the nominal model. Each corner's crop chord ends on
the smallest printed corner-boss barrel at the farthest printed rail faces
(`CORNER_CROP_BOSS_R_MIN`, `CORNER_CROP_FACE_OFFSETS`), so no conforming
casting keeps a flange nib outside a barrel. The 1/16 in × 45° break goes
only on edges that hold its print-worst leg and sliver land at those limits:
the rails' flange undersides (3.04 and 4.95 mm of shelf,
`T_FLANGE_SHELF_PRINTED_MIN`) and the hub rib's outer bottom beside the
set-screw boss (4.19 mm, `HUB_RIB_STUB_PRINTED_MIN`) do; the .99-wide
crossbar's flange undersides do not, once its web and sides take the as-cast
±.03 and their draft (owner rulings B1 and B2, 2026-11-10, #2333). The break
itself keeps .06 at the title block's ±.01: at the as-cast ±.03 two legs
(4.57 mm) would overrun that 4.19 mm stub. The model leaves the rest unbroken
at .06: the crossbar's flange undersides, its front side
bottoms and the gusset hypotenuses under the knife seats, the rib's inner
bottom, the V-gussets and the set-screw boss's edges on the faced top. Owner ruling 2026-11-07 scopes general note 1 to
the convex cast edges the views show chamfered, so those edges take the
title block's .010 break and nothing on the sheet reads SHARP. That break
(`TITLE_BLOCK_EDGE_BREAK_MAX`, 0.254) stays inside the knife seats' 0.5
edge-break clearance, and the dowel reams' underside mouths keep their wall
to the crossbar side inside it (`PIN_HOLE_MOUTH_BAR_WALL`). No band is
tightened to recover a break.

The grip no longer sets **MHA-SM-VN-52 thread engagement**: MHA-SM-00 step 4
cuts each bolt to its own hole's measured stack plus **.351 ±.005 in** (8.9154 ±0.127 mm)
reach. The crossbar median datum D controls the hanger axes in X only:
their BASIC X location is on D.
Owner rulings B5 and D2 (2026-11-10, #2333) replace the D locator from the
left bosses' tangent: D's station is as cast and prints **9.18 ±.03** from
the G plane on the CAST-DATUMS sheet (`build_fr_top_frame.D_STATION`), and
the hole table's origin is the F|G (west, rear) corner. The hanger holes
left the table; their front and rear Z stations print .XXX from the front
socket axes (1.104 and 7.959) and remain ordinary toleranced dimensions.

The mount's tap is cut on the part at **⌖Ø.005 | A | B | C▷**, datum C the
reamed bore, which only clocks it about B (owner ruling 2026-11-10 (Pedro),
#2334 option B1, S1, superseding the spot-through of sm Q3; zone Ø.005 by
margin option 1a of the same date, superseding B1's Ø.008, which left 0.018
of bolt spare once the gauge bar's play was charged; machinist exception
RV-06), and is charged its zone's radius (0.0635). Owner ruling
2026-11-08 (Pedro), #2144 item 11.3 (scheme S1) hangs each block on one
dowel, pressed into the crossbar and slipped into B, and the bolt. The X
leg is the ream's .XXX station (0.127), that tap radius, B's loosest slip
and B's datum simulator, which within ⊥Ø.001 to A may sit t/2 off the pin
root: **0.2489 mm**. The Z leg is the ream's implied-zero SAME Z (0.127),
the same three block terms, and the turn the gauge bar gives the block
about its dowel: the bar line runs through both bores, each off its station
by the #10 hole's ⌖ .010 | D centring (0.127, owner ruling 2026-11-06), the
ream's station, B's slip and simulator and the bore's ⌖Ø.008 radius (0.414
in all), at opposite limits over the 174.12 station spacing, a **0.272°**
turn; each block also turns on the bar by the bar's own .0017 maximum
diametral clearance over its shortest 13.72 bore, a further **0.180°**
(owner review of #2334). The tap, clocked to the bore, turns with the
block through **0.453°**, moving 7.62 from B across by 0.0602:
**hypot(0.2489, 0.3091) = 0.3969 mm**. Full-crossbar
drill drift over the printed grip's thickest **36.63 mm** (36.50 + 0.13) is
**0.1918 mm**; together they consume 0.5887 of the **0.6604 mm** radial
float (the C drill's Ø6.147 minimum less the bolt's 4.826 major, halved),
leaving **0.0717 mm** (and a 0.160 washer ring inside the knockouts, up from 0.053 at Ø.008). The rear mount, re-hung on the lever's stub at MHA-SM-00
step 6 and swung about its dowel until the rock gauge passes, may turn
**1.114°** inside its bolt float, above the 0.453° the bar line and play can ask of
it (`build_sm_summing_assembly.KNIFE_REAR_YAW_RANGE_DEG`). The block
carries no dowel-pattern frame: datum B is its round hole.

Owner ruling 2026-10-27 (#2016 option A) bounds the pin-to-hole tilt the
slip fit must take: the crossbar ream carries **⊥Ø0.025** (.001, owner
ruling 2026-11-06) to the faced underside and the block's round hole B
**⊥Ø.001** to A (the slot and its ⊥ are gone, owner ruling 2026-11-08
(Pedro), #2144 item 11.3). At the shortest printed depths less the floors'
corners (the ream's CORNER R.003 MAX; the block's title-block R.040 MAX,
since nothing seats on its floor) and less a 0.5 lead allowance (11.11 ream
wall, 7.63 hole wall), they tilt the pin against its hole by 0.1310° +
0.1908°. The lead allowance is
conservatism beyond the print, not an undersize tail: each hole's size band
applies over its full depth, so a conforming ream is full size to its floor
corner, the pin bottoms and the proud length holds.
An assumed 0.01 conformity of the clamped seats across the block's shortest
13.72 seat depth adds 0.0418°; this is an assumption about
ordinary face-milled seats drawn flat by the bolt, not a drawing control.
The charge totals **0.3636°**, inside the **0.4032°** the tightest slip
(.0020 clearance) takes over the longest proud pin short of its rounded
free end (`build_sm_summing_assembly.KNIFE_DOWEL_TILT_CHARGED_DEG` and
`KNIFE_DOWEL_TILT_ALLOWED_DEG`), a margin of 0.040°: the seats bind past
.00077 in (0.0195 mm).

The earlier 2.020267 mm crown-web proof was undercharged: it used the
nominal Ø3.797 pilot and an exact 118° point, omitting physical drill
oversize and point-angle variation. The correction is a tap-depth and
finished-bolt acceptance change, not new material, a bore change or a pose
change. The native Hole Wizard pilot row uses the **#25 drill designation**
instead of a three-place diameter, without repeating the title block's
**DRILLED HOLES +0.10/0** band. The indexed row (`STUD_TAP_DIA_BAND`)
accepts **Ø3.7973–3.8973 mm** (`STUD_TAP_DIA_ACCEPTED`), from the true
0.1495 in #25 size; native callout
variables clear the duplicate band and verify the readback. The crown proof
charges the conservative envelope **MAX Ø3.927 mm** (`STUD_TAP_DIA_MAX`),
retaining the earlier rounded .XXX ±0.13 reading. It is 0.0297 mm above the
accepted maximum. That envelope is charged, not accepted: nothing is drilled,
inspected or passed to Ø3.927. The row also dimensions the physical point
using the native drill-angle variable (`<hw-drlang>`,
`swCalloutVariable_Drill_Angle`):
**#25 DRILL ▽ .438 ±.002 X 118°**. The callout names **MHA-SM-VN-52**
and states that the depth bands set its tip clearance; it does not prescribe
a tapping tool. With no duplicate diameter band, the callout remains inside
the four-row limit. The title block supplies default class 2B; the thread
row prints **#10-24 UNC ▽ .375** under the title block's .XXX ±.005. The native point and physical
acceptance limits are unchanged. The final native layout audit remains
active and must prove the rebuilt sheet.
The now-dimensioned point takes the title block's **angular ±1°**, giving
117°–119°; the proof charges **MIN 117°**. This is not a claim that an
undimensioned tool point was already governed by the general angular grade.
The resulting point height is 1.2023 mm. With drill depth MAX
11.176 mm (.438 +.002), the built top at 14.866
leaves **2.1060 mm** over the worst-case bore crown, above the 2.032 floor
(`sm_knife_mount_spec.STUD_TAP_WEB_WORST`, `STUD_TAP_WEB_MIN`).
Full thread **.375 ±.005 in** (9.525 ±0.127 mm) gives MIN 9.398 mm, leaving
**0.3556 mm** tip air under the bolt's 9.0424 mm longest fit-up reach.
Drill-minus-full-thread runout is 1.6002 mm nominal and 1.4224 mm at the
adverse depth limits, above one 1.058333 mm pitch.

**Modified hanger-bolt shop route (MHA-SM-VN-52, two).** Source McMaster
92314A253, 18-8 stainless plain external-hex #10-24 UNC-2A ×2 in stock;
retain the supplied head. Leave the supplied length uncut at the bench:
MHA-SM-00 step 4 seats washer 96659A104 on each crossbar hole's faced top,
measures crossbar underside to washer top, and cuts the bolt to that plus
**.351 ±.005 in** (8.9154 ±0.127 mm) under the head (46.70 mm nominal; the
drawing prints it as the reference (1.84)). Restore the cut-end chamfer to
**RADIAL .03 ×45°** under the title block's **.XX ±.01 in** and **±1°** rows,
and deburr the thread start. Retain the conservative inspection
limit **MAX 1 P incomplete tip** (P = 1.058333 mm). The minimum radial
chamfer (0.508 mm) gives tip-flat Ø3.7846 on the largest class 2A major
(4.8006 mm), below the #25 drill Ø3.797; the maximum axial chamfer extent is
about 1.052 mm, below 1 P. Retain **.418 MIN (10.6172 mm) threaded tail from
the cut end**, giving useful full form ≥9.558867 mm
after the MAX 1 P chamfer. Check the retained #10-24 class 2A thread with
a GO gauge. These are manufactured acceptances; the live SKU omits
dimensional tolerances and a conformity standard. Nominal head AF 7.9375 mm
and height 3.175 mm do not imply a supplier head tolerance or under-head
bearing-circle bound. The ordinary hex-head-on-SAE-washer joint is accepted
practice, not a guaranteed stress or material allowable; no head-minimum,
neck or radial-play inspection is required. Assemble with washer 96659A104
seated on the whole faced top, not on as-cast skin.
The washer's actual ASME B18.21.1 bounds are ID 5.4356–5.7658,
OD 12.573–13.081 and thickness 0.9144–1.651 mm; use the full conservative
0.3302 mm radial OD-to-ID runout in the support/clearance stack.
The top-seat support proof charges full washer float over the sourced
#10-24 class 2A external-thread major-diameter limits **4.61772–4.8006 mm**
(0.1818–0.1890 in; [thread chart](https://www.engineersedge.com/screw_threads_chart.htm)).
Washer-to-thread radial float is 0.57404 mm. The frame builder additionally
charges hanger-pattern mismatch, through-hole drift and washer eccentricity
against the actual top-face edge: each washer bears wholly on the faced top,
inside the crossbar's 1/16 in × 45° top-rim break (printed 1.6 X 45 DEG),
charged at its print-worst leg of 2.4 mm. No neck or radial-play inspection is added.
Over the printed grip (36.373–36.627 mm) and washer (0.9144–1.651 mm) the cut
ranges 46.0756–47.3202 mm, leaving at least 3.4798 mm of the 50.8 mm stock to
remove with its factory end; inspect the cut bolt's threaded tail and thread
gauge acceptance rather than treating these as new SKU dimensions or vendor
tolerances. Useful-tail coverage beyond maximum reach is
9.558867 − 9.0424 = 0.516467 mm.
See [live vendor evidence](../references/mcmaster/README.md).

This route is shop documentation, not a generated traveler. The part has no
`cad/process/` plan and is not in `_process_plans.TRAVELER_STEMS`. No COM or
farm validation of the route is claimed here.

### Cylinder gear + cam, connecting rod (T1 — the 20 function generators)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`dt-cylinder-gear`** ×20 | round brass bar ~65; toothed disc OD64.41×3 + integral eccentric cam OD30.6×4.0565 (offset +Y 8.64); total H 7.0565 | Ø9.550 (.3760 +.0005/0) reamed through bore on the Ø9.525 (3/8") arbor — **rides free on arbor, no keyway**; 120T involute 48DP PA20 (2.5D through-cut, patterned → **DXF/2.5D-machinable**); cam = plain eccentric circle (2.5D); **0.4 mm alignment notch** = the +Y co-phased timing datum | cam thin-side wall **1.80 mm** (.071 MIN, RV-01); notch kerf **0.4 mm** (.014 in screw-slotting saw on a 1 in saw arbor, fragile crests; the saw is to buy, `tools.cylinder-notch-saw`, [#2364](https://github.com/pedropaulovc/harmonic-analyzer/issues/2364)); 3 mm slender disc; **double-sided** (teeth+notch front / cam boss far face) | **≥2** (flip for cam boss) | **manual** — lathe bore+OD, teeth with a stock 48DP PA20 #2 cutter indexed on the BS-0 (see [Cutter plan](#cutter-plan); wire-EDM = outsource); the cam turned about its offset axis and clocked to the teeth is **route not selected**: its eccentric fixture is not drawn ([#2361](https://github.com/pedropaulovc/harmonic-analyzer/issues/2361)); **hold the +Y phasing identical on all 20** |
| **`ch-connecting-rod`** ×20 | AISI 1018 plate, 1/4" faced to .240; 2D outline ~7.4×1.61; ring and shank .086, both faces at .077 / .163 ±.002 from the fork's datum face, fork .240 REF, all on one mid-plane; black finish | Ø1.213 +.003/0 strap bore (rides the Ø30.6 mm MHA-DT-12 cam); fork .390 wide, full R.195 crown on the pin, .710 long from the crown; tine .067 ±.002 from the datum face, slot .106 ±.002, .580 deep from the crown (#982); Ø.077 +.0009/+.0005 pin hole reamed through both tines (pin MHA-CH-10 pressed in at assembly, ends dressed flush; user ruling 2026-10-09, PR #1292) | tines **.067** (.065 MIN, owner-accepted RV-02) beside a .106 slot — slitting saw or a 3/32 end mill in two passes, hold the 3-place band; both faces stepped (thin .086 shank ~6 long faced from 1/4 plate — chatter/curl); the ream must hold its .0004 band for the press | **2** (flip to face the second side; slot, drill and ream in the second) | **manual**; the outline (ring, shank, fork) on the manual mill is **route not selected** ([#2340](https://github.com/pedropaulovc/harmonic-analyzer/issues/2340)); face both sides to the two levels, slit the fork, drill + ream |

### Cone gears + shaft (T1 — the 48DP PA20 train, tip gears fragile)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`dt-cone-gear`** ×19 (T012→T120) | round brass bar, extruded disc, face **6.8756 ±0.025** each, OD printed per gear at the AGMA (N + 2)/DP blank, +0/−0.05, capped by the cutter's form (`dt_cone_gear_spec.py`); tip gears T012–T024 harder yellow metal (`material_tip_specification`; the title block still prints `Brass`, [#1080](https://github.com/pedropaulovc/harmonic-analyzer/issues/1080)) | T030+ round Ø9.525 bore broached for the land-1 1/16 key (1/16 A broach, 3/8 A bushing; keyway on +X, clocked to the phase-0 tooth); T024 reamed round Ø6.350 (+.0018/+.0010 in) and T012/T018 reamed Ø1.5875 (+.0005/−0 in), bonded slip fits (owner decision C1 keyed, 2026-11-09, PR #1992); 12–120 involute teeth PA20, tooth thickness ±0.075, 2.5D through-cut | **T012 web 1.641 mm (.0646 in) minimum** over its reamed bore (RV-03); T030 keyway-corner web .0621 in (RV-07); whole gear tiny → difficult workholding | ≥2 (turn/bore, indexed teeth) | stock 48DP PA20 range cutter per gear, **indexed**, set up within 0.05 TIR of the finished bore (see [Cutter plan](#cutter-plan)). Measure the keyed faces 64T–T030 as one stack and T024–T006 as the bonded tip | 
| **`dt-cone-tip-gear`** ×1 (T006, MHA-DT-37) | C67500 bar; six leaves Ø4.31 +0/−0.02 OD, face 6.8756 ±0.025, integral Ø.0625 in spigot × .71 south and Ø.0625 in pivot × .25 north | DT6-FORM1 leaves, tooth thickness +0/−0.04; spigot bonded in MHA-DT-04's socket and through T012/T018; pivot carries the pressed MHA-DT-38 bushing (made to its measured bore) and runs in MHA-DT-39 | spigot L/D about 12 whips; ~4 mm gear hard to grip; the cutter must run off over both stems | ≥2 (turn, indexed leaves) | turning **route not selected**: no listed centre or steady fits the Ø.0625 stems ([#2468](https://github.com/pedropaulovc/harmonic-analyzer/issues/2468)); leaves with the custom ground tool DT6-FORM1, indexed ([#2358](https://github.com/pedropaulovc/harmonic-analyzer/issues/2358)) | 
| **`dt-cone-gear-shaft`** ×1 | stepped steel bar; integral Ø12.2555 post journal, thrust collar then Ø9.525 keyed land 1 and Ø6.35 round land 2 | turned steps plus **a 1/16 square keyseat milled along the Ø9.525 land on +X** (S .3355 +0/−.0040 in, width .0625 +.0020/−0 in; carries the MHA-DT-VN-71 key); land 2 ends .025 in inside the bonded T024's bore with a reamed Ø.0625 × .20 in socket for the MHA-DT-37 spigot. Finish the post journal for its printed running clearance | none severe: the slender terminal land, its D-flats and the tailstock note are gone (C1 keyed) | lathe + 1 milling setup (keyseat) | manual lathe, drill and ream the end socket, then mill the keyseat | 
| **`dt-cone-tip-bushing`** ×1 (MHA-DT-38) | C36000 brass bar; Ø.228 × .160 in | Ø.0615 in reamed bore, press fit on the MHA-DT-37 pivot; north face bears on MHA-DT-39 | wall .0805 in minimum | 1 (turn, ream, part) | manual lathe | 
| **`dt-cone-tip-end-screw`** ×1 (MHA-DT-39) | McMaster-Carr 91794A558 18-8 slotted fillister 1/4-28 × 5/8 | drilled and reamed Ø.0630 × .12 in pivot hole concentric in the threaded end (running fit on the MHA-DT-37 pivot) | wall to the 2A thread root **.067 in MIN** (RV-01, rule 17 minor) | 1 (hold on the thread in a threaded collet or split nut) | manual lathe, centre drill, drill, ream | 

### Pivot and fulcrum shafts (T1 — the 20-channel stacks)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`ch-pivot-shaft`** ×1 | 1018 CF bar per its registry, or 1/4 ground stock as the print allows (stock allocation: [#2346](https://github.com/pedropaulovc/harmonic-analyzer/issues/2346)); Ø.2500 +0/−.0008 × 6.40 tip to tip | domed both ends; two set-screw flats in line, one side, one at each end | **L/D about 25:1** → whip; follow rest | 2 (turn, face and dome both ends; mill both flats in one setup) | manual lathe, chuck and tailstock centre with a follow rest, then mill |
| **`ch-fulcrum-shaft`** ×1 | plain steel bar Ø6.35×166.6 | domed R3.175 ends; two 0.3-deep set-screw flats on one side at ±75.06 | **L/D 26:1** → whip; **same stock as pivot-shaft — don't mix** | 2 (turn domes; mill both flats in one setup) | manual lathe + steady, mill |

The 19 `pivot-bushing` and 19 `lever-bushing` spacers are retired. The 20 rocker arms ride the
pivot shaft and the 20 channel levers the fulcrum shaft on their own integral hubs, which stack face
to face and set the 7.0565 channel pitch (`ch_rocker_arm_spec.HUB_LENGTH`,
`ch_channel_lever_spec.HUB_LENGTH`).

### Rocker arms + support (T1 — built-up profile arm + cast bracket)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`ch-rocker-arm`** ×20 | one piece from solid per its registry, or (sheet note 2, RV-06, owner route v3 2026-10-16) built up: strap MHA-CH-13 from 1018 CF 1/8 × 1-1/2 flat faced to .098 ±.001, about 292 long (11.494 REF), with hub MHA-CH-12 turned from 1018 round and pressed into the strap's reamed hole | **top edge = R800 concave arc** (BASIC R31.486 under a .020 profile, RV-02; the amplitude-bar rides ON it) — it is the **2D OUTLINE of the strap, NOT a concave pocket/face**; bottom edge R816 concentric; integral hub sets the 7.0565 channel pitch; reamed pivot bore through the hub, #47 rod-pin hole through the strap | thin strap faced from 1/8 bar ([#2340](https://github.com/pedropaulovc/harmonic-analyzer/issues/2340)); hub wall .064 MIN (RV-03); a manual mill moves one axis at a time, so the arcs need the jig | strap faced, sawn to a preform, then hub hole drilled and reamed and both arcs cut on the jig in one clamping; hub turned; bore and length finished on the joined arm | **manual**: arcs cut on the oblique jig MHA-CH-06-TL-00 (`ch-rocker-arm-tl-oblique-jig`) by the held reference route `cad/process/ch_rocker_arm/plan.toml`, not yet qualified (jig open items include [#2336](https://github.com/pedropaulovc/harmonic-analyzer/issues/2336) and [#2443](https://github.com/pedropaulovc/harmonic-analyzer/issues/2443)) |
| **`fr-rocker-arm-support`** | modeled Gray Cast Iron; drawing permits gray iron casting or low-carbon steel stock; trapezoidal wedge, 6.35 mm shell/web | opposed 165.1 mm pockets with **R6.35** internal corners; through cavity with **R12.7** corners; **4× 5/16 through clearance drills** in the 6.35 mm foot for top-down 1/4-20 hex-head screws; .06 × 45° rim chamfer; 2× #8-32 bottoming-tapped seats in the top face, transferred from the MHA-CH-08 brackets at assembly | 6.35 mm web/shell; from solid stock, each pocket reaches about 28.6 mm at the wide foot. R6.35 is ordinary contour geometry on the PM-30MV and does not need square-corner EDM; a 1/8″ end mill can finish the radius, but its long reach in 1018 favors roughing with a stiffer cutter first | casting route: foot holes/rim; solid-stock route: **2 opposed pocket setups** + foot drilling | cast body, or rough both pockets from 1018 with a larger cutter and finish the R6.35 corners with a 1/8″ end mill; drill the clearance pattern from the seat face |

### Frame (T1 — cast top frame)

Owner ruling 2026-11-10
([#2333](https://github.com/pedropaulovc/harmonic-analyzer/issues/2333),
option a): `fr-top-frame` is a bought one-off gray-iron sand casting (ASTM A48
class 25B) poured from a 3D-printed pattern, parted on the faced top plane
and machined on its seats only. Owner rulings B1–B6 and D1–D6 of the same
date (#2333) are in the model and on the print:

- **B1 draft.** 2° added on the rail webs, the crossbar web and side walls,
  the plan gussets, junction lands, hub rib, hub V-gussets and the set-screw
  boss's side walls (nominal on the underside, the wall thickening toward the
  top); taken out of the four corner-boss barrels (Ø1.77 held on the faced
  top).
- **D1 draft on the faces B1 does not name.** Taken out on the .32 flange's
  outer and window rims and the hub-rib and land strips flush with them
  (nominal on the faced top), on the hub boss barrel (Ø1.18 held on the
  underside) and on the set-screw boss face (.95 held on the faced top).
- **D4 draft band.** The angle prints 2° +1°/−0 where draft is added and
  2° ±1° where it is taken out.
- **B2 as-cast band.** ±.03 on every printed dimension with an as-cast end;
  machined-to-machined dimensions keep the title block, and every proof
  charges the ±.03 at the as-cast limits.
- **B3 boss tops.** The four boss tops are faced seats with a native finish
  symbol, so .18, .90 and .642 +.010/0 are machined-to-machined; the boss
  bottom prints 1.69 ±.03 below the faced top.
- **B4 set-screw boss.** Full rail height to the faced top; its cast face
  moves .87 → .95 ±.03 from the gooseneck bore axis, held on the faced top;
  the spot face stays .83.
- **B5 datum D.** Stays the median plane of the as-cast crossbar sides,
  .99 ±.03 wide on the faced underside.
- **B6 cast datum targets.** E1–E3 on three boss bottoms, F1–F2 on the two
  rear boss barrels and G1 on the rear-west boss barrel.
- **D2 table origin.** The socket table's origin is the F|G (west, rear)
  corner and its coordinates are BASIC; the hanger holes leave the table,
  located .XXX from the socket axes, and keep ⌖ .010 | D.
- **D3 webs.** Thickness ±.03, median plane ⌖ .06 | A | B; B is a new datum,
  the 4X socket pattern.
- **D5 counterbore floor.** .62 from the socket axis (was .65;
  `fr_frame_attachment_spec.TOP_SCREW_SEAT_Z` 128.524 → 127.762 mm), which
  also seats MHA-FR-00's four top cross screws 0.76 mm deeper. The head
  sits .041 under the as-cast mouth at nominal and .0009 under it at the
  printed limits with the barrel on its socket's axis.
- **D6 sockets.** Two-tier position, ⌖ Ø.06 | E | F | G over ⌖ Ø.010 | A,
  the upper tier Ø.06; it prints as two single-segment frames, since the
  drawing guidelines allow no composite frame.

Main's delegated ruling 2026-11-11 (#2333) adds one frame the rulings do not
name: the 4X Ø1.77 boss callout carries ⌖ Ø.06 | A | B, each barrel on the
faced top to the socket pattern. Targets F and G touch the barrels 1.56
under the faced top, where a 2° ±1° barrel's radius runs ±.042, so the
sockets' Ø.06 to E | F | G does not hold a barrel to its own socket. The
socket-to-barrel wall (.247), the keeper-foot clearance (.009) and the
head recess charge this frame. With the barrel the full .03 off its socket
and every other limit against it, the cross-screw head can stand .029
proud of the counterbore mouth. The cap-recess ligament is only .008 over
its .080 target, far less than a floor .029 deeper would take, so the print
keeps D5's floor and the residual is the owner's
([#2516](https://github.com/pedropaulovc/harmonic-analyzer/issues/2516)).

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`fr-top-frame`** | gray-iron casting, ASTM A48 class 25B, about 24.2 lb as cast (18.0 lb finished; 17.35 × 10.59 × 1.93 in finished, 2.09 high as cast), poured by an outside foundry from a shop-printed pattern: the casting `[[stock]]` row in `cad/config/shop-equipment.toml` | T-section rails (.32 flange on the faced top, .51 web on the underside, R.12 roots), the .99 crossbar with its 1.117 pockets and four Ø1.77 bosses (on the faced top) .18 proud, as cast with 2° draft and ±.03; **machined:** the faced top (64.5 in²) and faced underside (23.5 in², datum A and both knife seats), the four boss tops, the edge breaks bordering those faced planes, 4 Ø1.004 sockets bored from solid bosses, 4 Ø1.083 cap recesses and their mouth chamfers, the Ø.520 gooseneck bore and its mouth chamfer, the 1/4-20 set-screw tap and its Ø.39 spot face, the 4 cross-screw Ø.35 counterbores with their Ø.206 clearance holes and 10-32 far-wall taps, the 2 letter C hanger holes with their Ø.1240 dowel reams and #51 knockouts, and the 2 keeper 2-56 taps transferred from MHA-CH-07 at assembly | flat parting on the faced top plane with no undercut along the pull (mesh audit of the farm-built model: 0.0 in² facing the wrong way, every plane wall and barrel at 2.00°), so the pattern needs no core or loose piece; at the as-cast limits the binding walls are the keeper 2-56 tap drill wall .0807 (target .080, floor .060), the counterbore-to-cap-recess ligament .088, the dowel ream to the crossbar side .105 (.098 at its mouth) and the socket to its barrel .247; the fillister head keeps .0009 under the counterbore mouth at the 3° barrel on its socket's axis and can stand .029 proud with the barrel also the boss position's .03 off its socket (owner question #2516); the set-screw spot face keeps .031 of stock; solid bosses are the heaviest sections, so feed them from the boss tops | the spindle stands 7.5 in from the column cover (`ch_rocker_arm_tl_oblique_trammel_spec.THROAT_TO_COVER`) and the frame is 10.59 deep, so each face takes two setups: with the rear boss barrels at the cover, both knife seats (print-worst hulls end 8.92 in from that edge) and both keeper feet (8.76 in) lie inside one pass of a facing cutter 2.85 in or wider, which the shop records do not yet list; the front hanger station (8.60) and the front socket row (9.705) are past the spindle, so the part is turned 180° and each station and socket row there is picked up from the rear row | stress-relieved casting from the foundry; stand it on the three E boss bottoms against F1–F2 and G1 and face the top and the boss tops, turn it over onto the faced top and face the underside to the 1.437 grip (datum A), bore the socket pattern within Ø.06 of E, F and G and transfer-bore the base from it (#2386) |

---

## Recommended actions (gaps this pass surfaced)

1. **Retain the executable native wall guard for the cone gears.** After a forced
   rebuild, `build_dt_cone_gear.py` measures the native floor edges directly and compares both radial
   extrema with `dt_cone_gear_spec.floor_radius_min_mm` / `floor_radius_max_mm` within 0.002 mm.
   These are the nominal finite-arc envelope; the separate printed diameters from `floor_limits_mm`
   also enclose the manufacturing corners. The guard checks the native web at the maximum allowed
   bore against the retained web requirement; `test_dt_cone_gear_drawing` pins the T012 web exception
   (`WEB_EXCEPTIONS_MM`). Keep both when changing the tooth profile or bore bands.
2. **Qualify the selected `sm-summing-lever` solid-stock route and the unchanged
   knife roots/edge.** Option A removes the pad step and rib ledge, not the
   multi-setup workholding, cutter-access or hardened-insert debt. Native/CAM
   clearance, mass/CG, swept fit and measured installed balance remain open.
3. ~~**Model the `sm-knife-mount` mounting holes**~~ — RESOLVED (top-frame rederive, 2026-08-02; #10-24 hex-head cutover, 2026-10-13): the
   block is clamped to the top-frame casting's integral crossbar by the cut-to-length 18-8 hex-head Bolt
   and new #10 SAE washer on the whole faced top, into a #10-24 bottoming tap and located by one dowel pressed into the crossbar's blind underside ream and slipped into the block's round hole (owner ruling 2026-10-24, T+H3; one dowel per mount and a gauge bar through both bores setting their yaw at MHA-SM-00, owner ruling 2026-11-08 (Pedro), #2144 item 11.3; #10-24 tap cut on the part, 4140 HT as supplied, owner ruling 2026-11-10 (Pedro), #2334); the current route is documented above. Its revised native wizard and dimension import require the scoped farm proof; offline tests alone are not native evidence.
4. ~~**Reconcile the `ch-rocker-arm` R800 vs book 812.8 mm**~~ — RESOLVED: the arm keeps the book's
   R800 arc (`_rocker_interface.BOOK_TOP_RADIUS`), set to the middle of its profile zone (owner ruling
   2026-11-08 (Pedro), #2144 item 10.3); the sheet prints it BASIC R31.486 under a .020 profile (RV-02).
5. **Consider enlarging the tip cone gears** (T006 `dt-cone-tip-gear` and T012) — the model already flags them marginal and a
   period build used harder metal. **DP caveat:** enlarging OD at a *fixed tooth count* changes the
   DP/module and **breaks the shared 48DP mesh** — tooth *counts* preserve the ratio, but DP/pitch
   diameter preserves the *mesh* (`dt_cone_gear_spec.py` and `dt_cylinder_gear_spec.py` both read `diametral_pitch` from `gear_train.yaml`; §4
   treats the shared DP/PA as the meshing-domain constraint). So a real enlargement must either re-cut
   the mating **cylinder gear + centre distance** to the same new DP for that pair, or keep DP and accept
   the small size. Not the free change it first looks — the cheaper de-risk is the **harder tip metal**
   the original used.
6. ~~**Reconcile the `sm-knife-mount` material**~~ — RESOLVED: 4140/4142 HT as supplied (owner ruling
   2026-11-10 (Pedro), #2334); the registry stamps the BOM/drawing, the builder's library material is density only.

> These are machinability flags, not tolerance rules — the fits/finish/GD&T for the same parts live in
> [`tolerance-gdt-assessment.md`](./tolerance-gdt-assessment.md) §6, and the drawing/CAM outputs that
> carry them to the bench in §11. Those drawings now carry the **full** GD&T vocabulary (runout,
> position, profile, perpendicularity — ASME Y14.5-2018), not a runout-only "lite" subset. The DFM
> consequence: **each geometric callout is itself a machinability + inspection cost** — a tight
> runout or profile constrains the process (form-cut, single-setup, mandrel) and adds an inspection
> step — so a frame is spent only where the error model rewards it (the knife edge, the 20 cams,
> channel consistency), exactly the parts flagged T1 above. Over-calling GD&T is the same trap as
> over-tolerancing: it limits the process and inflates inspection for no functional gain.

## How to get this reviewed (strategy — for future reference)

Nobody reviews a 100+-part reproduction for free, and none should. **Don't review the machine —
review the risk:** the ~10 T1 parts above plus a few go/no-go questions, spread across cheap targeted
steps instead of one big engagement.

**The automated-DFM ladder — necessary, not sufficient, and each tool is blind in a different place:**

- **DFMPro (SW add-in) and Xometry auto-DFM — false-green here (observed).** Both passed *every* SLDPRT
  — yet the model is full of sharp internal corners (every gear-tooth root, the cam notch) a round tool
  cannot cut, plus the thin T006 **root-to-bore web** (0.621 mm in the model they checked). Their rule sets are tuned for
  moulding / sheet / generic 3-axis and don't flag manual-machining hazards. **A green from these
  means little — trust it for nothing on the corners or walls.**
- **Fusion 360 CAM verify/simulate — a desk check only, with a known edge.** The shop has no CNC, so
  no program runs on the manual PM-30MV; but because it
  simulates the *actual tool against the actual solid*, it **surfaces the class DFMPro missed**: an
  internal corner smaller than the smallest endmill shows up as **un-cut stock** (you can't program a
  sharp internal corner), and tool-reach / gouge / holder-collision are caught. Banking on Fusion for
  the **majority of tool-access & gouge issues is reasonable** — it's a real simulation, not a
  rule-of-thumb checker.
  - **But its blind spot is exactly where the worst risk lives.** Fusion treats geometry as **rigid**
  and stock as **held**, so it will *not* warn that the **T012 web (1.64 mm minimum)** breaks in
  workholding, the **Ø1.5875 mm T006 spigot** whips, the **1.80 mm cam wall** is fragile, or that
  a ~4 mm gear can't be gripped. Thin-wall / fragile-feature / fixturing failures are not modelled
  by CAM sim. **A clean Fusion sim is not a substitute for a first cut on the fragile parts.**

**Order that actually de-risks the build:**
1. **Fusion CAM verify** (desk check, no CNC behind it) — cheap; catches the tool-access/gouge/reach majority, incl. the sharp corners
   (as uncut stock).
2. **First-article cut** — cut **one** of each fragile/hard part (a T006 gear, a cam-gear, a rocker arm,
   the thin shaft) and inspect **before** committing to 20×. The only check that catches
   thin-wall/workholding — precisely Fusion's blind spot.
3. Narrow paid consults / outsource-quotes only for whatever 1–2 leave open.

**Inspecting the geometric callouts (what the first-article cut actually measures).** The full-GD&T
frames map to concrete shop checks — this is part of the per-part inspection cost above, not free:
**runout** (gears, cams, journals, wheel) → mandrel + dial gauge rotated per cross-section (a
workflow the audience already knows as "indicating"); **flatness / straightness** (mount seats,
shaft axes) → dial-indicator sweep on jacks / Vee-blocks; **position** of the hole patterns (support
feet, the 20 spring holes) and **profile** (the R800 rocker, cam eccentric, gear-tooth flanks) →
CMM against the basic-dimension grid / nominal curve, since a hand gauge can't hold a profile; any
**angularity** → sine bar. The profile and position checks on the fragile T1 parts are where a CMM
(or an outsourced inspection) earns its keep — budget for it rather than assuming calipers suffice.

**Go/no-go — gear cutters: RESOLVED (stock cutters, one special).** The train moved from the
measured-photo pitch DP 49.82 to standard 48DP PA20 so that stock involute cutters cover every gear
except the T006 cone ([`gear-standard.md`](./gear-standard.md)). The per-part plan is below;
wire-EDM and hobbing stay outsource alternates.

## Cutter plan

Every cut gear uses a stock involute form cutter from the eight-cutter set for its pitch,
indexed on the dividing head, except the T006 cone. Three sets cover the machine: 48DP (cones,
cylinder gears, alignment drum and paper reducer), 24DP (crank pair) and 32DP (feed pinion); the
rack is bought. The cutter numbers follow the Brown & Sharpe
ranges (#1 135 teeth to a rack, #2 55–134, #3 35–54, #4 26–34, #5 21–25, #6 17–20, #7 14–16,
#8 12–13), which date to the period catalogues
([Brown & Sharpe 1904](https://archive.org/details/BrownAndSharpeMachineryAndTools1904Catalogue))
and are still sold today ([C.R.Tools](https://crtoolsuk.com/product/diametrical-pitch-involute-gear-cutters/),
[Newman Tools chart](https://www.newmantools.com/cutters/gear.htm)). Module cutters number the
same ranges in reverse, so order by DP.

Indexing assumes a 40:1 head, the ratio of the shop's Precision Matthews BS-0, so one tooth is
40/N crank turns. The hole circles are the standard Brown & Sharpe plates (15, 16, 17, 18, 19,
20, 21, 23, 27, 29, 31, 33, 37, 39, 41, 43, 47, 49), from
`references/machinerys-handbook/` (printed p. 2008, which also covers differential indexing). The BS-0's own
plates have not been checked against this list; check yours before cutting.

### Cone and cylinder train, 48DP PA20

| part | teeth | cutter | index per tooth (40:1) |
|---|--:|:--:|---|
| `dt-cone-tip-gear` T006 | 6 | special, see below | 6 turns + 10 holes on 15 |
| `dt-cone-gear` T012 | 12 | #8 | 3 turns + 5 on 15 |
| `dt-cone-gear` T018 | 18 | #6 | 2 turns + 4 on 18 |
| `dt-cone-gear` T024 | 24 | #5 | 1 turn + 10 on 15 |
| `dt-cone-gear` T030 | 30 | #4 | 1 turn + 5 on 15 |
| `dt-cone-gear` T036 | 36 | #3 | 1 turn + 2 on 18 |
| `dt-cone-gear` T042 | 42 | #3 | 20 on 21 |
| `dt-cone-gear` T048 | 48 | #3 | 15 on 18 |
| `dt-cone-gear` T054 | 54 | #3 | 20 on 27 |
| `dt-cone-gear` T060 | 60 | #2 | 10 on 15 |
| `dt-cone-gear` T066 | 66 | #2 | 20 on 33 |
| `dt-cone-gear` T072 | 72 | #2 | 10 on 18 |
| `dt-cone-gear` T078 | 78 | #2 | 20 on 39 |
| `dt-cone-gear` T084 | 84 | #2 | 10 on 21 |
| `dt-cone-gear` T090 | 90 | #2 | 8 on 18 |
| `dt-cone-gear` T096 | 96 | #2 | 10 on 24 (MHA-DT-03-TL-01) |
| `dt-cone-gear` T102 | 102 | #2 | 20 on 51 (MHA-DT-03-TL-01) |
| `dt-cone-gear` T108 | 108 | #2 | 10 on 27 |
| `dt-cone-gear` T114 | 114 | #2 | 20 on 57 (MHA-DT-03-TL-01) |
| `dt-cone-gear` T120 | 120 | #2 | 5 on 15 |
| `dt-cylinder-gear` ×20 | 120 | #2 | 5 on 15 |
| `dt-alignment-pinion` | 32 | #4 | 1 turn + 4 on 16 |

T096, T102 and T114 need 5/12, 20/51 and 20/57 of a crank turn, which no stock plate gives. The
shop-made index plate MHA-DT-03-TL-01 (`dt-cone-gear-tl-index-plate`, fitted by
`dt-cone-gear-tl-indexing-assembly`) carries 24-, 51- and 57-hole circles for them; its sizes are
best guesses until the BS-0 plate is measured
([#2157](https://github.com/pedropaulovc/harmonic-analyzer/issues/2157)). Differential indexing on a
universal head with change gears is the alternative. Those tooth counts did not change with the
pitch, so this was already true of the old train.

Each gear is modelled as the gap its stock cutter makes: the tooth of the lowest count in the
cutter's range. Each cone is cut at standard depth, so the cutter's pitch line sits on the cone's
pitch circle, and its blank is the AGMA standard outside diameter, (N + 2)/DP, cut down only where
the cutter's form would stop supporting the tip
([`gear-standard.md`](./gear-standard.md#cutter-native-teeth)). The meshes are not conjugate.
They are accepted by closed-form contact-ratio, interference, backlash and root-clearance checks
on the printed limits, plus the SolidWorks assembly interference gate
([`gear-standard.md`](./gear-standard.md#how-the-meshes-are-accepted)). Cut and roll one gear per
cutter before committing a set all the same.

Boston Y48120 is a catalogue brass 48DP PA20 120T spur. Using it as a donor for the cylinder-gear
teeth is possible in principle, but the part is not designed around it.

### T006 special cutter

No range cutter reaches 6 teeth, so T006 needs a tool made in the shop: DT6-FORM1, a custom
ground form tool. Sheet 2 of the MHA-DT-37 package defines the T006 tooth space it is ground to,
point by point with its form tolerance; the tool itself (blank, rake, relief, holder) is not drawn,
and the form band has no gauge the shop owns
([#2358](https://github.com/pedropaulovc/harmonic-analyzer/issues/2358)). T006 has no bore since owner
decision C1 keyed (2026-11-09, PR #1992), so the cutter leaves no root-to-bore web; it runs off over
the integral spigot and pivot (.011 in radial).

For background on shop-made form cutters, Law's *Gears and Gear Cutting*
(`references/gears-and-gear-cutting/`, ch. 12) forms the cutter profile with a button tool: two
hardened round buttons set at a chosen centre distance. The Eureka device named there is only an
attachment for relieving the cutter. Law's button table covers cutters from a 17-tooth pinion up,
so it does not give a six-tooth form.

### Crossed crank pair, normal 24DP PA20

| part | teeth | form | cutter | index per tooth (40:1) |
|---|--:|---|:--:|---|
| `dt-crank-pinion` | 16 | straight spur | #7 | 2 turns + 10 on 20 |
| `dt-crank-drive-gear` | 64 | straight teeth inclined 13.0011° right hand | #2 (virtual 69 teeth) | 10 on 16 |

Owner ruling 2026-11-10 (#2332, option A) supersedes the earlier true right-hand helix (lead
945.862 mm): the 64T has straight teeth inclined at the cone incline. The cutter is still the one
chosen for its virtual tooth count, N / cos³ of the 13.0011° inclination, which lands in the #2
range ([John F's workshop, helical gears](https://johnfsworkshop.org/home/making-other/gears-links/helical-gears-links/making-helical-gears-on-a-vertical-milling-machine/)).
Tilt the installed Precision Matthews BS-0
([BS-0](https://www.precisionmatthews.com/products/dividinghead-bs-0)) 13°, feed the #2 cutter in
a straight line through each tooth space and plain-index between spaces. Set the cutter centre
plane to cross the gear axis 1.778 mm (.07 in) north of the south (collar) face. No lead gearing
or spiral-capable head is needed. The printed tooth data are unchanged; approval is conditional
on the straight model passing the drive-train interference and soundness gates.

The tilt sense sets the hand, and every other printed number is the same for a left-hand gear.
With the cutter on the vertical spindle's stub arbor (cutter plane horizontal) and the head at
the left end of the table, raise the head's nose 13° and cut on the operator's side of the
blank. Putting the head at the right end, or the cutter behind the blank, cuts a left-hand gear;
doing both cuts a right-hand one again. Check the first scribed pass and the finished gear:
stood on either face, the teeth nearest you rise to the right.

Set each crank gear up for tooth cutting within 0.05 mm TIR of its finished bore
(`cad/config/tolerances/crank_mesh.yaml`, `tooth_cutting_runout_tir_mm`, read by both gear specs). This is a
setup allowance, not a gear accuracy grade.

### Paper drive

| part | teeth | pitch | cutter | index per tooth (40:1) |
|---|--:|---|:--:|---|
| `pd-rack-pinion` (reducer disc) | 150 | 48DP PA20 | #1, TTC 10-289-481 | 4 on 15 |
| `pd-transgear-knob-shaft` integral pinion | 15 | 48DP PA20 | #7, TTC 10-289-487 | 2 turns + 10 on 15 |
| `pd-transgear-feed-pinion` | 12 | 32DP PA20 | #8, Precise/Penn 10-289-328 | 3 turns + 5 on 15 |
| `pd-platen-rack` | rack, pitch 2.4936 mm | 32DP PA20 | none: bought as stock rack | none |

The reducer is 15:150 at 48DP (#2034 replaced 12:120; the ratio stays 1:10). Its two 48DP
cutters, #1 and #7, are sizes the cones do not use, so the 48DP set needs both. The knob's 15T is
cut straight through its face: its form root stands above the journal, so the cutter runs out in
air with no endcut. The feed 12T carries the stock #8 form, and its hub is shaped so the cutter
runs out clear.
The rack is bought, not cut: SDP/SI A1B12-Y324, a 48 in brass 32DP 20° rack, 3/16 × 3/16 in
(4.7625 mm) square ([product page](https://shop.sdp-si.com/a-1b12-y324.html),
[D820 catalogue](https://sdp-si.com/D820/PDFS/Gears.pdf)), cut to the printed 269.6 mm callout
(`cad/config/parts/pd-platen-rack.yaml`) and soldered to the existing backer. The 269.64 mm
CAD nominal is not the shop cut length; `pd_platen_rack_spec.DRAWING_PRECISION` prints it
to one decimal place under the ordinary .X band. Check it against the feed pinion before fitting; the pitch-index limit the model
allows for it is in `cad/config/tolerances/stock_form_quality.yaml` (`rack_pitch_index_deviation_mm`).

The chain is 66 links of ANSI #25, 12:24 from the crank sprocket to the knob sprocket (#2034
moved the knob 6.64 mm nearer the crank; the former 68 links no longer close). The
sprockets are made from McMaster 6793K blanks. The transgear arm and its plate are located by two
MHA-PD-VN-64 dowels (McMaster 98381A435, 3/32 × 5/16); the screws only clamp.

The knob-shaft journal length is **1.62 in**, under the title block's
two-place **±.01 in** row (#2169, Main delegated ruling 2026-11-04 under
#989). It runs .264 in behind the cup face, which sits at 1.356 ±.005 in
from the gear rear; the cup pin is at .120 in from the cup front, marked out
within ±.004 in on the cup sheet and ±.005 in on the assembly step. The
journal's rear-end rim takes the title block's .010 in edge break. The
crosshole is match-drilled through cup and journal together, so its mouths
stay buried in the cup bore and are left unbroken. The shortest journal,
less that break, leaves **.0825 in** beyond the largest Ø.065 pin hole at
the cup sheet's station band and **.0815 in** at the assembly step's; both
clear the .080 in wall target. The longest journal stays **.031 in** inside
the shortest cup (.056 in nominal). The cup and pin stations do not move;
only the journal is longer.
