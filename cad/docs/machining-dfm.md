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

- **Casting-vs-bar substitution (2 T1 parts are castings in the registry):** `sm-summing-lever` and
  `fr-rocker-arm-support` carry `material: Gray Cast Iron` in `cad/config/parts/*.yaml`
  (`ch-connecting-rod` is now 1018 plate, Main ruling 2026-10). The support is a **benign**
  substitution — it cuts fine from bar. The **lever is
  not** — its ribbed/leaf organic form is casting-native and hogging it from solid means 4–5 setups
  around cantilevered plates. Decide **cast, fabricate (weld/silver-solder up from simple stock), or
  accept the multi-setup hog** before you start; the support is just a stock choice, the lever is a
  real decision.
  - **`sm-knife-mount` is a material *conflict*, not a settled casting:** its registry
    (`parts/sm-knife-mount.yaml`) and assessment §6 say **Brass**, but `build_sm_knife_mount.py` hardcodes
    `MATERIAL = "Gray Cast Iron"`. The registry value is what stamps the BOM/drawing custom property, so
    the intended stock is a **brass bar block** (trivial) — the script constant looks stale. Reconcile
    before it reaches a drawing (gap below).

- `fr-rocker-arm-support` carries four **5/16 through clearance drills**. Four
  McMaster 92240A540 1/4-20 UNC-2A × 3/4 in hex-head screws install from the
  top into blind UNC-2B taps in `fr-harmonic-base`: the exact vendor under-head
  washer transition seats on the support, leaving 12.422 mm installed
  engagement (1.956D). The seat is sized at its printed .XX worst case:
  13.20 mm full thread (0.25 mm tip reserve at the low limit) and 20.60 mm
  cylindrical tap-drill depth (five 1.27 mm pitches past the thread).
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
  in one setup without repeating the numeric offsets, and states that D1
  table X/Y are reference. The generated native hole-table coordinates remain
  unchanged; the D1 row carries the same `SEE NOTE 1` flag in a custom NOTE
  column (#1744), because generated hole-table cells are not editable.

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

MHA-SM-03's two MHA-MG-01 bracket receivers use a **6.50 ±0.51 mm**
cylindrical tap-drill depth, explicitly symmetric in the native dimension.
The native hole callout prints **6.50** at two places, inheriting the same
ordinary title-block **.XX ±0.51 mm** band without restating it; this is not an
accepted tolerance exception. Only the **−Z receiver rib** grows inward by **0.90 mm**
to **8.20 mm**: its entry remains **−76.20 mm**, its inner boundary is
**−68.00 mm**, and the opposite end rib remains **5.08 mm**. The axes and
13.7 mm pitch, MHA-MG-VN-53 screws, and 3.175 mm flange are unchanged.
Native usable full thread remains **4.95 ±0.05 mm**, printed **4.95 MIN**.
At the printed limits the full-thread containment margin is **2.69 mm**,
bottoming-tap lead exceeds two pitches by **0.082857 mm**, and the entire
118° point plus conservative 0.3° wander stays inside the shortest rib by
**0.076133 mm**. This last value is point containment, not a bottom-wall
thickness or a reduced rule-17 wall floor.

A bounded depth remains necessary: an unbounded MIN drill could enter the
**5.08 mm plate** beyond the rib, where the receiver axes are inboard of the
spring-anchor pad and the plate alone cannot meet the unchanged **1.5 mm**
wall floor. The ordinary ±0.51 band bounds that reach without a special
tight drill band. `magnifying_bracket_joint_layout` owns the physical stack
and point/wander proof; section H-H shows the rib-to-plate transition.

View F retains the top-referenced **2.54 ±0.05 mm** receiver-row location
and the centreline through both taps and the hex centre. The duplicate
parenthesized 2.54 reference is omitted; it adds no independent requirement.

Section C-C retains the model-owned **5.08 mm** plate-thickness dimension
under the title-block two-place band. Both visible extension lines begin
1 mm outside the partial section's inboard cut edge, rather than continuing
from the outboard extrusion reference across the integral spring pad.
Only witness routing changes; the measurement, band and plate/pad geometry
are unchanged.

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`sm-summing-lever`** | modeled **Gray Cast Iron casting**; organic first-class lever ~120×28×196 | solid pivot cylinder Ø25.4×152.4 (**no bore**); 2× hex knife trunnions (edges = top-vertex ridges) protruding 21.717 each end; 20× #6-32 tapped anchor seats through the 5.08 plate @ 7.0565 pitch (web ~5.06, Ø2.705 tap drill); one #10-24 tap through the Ø19.05×19.05 summation-anchor boss — both purchased spring anchors thread straight in, no nuts | knife-edge ridge **delicate** (the precision line); trunnion slender cantilever → **chatter**; organic 3-pt-arc leaf/rib profiles hard to mill; turning Ø25.4 with cantilevered plates; 20 small through-taps in a 5.08 web → **tap breakage**, use a tapping head | **4–5 from bar** (2 sketch planes + turn) | **CAST or fabricate**, don't hog; knife edge → hardened insert (§6) |
| **`sm-knife-mount`** | rectangular block 25.4 ±0.8 wide ×29.6×14.0 (bar/plate); **2 identical** | unchanged Ø12.00 +0.03/0 reamed through bore and pose, centre 20.616 BASIC below the top face (`BORE_CY` −5.75 from the knife-edge origin, block top +14.866, clamped to the casting underside); #10-24 UNC-2B bottoming tap on the bore axis: #25 Ø3.7973 under the title-block DRILLED HOLES +0.10/0 row, cylindrical drill depth 11.24 ±0.05, full thread 9.65 ±0.13; fully charged drill-point crown web 2.0077656525, no break-in (conservative proof envelope Ø3.927, above accepted MAX Ø3.8973; point MIN 117°); 2× Ø3.175 reamed dowel press holes ×9.5 at ±7.632 from the tap axis (span 15.264 BASIC, pair ⌖Ø0.13 to top seat datum A, datum pattern B; row 7.0 from front face; tap ⌖Ø0.15 to A and B); bore floor and pose unchanged | hold the explicit tap/drill depth bands and accepted pilot diameter/point-angle bounds to preserve ≥2.0 crown web; all joint webs ≥2.0 at printed worst cases | 1–2 (square block, bore one axis) | **CNC-REPEAT** (×2) or manual. Modified #10-24 hex-head Bolt MHA-SM-VN-52 (92314A253, cut under head at MHA-SM-00 step 4 to its hole's measured crossbar-underside-to-washer-top stack plus 8.92 ±0.15; 46.70 nominal) and new 18-8 SAE washer MHA-SM-VN-54 (96659A104) clamp the block to the top-frame's integral crossbar through Ø6.045 #10 loose clearance. Crossbar width 25.0 ±0.8, symmetric about X=−15; washer seat on the whole faced top (no SPOTFACE), 36.50 (title-block ±0.51) above faced underside. Nominal reach 8.9173, range 8.77–9.07; full-form engagement MIN 7.711667 ≥7.239, tip air MIN 0.45. Retain removable medium-strength threadlocker. Unchanged MHA-SM-VN-53 dowels (98381A473, 1/8 ×3/4) enter Ø3.24 ±0.03 ×12.0 blind round hole and 3.24 ±0.03 wide ×3.95 ±0.13 long ×12.0 blind slot, BASIC 15.264 from and ⌖0.05 to round hole. One native linear pattern position control ⌖0.10 to the bar's two-face width median datum D limits X shift to ±0.05, retaining the Z socket station and ≥2.0 webs. The former #6 socket-head counterbore route is obsolete |

The Ø6.045 hanger clearance hole carries a **native explicit +0.13/0
diameter band** (MIN 6.045, MAX 6.175), not the symmetric general ±0.13
band: undersize would fail bolt float. With this maximum hole diameter,
the worst-case screw-to-round-dowel web is 2.645457488 mm and
screw-to-slot web is 2.110457488 mm; outer round-dowel and slot webs
are respectively 2.585978744 and 2.050978744 mm.

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
**DETAIL J** (underside hub enlargement), **K-K** (set-screw boss section)
and **DETAIL L** (front-slot radius-centre enlargement).
Datums B/C/D and A-A/E-E/F-F/VIEW G are unchanged. Section stations, endpoints,
profiles, orientations and scales retain the historical B/E/D placement
calibration; old B/D glyph bounds do not establish H/K glyph clearance.

In F-F, the ordinary **2X 15.264 ±0.13 mm** slot station names its actual
mate, the **MHA-SM-02 knife-mount dowel pattern**. It is neither BASIC nor
REF. The controlling **3.950 ±0.13 mm overall slot length** retains its
MHA-SM-VN-53 dowel-travel purpose, and **3.240 ±0.030 mm width** is unchanged.
The native **(0.710) radius-centre spacing** is a noncontrolling reference
in **DETAIL L, 4:1**, cropped at model R3.0 from the Bottom locator's front
slot. Its two short model-Z axes pass through the source-derived stadium
centres, `SLOT_X ± SLOT_FLAT/2`, where
`SLOT_FLAT = HANGER_SLOT_LENGTH - HANGER_SLOT_WIDTH`. F-F retains only its
original three axes and controlling dimensions. The original overall/width
limits still alone permit **0.550–0.870 mm** centre spacing; the reference
adds no tolerance or acceptance criterion. L imports no model dimensions
and is created before the locator's authored annotations; native inspection
must still rule out copied controls. Its outside arrows, outboard text and
native linked caption, and the renamed letters/captions, need native
clearance inspection rather than extrapolated historical glyph measurements.
On UNDERSIDE, the Bottom view note moves 4 mm up to reserve L's caption
lane. F-F's own linked **SECTION F-F / SCALE 1:1** caption is centred under
its hatched profile at **(120, 31) mm**, not beneath L's circle. The native
36.50 grip text sits beside the section at **(72, 76) mm**. The overall-slot
text alone moves to **(177, 45) mm** to free that caption band; its selected
ends, dimension line, witnesses and controlling value/band do not move.
The six-sheet layout and L's crop, reference and caption stay unchanged.
Native ink must establish the caption/border and depth-arrow clearances and
the jog's own-arrow/witness routing; estimated gaps are not acceptance.

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
cuts each bolt to its own hole's measured stack plus **8.92 ±0.15 mm**
reach. The crossbar median datum D controls the hanger axes in X only:
their BASIC X location is on D.
The socket-to-D locator retains its ordinary location band; the front and
rear Z station dimensions likewise remain ordinary toleranced dimensions.

The mount's tap position is **Ø0.15 A B**, the loosest two-place zone that
the existing clearance can absorb. Its radius adds to both mismatch legs:
**hypot(0.31623, 0.26373) = 0.4117704771 mm**. Full-crossbar drill drift
charges the printed grip's thickest **37.01 mm** (36.50 + 0.51) and is
**0.1937856778 mm**; together they consume **0.6055561549 mm** of the
**0.6095 mm** radial float, leaving **0.0039438451 mm**. A Ø0.16 zone would
give **−0.0030989128 mm** spare; Ø0.25 gives **−0.0665210205 mm**. The
dowel pattern's datum-B position frame explicitly applies to **2X holes**.

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
leaves **2.0077656525 mm** over the worst-case bore crown; the spec mirror's
rounded top at 14.87 gives 2.0117656525 mm, not the built guarantee.
Full thread **9.65 ±0.13 mm** gives MIN 9.52 mm, leaving **0.45 mm** tip air
under the bolt's 9.07 mm longest fit-up reach. Two printed places do not
loosen it to the general .XX ±0.51 band: that would give a 10.16 mm deepest
thread, which the drill's 11.19 mm shallowest limit clears by only 1.03 mm,
under one 1.058333 mm pitch of runout. Drill-minus-full-thread runout is
1.59 mm nominal and 1.41 mm at the adverse depth limits.

**Modified hanger-bolt shop route (MHA-SM-VN-52, two).** Source McMaster
92314A253, 18-8 stainless plain external-hex #10-24 UNC-2A ×2 in stock;
retain the supplied head. Leave the supplied length uncut at the bench:
MHA-SM-00 step 4 seats washer 96659A104 on each crossbar hole's faced top,
measures crossbar underside to washer top, and cuts the bolt to that plus
**8.92 ±0.15 mm** under the head (46.70 mm nominal; the drawing prints it as
a reference). Restore the cut-end chamfer to **RADIAL 0.60 ±0.05 mm
×45 ±1°**, and deburr the thread start. Retain the conservative inspection
limit **MAX 1 P incomplete tip** (P = 1.058333 mm). The minimum radial
chamfer gives tip-flat Ø3.726, below the #25 drill Ø3.797; the maximum
axial chamfer extent is about 0.673 mm, below 1 P. Retain **MIN 10.62 mm
threaded tail from the cut end**, giving useful full form ≥9.561667 mm
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
ranges 45.6744–47.731 mm, leaving at least 3.069 mm of the 50.8 mm stock to
remove with its factory end; inspect the cut bolt's threaded tail and thread
gauge acceptance rather than treating these as new SKU dimensions or vendor
tolerances. Useful-tail coverage beyond maximum reach is
9.561667 − 9.07 = 0.491667 mm.
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
2. **Decide the `sm-summing-lever` fabrication method** (cast / fabricate / hog) and the **knife-edge
   insert** now — it drives whether this is a 5-setup nightmare or two simple operations, and it is the
   critical interface.
3. ~~**Model the `sm-knife-mount` mounting holes**~~ — RESOLVED (top-frame rederive, 2026-08-02; #10-24 hex-head cutover, 2026-10-13): the
   block is clamped to the top-frame casting's integral crossbar by the cut-to-length 18-8 hex-head Bolt
   and new #10 SAE washer on the whole faced top, into a #10-24 bottoming tap and keyed by two blind pressed dowels; the current route is documented above. Its revised native wizard and dimension import require the scoped farm proof; offline tests alone are not native evidence.
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
| `pd-rack-pinion` (reducer disc) | 120 | 48DP PA20 | #2, Precise/Penn 10-289-482 | 5 on 15 |
| `pd-transgear-knob-shaft` integral pinion | 12 | 48DP PA20 | #8, TTC 10-289-488 | 3 turns + 5 on 15 |
| `pd-transgear-feed-pinion` | 12 | 32DP PA20 | #8, Precise/Penn 10-289-328 | 3 turns + 5 on 15 |
| `pd-platen-rack` | rack, pitch 2.4936 mm | 32DP PA20 | none: bought as stock rack | none |

The reducer is 12:120 at 48DP, and the two 48DP cutters are the same #2 and #8 sizes the cones
use. Both 12T pinions carry the stock #8 form, and each hub is shaped so the cutter runs out clear.
The rack is bought, not cut: SDP/SI A1B12-Y324, a 48 in brass 32DP 20° rack, 3/16 × 3/16 in
(4.7625 mm) square ([product page](https://shop.sdp-si.com/a-1b12-y324.html),
[D820 catalogue](https://sdp-si.com/D820/PDFS/Gears.pdf)), cut to the printed 269.6 mm callout
(`cad/config/parts/pd-platen-rack.yaml`) and soldered to the existing backer. The 269.64 mm
CAD nominal is not the shop cut length; `pd_platen_rack_spec.DRAWING_PRECISION` prints it
to one decimal place under the ordinary .X band. Check it against the feed pinion before fitting; the pitch-index limit the model
allows for it is in `cad/config/tolerances/stock_form_quality.yaml` (`rack_pitch_index_deviation_mm`).

The chain is 68 links of ANSI #25, 12:24 from the crank sprocket to the knob sprocket. The
sprockets are made from McMaster 6793K blanks. The transgear arm and its plate are located by two
MHA-PD-VN-64 dowels (McMaster 93600A189, 2 × 6 mm); the screws only clamp.
