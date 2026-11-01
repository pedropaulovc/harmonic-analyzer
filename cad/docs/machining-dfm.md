# Machining DFM — per-part manufacturability pass (Tier-1)

> Companion to [`tolerance-gdt-assessment.md`](./tolerance-gdt-assessment.md). That doc's §6 tiers
> the parts by **tolerance/fit/GD&T** effort; this one is the **machinability** layer for the same
> Tier-1 parts — *can the machinist actually cut this, in what stock, in how many setups, and where
> will it fight back.* Generic DFM checklists ("radius internal corners", "minimize setups") are
> useless as bare bullets; every row below is attached to a **named feature with a real number** from
> the build script. Audience + toolchain per §1/§11: period **brass + steel**, **manual mill + lathe
> primary (fidelity)**, **PM-30MV CNC for the repeat parts**, Fusion 360 CAM off the STEP export.

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
  1. **`dt-cone-gear` T006** — minimum root-to-bore web **0.64 mm** on a **Ø4.31 mm OD gear with a 1/32 in (Ø0.794 mm) bore**.
     The terminal journal was cut to 1/32 in so the 48DP PA20 gap floor keeps at least the 0.62 mm
     web floor, the one named web exception ([`gear-standard.md`](./gear-standard.md#what-it-costs)).
     The single hardest part in the machine. These teeth are cut as involute flanks closed by a gap
     floor with printed diameter limits; T006's floor, cut by DT6-FORM1, is Ø2.136 MIN / Ø2.201 MAX.
     After a forced T006 rebuild, `build_dt_cone_gear.py` compares the native minimum and maximum
     root radii with the nominal finite-arc envelope within 0.002 mm. The printed limits enclose
     the manufacturing corners, not just that nominal envelope. T012 shares the 1/32 in terminal and its web is 2.02 mm at the worst
     case, over the 2.0 target; the T018 and T024 webs meet the target on the S1 bores.
     Period mitigation: the tip gears were a harder yellow metal.
  2. **`sm-summing-lever` knife edge** — the sharp top-vertex ridge of a hex trunnion that protrudes
     **21.717 mm unsupported** past each end of a casting-shaped organic lever. Delicate (nicks/rounds)
     *and* fixturing-hostile from bar. Per §6 the edge should be a **separate hardened tool-steel
     insert**, not this parent — which also removes it from this part's machining hazard.
  3. **`dt-cone-gear-shaft` tip** — a **Ø0.79375 mm (1/32 in) terminal land, about 33.6 mm long in steel (L/D 42)**,
     carrying the T012/T006 seats and the MHA-DT-VN-54 stack collar, its cup tip seated in the MHA-DT-VN-55 adjuster.
     Support the slender work with a follower/steady and take a light finishing cut;
     the terminal D-flat continues from the T018 step through the shaft tip.
     Break the two long torque corners of the terminal flat no more than 0.02 mm; the 0.420 AF
     already pays for that break. The model leaves these corners sharp and the sheet prints the break
     as a callout, `TORQUE CORNERS: STONE BURR ONLY, 0.02 MAX`, because it is below the title block's
     R0.25 edge break. The stepped collar (Ø17.48 body, Ø6.40 × 3.5 nose, 11.5 overall;
     `dt_vn_cone_tip_collar_spec.OUTER_DIA`) has a
     finished bore of Ø0.849 ±0.030 and a radial #2-56 through tap. Fit the stock McMaster
     94355A213 #2-56 × 5/16 in flat-point screw unaltered, with no dog. To fit the collar, hold the
     gear stack south on the shaft's thrust collar, set the original 0.45 ±0.10 feeler off the
     T006 thrust face, seat both collar bore ends on the round back of the terminal, snug the
     stock flat point on the D-flat, then remove the feeler.
     Never run or swing a loose collar.
     During the post fit-up (MHA-DT-00 step 3), hold MHA-DT-05 pushed toward
     MHA-DT-21 along the shaft throughout: turn the post on its screws until the
     tip centres in the cup, tighten both MHA-DT-VN-61 screws and recheck. This takes
     up the post's along-shaft screw clearance away from G19.
     Installation notes are in `dt_vn_cone_tip_collar_spec.INSTALLATION_NOTES`;
     `dt_tip_collar_air.py` owns the
     air stack over the whole swing. Use worst-case arithmetic over every source if it
     clears everywhere; otherwise use the statistical method everywhere: nominal air
     minus the arithmetic sum of `IN_SERVICE_CLEARANCES`, minus the RSS of independent
     printed manufacturing and set tolerances, minus the swing-interval arc allowance.
     Fastener and running clearances, thread centring, the cup screw in its thread,
     shaft swing in the post journal off the cup, collar float and cock, set-screw
     thread rock, and G19 cock can all be taken up together; never put them in the RSS.
     ASME B18.6.2 limits only the cup diameter, not its depth or wall angle, so the
     released shaft swing is bounded by the post journal, not by assumed cup capture.
     The current calculated least nose air is 0.4681 mm (`dt_tip_collar_air.require_air()`),
     not a measured clearance.
     The shaft drawing's supplementary **Setup References** sheet measures from
     the collar's north / 64T-seat face to the three shoulders and the tip.
     These are native, parenthesized reference measurements only, with no
     independent acceptance band; **Shaft Controls** (sheet 1) retains every
     controlling dimension, including the tip-side stations measured from the
     journal-side thrust face, and the existing tolerance correlations.
     The presentation does not establish chuck access
     to either collar face or prescribe a workholding arrangement.

- **The CNC repeat families (make N identical on the PM-30MV — this is where CNC earns its keep):**
  | family | qty | why CNC |
  |---|---|---|
  | `dt-cylinder-gear` (+ integral cam) | 20 | 120 teeth + eccentric cam + 0.4 mm index notch, all co-phased +Y — hand-repeating 20× scatters the phase |
  | `dt-cone-gear` | 20 | involute teeth cut with stock 48DP PA20 range cutters indexed on a dividing head; T006 alone needs a special cutter (see [Cutter plan](#cutter-plan)); wire-EDM = outsource alt |
  | `pivot-bushing` / `lever-bushing` | 19 each | turned spacers whose **length** sets channel pitch — length consistency across the set is the point |
  | `ch-rocker-arm` | 20 | flat R800 profile, one setup — ideal CNC profile part |
  | `ch-connecting-rod` | 20 | flat 2D outline from 1018 plate, stepped both faces, slotted fork → 2.5D |
  | `sm-knife-mount` | 2 | trivial prismatic block, 2 identical |

- **Casting-vs-bar substitution:** `fr-rocker-arm-support` is a benign stock
  substitution; the **`sm-summing-lever` now explicitly uses a machined-from-solid
  route** in its registry. Option A simplifies its coefficient side to a uniform
  7.00 mm slab and one shared tangent rib profile, but does not turn the retained
  cylinder, counter web and delicate knife trunnions into a simple plate part.
  Plan the multi-setup workholding and cutter access for the actual solid; the
  setup count and machining clearance still need native/CAM qualification.
  - **`sm-knife-mount` is a material *conflict*, not a settled casting:** its registry
    (`parts/sm-knife-mount.yaml`) and assessment §6 say **Brass**, but `build_sm_knife_mount.py` hardcodes
    `MATERIAL = "Gray Cast Iron"`. The registry value is what stamps the BOM/drawing custom property, so
    the intended stock is a **brass bar block** (trivial) — the script constant looks stale. Reconcile
    before it reaches a drawing (gap below).

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
  through matching D-bores on the shaft's D-flat lands; the cylinder gears
  ride free on their stationary arbor. The gears seat against each other,
  without an adhesive joint or spacers, from the collar-supported 64T to T006.

- **`fr-harmonic-base` cross-screw seats:** the green-top height and the
  cross-screw axis are dimensioned from the same faced underside, rather than
  deriving the land through the flange, pad and deck-rise chain. With ordinary
  `.X` ±0.8 mm bands, the minimum ligament above the Ø9.0 spotface is
  `(47.8 − 0.8) − (38.1 + 0.8) − (9.0 + 0.8)/2 = 3.2 mm`.
  This changes the dimensioning scheme, not the casting or its interfaces.
  The #10-32 cross tap is one continuous lead through both casting walls,
  interrupted by the matched column socket; engagement counts both threaded
  segments, not only the near wall. Even allowing a 0.762 mm stock-screw length
  reduction, a Ø26.0 matched socket and two 1.5-pitch end losses, total engagement
  is `44.45 − 0.762 − 26.0 − 3 × 25.4/32 = 15.31 mm`, above 1.5D = 7.24 mm.
  The drawing states `COMMON THREAD LEAD IN BOTH WALLS`: the seat remains blind,
  and its associative full-thread and minimum-drill depth tokens are unchanged.
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

The two receiver axes move down **0.71 mm** to local **Y=−0.71 mm**.
**ReceiverY0 = .1280 ±.0020 in (3.25 ±0.0508 mm) below the actual coefficient top** owns that
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
of approximately **2.220535 / 2.578535 mm**. The connected-plate proof takes
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
pilot-only material budget. The **.1280 ±.0020 in** actual-top row location
places both receiver axes at local **Y=−0.71 mm**; the matched bracket holes
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
| **`sm-knife-mount`** | rectangular block 25.4 ±0.8 wide ×29.6×14.0 (bar/plate), hardened; sizes apply after heat treatment (owner ruling 2026-10-24, H3); **2 identical** | unchanged Ø12.00 +0.03/0 reamed through bore and pose, centre 20.616 BASIC below the top face (`BORE_CY` −5.75 from the knife-edge origin, block top +14.866, clamped to the casting underside); #10-24 UNC-2B bottoming tap on the bore axis: #25 Ø3.7973 under the title-block DRILLED HOLES +0.10/0 row, cylindrical drill depth 11.24 ±0.05, full thread 9.65 ±0.13; fully charged drill-point crown web 2.0077656525, no break-in (conservative proof envelope Ø3.927, above accepted MAX Ø3.8973; point MIN 117°); MHA-SM-VN-53 slip features cut from the top seat to one flat floor 9.5 deep (owner ruling 2026-10-24, T+H3): datum B, a Ø3.25 ±0.02 blind flat-bottom reamed round hole 7.632 +X of the tap axis (5.07 ±0.51 from the +X face; row 7.0 from front face), and datum C, a 3.25 ±0.02 wide slot on the −X dowel, ⌖0.05 to A and B, its half-round end 14.40 ±0.51 from B and open through the −X face; tap ⌖Ø0.14 (the largest two-place zone the bolt float admits) and bore ⌖Ø0.20 to A, B and C, the bore with a composite Ø0.05 orientation refinement to A, B and C (owner ruling 2026-10-27): knife rock 6.319° worst against the 5.0° floor, the far-end offset 0.197223 charging the dowel yaw (its pair shift carrying both datum simulators' ⊥0.015 t/2), the whole Ø0.05 refinement, and the lever ridge's yaw from both bores' Ø0.20 position zones over its 159.32 minimum mouth span; bore floor and pose unchanged | hold the explicit tap/drill depth bands and accepted pilot diameter/point-angle bounds to preserve ≥2.0 crown web; all joint webs ≥2.0 at printed worst cases | 1–2 (square block, bore one axis) | **CNC-REPEAT** (×2) or manual. Modified #10-24 hex-head Bolt MHA-SM-VN-52 (92314A253, cut under head at MHA-SM-00 step 4 to its hole's measured crossbar-underside-to-washer-top stack plus .351 ±.006 in (8.9154 ±0.1524); 46.70 nominal, printed (1.84) as a reference) and new 18-8 SAE washer MHA-SM-VN-54 (96659A104) clamp the block to the top-frame's integral crossbar through Ø6.045 #10 loose clearance. Crossbar width 25.0 ±0.8, symmetric about X=−15; washer seat on the whole faced top (no SPOTFACE), 36.50 (title-block ±0.51) above faced underside. Nominal reach 8.9173, range 8.763–9.0678; full-form engagement MIN 7.704667 ≥7.239, tip air MIN 0.4522. Retain removable medium-strength threadlocker. MHA-SM-VN-53 dowels (98381A473, 1/8 ×3/4) press 12.0 to the floors of two Ø3.175 +0/−0.010 blind reams in the crossbar's faced underside (0.0025–0.0177 interference; the +X ream 7.632 ±0.13 from its bolt axis, the −X ream BASIC 15.264 from the +X under ⌖Ø0.05), each pierced by a #51 (Ø1.70) knockout drilled up from its floor on the ream's axis; their 7.05 proud ends slip 0.047–0.093 into the block's B and C, the block fitting either way round. One native linear pattern position control ⌖0.10 to the bar's two-face width median datum D limits X shift to ±0.05, retaining the Z socket station and ≥2.0 webs. The former #6 socket-head counterbore route is obsolete |

The Ø6.045 hanger clearance hole carries a **native explicit +0.13/0
diameter band** (MIN 6.045, MAX 6.175), not the symmetric general ±0.13
band: undersize would fail bolt float. With this maximum hole diameter and
the MHA-SM-VN-53 press reams (owner ruling 2026-10-24, T+H3), the
worst-case screw-to-ream web is 2.667957488 mm and the outer ream web
2.608478744 mm, one pair for both reams charged at the −X ream's looser
station (7.632 ±0.13 plus its 0.025 zone radius, ±0.155). The #51
knockouts (Ø1.70, DRILLED HOLES +0.10/0) keep 3.030836665 mm to the bar face
and 2.963550987 mm to the screw hole. The ream floors print **4X FLAT BOTTOM, CORNER R0.1 MAX**. The
pressed end bears only inside its ASME B18.8.2 point (Ø2.794 MIN) and
outside that corner, a 0.313152237 mm bearing land on the ream floor at
the drawn coaxiality's implied ±0.13 per axis, under the 0.4 target by owner
ruling 2026-10-27 (machinist exception RV-06). The largest end flat (Ø3.048) sits on the fillet, which
holds it at most 0.009017859 mm off the floor. Each knockout is a ~15 D
run (25.81 mm from the shallowest floor to the top at the grip's far limit):
the shop drills it with a pecked **taper-length #51** (2 in flute, 3-3/4 in
overall), whose flutes clear the 37.01 mm from the underside, and removes a
dowel from the faced top with an extra-long 1/16 in pin punch or drill-rod
drift of at least **37.01 mm** reach (`HANGER_KNOCKOUT_PUNCH_REACH_MIN`).

The washer-seat grip is the model's actual driving thickness dimension
`HangerGrip@Crossbar`, **36.50 mm** from the finished underside to the
whole faced top, except the four corner bosses that remain 4.5 mm proud.
The builder authors no band on it and section F-F imports it bare under the
title block's .XX **±0.51 mm** band (owner ruling 2026-10-18); there is no
hanger spotface, separate floor driver or cleanup-stock offset.

On the MHA-FR-02 CROSS-TAPS sheet, the native 10-32 hole-callout leader
states that the near and far casting walls are threaded **in phase for
MHA-FR-VN-53**. The requirement travels with the feature, not a detached A-A
note; the Hole Wizard still owns the thread and tap-drill depths.

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
Datum A is new: the faced underside on F-F, to which the four press reams
carry **⊥Ø0.02** (RV-05). Datums B and C now name the +X press reams (front,
rear) in place of the retired round slip holes. Datum D and A-A/E-E/F-F/VIEW G
are unchanged. Section stations, endpoints,
profiles, orientations and scales retain the historical B/E/D placement
calibration; old B/D glyph bounds do not establish H/K glyph clearance.

Owner ruling 2026-10-24 (T+H3) retires the crossbar's dowel slot and round
slip holes. Each knife-mount station now carries two **Ø3.175 +0/−0.010 mm**
blind reams, **12.0 ±0.8 mm** deep from the faced underside to a flat
floor, into which the MHA-SM-VN-53 dowels press to the floor; each is
pierced on its axis by a **#51 knockout** drilled up from its floor on the
ream's axis (no setup note), which exits at the faced top under the MHA-SM-VN-54 washer
(the washer keeps a continuous bearing ring inside the knockouts). The +X
ream stands **7.632 ±0.13 mm** from its bolt axis and is the datum the −X
ream is located from: **BASIC 15.264 mm** under **⌖Ø0.05** to B and C
(front) or C and B (rear), so the block fits either way round. The slot
itself moved
to the MHA-SM-02 block (datum C, open to its −X face), so the 3.950
overall slot length, its (0.710) radius-centre reference and DETAIL L's
subject leave the crossbar. The replacement F-F and underside-locator
annotations belong to `draw_fr_top_frame` and need native inspection; the
historical slot-text placements and glyph clearances do not carry over.
The native 36.50 grip text sits on its line right of F-F's profile at
**(158, 75) mm** (`HANGER_GRIP_TEXT_XY`).
The top-frame recipe sets and reads back drawing-document wireframe curve
quality (Custom, value 100, high curve quality enabled) before creating views.
This per-drawing tessellation control is independent of the views' precise
HLR mode (`Faceted=False`); it does not change geometry, dimensions, tolerance
exceptions, crops or scales. Successful preference readback or offline tests
do not prove smooth exported ink: inspection of the resulting native drawing
and actual exported vector PDF is required.

The whole top except the four corner bosses is finished Ra 3.2 µm. The right
(west) rail alone remains flat within 0.04 so both MHA-CH-07 keeper bores
align. The finished underside and knife-mount pose remain unchanged.

The casting's flange corner crops and convex edge breaks are judged at the
print's limits, not on the nominal model. Each corner's crop chord ends on
the smallest printed corner-boss barrel at the farthest printed rail faces
(`CORNER_CROP_BOSS_R_MIN`, `CORNER_CROP_FACE_OFFSETS`), so no conforming
casting keeps a flange nib outside a barrel. The 1/16 in × 45° break goes
only on edges that hold its print-worst leg and sliver land at those limits.
The crossbar flange underside (`T_FLANGE_SHELF_PRINTED_MIN`) and the hub
rib's outer bottom beside the set-screw boss (`HUB_RIB_STUB_PRINTED_MIN`)
do not, so they stay sharp. The rib's inner bottom, the V-gussets and the
knife-seat bottoms also stay sharp, as the sheet notes say. No band is
tightened to recover a break.

The grip no longer sets **MHA-SM-VN-52 thread engagement**: MHA-SM-00 step 4
cuts each bolt to its own hole's measured stack plus **.351 ±.006 in** (8.9154 ±0.1524 mm)
reach. The crossbar median datum D controls the hanger axes in X only:
their BASIC X location is on D.
The socket-to-D locator retains its ordinary location band; the front and
rear Z station dimensions likewise remain ordinary toleranced dimensions.

The mount's tap position is **Ø0.14 A B C**, the largest two-place zone
the bolt float admits. Owner ruling 2026-10-24
(T+H3) presses the dowels into the crossbar and slips them into the block,
which fits either way round: the +X ream stands .XXX from its bolt axis and
the −X ream BASIC 15.264 from the +X under ⌖Ø0.05, so with B on the −X pin
its ream's 0.025 zone radius adds to both legs. The X leg is that ream
station, 0.025, the tap zone radius, B's loosest slip and B's datum
simulator, which within ⊥0.015 to A may sit 0.0075 (t/2) off the pin root;
the Z leg adds 0.025 again through the slot's offset from B, both
simulators' t/2 through that offset, and the B–C datum line's yaw
(the front and rear +X reams at opposite .XXX limits turn it by 2 × 0.13
over the 174.12 station spacing, moving the tap 7.632 along the pair across
by 0.0113962784): **hypot(0.27873, 0.3026262784) = 0.4114280949 mm**.
Full-crossbar drill drift charges the printed grip's thickest **37.01 mm**
(36.50 + 0.51) and is **0.1937856778 mm**; together they consume
**0.6052137727 mm** of the **0.6095 mm** radial float, leaving
**0.0042862273 mm**. The stack closes at a Ø0.1461 tap zone; Ø0.15 gives
**−0.0027789753 mm**. The −X ream zone closes near Ø0.0548: Ø0.055 gives
**−0.0001663540 mm**.
The block carries no dowel-pattern
frame: datums B and C are its round hole and its slot.

Owner ruling 2026-10-27 (#2016 option A) bounds the pin-to-hole tilt the
slip fit must take: the crossbar reams carry **⊥Ø0.02** to the faced
underside and the block's round hole and slot **⊥Ø0.015** to A. At the
shortest printed depths less the floors' corners (the ream's CORNER R0.1
MAX; the block's title-block R1.0 MAX, since nothing seats on its floor)
and less a 0.5 lead allowance (10.6 ream wall, 7.2 hole wall), they tilt
the pin against its hole by 0.1081° + 0.1194°. The lead allowance is
conservatism beyond the print, not an undersize tail: each hole's size band
applies over its full depth, so a conforming ream is full size to its floor
corner, the pin bottoms and the proud length holds.
An assumed 0.01 conformity of the clamped seats across the block's
shortest 13.2 seat depth adds 0.0434°; this is an assumption about
ordinary face-milled seats drawn flat by the bolt, not a drawing control.
The charge totals **0.2709°**, inside the **0.3522°** the tightest slip
takes over the longest proud pin (its 0.009 floor-fillet lift included)
short of its rounded free end (8.113 − 0.406), a margin of 0.0814°. That
margin comes from the slip band: Ø3.25 ±0.02 (a stock metric reamer; the
slot milled to the same band) keeps the 3.270 maximum, so the loosest slip
and every stack it feeds are unchanged, and opens the tightest slip from
0.027 to 0.047 (codjiflo round 6); the old Ø3.24 ±0.03 band took only
0.2036°. ⊥Ø0.04 on the ream (0.3790°), ⊥Ø0.03 on the block (0.3902°) or a
0.03 seat conformity (0.3577°) would bind; the seats bind past 0.029.

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
**#25 DRILL ▽ 11.24 ±0.05 ×118°**. The callout names **MHA-SM-VN-52**
and states that the depth bands set its tip clearance; it does not prescribe
a tapping tool. With no duplicate diameter band, the callout remains inside
the four-row limit. The title block supplies default class 2B; the thread
row prints **#10-24 UNC ▽ 9.65 ±0.13**. The native point and physical
acceptance limits are unchanged. The final native layout audit remains
active and must prove the rebuilt sheet.
The now-dimensioned point takes the title block's **angular ±1°**, giving
117°–119°; the proof charges **MIN 117°**. This is not a claim that an
undimensioned tool point was already governed by the general angular grade.
The resulting point height is 1.2032343475 mm. With drill depth MAX
11.29 mm, the built top at 14.866
leaves **2.0077656525 mm** over the worst-case bore crown (the bore's
⌖Ø0.20 charging 0.10 of crown); the spec mirror's rounded top at 14.87
gives 2.0117656525 mm, not the built guarantee.
Full thread **9.65 ±0.13 mm** gives MIN 9.52 mm, leaving **0.4522 mm** tip air
under the bolt's 9.0678 mm longest fit-up reach. Two printed places do not
loosen it to the general .XX ±0.51 band: that would give a 10.16 mm deepest
thread, which the drill's 11.19 mm shallowest limit clears by only 1.03 mm,
under one 1.058333 mm pitch of runout. Drill-minus-full-thread runout is
1.59 mm nominal and 1.41 mm at the adverse depth limits.

**Modified hanger-bolt shop route (MHA-SM-VN-52, two).** Source McMaster
92314A253, 18-8 stainless plain external-hex #10-24 UNC-2A ×2 in stock;
retain the supplied head. Leave the supplied length uncut at the bench:
MHA-SM-00 step 4 seats washer 96659A104 on each crossbar hole's faced top,
measures crossbar underside to washer top, and cuts the bolt to that plus
**.351 ±.006 in** (8.9154 ±0.1524 mm) under the head (46.70 mm nominal; the
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
Over the printed grip (35.99–37.01 mm) and washer (0.9144–1.651 mm) the cut
ranges 45.6674–47.7288 mm, leaving at least 3.0712 mm of the 50.8 mm stock to
remove with its factory end; inspect the cut bolt's threaded tail and thread
gauge acceptance rather than treating these as new SKU dimensions or vendor
tolerances. Useful-tail coverage beyond maximum reach is
9.558867 − 9.0678 = 0.491067 mm.
See [live vendor evidence](../references/mcmaster/README.md).

This route is shop documentation, not a certified generated traveler.
Strict traveler generation is **unenrolled and not exercised**; enrollment
awaits fresh farm feature/STEP geometry and a successful prechips exit-0
run. No COM, farm, or generated-traveler certification is claimed here.

### Cylinder gear + cam, connecting rod (T1 — the 20 function generators)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`dt-cylinder-gear`** ×20 | round brass bar ~65; toothed disc OD64.44×3 + integral eccentric cam OD30.6×4.0565 (offset +Y 8.64); total H 7.0565 | Ø9.575 through bore on the Ø9.525 (3/8") arbor — **rides free on arbor, no keyway**; 120T involute 48DP PA20 (2.5D through-cut, patterned → **DXF/2.5D-machinable**); cam = plain eccentric circle (2.5D); **0.4 mm alignment notch** = the +Y co-phased timing datum | cam thin-side wall **1.90 mm**; notch kerf **0.4 mm** (slitting-saw, fragile crests); 3 mm slender disc; **double-sided** (teeth+notch front / cam boss far face) | **≥2** (flip for cam boss) | **CNC-REPEAT** — lathe bore+OD, teeth with a stock 48DP PA20 #2 cutter indexed (see [Cutter plan](#cutter-plan); wire-EDM = outsource), cam offset, notch by slitting saw; **hold the +Y phasing identical on all 20** |
| **`ch-connecting-rod`** ×20 | AISI 1018 plate, 1/4" (6.35) faced to 6.075; 2D outline ~188×40.8; ring and shank 2.175, both faces at 1.950 / 4.125 ±0.05 from the fork's datum face, fork 6.075 REF, all on one mid-plane; black finish | Ø30.8 strap bore (rides Ø30.6 cam, 0.1/side); fork 10 wide, full R5 crown on the pin, 18 long from the crown; tine 1.700 ±0.05 from the datum face, slot 2.675 ±0.05, 14.75 deep from the crown (#982); Ø1.968 +0.010/0 pin hole reamed through both tines (pin MHA-CH-10 pressed in at assembly, ends dressed flush; user ruling 2026-10-09, PR #1292) | tines **1.700** (1.65 MIN) beside a 2.675 slot — slitting saw or a 3/32 end mill in two passes, hold the 3-place band; both faces stepped (thin 2.175 shank ~150 long faced from 6.35 — chatter/curl); the ream must hold +0.010/0 for the press | **2** (flip to face the second side; slot, drill and ream in the second) | **DXF/2.5D profile** the outline, face both sides to the two levels, slit the fork, drill + ream |

### Cone gears + shaft (T1 — the 48DP PA20 train, tip gears fragile)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`dt-cone-gear`** ×20 (T006→T120) | round brass bar, extruded disc, face **6.8756 ±0.025** each, OD printed per gear at the AGMA (N + 2)/DP blank, +0/−0.05, capped by the cutter's form (`dt_cone_gear_spec.py`; T006 Ø4.31 +0/−0.02); tip gears T006–T024 harder yellow metal | D-bore matching the land's single +X flat, clocked to the phase-0 tooth: round seat Ø by config (T006/T012 0.79375, T018 3.175, T024 6.350, T030+ 9.525); bore AF +0.010/+0.020 over shaft nominal AF (0.01–0.03 clearance), diametral slip clearance 0.025–0.105; 6–120 involute teeth PA20, tooth thickness ±0.075 (T006 +0/−0.04), 2.5D through-cut | **T006 web 0.64 mm minimum** on the 1/32 in bore (the flat cuts inward from that circle; see [`gear-standard.md`](./gear-standard.md#what-it-costs)); whole gear tiny → difficult workholding, especially forming and gauging the D without damaging the teeth | ≥2 (turn/bore, indexed teeth, plus D-bore finishing) | stock 48DP PA20 range cutter per gear, **indexed**, set up within 0.05 TIR of the finished bore (see [Cutter plan](#cutter-plan)); T006 needs its named custom ground tool, DT6-FORM1; form the bore flat to the AF gauge (filing or broaching is a hobby-shop possibility, not a selected route; EDM or a D-shaped punch needs process/fixture approval). Measure all 20 touching faces as a stack: **137.512 ±0.20** |
| **`dt-cone-gear-shaft`** ×1 | stepped steel bar; integral Ø12.2308 post journal, thrust collar then Ø9.525→6.35→3.175→0.79375 gear lands | turned steps plus **one milled +X D-flat on each gear land**, nominal AF **8.763/5.842/2.921/0.420** respectively, each +0/−0.010; the Ø0.79375 flat continues through the tip end and the MHA-DT-VN-54 stack collar's set screw locks on it. Finish the post journal for 0.05 diametral clearance | slender terminal land needs tailstock support; flat machining adds an indexed milling setup and inspection against the mating D-bores | lathe + at least 1 indexed milling setup | manual lathe **+ steady/follower**, then mill/gauge the co-clocked flats; do not leave a round section under the MHA-DT-VN-54 collar |

### Pivots, bushings, shafts (T1 — the 19-channel stacks)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`ch-pivot-shaft`** ×1 | plain steel bar Ø6.35×203.2 | solid, no bore/step/thread; 2 end faces | **L/D 32:1** → whip; steady-rest / between-centers | 1 | manual lathe + steady |
| **`ch-fulcrum-shaft`** ×1 | plain steel bar Ø6.35×166.4 | domed R3.175 ends; two 0.3-deep set-screw flats on one side at ±75.0 | **L/D 26:1** → whip; **same stock as pivot-shaft — don't mix** | 2 (turn domes; mill both flats in one setup) | manual lathe + steady, mill |
| **`pivot-bushing`** ×19 | brass, OD Ø10.0×**4.5565** | Ø6.5 through bore (rides Ø6.35, **0.15 mm** clr); stubby L/D 0.46 | **length 4.5565 sets the 7.0565 channel pitch** → parting-length repeatability across all 19 is *the* critical dim | 1 (turn + bore + part) | **CNC-REPEAT** / collet stop for length consistency |
| **`lever-bushing`** ×19 | brass, OD Ø12.0×**4.0565** | Ø6.5 through bore (rides Ø6.35, 0.15 mm clr); twin of pivot-bushing | same drill/ream as pivot-bushing; differs only OD (12 vs 10) + length (4.0565 vs 4.5565) — **don't mix the two sets** | 1 | **CNC-REPEAT** / collet stop |

### Rocker arms + support (T1 — flat profile + cast bracket)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`ch-rocker-arm`** ×20 | flat steel plate **2.5 mm** thick, ~270×21 | **top edge = R800 concave arc** (the amplitude-bar rides ON it) — it is the **2D OUTLINE of the plate, NOT a concave pocket/face**; bottom edge R816 concentric; Ø6.5 pivot bore + Ø2.0 rod-pin bore, both through the plate | none severe — pivot bore is **inherently square** (drilled through flat stock, one setup); no slot, no internal corner | **1** (all features one plane) | **CNC 2.5D profile** (×20 identical) or bandsaw+template; the R800 is profiled, not form-cut |
| **`fr-rocker-arm-support`** | modeled Gray Cast Iron; drawing permits gray iron casting or low-carbon steel stock; trapezoidal wedge, 6.35 mm shell/web | opposed 165.1 mm pockets with **R6.35** internal corners; through cavity with **R12.7** corners; **4× 5/16 through clearance drills** in the 6.35 mm foot for top-down 1/4-20 hex-head screws; RimChamfer 1.27 | 6.35 mm web/shell; from solid stock, each pocket reaches about 28.6 mm at the wide foot. R6.35 is ordinary contour geometry on a PM-25MV and does not need square-corner EDM; a 1/8″ end mill can finish the radius, but its long reach in 1018 favors roughing with a stiffer cutter first | casting route: foot holes/rim; solid-stock route: **2 opposed pocket setups** + foot drilling | cast body, or rough both pockets from 1018 with a larger cutter and finish the R6.35 corners with a 1/8″ end mill; drill the clearance pattern from the seat face |

---

## Recommended actions (gaps this pass surfaced)

1. **Retain the executable native wall guard for the smallest cone gear.** After a forced T006
   rebuild, `build_dt_cone_gear.py` measures the native floor edges directly and compares both radial
   extrema with `dt_cone_gear_spec.floor_radius_min_mm` / `floor_radius_max_mm` within 0.002 mm.
   These are the nominal finite-arc envelope; the separate printed diameters from `floor_limits_mm`
   also enclose the manufacturing corners. The guard checks the native web at the maximum allowed
   bore against the retained web requirement; `test_dt_cone_gear_drawing` pins the T006 web exception
   (`WEB_EXCEPTIONS_MM`). Keep both when changing the tooth profile or bore bands.
2. **Qualify the selected `sm-summing-lever` solid-stock route and the unchanged
   knife roots/edge.** Option A removes the pad step and rib ledge, not the
   multi-setup workholding, cutter-access or hardened-insert debt. Native/CAM
   clearance, mass/CG, swept fit and measured installed balance remain open.
3. ~~**Model the `sm-knife-mount` mounting holes**~~ — RESOLVED (top-frame rederive, 2026-08-02; #10-24 hex-head cutover, 2026-10-13): the
   block is clamped to the top-frame casting's integral crossbar by the cut-to-length 18-8 hex-head Bolt
   and new #10 SAE washer on the whole faced top, into a #10-24 bottoming tap and keyed by two dowels pressed into the crossbar's blind underside reams and slipped into the block's round hole and slot (owner ruling 2026-10-24, T+H3); the current route is documented above. Its revised native wizard and dimension import require the scoped farm proof; offline tests alone are not native evidence.
4. **Reconcile the `ch-rocker-arm` R800 vs book 812.8 mm** (already a §4 Finding) before it becomes a
   drawing callout — but note the good news from this pass: it's a *profile* dimension, cheap to change.
5. **Consider enlarging the tip cone gears** (T006–T012) — the model already flags them marginal and a
   period build used harder metal. **DP caveat:** enlarging OD at a *fixed tooth count* changes the
   DP/module and **breaks the shared 48DP mesh** — tooth *counts* preserve the ratio, but DP/pitch
   diameter preserves the *mesh* (`dt_cone_gear_spec.py` and `dt_cylinder_gear_spec.py` both read `diametral_pitch` from `gear_train.yaml`; §4
   treats the shared DP/PA as the meshing-domain constraint). So a real enlargement must either re-cut
   the mating **cylinder gear + centre distance** to the same new DP for that pair, or keep DP and accept
   the small size. Not the free change it first looks — the cheaper de-risk is the **harder tip metal**
   the original used.
6. **Reconcile the `sm-knife-mount` material** — `build_sm_knife_mount.py` (`Gray Cast Iron`) contradicts
   `parts/sm-knife-mount.yaml` + §6 (`Brass`); the registry drives the BOM/drawing, so fix the script
   constant to Brass (or decide the part is cast) before a drawing ships a wrong material.

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
- **Fusion 360 CAM verify/simulate — the one worth banking on, with a known edge.** Because it
  simulates the *actual tool against the actual solid*, it **surfaces the class DFMPro missed**: an
  internal corner smaller than the smallest endmill shows up as **un-cut stock** (you can't program a
  sharp internal corner), and tool-reach / gouge / holder-collision are caught. Banking on Fusion for
  the **majority of tool-access & gouge issues is reasonable** — it's a real simulation, not a
  rule-of-thumb checker.
  - **But its blind spot is exactly where the worst risk lives.** Fusion treats geometry as **rigid**
  and stock as **held**, so it will *not* warn that the **T006 web (0.64 mm minimum)** breaks in
  workholding, the **Ø0.79375 mm slender shaft tip** whips, the **1.90 mm cam wall** is fragile, or that
  a ~4 mm gear can't be gripped. Thin-wall / fragile-feature / fixturing failures are not modelled
  by CAM sim. **A clean Fusion sim is not a substitute for a first cut on the fragile parts.**

**Order that actually de-risks the build:**
1. **Fusion CAM verify** — cheap; catches the tool-access/gouge/reach majority, incl. the sharp corners
   (as uncut stock).
2. **First-article cut** — cut **one** of each fragile/hard part (a T006 gear, a cam-gear, a bushing,
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
| `dt-cone-gear` T006 | 6 | special, see below | 6 turns + 10 holes on 15 |
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
| `dt-cone-gear` T096 | 96 | #2 | 5/12 turn: no standard circle |
| `dt-cone-gear` T102 | 102 | #2 | 20/51 turn: no standard circle |
| `dt-cone-gear` T108 | 108 | #2 | 10 on 27 |
| `dt-cone-gear` T114 | 114 | #2 | 20/57 turn: no standard circle |
| `dt-cone-gear` T120 | 120 | #2 | 5 on 15 |
| `dt-cylinder-gear` ×20 | 120 | #2 | 5 on 15 |
| `dt-alignment-pinion` | 32 | #4 | 1 turn + 4 on 16 |

T096, T102 and T114 need differential indexing, which takes a universal head with change
gears, or a plate drilled with 12, 51 or 57 holes. Those tooth counts did not change with the
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
ground form tool whose full grind, including the relief that clears the drum tips, is
drawn on its own detail sheet in the MHA-DT-03 package. The root-to-bore web it leaves is
0.64 mm, over the 0.62 mm floor; see [`gear-standard.md`](./gear-standard.md#what-it-costs).

For background on shop-made form cutters, Law's *Gears and Gear Cutting*
(`references/gears-and-gear-cutting/`, ch. 12) forms the cutter profile with a button tool: two
hardened round buttons set at a chosen centre distance. The Eureka device named there is only an
attachment for relieving the cutter. Law's button table covers cutters from a 17-tooth pinion up,
so it does not give a six-tooth form.

### Crossed crank pair, normal 24DP PA20

| part | teeth | form | cutter | index per tooth (40:1) |
|---|--:|---|:--:|---|
| `dt-crank-pinion` | 16 | straight spur | #7 | 2 turns + 10 on 20 |
| `dt-crank-drive-gear` | 64 | right-hand helix 13.0011°, lead 945.862 mm | #2 (virtual 69 teeth) | 10 on 16 |

The 64T is cut with the cutter chosen for its virtual tooth count, N / cos³ of the helix angle,
which lands in the #2 range ([John F's workshop, helical gears](https://johnfsworkshop.org/home/making-other/gears-links/helical-gears-links/making-helical-gears-on-a-vertical-milling-machine/)).
The table is swivelled to the helix angle and the head is geared to the table leadscrew so the
blank turns once per 945.862 mm of travel. That needs a spiral-capable universal dividing head;
indexing alone, even with a DRO, cannot generate the lead. The installed Precision Matthews BS-0
is sold as semi-universal
([BS-0](https://www.precisionmatthews.com/products/dividinghead-bs-0)); the BS-2 is sold as able to
cut spirals ([BS-2](https://www.precisionmatthews.com/products/dividinghead-bs-2)). Change gears
for the lead depend on the head and the table screw: `TODO(cut it first)`.

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
MHA-PD-VN-64 dowels (McMaster 93600A189, 2 × 6 mm); the screws only clamp.
