# Fix-relation retirement — B0 inventory & migration checklist

Working document for the migration to semantic anchoring (point refs +
point-to-point driving dims, SolidworksMCP-python PRs #55/#56). Deleted when
B4 closes. End state: **zero `fix` relations** in `cad/scripts` except an
explicitly justified whitelist, verified by `grep -rn '"fix"' cad/scripts/`.

## Fix emitters (the only two, verified by grep — no build script calls
## `add_sketch_constraint(..., "fix")` directly, including via relation loops)

| # | Emitter | Sites | Migration |
|---|---------|-------|-----------|
| 1 | `_common.define_circle` (fix + driven diameter) | 190 calls / 68 scripts | B1: rewrite to coincident/`*_points`/distance-dims to origin + driving diameter — signature unchanged, all call sites migrate for free |
| 2 | `_common.ensure_fully_defined` escalation loop | 79 non-empty `fix_entities` call sites / 58 scripts | B1: gate behind `allow_fix_escalation=False` with loud WARN; B2 rebuilds expose which scripts actually relied on it; B3 redesigns those; flag + `fix_entities` param deleted at B3 close |

Two shared-module consumers route through emitter 2 with **equation-driven
curves** — the whitelist class (fixed equation curves have no free
endpoints; nothing to dimension):

- `_common.add_spring_end_hooks` — `fix_entities=[lead_line, loop_arc]`
  (build_channel_spring, build_counter_spring);
- `_gear.cut_tooth_gap` — `fix_entities=gap_curves`, six involute/chord/arc
  curves (every gear-building script, caught at B1 validation).

Both carry `allow_fix_escalation=True` with an inline comment for the
migration window. B3 attempts merge/coincident of curve endpoints to
dimensioned geometry first, keeps `fix` with the justification comment only
if no semantic scheme fully defines the sketch.

## Per-script burden

- 68 scripts use `define_circle` → zero per-script edits (B2 mechanical
  rebuild in batches of ~10, volume + fully-defined gates assert).
- 58 scripts pass non-empty `fix_entities`. Escalation fires only when the
  sketch is under-defined after its relations/dims, so this list splits at
  B2 rebuild time:
  - escalation never fired → rebuild passes untouched, only the dead
    `fix_entities=` argument is removed in B3 cleanup;
  - escalation fired → rebuild fails loudly → script joins the B3 redesign
    list (origin-anchored scheme: merged endpoints, segment relations,
    per-segment dims, ONE point-anchor per chain).
- 14 of the 58 fix a revolve **centerline** (`fix_entities=[centerline, ...]`):
  replace with coincident(centerline.start → origin or dimensioned point) +
  vertical/horizontal on the centerline.
- Common `fix_entities` shapes: `lines` (16), `[centerline, ...]` (13–14),
  `outline` (7), `entities` (5), `head` (3), plus one-offs (strap, notch,
  gap_curves, channel, block, web, top_rail, spoke_lines, slot, ...).

## Order of work

1. **B1**: rewrite `define_circle` + `ensure_fully_defined`; new helpers
   `anchor_point_to_origin` / `dimension_between`; update module-docstring
   recipes (lines 15–34). Validate on 3 representative parts before batching.
2. **B2**: rebuild all circle-using scripts serially (~10/batch), triage
   over-defined failures via `get_over_defining_relations` (expected culprit:
   circles already concentric/coincident now double-anchored — drop the
   redundant anchor dims, keep the semantic relation).
3. **B3**: redesign the scripts whose escalation fired (one commit each);
   attempt semantic scheme on the spring hooks; delete the escalation branch,
   the `allow_fix_escalation` flag, and every dead `fix_entities=` argument.
4. **B4**: full 90-script rebuild, top-level assembly, zero-interference,
   render comparisons. Closing sweep: `grep -rn '"fix"' cad/scripts/` must
   return only whitelisted, comment-justified sites (target ≤ 1).
