# Photo re-derive pass 2 -- chapter-by-chapter delta audit (2026-09-02)

> Not a status board (see the GitHub project). This is the working delta list
> of the second photo-fidelity pass (PR #651, stacked on #650): every place the
> model still read wrong against the book plates and the engineerguy stills,
> with what was done. Source of truth for each fix is the build script it names.

Method: the ch30 eight views, the per-chapter plates (ch11-ch25) and the 4/4
video keyframes were compared against meshprobe renders of the v31 GLB at
matching poses (`scratchpad/audit/*.png` during the session) and against the
release comparison gallery. Colour/texture deltas were deliberately skipped
(user: geometry first).

## Fixed in PR #651

| # | area | plate | delta | fix |
|---|---|---|---|---|
| 1 | crank handle | ch11 p.14 | 90 mm baton vs a 44 mm egg, 25 across | `crank_handle_spec` |
| 2 | crankshaft | ch12 p.19 | 34 mm bare stub out the column back vs a capped end just past the pinion | `crankshaft_spec` 150 -> 122 |
| 3 | cylinder end discs | ch13 p.23/25, ch25 p.67 | plain brass washers at both ends of the gear sandwich missing | `build_cylinder_end_disc` (O55: a O60 grazed the cone-tip bushing) x2 against gears 0 and 19 |
| 4 | rocker pivot supports | ch14 p.27 | chrome ball pillars vs black foot-and-ear brackets; south pillar 19 mm past the support's end in mid-air | `build_pivot_bracket` x2 on the support, shaft 203 -> 170 centred |
| 5 | measuring stick | ch16 p.34-37 | 80 mm / 11-tick scale vs 142 mm with tenths; no stop block | `build_measuring_stick` 14.2/division + tenths; `build_measuring_stick_stop` |
| 6 | pinion rig | ch25 p.68 | straps 43 x 18 leaning 50 deg with the blocks 33 mm east vs ~28 x 15 near-vertical straps with the blocks under the drum | `pinion_bracket_geometry` C2C 28 / W 15 / stud 6 above the pivot; block, spring, base taps re-solved |
| 7 | pinion T-handle | ch25 p.68 | O23 x 14 drum vs ~O15 ball, cross rod 85 vs ~65 | `pinion_handle_geometry` |
| 8 | transgear latch | ch23 p.58, 4/4 video | no spring latch on the swing cluster | `build_latch_strip` on the bar's front face (SUPERSEDED in pass 3 by `build_latch_hook`, the curved leaf the keyframes show) |
| 9 | pedestal arbor ends | ch13 p.23 | bare bore vs a domed cap screw | `build_dome_cap_screw` x2 |
| 10 | knife bearing block | ch18 p.42 | 34 x 44 block vs ~24 x 33 | `build_knife_mount` bore O16, 24 wide |

Gate result 2026-09-02: full build green on 620cdb70; ch30 p002/p004 and the
ch25/ch13/ch23/ch14/ch16 close-ups re-rendered from the export match the plates.

## Seen, still open (ordered by visibility)

- Rocker arms radiate in plan from the pivot (ch14 p.26-27, 140 mm at the
  tips vs a tight stack at the pivot); model keeps them parallel. Needs the
  channel mate contract rewritten -- see `rocker-arms-fan-in-plan.md`.
- Amplitude bar feet (ch15 p.31 `page002_img01`): each bar ends in a thin
  foot tab wider than the bar, offset to alternating sides. Re-read 2026-09-02:
  the tabs alternate BECAUSE the rocker arms fan in plan (the arm under each
  foot sits off the bar's own plane by a growing z offset), so the feet are
  part of the fan rewrite, not a standalone part -- do them together.
- Summing lever knife mounts (ch18 p.42 crop, ch19 p.44/45 front views):
  re-read 2026-09-02 -- the front views show the block UNDER the rail with the
  stud's hex nut ON TOP of the rail, which is what the model builds. The black
  bent strap in the crop is the channel-spring bank's anchor strip, not a
  hanger. Remaining delta is only a hex-head screw on the block's front face
  (small; not worth a part until the spring anchor itself is re-derived).
- Magnifying wheel hub nut (ch21 p.51): hex nut on the axle tip vs a round
  collar (blocked on the axle drawing's CollarDia contract).
- Crank column ~8 mm taller than the plate reads (within the photo-scale
  error band; the harvested `cone_pivot_post_spec` v2 post pins Y_CRANK, so
  not worth the cascade without a better read); pedestal foot bolts on top
  of the rocker support; base top-edge round instead of a chamfer.
- Summing-lever hub: the ch18 crop reads anywhere from ~O13 to ~O30
  depending on which block face is taken as the 24 mm scale -- UNVERIFIED,
  leave `CYL_R` 12.7 until a calibrated plate (ch30 p008) is measured.
- Wheel rim section.
- Pen v-block groove: marker axis 0.25 below the roof by the clearance
  convention rather than resting on it.
