---
name: drawing-spec-purity
description: "A draw_*.py holds LAYOUT only. Tolerance bands go on the MODEL dimension (set_dimension_*_tolerance); Ra grades come from _surface_finish; fit bands from _fit_limits via deviations(). Callout text is FROZEN — SetText survives a unit switch and lies."
metadata:
  type: project
---

Settled 2026-07-28 from a 10-sheet audit (45 verified findings; report in the
scratchpad, `docs/tolerance-gdt-assessment.md` is the natural home).

**The rule.** A `draw_<part>.py` owns sheet coordinates, view centres, view
scale, text placement, leader anchors and log labels. Every NUMBER that
describes the part — a nominal, a fit band, a roughness, a GD&T zone — belongs
to `<part>_spec.py`, a shared catalog, or the model itself.

**Why it is not cosmetic: the drawing-side paths are FROZEN TEXT.**

- `set_dimension_callouts` → `IDisplayDimension.SetText(3|4, s)` appends a
  literal beside a natively-rendered numeral. SolidWorks never re-renders it.
- `add_feature_control_frame` → `_gtol_frame_xml` writes the caller's
  `tolerance="0.03"` verbatim into a `<PrimaryToleranceValue>` XML text node.
- `add_surface_finish` → `SetText(8)` freezes `Ra 1.6`.

So when issue #290 flips generated drawings to inch display, every one of those
strings keeps its mm/µm number and silently means something else — `+0.00/-0.02`
becomes twenty-five times looser, `Ra 1.6` reads as 1.6 **µin** (the ips
convention; `title_block.yaml` already carries `value_uin: 125` beside display
`Ra 3.2`, and nothing reconciles them). A native model tolerance re-renders;
`SetText` does not. That is the whole argument.

**The mechanism already existed and was used by 2 of ~100 build scripts.**
`_drawing_marks.set_dimension_{symmetric,bilateral}_tolerance` — read-back
verified, `SetValues` in METERS internally — shipped in
`build_cone_pivot_screw.py` (whose drawing consequently ships
`DIMENSION_CALLOUTS = {}`) and `build_fillister_screw.py`. Everything else
leaked its bands into callout text. Propagating it, not building it, is the fix.

**Transposition trap — use `_fit_limits.deviations(band)`.** `_fit_limits`
bands are written `(upper, lower)` (how a print quotes a fit, ASME Y14.5
§2.3.2); `set_dimension_bilateral_tolerance` takes
`(lower_deviation_mm, upper_deviation_mm)`. Both orderings type-check and a
silent swap INVERTS the band. `deviations()` is the one chokepoint that
transposes; no call site may do it by hand.

**Catalogs, not per-part constants.** 42 `roughness_ra` literals across 39
sheets expressed a TWO-value vocabulary → `_surface_finish.py` (`GROUND` 0.8,
`MACHINED` 1.6 µm), a pure-data sibling of `_fit_limits` importable from both
tiers without tripping `check:partiso`. Creating 39 per-spec constants would
have institutionalised the duplication at 39 new addresses.

**Move the value and its NOTE in the same commit** — use `_fit_limits.band_text`. The `*_spec.py`
`DRAWING_NOTES` are a second copy: the nominal is f-stringed while the band
beside it is hardcoded (`f"{HANDLE_LENGTH:.2f}+0.00/-0.25"`). Render the note
from the same constant via `_fit_limits.band_text(band)`, and PROVE the rendered
text is byte-identical before and after — that is what makes the relocation a
refactor rather than a print change. `band_text` deliberately keeps a nil
deviation's SIGN (`-0.00`), which is what the released sheets print; Y14.5
§2.3.2 prefers a bare `0`, and switching is a deliberate drawing change to make
on its own, never a side effect of moving a constant.

**STATUS 2026-07-28 — partially applied.** 4 parts migrated (transgear-stub,
cone-gear-shaft, cone-tip-adjuster, crank-handle). Still outstanding: **33
sheets** carry a band in `DIMENSION_CALLOUTS`, **23 specs** hardcode a band
inside `DRAWING_NOTES`, and all **125** `tolerance="..."` FCF literals are
untouched (the `GEOMETRIC_CONTROLS` spec-table convention and the
`add_feature_control_frame` row overload were NOT built).

**Tests must assert IDENTITY, not source text.** `test_*_drawing.py` pinned
literals (`assert 'roughness_ra="1.6"' in source`), which makes the literal
load-bearing and turns every improvement red. `_drawing_contract.py` provides
`assert_sheet_references(module, name, expected)` and
`model_toleranced_dimensions(build_module)` (AST, not substring — the calls span
lines and a text assertion pins the formatting too).

**GD&T is still authored per-sheet** — model PMI is now PROVEN authorable
(datum + gtol + XML fill + save; the InsertDatum wedge was session state — see
[[dimxpert-authoring-probe]]), but the sheet-import leg
(`InsertModelAnnotations3` + DimXpert filter) is untested, so per-sheet
authoring stays. Not a prerequisite either way: the unit and drift hazards
close entirely with the spec relocation above.
