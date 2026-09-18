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

## Fix: one idiom, every drawing-sketch call site

`_drawing_common` now owns the idiom and every drawing recipe uses it. There is
no second spelling: the hand-rolled `AddToDB` set/restore no longer appears
anywhere in the drawing tier, and `test_sketch_preference_baseline.py` rejects
it rather than accepting it.

- `sketch_geometry_direct_to_db(sketch_manager)` -- contextmanager, sets
  `AddToDB` and restores it in `finally`. It reads the previous value LIVE off
  the sketch manager: `AddToDB` is an APPLICATION-level preference, so a value
  captured earlier can be one a previous leaf left behind. Eight hand-rolled
  copies were four lines each that had to get `bool()`, the `try` and the
  `finally` independently right; a copy that loses its restore under a later
  early `return` leaves the whole seat direct-to-DB.
- `assert_sketch_line_placed` / `assert_sketch_circle_placed` /
  `assert_sketch_geometry_placed` -- the read-back, refusing any drift above
  1e-9 m. This is the load-bearing half: a preference the seat DECLINES to
  write fails silently, so entering the block is not evidence. The comparison,
  the tolerance and the message are shared; the TRAVERSAL is per geometry
  type, because a line carries `GetStartPoint2`/`GetEndPoint2`, a circle a
  centre and a radius, and a created sketch point IS the point. Forcing one
  traversal over the three reaches for a member the entity does not have and
  surfaces as an `AttributeError` -- a guard that reads like a code bug instead
  of a placement refusal. A circle is checked on centre AND radius, not on its
  perimeter point: that catches a snap of either authored coordinate without
  depending on where SolidWorks puts a full circle's start point.
- `select_sketch_geometry` -- explicit `ISelectionMgr.Select4` plus a
  selected-count check. The guard CREATES the need for this: `AddToDB = True`
  is precisely what removes `CreateLine`/`CreateCircle`'s leaves-it-selected
  side effect that `CreateSectionViewAt5` and `CreateDetailViewAt4` consume.
  A site that worked *because* inference left the segment selected breaks the
  moment it is guarded, unless the selection is added.

## The overshoot is the bait

Ranked by how much slack a coordinate has between where the recipe put it and
the nearest entity that can capture it:

| risk | site | geometry | overshoot |
| --- | --- | --- | --- |
| 1 | `draw_top_frame.py` `_add_view_centerlines` | 7 `CreateCenterLine` | yes -- `-2.0`/`+3.0` mm past boss extents, and the full `+/-PLAN_HALF_X` plan boundary |
| 2 | `draw_cone_swing_platform.py` `_add_cone_axis_centerline` | `CreateCenterLine` | yes -- both endpoints ON the view outline, i.e. at the extreme silhouette |
| 3 | `draw_top_frame.py` `_hub_underside_detail` | `CreateCircle` fence | partial -- centre on a model point, perimeter point a free sheet coordinate |
| 4 | `draw_cylinder_gear.py` `_notch_detail` | `CreateCircle` fence | partial -- centre in the tooth gap with a flank either side |
| 5 | `_stock_trim_drawing.py` `end_detail` | `CreateCircle` fence | partial -- centre offset off the cut face by `detail_offset_mm` |
| 6 | `_drawing_common.py` `create_view_theoretical_datum` | `CreatePoint` | inherent -- a theoretical sharp is BY CONSTRUCTION not on the geometry shown |
| 7 | `draw_arbor_pedestal.py` `_add_bore_hidden_lines` | 4 `CreateLine` | no -- every endpoint on a bore silhouette or a physical face |
| 8 | `draw_rocker_arm_support.py` `_create_view_centerline` | `CreateCenterLine` | no -- endpoints on the part's own half-extents |

A recipe's defensive habit of extending past a boundary so a cut or an axis
spans the whole feature is exactly what puts an endpoint within screen-space
snap range of the boundary entity it just cleared. D-D authored endpoint A at
`-PLAN_HALF_X - 6.0`; the fitted oblique plane reaches the requested Z at
`x = -223.0945`, and `-PLAN_HALF_X` is `-223.1` -- 0.0055 mm apart. One
endpoint captured, one free, and the line rotated about the captured one.

Sites 7 and 8 overshoot nothing and are the lower-risk end, but a coordinate
sitting exactly ON an edge is the strongest automatic-relation candidate there
is, and the next entity (the far face 2 mm away, a chamfer corner) would move
the OTHER coordinate. Both are guarded; neither is exonerated.

Corrections to this document's own earlier claim: `draw_rocker_arm_support.py`
was NOT unguarded -- `4821f797` had already hand-rolled `AddToDB` +
`DisplayWhenAdded` there. It had no read-back, so it had the protection without
the evidence. And the list omitted `_drawing_common.py`'s own
`create_view_theoretical_datum`, which hand-rolled the same shape in the very
file that now defines the idiom.

## The one COM measurement that would close the loop

With the drawing open on a seat: read the D-D cutting line's sketch segment
endpoints and `GetRelationsCount` / its relations, the `IDrSection` plane
normal, and the seat's `swSketchInference`, `swSketchAutomaticRelations`,
`swSketchInferFromModel` values plus `ISketchManager.AddToDB`. That names the
entity the endpoints snapped to; it does not change the verdict.
