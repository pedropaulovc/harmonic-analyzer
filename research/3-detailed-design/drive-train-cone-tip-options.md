# Cone tip options and drive-train DFM, against the 2026-11-08 rubric

> **Proposal, not current status.** Nothing here is in CAD. The decision it feeds is
> [#1649](https://github.com/pedropaulovc/harmonic-analyzer/issues/1649); track the work on the
> [Harmonic Analyzer project](https://github.com/users/pedropaulovc/projects/1).
>
> This replaces §6 and §7 of the [v45 review](drive-train-v45-review.md). That review judged the
> v45 bundle by general drafting practice. This one judges main `a8441605f` (2026-11-09, after
> v47) by [`cad/docs/drawing-guidelines.md`](../../cad/docs/drawing-guidelines.md) as rewritten on
> 2026-11-08. Every number below is read from `cad/scripts` and `cad/config` on that commit; see
> [Reproducing](#reproducing).

![Cone tip: main today, the rule 17 bore limit, options A and B, cutter run-out, rejected
options and a summary](drive-train-cone-tip-options/cone-tip-options-v47.png)

## What changed since the v45 review

- **Units and review.** The drive-train sheets are now decimal inch (#290), and 49 of the 53
  `draw_dt_*` packages enforce machinist review. The tip geometry did not move: the cone stations
  and every dimension in the sketch are the v45 values.
- **The tip ships on owner exceptions.** MHA-DT-03 carries RV-01 (the T006/T012 D-bore), RV-03
  (T012 web .0797) and RV-04 (T006 web .0256, under the .060 floor, "accepted until #1649").
  MHA-DT-04 carries RV-01 (the Ø.031 × 1.32 land) and RV-02 (the tailstock note).
- **Tip-gear material is already decided.** `dt-cone-gear` prints C67500 manganese bronze for
  T006–T024 and C36000 brass from T030. That matches the book's "more yellow ... harder metal"
  better than the phosphor bronze the v45 review proposed, so this review keeps C67500.
- **The rubric changes three earlier conclusions.**
  - Rule 17 makes the web floor a blocker unless the owner rules otherwise. T006 cannot carry
    any bore (below).
  - Rule 23 says solder never holds a drive-torque joint. That rules out the v45 review's
    sweated cluster (option C) and its soldered T012/T018.
  - Rule 23 prefers a hidden bond to an added visible screw. The v45 review's "avoid Loctite"
    is reversed where period form is not visible.

## Constraints every option must meet

| | value | source |
|---|---|---|
| Web floor / target (rule 17, inch) | .060 / .080 in (1.52 / 2.03 mm) | `_inch_wall_limits` |
| D-bore upper deviation | +.0018 in | `dt_cone_gear_spec.BORE_DIA_BAND` |
| T006 root, minimum envelope | Ø.0840 (2.134 mm) | `floor_limits_mm(6)` |
| Largest T006 bore with a .060 web | none (.0840 − .120 < 0) | calculated |
| T012 root, minimum envelope | Ø.1922 (4.882 mm) | `floor_limits_mm(12)` |
| Largest T012 bore with a .060 web | Ø.0722 at its printed maximum | calculated |
| Contact zone on each band | 2.2–5.3 mm from its big-end face | v45 GLB, surface-sampled |
| T012 shoulder above T006 root | .101 in (2.57 mm) | calculated |
| Run-out of a Ø1/4 cutter at that depth | 3.1 mm, more than the 2.2 available | √(h(2R−h)) |

The web check reproduces main's own exception values: .0256 for T006 (RV-04) and .0797 for
T012 (RV-03).

Two conclusions follow, and they decide the shortlist:

1. **T006 must be solid with whatever carries it.** No bore of any size leaves a .060 web, so
   #1649's A (drill-rod tip), D (broached D), E (1/16 land) and F (round pinned bore) all keep
   an owner exception on T006.
2. **T006 cannot be milled next to a larger neighbour on the same part.** A one-piece
   T006 + T012 needs a non-rotating cutter (planing). If T012 is separate and goes on after T006
   is cut, an ordinary fly cutter runs off over the thin stem.

## Options

### A · T006 cut on a bronze tip arbor (recommended)

- **Arbor.** One C67500 part, turned between centres: Ø.125 spigot, Ø.250 T024 seat with its
  flat, Ø.125 T018 seat with its flat, Ø.0625 T012 seat, the T006 blank, then a Ø.0625 pivot.
  It replaces DT-04's lands 2–4, so DT-04 ends at its Ø.375 land.
- **T006.** Cut on the arbor with the DT6-FORM1 fly cutter main already specifies. The seat and
  pivot are .0108 below the T006 root, so the cutter runs off on both sides. No bore, no web,
  no RV-01/RV-04.
- **T012.** A separate gear on the Ø.0625 seat, keeping the one-flat-per-land ruling
  (2026-09-28). Web .0640 MIN: above the floor, below the target, so the sheet states
  `WALL .064 MIN` under rule 20. T012 cuts conventionally on its own mandrel: T006's OD (.170)
  is inside T012's root (.192).
- **T018, T024.** Unchanged gears; their flats move from DT-04 to the arbor.
- **Joint to DT-04.** The spigot is bonded with LOCTITE 638 in a reamed Ø.125 hole in the end of
  DT-04's Ø.375 land, under T030 and out of sight. The wall from that hole to the land's flat is
  .095. A cross pin would leave .033 of spigot wall on each side and fails rule 17, so the bond
  is the only rule 23 means that fits. Press fit is the alternative.
- **Tip end (period form).** A brass bushing (about Ø5 × 4 mm, wall .067) is pressed on the pivot
  against T006, so it turns with the cone, as in video 4. A long slotted, domed 1/4-28 end screw
  runs through MHA-DT-21. Its inner end carries a Ø.063 pivot hole and takes the bushing's
  thrust, and the existing pinch slit locks it (rule 23, adjuster). VN-54 and VN-55 go.
  - A #10-32 end screw would leave about .043 of wall round a drilled Ø.0625 pivot hole, under
    the .060 floor. A 1/4-28 screw leaves about .070, so the screw is 1/4-28.
  - With the mouth countersinks, 1.5D of 1/4-28 needs DT-21 about .43 deep instead of .380.
    The block grows south, as the 2026-09-29 ruling already allows. That also clears main's
    1.0D adjuster engagement (#975).
- **Setting it at assembly (rule 19), proposed steps.**
  1. Slide T024, T018 and T012 onto the arbor.
  2. Apply 638 to the spigot and push it into DT-04 until T006 seats on T012 with the stack
     closed against T030.
  3. Lay a parallel across DT-04's Ø.375 flat and the arbor's Ø.250 flat; it must lie on both
     (`4 FLATS IN LINE`).
  4. Hold that until fixture time. Cure before turning the crank.
  5. Acceptance: the tip does not turn or slide by hand against DT-04.

### B · One-piece T006–T018 arbor, T012 and T006 planed

- Same spigot, T024 seat, pivot, bushing and end screw as A.
- T018 is still milled: T024, the only neighbour above its root, is a separate gear.
- T012 and T006 are planed with form tools, on a shaper or the lathe used as one. Each stroke
  ends in a 1.5 mm relief groove inside the untouched 2.2 mm at the band's big-end face.
  That is 18 tooth spaces, indexed from one 72-hole plate.
- No joints in the tip at all. The cost is the route: the declared shop is a lathe and a mill,
  so a reviewer may call planing implausible for a first-time builder under rule 16. T012 and
  T018 also lose their flats, which needs the owner to set aside the 2026-09-28 ruling for the
  tip.

### Rejected

| option | why, under the current rubric |
|---|---|
| Keep main (#1649 C) | T006 web .0256 < .060; Ø.031 × 1.32 land and .017 flat; VN-54 has no counterpart on the original. Ships only by exception. |
| #1649 A, drill-rod tip | T006 stays bored; .047 wall round the rod in DT-04's Ø.125 land; still needs VN-54. |
| #1649 D, E, F | each keeps a bore in T006. E (1/16) gives a .0099 web; F cannot cross-pin a .031 shaft. |
| #1649 B, pinion wire | clock pinion wire is a cycloidal leaf, not DT6-FORM1's 20° profile against the 120T drum. No 48DP stock found; not pursued. |
| v45 option C, sweated cluster | rule 23: solder does not hold a drive-torque joint. |

## Owner decisions

1. **A or B** (or keep main's exceptions). A is recommended: standard tooling, every web at or
   above the floor, and it keeps the flat ruling.
2. **Period tip end.** Replace VN-54 and VN-55 with a pressed brass bushing and a long 1/4-28
   end screw, and deepen DT-21 to about .43.
3. **T012 web .064** on the Ø.0625 seat, stated on the sheet (rule 20 shortfall, minor).

Each choice retires DT-03 RV-01/RV-04 and DT-04 RV-01/RV-02. A adds one part (the arbor), one
fabricated end screw and one bushing, and removes VN-54 and VN-55.

## Drive-train DFM recommendations (replaces v45 §6)

Ordered by what they unblock. "Verified" means read on main `a8441605f`; the rest need a look at
the current sheet first.

1. **Cone tip: option A** (above). It retires four owner exceptions and the one part with no
   historical counterpart.
2. **Stop MHA-DT-21 turning on its single screw**
   ([#1178](https://github.com/pedropaulovc/harmonic-analyzer/issues/1178), open).
   - Rule 23 (static clamp): a one-screw part whose turning changes a setting needs a dowel,
     tongue, step or second screw.
   - Option A makes this more pressing, because turning the end screw torques the block.
   - A tongue in a platform slot, or a dowel beside the hold-down screw, keeps the slit
     clamp's function.
3. **Re-check the crank drive gear route.**
   - The 13° helical 64T (#1272, verified on main) needs a lead of 945.9 mm (37.24 in). That means
     a dividing head geared to the table screw.
   - The declared shop does not include one, and the indexing kit MHA-DT-03-TL-00 is a plate kit
     for plain indexing.
   - Under rules 16 and 21 the owner either names that route or allows a spur 64T meshed
     obliquely at 13°, the way every cone mesh works. Run the `dt_mesh_checks` contact gates
     before choosing.
4. **Give every jig the parts need a drawing.** The rubric's shop has "no jig the package does
   not tell the builder to make".
   - The indexing kit exists but its review is OFF; enrol it.
   - Add a D-flat plug gauge per land size: the across-flat bands (.0004) are narrower than
     the milled-width row (±.001), so the fit route needs a gauge the builder can make.
   - Add an offset-turning fixture for the cylinder gear's 8.64 mm eccentric (±.0010).
   - For option A, add the parallel used to line up the flats.
5. **Matched pairs where a stack depends on two loose parts** (rule 19): the arbor pedestals,
   pinion brackets and pivot blocks. Make each pair together, or give the step a feeler-set
   gap. This came from the v45 sheets; re-check the inch sheets.
6. **Cone pivot post mounting at print-worst**
   ([#1134](https://github.com/pedropaulovc/harmonic-analyzer/issues/1134), open), together with
   the deep 2X Ø.281 holes. Rule 17 counts drill wander on a deep hole.
7. **Compass words that ENFORCE review missed** (rule 26, verified): DT-04 prints
   `COLLAR NORTH FACE / 64T SEAT`, and VN-68's installation note says `NORTH FACE … NORTH
   MHA-DT-02 STRAP`. Option A removes the first. The second belongs in an MHA-DT-00 step
   (#930).

Dropped from the v45 list because the rubric now says otherwise: a datum and frame scheme
(rule 5), per-part operation plans and named tools on the prints (rule 7: route in the book or a
`cad/process` traveler), an ISO 2768 tolerance block (#290), DRO-free setups (a DRO and edge
finder are declared shop equipment), and phosphor bronze tip gears (C67500 is on main).

## Reproducing

Scripts are in [`drive-train-cone-tip-options/`](drive-train-cone-tip-options/). From a checkout
of `a8441605f` with `uv sync --frozen`:

```bash
uv run --frozen python research/3-detailed-design/drive-train-cone-tip-options/dump_geometry.py \
  > geometry.json
uv run --no-project --with matplotlib python \
  research/3-detailed-design/drive-train-cone-tip-options/cone_tip_options.py \
  geometry.json cone-tip-options-v47.png
```

The second command also writes `cone-tip-options-v47.numbers.json` with every computed web,
wall and run-out quoted above. The contact zone is the v45 measurement (trimesh surface sampling
of `gltf/dt-drive-train.glb`, described in the v45 review); the cone stations have not changed
since.
