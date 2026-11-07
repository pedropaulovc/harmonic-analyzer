# Drive-train review: release v45

> **Snapshot review, not current status.** This reviews the published v45 bundle as a shop
> would receive it. Findings may already be fixed on `main`. Track the work on the
> [Harmonic Analyzer project](https://github.com/users/pedropaulovc/projects/1).
>
> **Revised 2026-10-27.** The cone-tip findings are corrected (VN-54, tip-gear material, and the
> rotating brass bushing and end screw from video 4), and §7 adds cone-tip options with a
> to-scale sketch.

## Scope and method

- **Release.** `v45` (tag commit `ad4559608`, built 2026-10-24). The review used
  `harmonic-analyzer-v45.zip`: `gltf/dt-drive-train.glb`, `pdf/dt-*.pdf` (51 files, about 90
  sheets), `READOUT.md`, `NOTICE.md` and `comparisons/`.
- **Original-machine evidence.** Hammack, Kranz and Carpenter (2014), chapters Crank, Cone
  Gear Set, Cylinder Gear Set, Pinion Gear and Translational Gearing (`references` submodule).
  Only facts are cited here. No image or text from the book is reproduced, because it is
  licensed for non-commercial use only. The engineerguy video stills in
  `references/engineerguy-youtube/stills/full/` are cited by path and not reproduced either.
  The main one is video 4, "The details of setting up the Harmonic Analyzer", at 6:36 and 6:39.
- **3D inspection.** meshprobe 1.4.0 on Blender 5.2.0 (software GL) against
  `dt-drive-train.glb`: component census and world bounds, top/side orthographic views,
  close-ups of the cone tip, the crank mesh and the alignment-pinion rig, and a side-by-side
  with the book's top-down photo (p.18). A surface-sampled trimesh pass measured where each
  cylinder gear actually touches its cone gear (§7). See
  [Reproducing the renders](#reproducing-the-renders).
- **Drawings.** Three parallel sheet reviews (crank group, cone group, cylinder and pinion
  group) plus a direct read of the 13-sheet assembly `MHA-DT-00`. The headline claims in the
  summary were re-checked by hand against `pdftotext -layout` output. The per-drawing items
  in §5 come from the sheet reviews and were not all re-checked.
- **Legend.** **[V]** = read on the sheet. **[I]** = inferred or calculated.
- **Codebase.** The source repository was deliberately not read. Everything here is judged
  from the released artefacts.

## Summary

1. **Fidelity: high at the level of layout and kinematics.** Tooth counts, the 4:1 crank
   reduction, the 13° oblique cone, the tip pivot and lock, the 120T cylinder gears with 3 mm
   notches, and the alignment-pinion rig all match the book. The departures are in small-part
   detail, and the cone tip is the clearest one: `MHA-DT-VN-54`, a Ø17.48 steel set-screw
   collar, has no counterpart on the original. The original has a small brass bushing that
   turns with the cone and runs against a long end screw in a split tip block. There is also one known accuracy defect: a 1.5° cam phase error that `READOUT.md`
   documents itself.
2. **Drawings: rich in shop knowledge, weak on drafting discipline.** The sheets have gear data
   blocks, vendor SKUs, a complete BOM and a feeler-gauge assembly procedure. But they cite
   ASME Y14.5-2018 with almost no datums, apply an inch-derived tolerance block to mm sheets,
   and mix design rationale into the requirements.
3. **Uncommon practice.** The assembly uses compass directions with the top view drawn "SOUTH
   UP AND EAST LEFT", three gear numbering schemes, assembly-time machining on part sheets, and
   a part held to 10 µm next to critical dimensions left at ±0.51.
4. **Novice barriers.** The worst are a Ø0.794 mm D-shaped wire journal under the two smallest
   gears, a 13° helical drive gear, 10 µm D-bores, and dividing-head counts that standard
   plates can't index.
5. **Release risks (non-technical, highest priority).** Every PDF in the bundle (208 of 208)
   prints "SOLIDWORKS Maker Product. For Personal Use Only." The MIT bundle also ships 18 crops
   from the non-commercial Hammack book, and the bundle's own notices contradict each other
   about them.

## 1. Fidelity to the original

### Matches

| Feature | Original (book) | v45 |
|---|---|---|
| Cone gear tooth counts | 6, 12, …, 120 (+6 each) | T006…T120, 48 DP, 20° PA **[V]** |
| Cone/cylinder engagement | "at an oblique angle"; wear on the small gears | cone axis skewed 13° to the cylinder axis (meshprobe top view; sheet arithmetic 6.8756·tan13° = 1.5875 radius step) **[V/I]** |
| Gear pitch | 7 mm (photo callout) | cone gear width 6.8756; cylinder stack pitch 7.0565 **[V]** |
| Cone length | ~150 mm (photo callout) | stack ≈145 mm **[I]** |
| Crank reduction | 4:1 (one crank turn = ¼ cone turn) | 16T pinion : 64T drive gear **[V]** |
| Cylinder gears | 20 equal gears; gear *n* turns *n*/80 per crank turn | 20 × 120T; consistent with *n*/80 **[V/I]** |
| Alignment notch | single notch ~3 mm deep | "3.0 FROM OD", 0.40 max wide **[V]** |
| Cone disengage | pivot at the tip, lock by a knob | tip pivot screw on the swing platform, lock knob at the big end **[V]** |
| Alignment pinion | long pinion across all 20 gears; T-handle on the front; small lever engages it | same layout; matches the book's p.67 photo (meshprobe + bundled overlay) **[V]** |
| Crank | tapered pin with ring, fiducial marks, pivoting black wood handle, brass ferrule, eyelet for a lost chain | 1:48 taper pin with ring, punch-mark fiducial, pivoting ebonized handle, brass ferrule, eye plus restored keeper chain **[V]** |
| Zeroing procedure | notches up = cosines, 90° = sines; pinion engaged, then parked | assembly sheet 12, check 5, follows the same procedure **[V]** |

### Departures

- **Known 1.5° cam phase error.** `READOUT.md` says the as-built drive train locks every cylinder
  gear half a tooth pitch (1.5°) off vertical with the cam lobe on a tooth crest. It quotes
  0.30 % MAE / 1.9 % max error on the reference inputs and a 0.76 % total budget against
  Michelson's 0.7. The fix (#749) is not in this release, and `dt-cylinder-gear` still calls
  "1.5° ±0.25° NOTCH CCW FROM CAM LOBE" **[V]**.
- **Smallest cone gears.** T006 and T012 are separate brass gears with a "Ø0.794 +0.055/+0.025
  THRU" D-bore, riding on a Ø0.794 wire section of `dt-cone-gear-shaft` (133.167 → 166.78,
  ≈33.6 mm long, L/D ≈ 42) **[V]**.
  - **Material.** The book says "the four smallest gears at the tip of the cone are slightly
    more yellow in appearance and seem to be made of a different, perhaps harder metal"
    (p.17). That covers T006–T024. The p.21 close-up shows verdigris on the 6-leaf pinion,
    which points to a copper alloy, not steel **[I from photo]**. In the video 4 side view
    (6:36) the four smallest gears are visibly lighter than the bronze-brown rest of the cone
    **[I from video]**.
  - **Construction.** The photos don't show whether the tip gears are integral with the shaft
    or separate gears.
  - **v45.** All four are drawn in plain "Brass".
- **No counterpart for `MHA-DT-VN-54`.**
  - **Model:** a Ø17.48 × 11.5 steel collar from 3/4″ bar with a radial 2-56 set screw on
    the wire flat, set "0.45 FEELER OFF T006 THRUST FACE" **[V]**.
  - **Original:** the sources show only a small brass bushing, about Ø5 × 4 mm (scaled from
    the gear pitch, ±25 %), right against T006 **[I from photos]**. The sources are the book's
    top-down photo (p.18; bundled overlay `comparisons/*/harmonic_analyzer--ch12-p002-img09*`),
    the p.21 close-up and the video 4 side view.
  - **The bushing turns with the cone.** Between the video 4 frames at 6:36 and 6:39 the crank
    turns. The bushing changes as much as the rotating 6-leaf pinion beside it (mean pixel
    change 18.7 against 13–20). The end-screw thread, black block and side screw stay at the
    compression floor (about 2–3) **[I from video]**. The bushing is therefore fixed to the
    cone shaft. It is a rotating thrust collar, not a bush in the block.
  - **Verdict:** VN-54 is roughly 3× too large in diameter and length, the wrong metal, and
    has no set screw on the original.
- **Tip block hardware.**
  - **Original** (book pp.17–18, video 4 at 6:36) **[I from photos/video]**:
    - A long end screw is threaded through the black split block. Its domed, slotted,
      blackened head is outboard, and its threaded end sticks out toward the cone.
    - The rotating brass bushing runs against that inner end.
    - A bright slotted pinch screw on the side crosses the slit and locks the end screw's
      thread.
  - **v45:** a short headless #10-32 cup-point set screw (`VN-55`) for the end screw and a
    #4-40 fillister (`VN-56`) for the pinch **[V]**.
  - In the aligned overlay, the model's pinch-screw head is on the side facing the cylinder
    bank. On the original it is on the outboard side **[I]**.
- **Helical crank drive gear.** `dt-crank-drive-gear` is "HELIX AT PITCH DIA: 13.0 ±1 DEG RIGHT
  HAND", meshing with a 16T spur pinion as a crossed-axis pair **[V]**. Nothing in the book
  suggests a helical gear, and every other skewed mesh on the machine is spur-on-spur oblique.
  It is the hardest gear in the set to make.
- **Built-in interference.** Assembly sheet 12, check 4: "(WORST-CORNER OVERLAP 0.34 REF), STONE
  THE T012 TIP UNTIL IT TURNS FREE" **[V]**. The design hands the builder a fit-at-assembly fix.
- **Restored or invented parts.** The keeper chain is a bead chain (McMaster 3606T118). The book
  says the original chain is lost, so its form is a guess **[V]**.
- **Appearance (GLB only).** The crank arm renders black, where the original is nickel-bright.
  The post renders turquoise, where the original is dark green. These are cosmetic. The tip
  collar (VN-54) is not cosmetic; see the VN-54 item above.

## 2. Drawing quality

### Strengths

- Gear data blocks give the cutter number, plunge depth, tooth thickness, and a span or
  over-pins acceptance value.
- The BOM (`MHA-DT-00` sheet 2) is complete: 53 items with quantities and McMaster/MSC SKUs.
- Match-fit notes ("FINISH BORE THRU; ALL 20 GEARS MATCH TO FINISHED SHAFT") are realistic for
  a home shop.
- The assembly checks use tools a hobbyist owns: feeler leaves, an indicator, "turns freely by
  hand".
- Cross-sheet arithmetic holds **[V, calculated]**:
  - T120 pitch diameter Ø63.500 equals the `MHA-DT-12` pitch diameter.
  - The 16T:64T centre distance of 43.225 sits inside the post's "43.10 +0.37/0".
  - The platform's 13° hole pair matches the post (25.97 vs 25.96).
  - The 141.13 closed stack = 20 × 7.0565.
  - Every part number referenced on a sheet appears in the BOM.

### Cross-cutting weaknesses

- **Inch-derived tolerance block on mm sheets.** ".X ±0.8 / .XX ±0.51 / .XXX ±0.13" is inch
  practice converted to mm. It leaves two-decimal critical dimensions loose:
  - cone axis height 38.10 on `dt-cone-tip-block`, untoleranced, while the post holds 38.10 ±0.25;
  - pedestal bore height 44.45 on `dt-arbor-pedestal`;
  - bracket spacing 28.00 on `dt-pinion-bracket`;
  - pivot-block 18.50 / 2.16 "SETS LIFT CAM CLEARANCE".

  Meanwhile the D-bore across-flats are held to "+0.02/+0.01" (10 µm) **[V]**.
- **Y14.5-2018 cited but not applied.** There are almost no datums or feature control frames.
  Runout appears as prose ("0.05 TIR MAX TO FINISHED BORE"), and stacked gear faces have no
  perpendicularity to the bore **[V]**.
- **Unit and thread mixing.** "THREADS UNC/UNF CLASS 2A/2B" appears on mm sheets, inch values
  sit on "UNIT: mm" vendor sheets, and inch screws share the assembly with an ISO 2338 4 mm
  dowel **[V]**.
- **Rationale inside requirements.** Examples: "SETS CHANNEL GAIN", "SETS BACKLASH WITH CONE
  GEARS", "MESHES WITH MHA-DT-12", "CLEARS #25 CHAIN". Useful context, but it hides which
  features are actually critical **[V]**.
- **Assembly operations on part sheets.** The taper-pin hole is pre-drilled "#14 DRILL Ø4.62" on
  `dt-crank-hub` and "#9 DRILL Ø4.98" on `dt-crankshaft`, then match-reamed at assembly **[V]**.
- **General corner note conflicts with fits.** "INSIDE CORNERS R1.0 MAX" applies to shoulders that
  a mating part must sit flush against (crank hub/arm) and to D-bore corners, while the shaft
  flats call "CORNERS 0.02 MAX" **[V/I]**.
- **Title blocks.** There is no quantity field. PART is the file stem. REV is the build counter
  (`v45`). Material ranges from "SAE 1018 CF bar, ASTM A108-24" down to bare "Brass" and
  "Plain Carbon Steel" **[V]**.
- **False precision.** Examples: "7.0565 ±0.025", "6.8756 ±0.025", "21.1777", "4.1411 +0.000/-0.100"
  **[V]**.

## 3. Uncommon or bad practice

- **Compass directions.** Assembly sheet 7: "FRONT IS SOUTH, THE CRANK END; BACK IS NORTH … THE
  TOP VIEW HAS SOUTH UP AND EAST LEFT" **[V]**.
- **Three gear numbering schemes.**
  - Stations "STN 1 T120 … STN 20 T006", front to back (sheet 9).
  - Tooth-count names T006–T120.
  - "GEAR 0 … GEAR 19" (step 8).

  Station 1 is the fastest channel, the reverse of Michelson's harmonic number **[V]**.
- **One 21-page drawing for 20 gear variants.** Each sheet has its own number
  "MHA-DT-03-Txxx" but reads "SHEET n OF 21". The T006 tooth form is on sheet 21, plotted at
  ~75:1 with a "SCALE: 1:1" title block. A single tabulated sheet is the norm **[V]**.
- **Assembly drawing shape.** Text walls of part numbers with no per-step pictures. The exploded
  views are tiny and the parts barely separated; the 20 cone gears share one balloon (sheet 4).
  Apart from sheet 13 there are no dimensions on the assembly views. Step 8 depends on
  `MHA-CH-00` step 2, and step 9 drills the frame base **[V]**.
- **Purchased parts redrawn.** Catalogue parts are drawn at 1:4–1:8 with full general-tolerance
  blocks. The made tip collar carries a vendor number (`MHA-DT-VN-54`) and folds a purchased set
  screw into the same number. `MHA-SH-VN-54` is a different part **[V]**.
- **Stack tolerance.** Twenty gears at ±0.025 each against a "141.13 ±0.10" closed stack is handled
  by measure-and-reface (step 8: "REMAKE THE THINNEST GEAR"). That is selective assembly, and it
  is not stated as such **[V/I]**.

## 4. Release and licensing issues

- **SOLIDWORKS for Makers watermark.** "SOLIDWORKS Maker Product. For Personal Use Only." is
  printed on all 208 PDFs in the bundle, over the zone-4 numeral. It conflicts with the
  commercial book and Kickstarter plans; check the Makers licence terms before either ships
  **[V]**.
- **Hammack book images in an MIT bundle.**
  - All 18 `comparisons/ref/` images (and the `composite/` blends) are crops from the 2014
    book (`manifest.json`, `"source": "book …"`) **[V]**.
  - `comparisons/ATTRIBUTION.md` says the book is "published under **CC BY**".
  - The book itself says "free for you to view and share for non-commercial purposes" and
    "All rights reserved".
  - `NOTICE.md` in the same bundle says "no photograph or drawing from it is reproduced here",
    while `LICENSE` invites commercial use **[V]**.
  - Repository rule 4 (`AGENTS.md`) says nothing from that book goes into a commercial product.

## 5. Per-drawing findings

Severity: **BLOCKER** (can't be made or will not work as drawn), **MAJOR**, **MINOR**, **NICE**.

### Crank group

- `dt-crank-arm` (DT-06)
  - **MAJOR [V]** The Ø19.4 bore has no tolerance of its own; only "0.010-0.030 DIAMETRAL
    INTERFERENCE" with the hub. A 20 µm band needs metrology a hobby shop lacks. Give limits
    plus a shop test such as "presses home with an arbor press".
  - **MAJOR [V]** It never identifies the outboard face. "NEAR SIDE" and the punch mark depend
    on it.
- `dt-crank-hub` (DT-31)
  - **MAJOR [V/I]** The title-block R1.0 inside corner on the Ø19.4/Ø22.25 shoulder against a
    0.25 edge break defeats "FACES FLUSH". Add a local R0.2 max or an undercut.
  - **MAJOR [V]** Taper-pin pilot "#14" here vs "#9" on DT-11. Reamer size, ream depth and
    large-end side are not given. Pilot both parts together at assembly.
- `dt-crankshaft` (DT-11)
  - **MAJOR [V]** "2X REAM Ø2.38 -0.01/0.00" (2.37–2.38) is below a standard 3/32″ reamer
    (≥2.381). Name an undersize reamer or give a go/no-go gauge.
  - **MAJOR [I]** "DRIVE-PIN HOLE TO SPIGOT RIM 0.48 MIN" leaves about 0.5 mm of wall beside a
    pressed dowel, so the rim may bulge.
  - **MAJOR [V]** No datum or runout control ties the journals, hub seat and pinion seat together.
- `dt-crank-pinion` (DT-10) / `dt-crank-drive-gear` (DT-07)
  - **MAJOR [V]** A spur 16T mates a 13° helical 64T. Neither sheet states the shaft angle or
    centre distance; the centre distance appears only on DT-05.
  - **BLOCKER (novice) [V/I]** "LEAD (mm/rev, REF): 945.862" needs a universal mill with a
    geared dividing head, or a 4th axis.
  - **MAJOR [V]** "8.763 +0.02/+0.01 BORE ACROSS FLAT" (10 µm) and "BASE TANGENT SPAN OVER 2
    TEETH … 4.9071 TO 4.9230" (16 µm) are beyond caliper checks.
  - **MAJOR [V]** The pinion bore "Ø9.000 +0.055/+0.025" sits next to "BORE LIMITS GOVERN
    (Ø9.000 +0.000/-0.020)", which quotes the shaft limits and reads as a conflicting bore
    tolerance.
- `dt-crank-pin` (DT-09)
  - **MAJOR [V]** "Plain Carbon Steel" names no grade.
  - **MAJOR [V]** The taper has no tolerance; the ±1° general angle tolerance is meaningless on
    a 0.6° taper. Name the reamer (#4 taper-pin reamer **[I]**) and accept by bluing.
- `dt-crank-handle` (DT-08)
  - **MAJOR [V]** "Ø4.10 +0.05/0.00 REAM THRU" about 48 mm deep in end-grain oak. A 50 µm band
    means nothing in wood.
  - **NICE** Maple or pear turns smoother than open-pored white oak; add a 1:1 profile template.
- `dt-crank-handle-pivot-screw` (DT-32)
  - **MAJOR [V]** 53 mm of "Ø4.00 -0.03/-0.08" at Ra 1.6 (L/D ≈ 13) will deflect while turning.
    Give a sequence with tailstock support, or allow ground 4 mm stock.
- `dt-crank-pin-eye` (DT-28)
  - **MAJOR [I]** The straight tail beyond the loop is about 1.35 mm, too short to seat under a
    #4 fillister head. Form a closed eye around the screw instead.

### Cone group

- `dt-cone-gear` (DT-03, 21 sheets)
  - **BLOCKER [V/I]** T006/T012 call "Ø0.794 +0.055 +0.025 THRU" with "0.420 +0.02 +0.01 BORE
    ACROSS FLAT", a ~0.8 mm near-half-round bore about 7 mm long. It needs wire EDM and can't
    be gauged. §7 gives three ways around it.
  - **BLOCKER (novice) [V]** T006: "CUTTER: NOT STOCK; FORM = TOOTH SPACE, SHEET 21". There is a
    16-point form table but no cutter drawing.
  - **MAJOR [V]** The T018–T120 D-bores are held to "+0.02 / +0.01" across the flat.
  - **MAJOR [V/I]** Edge contact from the 13° skew means one face edge of each gear does the
    work. The sheets never say which face is the contact face. "DO NOT BREAK OR CHAMFER EDGES ON
    TOOTH FLANKS" conflicts with the title block's "REMOVE BURRS AND BREAK SHARP EDGES".
  - **MAJOR [V]** "MATERIAL Brass" names no alloy, and v45 draws all 20 gears in it. The book
    says T006–T024 look yellower and harder than the rest, and video 4 shows them lighter.
    Specify bronze (phosphor bronze C544) for T006–T024 and an alloyed brass (e.g. C360) for
    T030–T120.
  - **NICE [I]** On Brown & Sharpe-pattern plates (15–49 holes), 96T, 102T and 114T have no
    simple index (40/N = 5/12, 20/51, 20/57). Add an indexing table that flags them.
- `dt-cone-gear-shaft` (DT-04)
  - **BLOCKER [V/I]** "Ø0.794 -0.02 SLIDES IN T006, T012, MHA-DT-VN-54", about 33.6 mm long,
    with a "0.420 -0.01" flat, turned from 5/8″ 1018 bar. "TURN THE TIP LAND WITH TAILSTOCK
    SUPPORT" can't be centre-drilled at 0.8 mm. It also has to drive T006/T012 against cam load.
  - **MAJOR [V]** There is no runout between the journal, the gear seats and the tip, and no
    angular tolerance on "4 FLATS IN LINE", while the gears are phased ±0.25° to the flats.
  - **MINOR [V]** Steps are dimensioned twice from different faces (sheet 1 from the collar
    south face, sheet 2 from the "COLLAR NORTH FACE").
- `dt-cone-pivot-post` (DT-05)
  - **MAJOR [V]** "LOW-CARBON STEEL OR GRAY IRON". It is a casting shape with no
    fabricated-from-bar route.
  - **MAJOR [V]** There is no orientation control from the cone bore (A) to the foot (B); any
    tilt is amplified about 150 mm to the tip.
  - **MAJOR [V/I]** "2X Ø7.14 THRU ALL", about 95 mm deep, with "WALL 1.50 MIN": drill wander
    risk.
- `dt-cone-tip-block` (DT-21)
  - **MAJOR [V]** The cone-axis height "38.10" is untoleranced (±0.51), while the post holds
    "38.10 ±0.25 AXIS MATCHES MHA-DT-21". At T006 that is about half a tooth **[I]**.
  - **MINOR [I from photos/video]** The original's end screw is a long, headed screw. It goes
    through the block, with its head outboard and its thread exposed toward the cone. It is not
    a short headless cup set screw (VN-55), and the side pinch screw is on the opposite side
    from the model's.
- `dt-cone-swing-platform` (DT-20)
  - **MINOR [V]** "REAM Ø6.35 +0.02/0.00 … RUNNING FIT" against a Ø0.250 -0.001 shoulder allows
    zero clearance.
  - **MINOR [V]** "SWINGS FREE, NO AXIAL SHAKE" has no end-play number.
  - Good: a clear stock call.
- `dt-vn-cone-tip-collar` (VN-54)
  - **MAJOR [I from photos/video]** It has no counterpart on the original (§1 Departures). The
    real tip has a small brass bushing, about Ø5 × 4, fixed on the shaft. It turns with the
    cone and runs against the end screw.
  - **MAJOR [V]** A made part ("REAM THRU", "3/4 STEEL BAR STOCK OK") carries a VN number.
  - **MAJOR [I]** A 2-56 set screw clamping a 0.8 mm half-round wire will bend or mark it.
- Vendor sheets (VN-51, -52, -55, -56, -60, -61)
  - **MINOR [V]** SKUs given. Views at 1:4–1:8 are illegible.
  - **MINOR [V]** VN-61 sheet 2 carries modelling notes ("CURRENT SOLID HAS DIFFERENT SKIRT …").

### Cylinder and alignment-pinion group

- `dt-cylinder-gear` (DT-12)
  - **MAJOR [V/I]** The notch is controlled only relative to the cam lobe. No requirement ties
    the tooth spaces to the lobe or notch; only Detail A and "MAX CLEARS FLANKS" imply the notch
    sits in a tooth space. Because the straight alignment pinion engages all 20 gears at once,
    random tooth phase would be pulled up to ±1.5°, swamping the ±0.25°. "CCW" has no viewing
    side, so a mirrored notch gives 3°.
  - **MAJOR [V]** There are no datums. "0.05 TIR MAX" is prose, and the stacked faces have no
    perpendicularity.
  - **NICE [I]** The 8.640 ±0.025 eccentric needs an offset fixture; inspect it as max wall
    minus min wall = 2e. The Ø9.575 match bore suits a 0.377″ reamer. The 1.5° notch offset is
    3 holes on an 18-hole circle; the 0.40 notch needs a 0.4 mm slitting saw.
- `dt-arbor-pedestal` (DT-02)
  - **MAJOR [V]** Bore height 44.45 falls under ±0.51 and has no perpendicularity to the foot.
    Make the two pedestals as a matched pair.
- `dt-cylinder-gear-shaft` (DT-13)
  - **MINOR [V]** "RUNNING FIT" contradicts DT-02's "SLIDING FIT" plus set screw.
  - **MINOR [V]** "SUPPLY 190 LONG, UNCUT" contradicts the drawn length.
- `dt-alignment-pinion` (DT-01)
  - **MAJOR [V/I]** There is no lead or pitch-runout requirement over 143.2 mm, yet that is what
    phases all 20 gears.
  - **MAJOR [V/I]** The bore/bond-zone clearance allows about 0.1 mm eccentricity after bonding.
    Bond to the arbor first, then cut the teeth between centres.
- `dt-pinion-arbor` (DT-22)
  - **MAJOR [V]** The Ø15 head is integral with a 243 mm Ø8 shaft (L/D ≈ 30), with journals at
    -0.01/-0.03. Ground 8 h6 rod doesn't meet that. Suggest a separate bonded head.
- `dt-pinion-bracket` (DT-14) / `dt-pinion-pivot-block` (DT-18)
  - **MAJOR [V]** Pair-critical spacings are at ±0.51 while the cam is held to ±0.05: the
    tolerance allocation is inverted. Make them as stacked pairs.
- `dt-pinion-lever` (DT-16)
  - **MAJOR [V]** One-piece Ø6 × 86 grip plus Ø13 hub means milling from solid. Allow a two-piece
    pressed or bonded version.
  - **MINOR [V]** The engaged angle is not defined.
- Lift geometry **[I]**
  - Reconstructed from DT-18/14/23, a 90° lever swing moves the pinion about 3.7 mm if the
    eccentric throws toward the drum, or about 2.3 mm (no engagement) if it throws away.
    Full working depth needs about 3.3 mm.
  - No sheet defines the engaged position or an engaged-depth check.
  - The park geometry checks out: 2.50 feeler, arbor at about 44.48 vs the 44.45 gear centre.
- `dt-pinion-spring` (DT-24)
  - **MINOR [V]** "SETS PRELOAD" appears five times, with no load at installed deflection and no
    flat-blank length.
- Naming drift **[V]**
  - DT-13 is "ARBOR", "SHAFT" and "MANDREL".
  - DT-14 is "BRACKET" and "STRAP".
  - DT-15 is "HANDLE" and "CROSSROD".

### Assembly `MHA-DT-00` (13 sheets)

- **Good [V]**
  - Complete BOM.
  - Functional checks with feeler leaves.
  - The zeroing procedure mirrors the book.
  - The closed-stack and blade settings are dimensioned on sheet 13.
  - Sheet 1 notes that views at 1:2 and smaller omit teeth and threads.
- **MAJOR [V]** Sheets 7–10: sequence steps are dense part-number prose with no pictures.
- **MAJOR [V]** Sheets 3–6: exploded views at 1:2–1:3 occupy about a quarter of the sheet, with
  minimal separation.
- **MAJOR [V]** Sheets 7 and 9: the compass convention and three numbering schemes (§3).
- **MINOR [V]** Sheets 8 and 12: steps rely on a DRO and edge-finder coordinates ("X
  168.11-168.30"). This is an advanced setup for a novice.
- **MINOR [V]** General tolerance and finish blocks are printed on every assembly sheet.

## 6. What would help a novice (prioritised)

1. **Rework the cone tip (§7).**
   - Drop the Ø0.794 mm journal, the T006/T012 D-bores and VN-54.
   - Replace VN-54 with the original's small brass bushing. Fix it on the shaft so it turns
     with the cone and bears on a long end screw.
   - Pick one of the three period-accurate options: an integral 6-leaf pinion on a tip arbor,
     a one-piece planed arbor, or gears cut separately and sweated into a cluster.
   - Make T006–T024 and any new tip arbor in bronze (phosphor bronze C544), and T030–T120 in
     brass, to match the real device.
   - A one-piece T006–T018 can't be cut with a rotating cutter.
2. **Offer an easier crank drive gear.** Allow a spur 64T that meshes obliquely like the cone
   gears, or a purchased gear, alongside the 13° helical.
3. **Replace the 10 µm D-bores** with a cross pin or key, or a round bore and a phasing jig, and
   give a go/no-go gauge.
   - Fix the gear with soft solder or a riveted collet (period), or retaining compound (modern,
     1950s+).
4. **Make one tabulated gear sheet** listing, per tooth count: cutter (48 DP, 20° PA, custom for
   6T), dividing-head turns and holes (flag 96/102/114T), blank stock and an operation sequence.
5. **Write a per-part plan:** stock size, operation order, workholding, and critical vs cosmetic
   features. Give shop acceptance tests (go/no-go, bluing, "slides by hand") and a named tool
   list (0.3760″ and 0.377″ reamers, #4 taper-pin reamer, undersize 3/32″ reamer, 0.4 mm
   slitting saw).
6. **Add a cylinder-gear fixture drawing** (bore pin plus 8.640 offset pin). State the
   tooth-space-to-lobe requirement and the viewing side for "CCW".
7. **Add "make as matched pair" notes** for the pedestals, brackets and pivot blocks, and put
   all match-drilling on one assembly sheet.
8. **Rewrite the assembly instructions** with a picture per step, part names next to numbers,
   one gear numbering scheme, and front/back/left/right instead of compass points.
9. **Fix the drafting basis.** Use a metric general-tolerance block (ISO 2768-m or an explicit
   mm table), add a datum scheme with real FCFs, add QTY and descriptive part names, and use a
   revision letter distinct from the build number.

## 7. Cone-tip options (period-accurate)

![Cone tip: v45 vs three period-accurate options, why a one-piece tip can't be milled, and
c.1898 fixing methods](drive-train-v45-review/cone-tip-options.png)

The sketch is drawn to scale from MHA-DT-03/-04/VN-54 and the GLB. It is a proposal only; none
of it is in CAD.

### What the original tip looks like

- **Brass bushing.** A small brass bushing, about Ø5 × 4 mm, sits right against the T006 face
  (book p.18 top-down, p.21 close-up, video 4 side view).
  - It is fixed on the shaft and turns with the cone. Between the video 4 frames at 6:36 and
    6:39 it changes like the rotating pinion, while the screw and block don't **[I from
    video]**.
  - Its outer face is a thrust face.
- **End screw and block.** A long end screw is threaded through the black split block.
  - Its domed, slotted, blackened head is outboard; its threaded end sticks out toward the cone
    and faces the bushing.
  - A bright slotted pinch screw on the side crosses the slit and locks the thread.
  - End play is set by turning the end screw against the bushing, then tightening the pinch
    screw (book pp.17–18, video 4) **[I from photos/video]**.
- **What we don't know.**
  - The 1898 paper says only that the wheels "are all fastened together on the same axis and
    form the cone D" (Michelson & Stratton, p.4). How they are fixed is not stated.
  - Whether the shaft's pivot point enters a centre in the end screw is hidden by the bushing.

### Constraints any option must meet

- **Contact zone.** Each cylinder gear touches its cone gear only 2.2–5.3 mm from the cone
  gear's big-end face, with up to ~0.7 mm penetration. This holds for T006, T012, T018 and
  T024. It was measured by surface-sampling the cylinder gears against each cone band on
  `dt-drive-train.glb` (saved pose) **[I, measured]**.
- **Unused faces.** The first 2.2 mm from the big end and the last 1.6 mm at the tip side are
  never touched. Relief grooves and solder fillets can go there.
- **No one-piece milling.** A one-piece T006–T018 can't be cut with a rotating disc cutter.
  - Each larger neighbour stands ≈2.6 mm above the next band's root. A cutter of radius R
    must therefore keep its lowest point √(2·R·2.6) from that shoulder: ≥ 8.1 mm for a 1″
    cutter, ≥ 5.8 mm even for a Ø13 fly cutter.
  - Contact starts 2.2 mm from the shoulder, so the cutter would have to be under Ø1.9.
  - This is the classic cluster-gear problem **[I, calculated]**.

### Options

All three are period-accurate (c.1898). All three:
- make T006–T024 and every new tip part (arbor, one-piece arbor, T006 part) in bronze
  (phosphor bronze C544), and keep T030–T120 in brass, to match the real device;
- delete VN-54 and the Ø0.794 wire;
- add the original's brass bushing, soft-soldered or driven onto the pivot after the teeth are
  cut, with its outer face square and smooth;
- use the original's tip hardware: a split block with a long end screw that bears on the
  bushing, and a side pinch screw.

- **A · 6-leaf pinion cut on a tip arbor.**
  - **Arbor.** Phosphor bronze, carrying the integral T006, a Ø2.0 stem and a Ø1.5 pivot. It
    plugs into a Ø2.0 H7 × 8 hole in a shortened DT-04, soldered or pinned with a Ø0.8 pin.
  - **Cutting T006.** The stem is 0.07 mm and the pivot 0.32 mm below the T006 root (Ø2.14),
    so a fly cutter ground to the sheet-21 form runs off both sides. Support the work with a
    temporary tailstock boss beyond the pivot.
  - **T012 and T018.** Make them separate bronze gears. Bore both Ø2.0 and soft-solder them
    onto the stem, setting the phase with a pin jig first. T024 stays a separate bronze gear
    on DT-04.
  - **Bushing.** Fit the brass bushing on the pivot after cutting.
  - **Drive.** T006's torque reaches it through metal.
- **B · One-piece T006–T018 with planed teeth.**
  - **Material.** Bronze arbor carrying T006, T012 and T018. T024 stays a separate bronze
    gear.
  - **Method.** Plane the teeth (shaper, or the lathe used as one) with three HSS form tools.
    Each stroke ends in a 1.5 mm relief groove inside the untouched 2.2 mm.
  - **Indexing.** One 72-hole spindle plate indexes 6, 12, 18 and 24; a 60T bull gear can't
    do 18.
  - **Effort.** Slow: 36 tooth spaces.
- **C · Gears cut separately, then sweated into a cluster.**
  - **Cutting.** Each gear is cut alone with ordinary setups.
  - **T006.** It becomes one small bronze part with a Ø2.0 spigot, the 6 leaves and the Ø1.5
    pivot, and its leaves run off over its own spigot and pivot. T012, T018 and T024 are
    separate bronze gears.
  - **Joining.** T018, T012 and T006 are soft-soldered face to face. The joints sit at the
    big-end faces, in the untouched zone. Phase all three with a pin jig through lined-up
    tooth spaces; reheat to take the cluster apart.
  - **Mounting.** The cluster stays on DT-04's existing Ø3.175 D-seat.
  - **Trade-off.** Simplest tooling; the tip hangs on solder joints, though its torque is tiny.

### Period fixing methods (c.1898)

- **Riveted collet.** Standard clockwork. It fits T018 and up; there is no room inside T006 or
  T012.
- **Drive fit on a taper.** Removable.
- **Soft solder (sweating).** Works at any size; options A and C use it.
- **Taper pin.** The crank on this machine uses one. It is too coarse for a Ø2 stem.
- **Square seat.**
- **Nut-clamped stack with one feather key.** Plausible for the whole cone, but unproven on
  this machine.
- **Avoid retaining compounds (Loctite type).** They date from the 1950s; use them only where
  period accuracy doesn't matter.

### Open questions for the CAD change

- Confirm the 2.2–5.3 mm contact zone against the CAD source, not only the saved GLB pose.
- Resolved: the brass bushing is a thrust collar on the shaft (video 4 frame diff). End play
  is set by the long end screw bearing on it.
- Still open: whether the pivot runs in a centre in the end screw's tip. The photos and video
  can't show it.
- Choose A, B or C. Each touches:
  - MHA-DT-03 (T006/T012 at least) and MHA-DT-04;
  - VN-54, which is deleted;
  - VN-55, replaced by a long headed end screw through the block;
  - VN-56, the pinch screw, which moves to the outboard side.

## Reproducing the renders

```bash
export MESHPROBE_BLENDER=/path/to/blender-5.2.0/blender
MP="uv run --project <meshprobe checkout> meshprobe --session dt"
$MP open harmonic-analyzer-v45/gltf/dt-drive-train.glb
# plan view: cone skew, tip pivot, cylinder bank, pinion rig
$MP view-frame --all --azimuth -90 --elevation 90 --margin 1.05 --aspect-ratio 0.8 \
  --projection-json '{"mode":"orthographic","scale_mm":100}'
$MP render-image --output top.png --width 1000 --height 1250
# cone tip and the Ø0.794 journal
$MP view-frame dt-cone-tip-block-1 dt-vn-cone-tip-collar-1 dt-cone-gear-20 dt-cone-gear-19 \
  dt-cone-gear-18 dt-vn-cone-pivot-screw-1 --azimuth -150 --elevation 25 --margin 1.4 \
  --aspect-ratio 1.6 --projection-json '{"mode":"perspective","focal_length_mm":85}'
$MP render-image --output tip.png --width 1600 --height 1000
# alignment-pinion rig (compare book p.67)
$MP view-frame dt-alignment-pinion-1 'dt-cylinder-gear-*' dt-pinion-arbor-1 --azimuth -10 \
  --elevation 15 --margin 1.1 --aspect-ratio 1.6 \
  --projection-json '{"mode":"perspective","focal_length_mm":60}'
$MP render-image --output pinion.png --width 1600 --height 1000
```

The book-photo side-by-side used the same session with `--reference-image` pointing at
`references/albert-michelsons-harmonic-analyzer/ch12_images/page002_img09.jpeg`. It is
deliberately not committed, because the photo is licensed for non-commercial use only. The
tip comparison in §1 also uses the bundle's own overlay pair
`harmonic_analyzer--ch12-p002-img09`, and the book's p.21 close-up
(`ch12_images/page003_img02.jpeg`).

The §7 contact zone came from loading `dt-drive-train.glb` with trimesh and fitting the cone
and cylinder axes through the 20 gear centroids (skew 13.05°). Each cylinder gear was then
surface-sampled at 400 000 points, keeping the points that fall inside each cone band's OD
within that band's axial span. The committed sketch contains no book imagery; it is drawn from
the drawings and those measurements.

The rotating-bushing finding compares `engineerguy-youtube/stills/full/v4_t00396.png` and
`v4_t00399.png`. The camera is locked off and the crank turns between the two frames. Mean
absolute grey-level difference was taken in small windows:

| Window | Mean change |
|---|---|
| 6-leaf pinion | 13.3 |
| brass bushing | 18.7 |
| exposed end-screw thread | 6.5 (edge bleed; ~4 a few px further on) |
| black block | 2.1 |
| end-screw head | 2.9 |
| bright side screw | 3.0 |

The video stills are not committed.
