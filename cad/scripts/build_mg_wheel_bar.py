r"""Reproduction script: magnifying-wheel bar (book ch. 21, pp. 50-51).

The short bar carrying the magnifying-wheel axle and the pen-hanger
strap. M6.8 ch30 8-view pass (user-confirmed): unlike the two full-width
platen rails, this bar spans only ~HALF the frame width -- every plate
shows it clamped at ONE column (the machine +x / west one) with a
free end just past the pen hanger; there is no second clamp on the far
column at this height.

Section 10 tall x 9.5 deep -- the support-bar stock (the front faces of
both bars share the machine z -138.9 plane; the 9.5 depth puts the back
face on the front clamp arc's face at -129.4, the same two-piece clamp
seat as build_pd_support_bar.py). 234 long: the clamped end runs 29 past
the west column line (the support-bar idiom -- the clamp-screw stack
bar -> front arc -> back arc needs bar over BOTH ear holes), the free
end just past the hanger. Placed IDENTITY in build_mg_magnifier_assembly at
centre x +109 (machine = local + 109): span -8..+226, covering the wheel
axle (+53) and the pen-hanger strap top with margin.

Holes (all along local Z, the machine front-back axis):
* 1x reamed axle bore at local (AXLE_BORE_X, 0) = machine x WHEEL_X, the
  mg-wheel-axle pressed in to a gauge from the front face (mg_wheel_axle_spec).
* 2x O4.4 clamp-screw through-holes flanking the column at local
  x 70.5 / 105.5 (the column line crosses the bar at local +88 =
  column +197 - centre +109; ears at +-17.5,
  _clamp_arc.EAR_HOLE_Z): heads on the bar's front face, threading into
  the back arc -- exactly the support-bar stack.
* 1x #8 close-clearance pen-hanger screw hole at local (-112, 0)
  (machine (-3, 575.7) = local + 109), taking the screw from behind
  the bar. The centre is 5.0 from the fixed free end; the standard Ø4.572
  clearance leaves 2.714 mm nominal end wall, with a 2.0 mm finished
  minimum after the hole-size and end-referenced station tolerances.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_mg_wheel_bar.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_rectangle import define_centered_rectangle
from _hole_spec import blind_cut_dia_mm
from _holes import wizard_holes
from pn_vn_hanger_screw_spec import SHANK_DIA as HANGER_SCREW_DIA
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import (
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_deviations import deviations
from mg_wheel_bar_geom import (
    AXLE_BORE_BAND,
    AXLE_BORE_DIA,
    AXLE_BORE_X,
    BAR_DEPTH,
    BAR_DEPTH_BAND,
    BAR_LENGTH,
    BAR_SIDE,
    BAR_SIDE_BAND,
    BORE_ROW_HEIGHT,
    BORE_ROW_HEIGHT_TOL,
    CLAMP_HOLE_DIA,
    CLAMP_HOLE_SPEC,
    CLAMP_HOLE_X,
    CLAMP_STATIONS,
    DRILLED_HOLE_PLUS,
    HANGER_STATION,
    LEFT_END_X,
    PEN_HANGER_HOLE_DIA,
    PEN_HANGER_HOLE_SPEC,
    SCREW_HOLE_X,
    require_hanger_end_wall,
)
from mg_wheel_bar_spec import (
    AXLE_BORE_STATION,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
)

PART_NAME = "mg-wheel-bar"
MATERIAL = "Plain Carbon Steel"

# Bar section, hole stations, and standard clearance specs live in mg_wheel_bar_geom.
PEN_HANGER_DIAMETRAL_CLEARANCE = PEN_HANGER_HOLE_DIA - HANGER_SCREW_DIA
if PEN_HANGER_DIAMETRAL_CLEARANCE <= 0.0:
    raise AssertionError("standard #8 hanger clearance binds on the stock screw")
PEN_HANGER_HOLE_DIA_TOL = DRILLED_HOLE_PLUS
PEN_HANGER_END_WALL = require_hanger_end_wall(
    SCREW_HOLE_X, PEN_HANGER_HOLE_DIA, PEN_HANGER_HOLE_DIA_TOL
)


def _as_construction(adapter, entity_id: str, label: str) -> None:
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{label} did not take the construction flag")


async def _author_bore_row(adapter) -> list[tuple[str, str]]:
    """The bore row as model dimensions (the dt_cone_tip_block reference-sketch
    pattern): a Hole Wizard placement sketch cannot dimension from the bar's end
    or bottom face, so one construction chain on the row carries the printed
    stations from the left end and a rise at the right end carries the row's
    height from the bottom face. The stations drive from the same globals as
    the Hole Wizard placement points, so each print dimension moves with its
    hole."""
    right_end_x = BAR_LENGTH / 2.0
    bottom_y = -BAR_SIDE / 2.0
    row_xs = (LEFT_END_X, SCREW_HOLE_X, *CLAMP_HOLE_X, right_end_x)
    row = SketchDims()
    check("create_sketch bore row", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    rise = check(
        "bore row rise",
        await adapter.add_line(right_end_x, bottom_y, right_end_x, 0.0),
    )
    legs = [
        check(f"bore row leg {index}", await adapter.add_line(x0, 0.0, x1, 0.0))
        for index, (x0, x1) in enumerate(zip(row_xs, row_xs[1:]))
    ]
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, rise, "bore row rise")
    check(
        "bore row rise vertical",
        await adapter.add_sketch_constraint(rise, None, "vertical"),
    )
    for index, leg in enumerate(legs):
        _as_construction(adapter, leg, f"bore row leg {index}")
        check(
            f"bore row leg {index} horizontal",
            await adapter.add_sketch_constraint(leg, None, "horizontal"),
        )
    for index, (leg, after) in enumerate(zip(legs, [*legs[1:], None])):
        end = f"{rise}.end" if after is None else f"{after}.start"
        check(
            f"bore row leg {index} chained",
            await adapter.add_sketch_constraint(f"{leg}.end", end, "coincident"),
        )
    await anchor_point_to_origin(
        adapter, f"{rise}.start", right_end_x, bottom_y, "bar bottom right corner"
    )
    row.record("RowEndX", '"BarLength" / 2')
    row.record("RowBottomY", '"BarSide" / 2')
    await dimension_between(
        adapter,
        f"{rise}.start",
        f"{rise}.end",
        "vertical_distance",
        BORE_ROW_HEIGHT,
        "bore row height",
    )
    row.record("BoreRowHeight", '"BarSide" / 2')
    start = f"{legs[0]}.start"
    await dimension_between(
        adapter, start, "origin", "horizontal_distance", -LEFT_END_X, "bar left end"
    )
    row.record("RowStartX", '"BarLength" / 2')
    # Each hole ends one leg; the last leg runs on to the rise.
    for leg, station, name in zip(
        legs[:-1],
        (HANGER_STATION, *CLAMP_STATIONS),
        ("HangerStation", "ClampStation1", "ClampStation2"),
        strict=True,
    ):
        await dimension_between(
            adapter, start, f"{leg}.end", "horizontal_distance", station, name
        )
        row.record(name, f'"{name}"')
    await ensure_fully_defined(adapter, "bore row sketch")
    check("exit_sketch bore row", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreRowReference")
    return row.apply(adapter, "BoreRowReference")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the section, the bar length, and the
    # screw holes (diameters + X stations). The mm suffix is load-bearing --
    # this is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 200 = 200 in). BarDepth drives the bar
    # extrude's depth, a named feature dimension the drawing prints.
    # (The old ScrewHoleDia/ScrewHoleX/ClampHoleDia knobs are gone: the holes are
    # now native Hole Wizard features whose diameters come from the clearance
    # tables and whose points are driven from the stations below.)
    await set_global(adapter, "BarSide", f"{BAR_SIDE}mm")
    await set_global(adapter, "BarDepth", f"{BAR_DEPTH}mm")
    await set_global(adapter, "BarLength", f"{BAR_LENGTH}mm")
    await set_global(adapter, "HangerStation", f"{HANGER_STATION}mm")
    await set_global(adapter, "ClampStation1", f"{CLAMP_STATIONS[0]}mm")
    await set_global(adapter, "ClampStation2", f"{CLAMP_STATIONS[1]}mm")
    await set_global(adapter, "AxleBoreDia", f"{AXLE_BORE_DIA}mm")
    await set_global(adapter, "AxleBoreStation", f"{AXLE_BORE_STATION}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Square bar profile: width along X = length, depth along Z = section,
    # origin-centred. The old add_line_chain + define_rectilinear_chain pair is
    # an origin-centred rectangle, so switch it to define_centered_rectangle
    # (cleaner; emits exactly width, depth, cornerX, cornerZ).
    bar = SketchDims()
    check("create_sketch bar", await adapter.create_sketch("Front"))
    await define_centered_rectangle(
        adapter,
        BAR_LENGTH / 2.0,
        BAR_SIDE / 2.0,
        "bar",
        dims=bar,
        name_width="Length",
        drive_width='"BarLength"',
        name_depth="Side",
        drive_depth='"BarSide"',
    )
    await ensure_fully_defined(adapter, "bar sketch")
    check("exit_sketch bar", await adapter.exit_sketch())
    name_last_feature(adapter, "BarProfile")
    drive_jobs += bar.apply(adapter, "BarProfile")
    check(
        "extrude bar",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=BAR_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bar")
    bar_depth = name_dimensions(adapter, "Bar", ["BarDepth"])
    drive_jobs.append((bar_depth[0], '"BarDepth"'))

    expected = BAR_LENGTH * BAR_SIDE * BAR_DEPTH
    await volume_check(adapter, "bar", expected, 0.005 * expected)

    # All bores drilled through along Z from the bar FRONT face (local
    # z = -BAR_DEPTH/2, the heads' side), while the bar is a plain prism:
    # ONE pen-hanger #8 close-clearance hole + ONE 2-instance #8 normal-clearance
    # clamp feature (the support-bar stack: heads on the bar front face, shanks
    # through the bar + front arc, threading into the back arc). Positions are
    # the photo layout; each point drives from its station off the left end.
    front_z = -BAR_DEPTH / 2.0
    screw_dia = blind_cut_dia_mm(PEN_HANGER_HOLE_SPEC)
    clamp_dia = blind_cut_dia_mm(CLAMP_HOLE_SPEC)
    screw_cut = wizard_holes(
        adapter,
        PEN_HANGER_HOLE_SPEC,
        [[SCREW_HOLE_X, 0.0, front_z]],
        (0.0, 0.0, -1.0),
        "pen-hanger screw hole (#8 clearance)",
        name="ScrewHole",
        expect_dia_mm=PEN_HANGER_HOLE_DIA,
        placement_dims=[
            (("ScrewHoleCx", '"BarLength" / 2 - "HangerStation"'), (None, None))
        ],
    )
    drive_jobs += screw_cut.placement_drive_jobs
    expected -= math.pi * (screw_dia / 2.0) ** 2 * BAR_DEPTH
    await volume_check(adapter, "bar with screw hole", expected, 1.0)

    clamp_cut = wizard_holes(
        adapter,
        CLAMP_HOLE_SPEC,
        [[x, 0.0, front_z] for x in CLAMP_HOLE_X],
        (0.0, 0.0, -1.0),
        "clamp-screw clearance holes (#8)",
        name="ClampHoles",
        expect_dia_mm=CLAMP_HOLE_DIA,
        placement_dims=[
            (("ClampHole1Cx", '"ClampStation1" - "BarLength" / 2'), (None, None)),
            (("ClampHole2Cx", '"ClampStation2" - "BarLength" / 2'), (None, None)),
        ],
    )
    drive_jobs += clamp_cut.placement_drive_jobs
    expected -= 2.0 * math.pi * (clamp_dia / 2.0) ** 2 * BAR_DEPTH
    await volume_check(adapter, "bar with clamp holes", expected, 1.0)

    # Reamed axle bore, through along Z. Its centre is located from the bar's
    # LEFT END (where every hole station reads from) by one construction line
    # on the mid-height axis, whose length is the printed station; the line's
    # left end is anchored at the end face (x = -BarLength/2).
    bore = SketchDims()
    check("create_sketch axle bore", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    bore_circle = check(
        "axle bore circle",
        await adapter.add_circle(AXLE_BORE_X, 0.0, AXLE_BORE_DIA / 2.0),
    )
    station_line = check(
        "axle bore station line",
        await adapter.add_line(-BAR_LENGTH / 2.0, 0.0, AXLE_BORE_X, 0.0),
    )
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[station_line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError("axle bore station line did not take construction flag")
    check(
        "axle bore station line on the centre",
        await adapter.add_sketch_constraint(
            f"{station_line}.end", f"{bore_circle}.center", "coincident"
        ),
    )
    check(
        "axle bore station line horizontal",
        await adapter.add_sketch_constraint(station_line, None, "horizontal"),
    )
    await anchor_point_to_origin(
        adapter, f"{station_line}.start", -BAR_LENGTH / 2.0, 0.0, "bar left end"
    )
    bore.record("AxleBoreEndX", '"BarLength" / 2')
    await dimension_between(
        adapter,
        f"{station_line}.start",
        f"{station_line}.end",
        "horizontal_distance",
        AXLE_BORE_STATION,
        "axle bore station",
    )
    bore.record("AxleBoreStation", '"AxleBoreStation"')
    check(
        "axle bore diameter",
        await adapter.add_sketch_dimension(
            bore_circle, None, "diameter", AXLE_BORE_DIA
        ),
    )
    bore.record("AxleBoreDia", '"AxleBoreDia"')
    await ensure_fully_defined(adapter, "axle bore sketch")
    check("exit_sketch axle bore", await adapter.exit_sketch())
    name_last_feature(adapter, "AxleBoreProfile")
    drive_jobs += bore.apply(adapter, "AxleBoreProfile")
    check(
        "cut axle bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * BAR_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "AxleBore")
    expected -= math.pi * (AXLE_BORE_DIA / 2.0) ** 2 * BAR_DEPTH
    await volume_check(adapter, "bar with axle bore", expected, 1.0)

    drive_jobs += await _author_bore_row(adapter)

    # Deferred drive equations after the model + a rebuild exists, then re-check:
    # each equation evaluates to the as-built value, so geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven wheel bar (equations neutral)", expected, 1.0)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Manufacturing drawing support: the native bands, then mark exactly the
    # print's dimensions and stamp the make-critical title-block properties.
    set_dimension_bilateral_tolerance(
        adapter, "BarProfile", "Side", *deviations(BAR_SIDE_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "Bar", "BarDepth", *deviations(BAR_DEPTH_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "AxleBoreProfile", "AxleBoreDia", *deviations(AXLE_BORE_BAND)
    )
    set_dimension_symmetric_tolerance(
        adapter, "BoreRowReference", "BoreRowHeight", BORE_ROW_HEIGHT_TOL
    )
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    # Hidden in the part so no assembly instance renders the row; the drawing
    # shows it in the front view (_drawing_hidden_sketches).
    blank_sketch(adapter, "BoreRowReference")
    row_feature = _early_bound(
        _early_bound(adapter.currentModel, "IPartDoc").FeatureByName(
            "BoreRowReference"
        ),
        "IFeature",
    )
    if int(row_feature.Visible) != 1:  # swVisibilityStateHide
        raise RuntimeError("BoreRowReference still visible after BlankSketch")
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
