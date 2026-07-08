---
name: summing-lever-true-geometry
description: The real summing lever has NO bore; hex protrusions at the pivot form the knife edge; revert to the .cs shape
metadata: 
  node_type: memory
  type: project
  originSessionId: 1f309627-0ce3-4562-b4bc-935d4f44247a
---

The M6.4 summing-lever model (knife-edge TUBE + Ø14 bore on an external diamond
knife-bar) is WRONG per the user (authoritative on the physical machine). The real
summing lever:

* has **NO bore** — the pivot is solid;
* has **two hexagonal protrusions at the pivot** that form the **knife edge** on which
  the lever hangs and rocks as a **first-class lever in suspension** (channel springs on
  one arm, counter-spring on the other);
* otherwise matches the legacy `cad/SummingLever.cs` shape (solid pivot cylinder + edge
  ribs + tapering summation tongue + summation anchor eye + middle rib).

Decision (2026-06-16): revert `build_summing_lever.py` to the `.cs` shape (ported to
Python), ADD the hex knife-edge protrusions, MOVE the spring holes to the existing
channel registration (move holes, not springs), and fully re-integrate
`build_output_assembly.py`. The `.cs` summation-anchor eye (local +X tip ≈ machine 91)
sits right where the counter-spring boss-hook attaches (machine 90.5), so the
counter-spring hangs from the anchor — no orphan −X boss.

Evidence: book `references/.../ch18_images/page001_img01.png` + `page001_img03.jpeg`
(green cast lever hung from the crossbar stud, faceted pivot block) and photogrammetry
`photogrammetry/raw/20250828_194637152` / `_194651412` (hex/faceted fulcrum block on top
of the arm, below the crossbar). Hex exact size/clocking is LOW confidence (museum-glass
photos) — tune against the knife-mount fit + ch30 parity. Plan:
`~/.claude/plans/serialized-wobbling-lerdorf.md`. See [[harmonic-analyzer-project]],
dof-refactor (dropped memory), [[parametric-springs]].

> **NOTE (later drift):** `build_output_assembly.py` referenced throughout was SPLIT
> 2026-06-20 into 4 flat subassembly builders — the summing-lever now lives in
> `build_summing_assembly.py`. The ch30 parity scores below (mean ≈ 76.7) are the
> 2026-06-17 snapshot; the gallery has been re-tuned since (current mean ≈ 69). The
> geometry constants and fix narratives remain accurate.

**Knife mount = BORED bearing support (2026-06-17, user-confirmed):** the hex trunnion
(vertex-up, on the lever) rides inside an OVERSIZED circular bore on the fixed support so
only the hex's TOP vertex line nears the bore's upper inner wall → true knife-edge line
contact. `build_knife_mount.py` rewritten = Gray-Cast-Iron block + Ø25.4 bore (R_BORE 12.7
≫ ~Ø10.3 hex); placed ×2 at z ±87.06 (HEX_Z_MID). Lever mates **Axis3** (knife ridge, local
y +HEX_H/2=+5.134) to the mount Axis1. This killed the old 4549 mm³ knife-bar↔cylinder clash.

**Plate vertical registration = OPTION A, DONE+VALIDATED (2026-06-17):** the .cs plate is a
COPLANAR casting (mid-plane ON the pivot at knife y=990 → spans 987.46..992.54, top 992.54
NOT the old M6.4 998). User chose to DROP everything that hung off the old 998 to meet it
(most faithful to .cs), not lift the plate. Changes (commit da97b0d): magnifying-bracket
`FLANGE_Y (3.9,7.9)→(-1.54,2.46)` + `FLANGE_SCREW_POS_Y 988.9→983.46` (killed the 18.02 mm³
flange↔plate overlap); channel `PLATE_TOP_Y 998→992.54` + spring `PLATE_EYE_Y 989.5→984.04`
(both ends drop 5.46 so `_assert_plate_threading` margins preserved ~0.13/0.12; installed
spring body elongates 63.05→68.51 vs the FIXED channel-lever tab at 1063.65). knife-mount got
explicit `MIRROR_PLANE ("x",0.0)`. Rebuilt bracket→spring→channel.SLDASM→output.SLDASM all
exit 0, output 124 comps interference-NONE. Decision-driver: the 20 channel springs register
to the plate too (thread clearance holes so they never trip interference) — option A's real
cost was re-registering them, ruled out the "just drop the bracket" reading. Hex size/clocking
still untuned.

**Raise-rod refinement, DONE+VALIDATED (2026-06-17, commit 09adcab):** after option A the
magnifying-lever rod still hung 5mm below the plate (side-view gap). User chose "raise rod to
plate level (y990)". `build_output_assembly` LEVER_ROD_Y 985→990 (VROD_TOP_Y now =LEVER_ROD_Y+5,
clamp follows); `build_magnifying_bracket` flange reshaped to butt the plate FRONT face. KEY
GEOMETRY (decoded from a 13.6 mm³ clash = 0.45 x-clip × 5.95 z-penetration × 5.08 plate-height):
the coefficients plate is the Top-rect **local x[0,44.45], z[−76.2,+76.2] centred on the pivot**
→ machine **plate east edge ≈ x+29.45, FRONT (−Z) face at z−76.2** (NOT −70 — the bracket
docstring's "−70" was a mis-read; −70 is just where the arm reaches BESIDE the plate). Bracket
collar at machine x+40 is EAST of the plate, so the arm (x35–45) never interferes; only the
flange (west edge x+29) clipped the plate east edge inside its z-span. Fix = FLANGE_Z 6..14.75→
**4..8.55** (north face z−76.45, 0.25 south of −76.2) so the flange sits fully in front of the
plate. Dropped the 2 cosmetic flange screws (no room for heads in front of the collar; they
bored into it/each other) AND the bracket's 2 screw-HOLES (a thin offset flange straddles no
standard plane at the |x|>5 bore line → all 3 FeatureCut overloads fail "Parameter not optional"
on auto-select; even a mid-flange offset reference plane failed — deferred). output.SLDASM now
**122 comps, interference NONE**, counter-spring hang gap 0.05.

**Widen-flange follow-up (commit f428c03):** even after butting the front face the bracket
still read as "floating in air / not making contact" (top view) — at FLANGE_X −11 the flange
stopped at machine x+29, touching the plate (east edge +29.45) only over a 0.45mm corner sliver
while its body sat EAST of the plate in air. Fix = FLANGE_X (−11,5)→**(−20,5)** (machine x+20..
+45) so the flange reaches WEST onto the plate front face and butts it over 9.45mm (x+20..+29.45);
the rest wraps the collar. West tab clears the channel springs (z≥−67.1; flange at z≤−76.45).
The 0.25 front-face gap is the standard touching-faces margin (0-gap risks a false sliver) and is
sub-pixel at junction zoom. Still 122 comps interference-NONE. NEXT (paused for sign-off): Phase 4
verify suites + Phase 5 ch30 parity.

**Phase 4 static — middle-rib vs channel-spring-6 clash, FIXED+VALIDATED (2026-06-17, commit
after f428c03):** `--suite static` surfaced a latent 4.21 mm^3 `summing-lever-1 <->
channel-spring-installed-6` clash (PRE-EXISTING since the .cs port; sub-assembly checks miss
cross-assembly clashes — only the TOP harmonic-analyzer level catches output<->channel). ROOT
CAUSE: `channel-spring-installed-6` = base-instance #6 = channel **j=10 (z+3.47)**; its plate
clearance hole sits at local **z+1.515** (`HOLE_X=37.10`, `HOLE_Z_OFFSET=-1.95`), INSIDE the
middle rib's z-span (+-RIB_T/2 = +-2.54). The middle rib (feature 7) extrudes AFTER the holes
(feature 1) so it RE-FILLED that one hole → its spring had no clear bore. Only j=10 fails because
it's the sole hole whose z lands in the rib span (j=9 at z-5.54 is outside) AND it's a vertical
BASE spring (the tilted stretch springs swing clear). FIX = trim the rib's +X vertex from the
plate edge (local x44.45=PLATE_W) to **`MID_RIB_PLATE_REACH = HOLE_X - 4.1 = 33.0`** (inboard of
the hole column + ~3.25 coil radius + margin); rib still stiffens the inner lever, outer plate arm
is the spring-hole field. DIAGNOSIS METHOD that worked: (1) analytic no-SW map of all 20 channel
z-stations → base-instance#→channel j (base springs = a_j=0 vertical, reuse "channel-spring-
installed"); (2) cheap isolated mini-assembly (summing-lever + ONLY the j=10 base spring at its
exact placement) + interference + zoom render localized it in 13s. GOTCHA: re-running static after
ONLY rebuilding the PART (not the assembly) FALSE-FAILED — the part topology change orphaned mate
`Coincident1` (summing-lever/boss-hook went under-defined). The summing-lever mates ARE robust
(named Axis1/2/3 + Front-plane), so the cure was just to REBUILD the chain: build_summing_lever →
build_output_assembly → build_harmonic_analyzer_assembly → static. Final: **static 30/30, 0 failed**
(all interference-none + DOF-fully-defined). **Phase 4 COMPLETE**: config 14/14 + static 30/30 +
isolation 27/27 (all green).

**Phase 5 ch30 parity — DONE, PLAN COMPLETE (2026-06-17):** export_models (full STL re-export) →
render_offline → composite for all 8 ch30 views. Mean photo score **76.28 → 76.73 (flat)**; per-view
+-2 jitter is sub-pixel tessellation noise from the full mesh re-export, NOT the occluded rib trim
(p002 65.65 / p003 86.46 / p004 77.16 / p005 82.7 / p006 64.82 / p007 78.16 / p008 73.62 / p009 85.27).
No parity regression from the .cs summing-lever integration. parity_check.py = a one-off SW-vs-Blender
CAMERA-framing IoU check (globs comparisons/composite/.parity_sw/*.jpg, now EMPTY → no rows); it is
NOT the photo-match metric (that's scores.json). HEX TRUNNION TUNING (the plan's lone open item):
RETAINED as-is, NOT tuned — the ch30 8-views occlude the pivot/hex and the photogrammetry close-ups
(20250828_1946*) are museum-glass/reflective/low-res, so there's no reliable signal to re-dimension
it; blind tuning would risk regressing. Current hex (vertex-up 8.653 W x 10.268 H x 21.717 deep) is a
sound reading. All 5 phases done; commits: rib-trim fix + render/BOM artifacts + ch30 comparisons.

**Reversed linear-pattern of the spring holes — FIXED+VALIDATED (2026-06-19, commit 4e55028):** during
the PR #67 + #26/#27 integration build, the top harmonic-analyzer level threw TWO 3.99 mm³
`summing-lever-1 ↔ channel-spring-installed-stretch00-{2,3}` clashes (3-channel neutral config). ROOT
CAUSE: the 20 coefficient-plate spring holes were a single SEED cut at station j=0 then replicated by
`adapter.linear_pattern_feature` → `FeatureLinearPattern5`. That adapter picks the pattern DIRECTION by
auto-selecting an edge at `direction_point=[0,0,+76.2]` and marches with `FlipDir1=False` (the edge's
NATURAL parametric sense). That sense resolved to **−Z**, so the 19 patterned holes marched off the −Z
plate edge into air — only the seed (j=0) stayed cut. Every other spring eye threaded SOLID plate. The
j=0-clears / j≥1-clashes discrimination is the tell: seed cut present, pattern instances absent. (At
3-channel the springs sit on the first 3 stations, so j=1,2 clashed; the build's own gate had been
passing earlier only because the validated full build predates whatever nudged the auto-selected edge's
sense.) DIAGNOSIS METHOD that nailed it precisely: `IInterference.GetInterferenceBody().GetBodyBox()`
(mm) → each clash was a **1.0 mm (=WIRE_DIA) × 5.08 mm (=full PLATE_T) × 1.0 mm** sliver centered exactly
on `HOLE_Z[1]`=−61.99 / `HOLE_Z[2]`=−54.94 = a wire through an un-cut bore (component AABBs were too loose
to see it; the interference-body box is the right tool). FIX: drop the seed + edge-directed pattern;
cut a circle at EVERY `HOLE_Z[j]` station in one Top-plane sketch + a single `create_cut_extrude`
(`build_summing_lever.py` `_coefficients_plate`). Direction-free, deterministic, identical 20-hole
geometry. Full-assembly gate now "interference check: none found"; `diag_sl_clash.py` (extended with the
GetInterferenceBody box dump) confirms 0 interferences; top-view render shows all 20 holes cut with the
3 active springs threading cleanly. LESSON: never trust `FeatureLinearPattern5`'s auto-selected-edge
direction for a field that must land on exact stations — cut the stations explicitly. See
[[channel-amplitude-state]], [[parametric-springs]].

**Springs join the plate via a SEPARATE hook fastener, NOT a plate-threading eye — DONE+VALIDATED
(2026-06-25):** book ch.17 (page002_img04/img06) shows the channel spring bank landing on the coefficient
plate through a row of little open hooks, exactly the boss-hook / counter-spring idiom one size down —
the spring does NOT thread its own eye through the plate. NEW part **`spring-hook` (MHA-090, Plain
Carbon Steel, `build_spring_hook.py`)**: the proven line-arc-line open-J idiom (a 270° planar loop
self-intersects the swept wire and FAILS — use the shank+90°-elbow+arm chain, profile at a true path
ENDPOINT). It seats shank-UP in the plate's Ø4.5 bore (natural orientation) and presents its +X arm just
ABOVE the plate where the spring's bottom eye links on. Knobs: `ROD_DIA 1.4`, `SHANK_RISE 7.6`,
`ELBOW_R 1.5`, `ARM_RUN 2.5` → arm height SHANK_RISE+ELBOW_R = **9.1** above the shank base.

GEOMETRY FORK (user chose "move eye above plate (cascade)", the most faithful): shorten the spring so its
bottom eye sits ABOVE the plate (the spring no longer passes through it). Cascade — `build_channel_spring_installed.py`
`PLATE_EYE_Y 984.04→996.54`, `BOTTOM_LEAD 9.1→2.0` (normal hook lead, was plate-spanning), body
auto-drops to **62.61**; `build_summing_lever.py` `HOLE_DIA 4.5` (hook-shank clearance), `HOLE_X
37.10→39.85`, `HOLE_Z_OFFSET −1.95→+0.8` (coaxial with the spring axis in Z, shifted one arm-offset −X
to seat the shank); `verify.py` channel count band `7*→8*` (164, was 144). 20 hook `grounded_specs` added
in `build_channel_assembly.py` at `[hole_x_0 − HOOK_ARM_OFFSET_X, PLATE_EYE_Y − HOOK_ARM_HEIGHT, z_mid]`
IDENTITY (grounded specs carry FINAL world transforms — NO `MIRROR_PLANE` entry needed, like the bushings).

FRAME TRAP (cost a wrong-side rebuild): the top assembly inserts every subassembly at [0,0,0] IDENTITY, so
the summing-lever placed at world (15.0, 990.0) maps its **local +X to world −X**: `world_x = 15.0 −
local_x` (boss-hook at world 90.5 = 15 − (−76.20) confirms it). So the +2.75 local hole shift lands at
world −2.75. HOLE_Z is already world Z (no flip). Keep the spring VERTICAL at `hole_x_0` (don't lean it) so
verify:math `spring:neutral-body-canonical` stays green — move the hole+hook −2.75 in world X instead.

EYE-RING-VS-PLATE TRAP (cost one full top-level rebuild): `_assert_plate_threading` → renamed
`_assert_hook_fastener`. First pass set PLATE_EYE_Y so the eye CENTRE cleared the plate (4.0 above) but the
eye is a **torus, ring plane vertical (axis +X), so its LOWEST point hangs a full `SPRING_LOOP_R + wire_r`
= 3.25 below the centre** → ring bottom dipped 0.85 below the plate top → 20× spring↔plate clashes at 2.04
mm³ each at the TOP level only (channel-only interference was clean — the plate lives in summing). Fix =
raise PLATE_EYE_Y to 996.54 (ring bottom 993.29, clears plate top 992.54 by 0.75) + lengthen the hook
(SHANK_RISE→7.6) to keep the arm at the eye and the shank seated. Added a **ring-bottom clearance check**
(`ring_above_plate ≥ 0.3`) to the gate so the dip is caught OFFLINE next time, not at a ~500 s COM rebuild.
Final: spring-hook 19.2 mm³, channel 164 comps 0-DOF interference-NONE, summing/top interference-NONE,
math 9/9 + config 13/13 (tolerance audit 74 parts, spring-hook picked up). See [[parametric-springs]].

**TWO bugs interference=0 did NOT catch — found by RENDERING (2026-06-25, user-flagged):** the gates
were all green but the user's screenshots showed (a) the spring eye not engaging the hook, (b) the
plate holes far bigger than the shanks. interference=0 only proves nothing OVERLAPS, never that two
parts ENGAGE. Lesson: for an engagement/fit change, render a tight close-up and eyeball it — don't trust
the interference gate alone. The `diag_hook_engage.py` diagnostic (inserts channel+summing, isolates
plate+springs+hooks, renders right/front/iso) is the tool; the RIGHT view (along world X) shows each eye
as a ring with the hook arm end-on as a stub — stub inside ring ⇒ threaded.
1. **MIRROR FLIP (the real bug).** `place_components_batch` routes EVERY grounded spec through
   `mirror_placement` (`_assembly.py` ~728, `mirror=True` default), which uses `MIRROR_PLANE.get(part,
   "x")` — **default "x"**. Grounded specs are authored in a PRE-mirror frame; achiral parts (the
   z-symmetric springs carry `"z"`; the x-symmetric bushings tolerate the default) place fine, but the
   CHIRAL spring-hook with no entry got X-mirrored → arm flipped to +X pointing AWAY from the eye, hook
   on the wrong side (the shank still landed in a hole, so no interference). FIX = add
   `MIRROR_PLANE["spring-hook"] = ("z", 0.0)` in `_transforms.py` — identical to `channel-spring-installed`
   and `boss-hook` (the analogous chiral planar hooks). The hook is a planar wire in its local X-Y plane
   (achiral about local z=0), so the z-mirror is a proper rotation that keeps its shape and makes it
   mirror IDENTICALLY to the spring it engages → arm mid lands exactly on the eye centre, arm ∥ eye axis.
   Verify offline by calling `mirror_placement` on both specs and comparing final pos/rows (instant, no COM).
2. **Hole too big.** `HOLE_DIA` was still O4.5 (sized when the spring eye threaded the plate). Now only
   the O1.4 shank seats → shrank to **O2.0** (0.3 radial clearance) in `build_summing_lever.HOLE_DIA` +
   `build_channel_assembly.PLATE_HOLE_DIA`. summing-lever volume rose 134359→135655 (less material removed).
Re-validated: channel/summing/top interference-NONE, render confirms each eye threads its hook arm and the
shank fills the snug bore. LESSON for chiral grounded parts: ALWAYS give them a MIRROR_PLANE entry.

> **Superseded 2026-07-08 (#151):** the M6.8 mirror layer (`mirror_placement`,
> `MIRROR_PLANE`, the batch-spec default-mirror trap described above) is RETIRED.
> Every placement — including batch grounded specs — now inserts its exact
> machine transform verbatim. See [[mirror-retirement-sweep]].
