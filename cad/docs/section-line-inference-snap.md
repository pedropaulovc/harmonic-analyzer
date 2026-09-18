# `drawing:top_frame` D-D section: the cut plane is oblique, not the model

Leaf `2026-09-18T14:40Z`, `draw_top_frame.py:1992` -> `_hub_pocket_section` ->
`_cut_face_edge` (`:519`):

```
RuntimeError: set-pocket outer rail face: no visible cut-face line at
  {0: -214.1, 2: 3.0875877804265315} (near=None); 19 visible lines, nearest:
  (-214.1, -8.0, 2.413)->(-214.1, -18.25, 2.413)   dev=0.674;
  (-214.1, 16.25, 2.413)->(-214.1, 8.0, 2.413)     dev=0.674;
  (-212.1, -8.0, 2.263)->(-212.1, -2.416, 2.263)   dev=2;
  (-214.1, -8.0, 2.413)->(-212.1, -8.0, 2.263)     dev=2;
  (-212.1, 8.0, 2.263)->(-214.1, 8.0, 2.413)       dev=2
```

## Both Z chains

Expected (drawing): `draw_top_frame` imports `GOOSENECK_Z` from
`build_top_frame.py:184` = `SUMMING_Z` =
`cone_pivot_post_installation.MECHANISM_Z_SHIFT` = `3.0875877804265315`
(a hardcoded calibration literal, not a computed chain). Reproduced exactly.
`OUTER_X = COLUMN_X + RAIL_W_SIDE/2 = 197.0 + 17.1 = 214.1`.

Actual (section): **the reported z values are not a model station at all --
they are where an OBLIQUE cut plane crosses the part.** All ten endpoints of
the five logged lines lie on one plane containing the Y direction:

    z = -13.6445 - 0.075 * x      (max residual 4.44e-16 mm)

i.e. 4.2892 deg off the Z axis. At the rail face `x = -214.1` it gives
`z = 2.413` (dev 0.674588); at the pocket floor `x = -212.1` (= `-OUTER_X +
SET_POCKET_DEPTH`) it gives `2.263`. The 0.15 mm step between the two rails is
just 2.0 mm of X times the 0.075 slope -- NOT a stock-thickness or inch
artefact. ("2.413 = 0.095 in" is a red herring: `_cut_face_edge` prints `dev`
with `%.3g`, and z=2.4130 would print `dev=0.675`, not the logged `0.674`, so
the true face sits in (2.41309, 2.4135).) The plane reaches `GOOSENECK_Z` at
`x = -223.0945`, which is `-PLAN_HALF_X` (-223.1) to within rounding.

X is correct throughout (-214.1 and -212.1), so the section cuts the intended
feature: the model is fine. Only the plane's tilt is wrong.

## Which side is wrong: the drawing's AUTHORING path (not its expected value)

`GOOSENECK_Z` is right and must not change; the model is right. The defect is
in `_drawing_common.create_section_view`, which authored the cutting line with
a bare

    segment = sketch_manager.CreateLine(*points[0], *points[1])

with no `AddToDB` guard, so SolidWorks sketch inference / automatic relations
were free to snap the endpoints. Evidence that it is a snap and not a bad
argument: the two authored endpoints (`x = -PLAN_HALF_X - 6.0 = -229.1` and
`-INNER_X + 5.0 = -174.9`, both at `z = GOOSENECK_Z`) are BOTH off the fitted
plane, by +0.4504 mm and -3.6146 mm -- a single mistyped coordinate cannot tilt
a line about a point that is off it. At `SHEET_SCALE` 1:3 those are 0.150 mm
and 1.205 mm ON THE SHEET: screen-space-sized, which is the signature of an
inference pick (`_holes.py:440-464` documents the same class).

## When it started failing

Latent on `origin/main` (`7010782e`); `git log 7010782e..c99e0026 --
cad/scripts/draw_top_frame.py cad/scripts/build_top_frame.py cad/config` is
EMPTY, so the integration branch did not introduce it -- `6d3704a6`
(title-block text) invalidated all 96 drawing digests and forced the recipe to
re-run for the first time in a long while.

The behaviour changed at **`de2fc7af`** "recipes: author sketch closure
explicitly instead of inheriting seat inference" (2026-09-17 23:10 -0700 =
06:10Z 2026-09-18): it declares `SEAT_SKETCH_BASELINE` with
`swSketchAutomaticRelations`, `swSketchInferFromModel` and `swSketchInference`
all **True** and now RESTORES that declared constant on exit (the old code
latched and restored whatever it observed), and `_stock_fastener.py:469+`
calls `assert_seat_sketch_baseline` for every component. Those are
APPLICATION-level toggles: they outlive the document, the recipe and the leaf.
Seats had been drifting with inference OFF, which accidentally protected every
unguarded `CreateLine` in the drawing recipes. Last `drawing:top_frame`
success: 05:39Z, 31 minutes BEFORE `de2fc7af`. First failure: 14:40Z.

## `_cut_face_edge`'s tolerance is SOUND -- do not widen it

The pinned-axis match is exact (1e-6 mm) and it correctly refused a plane in
the wrong place. The logged deviations are bimodal -- 0.674 for both rail-face
lines, 2.0 for the floor lines, nothing between -- so no threshold accepts the
right line without also accepting the floor of an obliquely cut pocket, and
`near=None` correctly declined to guess between the two equidistant +/-y
candidates. Widening it would silently ship a drawing whose every sectional
dimension is measured on a 4.3 deg oblique plane.

## Fix (this branch)

`create_section_view` now creates the cutting line with
`ISketchManager.AddToDB = True` (restored in `finally`), READS THE ENDPOINTS
BACK off the `ISketchLine` and raises if either moved more than 1e-9 m (a
declined preference write is silent, so suppression is not evidence), and
selects the segment explicitly via `ISelectionMgr.Select4` because
direct-to-DB creation does not leave it selected -- the `CreateSectionViewAt5`
precondition the old docstring relied on.

## Same class, still unguarded (outside this patch)

Raw drawing-sketch creations with no inference guard:
`draw_top_frame.py:427` (`CreateCenterLine`, same parent view, created BEFORE
the section -- itself a snap target) and `:856` (`CreateCircle`),
`draw_arbor_pedestal.py:282`, `draw_cone_swing_platform.py:153`,
`draw_cylinder_gear.py:155`, `draw_rocker_arm_support.py:234`,
`_stock_trim_drawing.py:69`. `test_sketch_preference_baseline.py` only walks
`DIAGNOSTICS_DIR.rglob("*.py")` (lines 36-37, 589-600), so none of the drawing
or build recipes are audited at all -- widening that scan is the durable fix.

## The one COM measurement that would close the loop

With the drawing open on a seat: read the D-D cutting line's sketch segment
endpoints and `GetRelationsCount` / its relations, the `IDrSection` plane
normal, and the seat's `swSketchInference`, `swSketchAutomaticRelations`,
`swSketchInferFromModel` values plus `ISketchManager.AddToDB`. That names the
entity the endpoints snapped to; it does not change the verdict.
