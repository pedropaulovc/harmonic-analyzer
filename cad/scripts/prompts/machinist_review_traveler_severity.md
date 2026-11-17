Pass 2 — classification. Assign each distinct candidate exactly ONE defect
type: apply the specific cases named in the table first, and use this
precedence only when one defect meets more than one type:

    contradiction > missing > unbuildable > over_specification
        > presentation > shortfall > polish

Then file it in that type's category. Never file one defect twice, never
invent a hybrid category such as "minor clarity", and never move a finding to
a lower category because it feels minor, because an experienced machinist could
work out the intent, or because the fix is easy — the type decides.

| type | what qualifies | category |
|---|---|---|
| contradiction | Traveler against companion part drawing: part number, revision, material, unit, feature count, size, tolerance band, datum reference or `SHARP` / edge-break requirement that disagrees (rules T1, T2, T14, 25). Traveler against itself: op text vs. `Tool / settings` column vs. `Holding` / `Datum` vs. setup diagram; broken `face 1` / `face 2` or reference-edge tracking across flips/reseats (rule T7); a `G54 unchanged` claim falsified by an intervening move or layer without stated program/operator offset (rule T6); conflicting tool `T` numbers, program names or clamp/plug states (rules T5, T8) | blockers |
| missing | A manufactured feature or toleranced requirement on the drawing with neither an producing op nor a printed check / explicit `process-held` statement with registration check (rule T2); a shop-made fixture, sub-plate, plug, soft jaw or template that setups depend on with neither a drawing/make reference nor printed interface dimensions (rule T3); an adhesive or tape hold whose product/grade is unnamed when strength or breakthrough depends on it (rule T3); a fixed-Z cut that depends on variable stock size with no incoming measurement gate and stop (rule T4); an axis zero placed on no physical feature (rule T6); a flip/reseat that leaves face or datum-edge orientation ambiguous so a part can be mirrored or mis-datum'd (rule T7); a CNC traveler with no first-article program/clearance prove-out step (rule T8); a drawing-requirement check with no acceptance criterion, an instrument outside T0 (rule T11), or a check whose named instrument cannot physically measure the toleranced quantity as written because slant/offset geometry shifts the reading outside/across the band with no workable route printed — arithmetic shown (rule T10); unresolved template placeholders (`{{…}}`, `?`, `NaN`) | blockers |
| unbuildable | An arithmetic-proven physics, clearance or sequence failure from printed values (rule T9): cutter or holder hitting a clamp, fence, stop, screw head or vise jaw; a twist-drill `0.3D` point or reamer lead leaving an uncut web or bottoming in a relief floor; a through-cut failing to part the skin or gouging a non-sacrificial fixture plate; live side clamps pinching freed waste into a cutter; hogging one side of thin cold-finished bar to final size without stress release where flatness/thickness bands govern; an in-process cut-to-number band narrower than "What the shop holds" with no fit/offset route (rule 4) | blockers |
| over_specification | Final acceptance limits tighter than the part drawing's (rule T15); un-toleranced features turned into pass/fail final gates instead of labelled diagnostic/in-process checks; fixtures or metrology wildly disproportionate to a loose band; multi-sentence rationale essays inside op cells; restating the `Tool / settings` column verbatim without adding handoff detail; production QA paperwork — FAI/AS9102, sign-offs, lot/heat tracking, material certs, SPC, calibration logs or PPE boilerplate (rule T15) | over_specification |
| presentation | An op cell exceeding six printed lines on the sheet image or bundling unrelated setup stages without splitting into numbered ops (rule T12; list every offending op number); a check and its remedy merged or an in-process rework with no concrete action (`goes back for a skim` on a fixed-Z program without saying how, rule T10); a straightening or surface-plate flatness step with no concrete acceptance or recheck (rules T10, T17); missing `Z0` / tool-setter reference explanation or reset condition where a novice would have to guess (rule T6); clearance-governing hardware or clamps named only generically (`washer and screw`, `Pitbull clamps` without size/model, rule T3); a setup/inspection diagram leader landing in blank air or at an off-centre curved-edge station where the printed centreline band does not hold (rule T13); a legend word or fill used inconsistently or colliding with the part's own name (`strap` meaning both the part and a clamp while hardware uses that fill, rules T12, T13, 26); a CNC sub-op written like a separate manual start when it runs continuously inside one file (rule T12); hands-in action not tied to a named pause where non-hazardous, or clipped/overlapping rendered text (rule T13) | clarity |
| shortfall | A departure covered by a supplied traveler `machinist_exceptions` entry (`kind: minor`), quoted with its value and exception id | minor |
| polish | Minor number/unit formatting (`0.010` vs `.010`, `0.5 ft-lb` vs `6 in-lb`, `1-1/2` vs `1 1/2`), minor machine-subtitle wording variation across setups, a direction-only `+X/+Y` triad placed beside rather than on `X0/Y0` when `Datum:` defines the zeros, omitting `T` numbers in the top Tools table when each op names both `Tn` and the tool, oiling a drill at low RPM, or style preferences that break no explicit rule | minor |

TRAVELER ADJUDICATION RULES (FOR BOTH REVIEWER AND JUDGE)
1. **Companion part drawing is reference-only:** Confirm cross-document claims
   by inspecting both the traveler sheets and any attached part-drawing sheets,
   but classify any critique of the part drawing's own tolerances, notes, views
   or layout as `misread` (judged by the drawing's own review).
2. **Deterministic gates own cutting & holding math:** Reject as `misread` any
   claim that re-argues spindle speed, feed, chip load, DOC/WOC, deflection,
   vise grip, adhesive bond strength, machine travel, pecking, G-code retract
   safety or declared gauge resolution, unless two printed numbers on the sheets
   contradict each other.
3. **Arithmetic for physical & measurement claims:** Confirm a collision,
   clearance, breakthrough, drill-point or caliper-slant/measurability blocker
   only after working the arithmetic yourself from printed numbers and showing
   it in `reason`. If any ordinary configuration works, mark `misread`.
4. **PDF text-layer artefacts are `misread`:** Headless browser PDF text layers
   frequently split or double letters (`ToTools`, `off ff`, `Z .1 165`,
   scrambled SVG labels). Judge rendered pixels via `view_sheet` and `crop`;
   any claim grounded only in text-layer corruption is `misread`.
