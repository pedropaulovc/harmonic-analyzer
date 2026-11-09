# Cone tip options and drive-train DFM

> **Proposal, not current status.** Nothing here is in CAD. The decision it feeds is
> [#1649](https://github.com/pedropaulovc/harmonic-analyzer/issues/1649); track the work on the
> [Harmonic Analyzer project](https://github.com/users/pedropaulovc/projects/1).
>
> This replaces §6 and §7 of the [v45 review](drive-train-v45-review.md). It judges main
> `a8441605f` (2026-11-09, after v47) by
> [`cad/docs/drawing-guidelines.md`](../../cad/docs/drawing-guidelines.md) as rewritten on
> 2026-11-08, with two owner directions given on 2026-11-09:
>
> - **T006's web is best effort.** T006 is the hardest part on the machine; rule 17's .060 floor
>   is a goal there, not a gate.
> - **Soft solder may carry the tip's drive torque,** which is minimal. Rule 23 would otherwise
>   exclude solder from a drive-torque joint.
>
> Both still need to be recorded as owner exceptions; the table below lists them. All values
> are inches and are read from `cad/scripts` and `cad/config` on that commit (see
> [Reproducing](#reproducing)).

![Cone tip: main today, webs by option, options C1, C2, A and B, cutter run-out, and the exceptions
each option still needs](drive-train-cone-tip-options/cone-tip-options-2026-11-09-r2.png)

## Where main stands

The drive-train sheets are decimal inch (#290), and 49 of the 53 `draw_dt_*` packages enforce
machinist review. The tip geometry has not moved since v45. It ships under nine tip-related
owner exceptions, four of them waiting on #1649:

| ID | what it accepts |
|---|---|
| DT-03 RV-01 | T006/T012 Ø.0310 D-bore, AF .0170: no hobby route to cut or check |
| DT-03 RV-02 | no process word on any cone-gear D-bore (all 20 sheets) |
| DT-03 RV-03 | T012 web .0797, under the .080 target |
| DT-03 RV-04 | T006 web .0256, under the .060 floor, "accepted until #1649" |
| DT-04 RV-01 | Ø.0310 × 1.32 terminal land, L/D 43, flat AF .0170 |
| DT-04 RV-02 | "TURN THE TIP LAND WITH TAILSTOCK SUPPORT" note |
| VN-54 RV-01 | Hole Wizard callout places written at drawing time |
| DT-21 RV-01 | Hole Wizard callout places written at drawing time |
| DT-00 DT-03 | VN-55 #10-32 adjuster engages .190 (1.0D), under 1.5D (#975) |

Tip-gear material is already C67500 manganese bronze for T006–T024 and C36000 brass from T030,
which matches the book's "more yellow ... harder metal". This review keeps it.

## What any option must respect

| | value |
|---|---|
| T006 root, minimum envelope | Ø.0840 |
| T012 root, minimum envelope | Ø.1922 |
| Contact zone on each band (v45 GLB) | .087–.209 from its big-end face |
| T012 shoulder above T006's root | .101 |
| Full-depth reach of a Ø1/4 cutter from that shoulder | .123, more than the .087 available |

- **Best-effort web means no bore in T006 when a design can avoid one.** Any bore leaves T006
  under the floor: .0256 at today's .031, .0099 at 1/16. A T006 cut solid with its own spigot or
  arbor has no web to fall short.
- **T006 must be cut before anything larger sits next to it.** With T012 beside it, no rotating
  cutter reaches full depth in the contact zone. T012 can always be cut next to a finished T006,
  because T006's OD (.170) is inside T012's root (.192).

## Moving the tip block

Options A, B, C1 and C2 end the shaft about .29 past T006's north face, not 1.32 past it. MHA-DT-21
therefore moves .42 south, so its adjuster still reaches the pivot. The moved block's south face
sits .200 from T006's north face.

- **Drum bank.** The nominal air from the moved block's south face to G19's back face is
  .195 (4.95 mm), over the P1 swing angles the VN-54 air proof sweeps. That is more than VN-54's
  body has today (.144 nominal, .092 proved worst case).
- **Bushing.** The Ø.225 × .160 brass bushing on the pivot has .055 nominal air (VN-54's nose
  has .069 nominal and .026 proved worst case). Estimate: about .01 at the worst case. Before
  CAD, add the bushing and the block as tiers in `dt_tip_collar_air`'s proof.
- **Platform.** The block still sits on MHA-DT-20. Its .335 half width is inside the plate's
  .42–.47 west and .63 east half widths at the new station. The hold-down hole in DT-20 moves
  .42 south with it.
- **Adjuster.** A long 1/4-28 slotted, domed end screw replaces VN-55, in the period form. Its
  inner end has a Ø.0625 reamed pivot hole (wall .072) and takes the bushing's thrust, and the
  existing pinch slit locks it (rule 23, adjuster). DT-21 deepens from .380 to .430, so the screw
  gets 1.5D past both mouth countersinks. That retires DT-00 DT-03.
  - A #10-32 screw would leave .043 of wall round the pivot hole.
  - A 5/16-24 screw would clear the .080 target, with DT-21 about .52 deep.

## Options

### C · Gears cut alone, sweated into a tip cluster

Common to both variants:

- **T006** becomes its own small C67500 part: a Ø.0625 spigot, the six leaves, and a Ø.0625
  pivot. Spigot and pivot sit .0108 under T006's root, so the DT6-FORM1 fly cutter runs off on
  both sides.
- **T012** is reamed round Ø.0625 and cut alone on a mandrel, giving a .0646 web.
- **Joints** are sweated face to face at the big-end faces, in the untouched .087, phased by a pin
  through lined-up tooth spaces. Reheating takes them apart.
- **Tip end.** The pressed brass bushing, the moved DT-21 and the 1/4-28 end screw, as above.

The variants differ in what centres T012 and T006 on the shaft.

#### C1 · Long spigot into DT-04 (recommended)

- T006's spigot is .73 long. It runs through T012 and T018 into a reamed Ø.0625 × .19 socket in
  the end of DT-04's Ø.250 land. DT-04 ends at T024's north face and loses lands 3 and 4.
- T018 is reamed round Ø.0625 (web .127). T024 keeps its flat, and T024, T018, T012 and T006 are
  sweated face to face. The socket fit locates the cluster; the solder carries the torque.
- The socket's wall to the T024 flat is .0735, a minor rule 17 shortfall.
- The cost is the spigot: .73 of Ø.0625 (L/D 12), turned between centres with a steady or
  tailstock support.

#### C2 · Soldering jig

- DT-04 loses only its Ø.031 land and ends where it does today under T012. T018 keeps its D-bore
  and flat on DT-04's Ø.125 land.
- T006's short spigot (.27) centres T012, but nothing fits the T012/T006 pair to DT-04. A
  stepped-bore jig on the T018, T012 and T006 tooth tips holds them true while the solder sets,
  so their run-out is whatever the jig holds. The jig needs its own drawing.

**Why C1 wins.** Every gear is cut alone on an ordinary mandrel, a fit rather than a jig sets the
tip's concentricity, and soft solder is a period method. C2 leaves DT-04 nearly untouched but
moves concentricity onto a jig.

### A · T006 cut on a bronze tip arbor

- A C67500 arbor replaces DT-04's lands 2–4. It carries the T024 and T018 seats with their
  flats, a Ø.0625 T012 seat, the integral T006 and the pivot.
- Its Ø.125 spigot is bonded with LOCTITE 638 into a reamed hole in DT-04's Ø.375 land; the wall
  to that land's flat is .095. T012 is sweated to T006 (web .0646).
- It has one fewer soldered face than C1, at the cost of a longer slender part turned between
  centres.

### B · One-piece T006–T018 arbor, T012 and T006 planed

- As A, but T018, T012 and T006 are teeth on the arbor itself. T018 can still be milled, because
  T012's OD (.286) is under T018's root (.317). T012 and T006 are planed: 18 tooth spaces, with a
  .06 relief groove at each big-end face.
- No joints in the tip. The cost is the planing route: the declared shop is a lathe and a mill,
  so a reviewer may refuse it under rule 16.

## Exceptions after each option

"Retired" exceptions disappear with the geometry that caused them. "New or changed" are what the
owner would record. Callout-place exceptions (DT-21 RV-01, DT-20 RV-03) stay wherever the parts
keep drawing-side Hole Wizard places; they are re-scoped to the moved holes.

| option | retired | still needed | new or changed |
|---|---|---|---|
| Main today | — | all nine above | — |
| **C1 (recommended)** | DT-03 RV-01, RV-04; DT-04 RV-01, RV-02; VN-54 RV-01; DT-00 DT-03 | DT-03 RV-02 (T024–T120 D-bores); DT-21 RV-01; DT-20 RV-03 | DT-03 RV-03 becomes T012 web .0646; new DT-00: soft solder on the T024–T018–T012–T006 drive joints (rule 23); new DT-04: socket wall .0735 to the T024 flat (rule 17 minor); new end-screw sheet: pivot-hole wall .072 (rule 17 minor; none with 5/16-24) |
| C2 | DT-03 RV-01, RV-04; DT-04 RV-01, RV-02; VN-54 RV-01; DT-00 DT-03 | DT-03 RV-02 (T018–T120 D-bores); DT-21 RV-01; DT-20 RV-03 | DT-03 RV-03 becomes T012 web .0646; new DT-00: soft solder on the T018–T012–T006 drive joints; end-screw wall .072; plus a drawing for the soldering jig |
| A | DT-03 RV-01, RV-04; DT-04 RV-01, RV-02; VN-54 RV-01; DT-00 DT-03 | DT-03 RV-02; DT-21 RV-01; DT-20 RV-03 | DT-03 RV-03 becomes .0646; new DT-00: solder on the T012–T006 joint; end-screw wall .072 |
| B | DT-03 RV-01, RV-03, RV-04; DT-04 RV-01, RV-02; VN-54 RV-01; DT-00 DT-03 | DT-03 RV-02; DT-21 RV-01; DT-20 RV-03 | end-screw wall .072; possibly a rule 16 acceptance for planing |
| #1649 A, drill-rod tip | DT-04 RV-02 | DT-03 RV-01, RV-02, RV-03, RV-04; VN-54 RV-01; DT-21 RV-01; DT-00 DT-03 | DT-04 RV-01 becomes a rod-socket wall of .047, under the floor |
| #1649 E, 1/16 land | DT-04 RV-02, if L/D 21 turns without support | DT-03 RV-01, RV-02; DT-04 RV-01; VN-54 RV-01; DT-21 RV-01; DT-00 DT-03 | RV-04 becomes T006 web .0099 (worse than today); RV-03 becomes .0640 |
| #1649 F, soldered round bore | DT-03 RV-01 (no D on T006, T012) | DT-03 RV-02, RV-03, RV-04; DT-04 RV-01, RV-02; VN-54 RV-01; DT-21 RV-01; DT-00 DT-03 | new DT-00: solder on T006 and T012 to the land |

#1649 D (broached D) changes no exception: it only names a route for RV-01. #1649 B (pinion
wire) is not pursued: clock pinion wire is a cycloidal leaf, not DT6-FORM1's 20° profile against
the 120T drum, and no 48DP stock turned up.

Two owner rulings also need amending, not excepting:
- **2026-09-28** (one flat per gear land; no gear bonded). C2 and A drop T012's flat and solder
  T012/T006; C1 also drops T018's flat and solders T018 to T024. B drops the T012 and T018 flats.
- **U40** (integral Ø.031 land). It retires in A, B, C1 and C2.

## Owner decisions

1. C1, C2, A or B. C1 is recommended: a fit centres the tip, every gear is cut alone, and the
   solder is period. B retires one more exception (RV-03) but needs planing.
2. Move DT-21 .42 south and deepen it to .430 for a 1/4-28 end screw (or .52 for 5/16-24),
   replacing VN-54 and VN-55 with the brass bushing and end screw.
3. Record the solder exception and the T012 .0646 web.

## Drive-train DFM recommendations (replaces v45 §6)

"Verified" means read on main `a8441605f`; the rest need a look at the current sheet first.

1. **Cone tip: option C1** (above).
2. **Stop MHA-DT-21 turning on its single screw**
   ([#1178](https://github.com/pedropaulovc/harmonic-analyzer/issues/1178), open). Rule 23
   (static clamp): a one-screw part whose turning changes a setting needs a dowel, tongue, step or
   second screw. Moving the block is the moment to add one; turning the end screw torques it.
3. **Re-check the crank drive gear route.** The 13° helical 64T (#1272, verified) needs a 37.24
   lead, which means a dividing head geared to the table screw. The declared shop has none, and
   MHA-DT-03-TL-00 is a plate kit for plain indexing. Under rules 16 and 21 the owner either names
   that route or allows a spur 64T meshed obliquely at 13°, like every cone mesh. Run the
   `dt_mesh_checks` contact gates first.
4. **Give every jig and gauge a drawing** (the declared shop has "no jig the package does not
   tell the builder to make"):
   - enrol the indexing kit, whose review is OFF;
   - draw the tip cluster's phasing pin jig;
   - draw a D-flat plug gauge per land size, since the .0004 across-flat bands are narrower than
     the milled-width row (±.001);
   - draw the cylinder gear's .340 eccentric offset-turning fixture (±.0010).
5. **Matched pairs where a stack depends on two loose parts** (rule 19): arbor pedestals, pinion
   brackets and pivot blocks. Make each pair together, or give the step a feeler-set gap. This
   came from the v45 sheets; re-check the inch sheets.
6. **Cone pivot post mounting at print-worst**
   ([#1134](https://github.com/pedropaulovc/harmonic-analyzer/issues/1134), open), with the deep
   2X Ø.281 holes; rule 17 counts drill wander.
7. **Compass words ENFORCE review missed** (rule 26, verified): DT-04's
   `COLLAR NORTH FACE / 64T SEAT`, and VN-68's `NORTH FACE … NORTH MHA-DT-02 STRAP`. Options C1 and C2
   remove the first. The second belongs in an MHA-DT-00 step (#930).

Dropped from the v45 list because the rubric now says otherwise: a datum and frame scheme
(rule 5), operation plans and named tools on the prints (rule 7: route them in the book or a
`cad/process` traveler), an ISO 2768 block (#290), DRO-free setups (the DRO is declared shop
equipment), and phosphor bronze tip gears (C67500 is on main).

## Reproducing

Scripts are in [`drive-train-cone-tip-options/`](drive-train-cone-tip-options/). From the root of
a checkout of `a8441605f` after `uv sync --frozen`:

```bash
D=research/3-detailed-design/drive-train-cone-tip-options
uv run --frozen python $D/dump_geometry.py > geometry.json
uv run --frozen python $D/block_air.py > air.json
uv run --no-project --with matplotlib python $D/cone_tip_options.py geometry.json air.json \
  cone-tip-options-2026-11-09-r2.png
```

The last command also writes `cone-tip-options-2026-11-09-r2.numbers.json` with every web, wall, air and
run-out quoted above. The air figures are nominal, through `dt_tip_collar_air`'s own pose and
support functions. The contact zone is the v45 surface-sampled measurement; the cone stations
have not changed since.
