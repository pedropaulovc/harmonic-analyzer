r"""Build MHA-CH-13-TL-01, the rocker strap's sub-plate (shop tooling).

``ch_rocker_strap_tl_sub_plate_spec`` owns every number. Model frame = the
strap programs' G54: X0 the end stop's face, Y0 the fence's face, Z0 the
plate top (the Front Plane), +Z up.

Feature tree, each sketch fully defined and every printed size a driving
model dimension located from X0, Y0 or Z0:

* ``FacedTopPlane``: the faced top, FenceHeight above the Front Plane.
* ``PlateProfile`` / ``Plate``: the sawn and edge-milled blank on the faced
  top, its left end LeftEnd behind X0, its back edge FenceWidth behind Y0,
  extruded down by PlateThickness (the underside as received).
* ``PlateTopProfile`` / ``PlateTop``: the Z0 floor, everything in front of
  Y0 and right of X0 milled FenceHeight down from the faced top, leaving the
  fence and the end stop integral.
* ``NotchProfile`` / ``FenceNotches`` / ``NotchCorners``: the two fence
  notches cut up through the fence from Z0, the left one from the stop face,
  the right one open at the right end; their three back corners R MAX.
* ``PocketProfile`` / ``ClampPockets`` / ``PocketCorners``: the four clamp
  pockets cut PocketDepth down from Z0, their corners R MAX.
* ``HubCboreProfile`` / ``HubCbore``: the hub counterbore down from Z0.
* ``ClampTaps``: one native #4-40 THRU wizard feature, four instances on the
  pocket floors; ``HubTap``: the native 1/4-20 THRU from the counterbore
  floor.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_strap_tl_sub_plate.py
"""

from __future__ import annotations

import sys
from typing import Any

import ch_rocker_strap_tl_sub_plate_spec as spec
from _appearance import apply_material
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _drawing_prefix import set_dimension_prefix
from _drawing_tolerances import set_dimension_symmetric_tolerance
from _feature_tree import name_last_feature
from _holes import SharedCoordinate, wizard_holes
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _single_limit_tolerance import SW_TOL_MAX, set_single_limit
from _sketch import SketchDims, add_line_chain, dimension_between, ensure_fully_defined
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry

PART_NAME = "ch-rocker-strap-tl-sub-plate"
if PART_NAME != spec.PART_NAME:
    raise AssertionError("the builder's PART_NAME and its spec disagree")
MATERIAL = "6061 Alloy"  # 6061-T6511 flat (the registry row names it)
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)
# The floor and notch cuts run this far past the plate's right end and front
# edge, so no cut face lies in a stock face.
CUT_OVERRUN = 2.54
# Absolute (mm^3), so the smallest step (three notch corners, about 4 mm^3;
# the four clamp taps, about 110) still fails if it is missing or cut into air.
_V_TOL = 2.0

# Editable knobs (Tools > Equations); the mm suffix is load-bearing (inch
# document). Distances behind or in front of the origin are magnitudes.
GLOBALS: dict[str, float] = {
    "LeftEnd": -spec.LEFT_END_X,
    "PlateLength": spec.PLATE_LENGTH,
    "FenceWidth": spec.FENCE_WIDTH,
    "PlateWidth": spec.PLATE_WIDTH,
    "PlateThickness": spec.PLATE_THICKNESS,
    "FenceHeight": spec.FENCE_HEIGHT,
    "CutOverrun": CUT_OVERRUN,
    "NotchLeftEnd": spec.NOTCH_LEFT_END,
    "NotchRightStart": spec.NOTCH_RIGHT_START,
    "NotchDepth": spec.NOTCH_DEPTH,
    "CornerRadius": spec.CORNER_RADIUS,
    "PocketLength": spec.POCKET_LENGTH,
    "PocketNearWallY": -spec.POCKET_NEAR_WALL_Y,
    "PocketBackWallY": -spec.POCKET_BACK_WALL_Y,
    "PocketDepth": spec.POCKET_DEPTH,
    **{
        f"ClampStation{index}": station
        for index, station in enumerate(spec.CLAMP_STATIONS, 1)
    },
    "ClampTapY": -spec.CLAMP_SCREW_Y,
    "HubX": spec.HUB_X,
    "HubY": -spec.HUB_Y,
    "HubCboreDia": spec.HUB_CBORE_DIA,
    "HubCboreDepth": spec.HUB_CBORE_DEPTH,
}
_RIGHT_OF_X0 = '"PlateLength" - "LeftEnd" + "CutOverrun"'
_FRONT_OF_Y0 = '"PlateWidth" - "FenceWidth" + "CutOverrun"'


def _rectilinear(
    adapter: Any, points: list[tuple[float, float]], label: str
) -> list[str]:
    """A closed axis-parallel chain through ``points``, each segment held
    horizontal or vertical; its sizes are the caller's dimensions."""
    lines = add_line_chain(adapter, points)
    for index, line in enumerate(lines):
        x0, _y0 = points[index]
        x1, _y1 = points[(index + 1) % len(points)]
        relation = "vertical" if x0 == x1 else "horizontal"
        check(
            f"{label} {relation} {line}",
            adapter.add_sketch_constraint(line, None, relation),
        )
    return lines


def _plate(adapter: Any, drive_jobs: list[tuple[str, str]]) -> None:
    """The faced-top plane and the blank extruded down from it."""
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check(
        "create_plane FacedTopPlane",
        adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=spec.FENCE_HEIGHT
            )
        ),
    )
    name_last_feature(adapter, spec.FACED_TOP_PLANE)
    (plane_dim,) = name_dimensions(adapter, spec.FACED_TOP_PLANE, ["FacedTopZ"])
    drive_jobs.append((plane_dim, '"FenceHeight"'))

    # Corners left-front, right-front, right-back, left-back: lines bottom,
    # right, top, left. Every location runs from the origin (X0, Y0).
    dims = SketchDims()
    check("create_sketch plate", adapter.create_sketch(spec.FACED_TOP_PLANE))
    corners = [
        (spec.LEFT_END_X, spec.FRONT_EDGE_Y),
        (spec.RIGHT_END_X, spec.FRONT_EDGE_Y),
        (spec.RIGHT_END_X, spec.BACK_EDGE_Y),
        (spec.LEFT_END_X, spec.BACK_EDGE_Y),
    ]
    _bottom, _right, top, left = _rectilinear(adapter, corners, "plate")
    dimension_between(
        adapter,
        f"{left}.start",
        "origin",
        "horizontal_distance",
        -spec.LEFT_END_X,
        "left end",
    )
    dims.record("LeftEnd", '"LeftEnd"')
    dimension_between(
        adapter,
        f"{top}.start",
        f"{top}.end",
        "horizontal_distance",
        spec.PLATE_LENGTH,
        "length",
    )
    dims.record("PlateLength", '"PlateLength"')
    dimension_between(
        adapter,
        "origin",
        f"{left}.start",
        "vertical_distance",
        spec.FENCE_WIDTH,
        "fence width",
    )
    dims.record("FenceWidth", '"FenceWidth"')
    dimension_between(
        adapter,
        f"{left}.start",
        f"{left}.end",
        "vertical_distance",
        spec.PLATE_WIDTH,
        "width",
    )
    dims.record("PlateWidth", '"PlateWidth"')
    ensure_fully_defined(adapter, "plate sketch")
    check("exit_sketch plate", adapter.exit_sketch())
    name_last_feature(adapter, "PlateProfile")
    drive_jobs += dims.apply(adapter, "PlateProfile")
    # Down from the faced top: a boss extrudes along the plane's normal (+Z)
    # unless reversed.
    check(
        "extrude plate",
        adapter.create_extrusion(
            ExtrusionParameters(depth=spec.PLATE_THICKNESS, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "Plate")
    (thickness,) = name_dimensions(adapter, "Plate", ["PlateThickness"])
    drive_jobs.append((thickness, '"PlateThickness"'))
    volume_check(adapter, "plate blank", spec.V_PLATE, 0.001 * spec.V_PLATE)
    bbox_extent_check(adapter, "plate length", "x", spec.PLATE_LENGTH)
    bbox_extent_check(adapter, "plate width", "y", spec.PLATE_WIDTH)
    bbox_extent_check(adapter, "plate thickness", "z", spec.PLATE_THICKNESS)


def _floor(adapter: Any, drive_jobs: list[tuple[str, str]], volume: float) -> float:
    """Z0: everything right of X0 and in front of Y0 milled FenceHeight down
    from the faced top, round the fence and the end stop."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    dims = SketchDims()
    check("create_sketch floor", adapter.create_sketch(spec.FACED_TOP_PLANE))
    far_x = spec.RIGHT_END_X + CUT_OVERRUN
    far_y = spec.FRONT_EDGE_Y - CUT_OVERRUN
    # Corners X0-front, far-front, far-Y0, X0Y0: lines bottom, right, top, left.
    _bottom, right, _top, left = _rectilinear(
        adapter, [(0.0, far_y), (far_x, far_y), (far_x, 0.0), (0.0, 0.0)], "floor"
    )
    check(
        "floor corner on X0 Y0",
        adapter.add_sketch_constraint(f"{left}.start", "origin", "coincident"),
    )
    dimension_between(
        adapter, "origin", f"{right}.start", "horizontal_distance", far_x, "floor right"
    )
    dims.record("FloorRightX", _RIGHT_OF_X0)
    dimension_between(
        adapter, "origin", f"{right}.start", "vertical_distance", -far_y, "floor front"
    )
    dims.record("FloorFrontY", _FRONT_OF_Y0)
    ensure_fully_defined(adapter, "floor sketch")
    check("exit_sketch floor", adapter.exit_sketch())
    name_last_feature(adapter, "PlateTopProfile")
    drive_jobs += dims.apply(adapter, "PlateTopProfile")
    # A cut runs against the plane's normal (down) unless reversed.
    check(
        "cut floor",
        adapter.create_cut_extrude(ExtrusionParameters(depth=spec.FENCE_HEIGHT)),
    )
    name_last_feature(adapter, "PlateTop")
    (height,) = name_dimensions(adapter, "PlateTop", ["FenceHeight"])
    drive_jobs.append((height, '"FenceHeight"'))
    volume -= spec.V_FLOOR_CUT
    return volume_check(adapter, "Z0 floor", volume, _V_TOL)


def _notches(adapter: Any, drive_jobs: list[tuple[str, str]], volume: float) -> float:
    """Both fence notches up through the fence from Z0, then their three back
    corners rounded to the MAX radius."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    depth = spec.NOTCH_DEPTH
    front = -CUT_OVERRUN
    far_x = spec.RIGHT_END_X + CUT_OVERRUN
    dims = SketchDims()
    check("create_sketch notches", adapter.create_sketch("Front"))
    # Each rectangle: lines bottom, right, top (the back wall), left.
    left_bottom, _l_right, left_top, left_side = _rectilinear(
        adapter,
        [
            (0.0, front),
            (spec.NOTCH_LEFT_END, front),
            (spec.NOTCH_LEFT_END, depth),
            (0.0, depth),
        ],
        "left notch",
    )
    right_bottom, right_side, right_top, _r_left = _rectilinear(
        adapter,
        [
            (spec.NOTCH_RIGHT_START, front),
            (far_x, front),
            (far_x, depth),
            (spec.NOTCH_RIGHT_START, depth),
        ],
        "right notch",
    )
    # The left notch's end wall is the stop face (X0).
    check(
        "left notch end wall on X0",
        adapter.add_sketch_constraint(
            f"{left_side}.start", "origin", "vertical_points"
        ),
    )
    for ours, theirs, label in (
        (right_top, left_top, "back walls"),
        (right_bottom, left_bottom, "front overruns"),
    ):
        check(
            f"notch {label} collinear",
            adapter.add_sketch_constraint(ours, theirs, "collinear"),
        )
    dimension_between(
        adapter,
        "origin",
        f"{left_top}.start",
        "horizontal_distance",
        spec.NOTCH_LEFT_END,
        "left notch end",
    )
    dims.record("NotchLeftEnd", '"NotchLeftEnd"')
    dimension_between(
        adapter,
        "origin",
        f"{left_side}.start",
        "vertical_distance",
        depth,
        "notch depth",
    )
    dims.record("NotchDepth", '"NotchDepth"')
    dimension_between(
        adapter,
        "origin",
        f"{left_bottom}.start",
        "vertical_distance",
        CUT_OVERRUN,
        "notch overrun",
    )
    dims.record("NotchOverrun", '"CutOverrun"')
    dimension_between(
        adapter,
        "origin",
        f"{right_bottom}.start",
        "horizontal_distance",
        spec.NOTCH_RIGHT_START,
        "right notch start",
    )
    dims.record("NotchRightStart", '"NotchRightStart"')
    dimension_between(
        adapter,
        "origin",
        f"{right_side}.start",
        "horizontal_distance",
        far_x,
        "right notch far end",
    )
    dims.record("NotchRightX", _RIGHT_OF_X0)
    ensure_fully_defined(adapter, "notch sketch")
    check("exit_sketch notches", adapter.exit_sketch())
    name_last_feature(adapter, "NotchProfile")
    drive_jobs += dims.apply(adapter, "NotchProfile")
    # Up (reversed: a cut runs against the Front Plane's +Z normal by
    # default) through everything above Z0: a wrong direction would cut the
    # plate below Z0 and fail the volume gate.
    check(
        "cut fence notches",
        adapter.create_cut_extrude(
            ExtrusionParameters(
                depth=spec.FENCE_HEIGHT,
                end_condition="ThroughAll",
                reverse_direction=True,
            )
        ),
    )
    name_last_feature(adapter, "FenceNotches")
    volume -= spec.V_NOTCHES
    volume = volume_check(adapter, "fence notches", volume, _V_TOL)

    z = spec.FENCE_HEIGHT / 2.0
    check(
        "round notch back corners",
        adapter.add_fillet(
            spec.CORNER_RADIUS,
            [
                [0.0, depth, z],
                [spec.NOTCH_LEFT_END, depth, z],
                [spec.NOTCH_RIGHT_START, depth, z],
            ],
            propagate=False,
        ),
    )
    name_last_feature(adapter, "NotchCorners")
    (radius,) = name_dimensions(adapter, "NotchCorners", ["NotchCornerR"])
    drive_jobs.append((radius, '"CornerRadius"'))
    volume += spec.V_NOTCH_CORNERS
    return volume_check(adapter, "notch corners", volume, _V_TOL)


def _pockets(adapter: Any, drive_jobs: list[tuple[str, str]], volume: float) -> float:
    """The four clamp pockets down from Z0, centred on their stations, then
    their corners rounded to the MAX radius."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    half = spec.POCKET_LENGTH / 2.0
    back, near = spec.POCKET_BACK_WALL_Y, spec.POCKET_NEAR_WALL_Y
    dims = SketchDims()
    check("create_sketch pockets", adapter.create_sketch("Front"))
    # Each rectangle: lines back wall, right end, near wall, left end.
    pockets = [
        _rectilinear(
            adapter,
            [(s - half, back), (s + half, back), (s + half, near), (s - half, near)],
            f"pocket {index}",
        )
        for index, s in enumerate(spec.CLAMP_STATIONS, 1)
    ]
    first_back, _r, first_near, first_left = pockets[0]
    last_near = pockets[-1][2]
    for index, (back_wall, _right, near_wall, _left) in enumerate(pockets[1:], 2):
        for ours, theirs, label in (
            (back_wall, first_back, "back wall"),
            (near_wall, first_near, "near wall"),
        ):
            check(
                f"pocket {index} {label} collinear",
                adapter.add_sketch_constraint(ours, theirs, "collinear"),
            )
    for index, (_back, _right, near_wall, _left) in enumerate(pockets[:-1], 1):
        check(
            f"pocket {index} length equal",
            adapter.add_sketch_constraint(near_wall, last_near, "equal"),
        )
    # Every location from the origin: each pocket's left end from X0 (an
    # equation of its station, so the station prints once, on its tap), the
    # walls from Y0 on pocket 1, the length on pocket 4.
    for index, ((_back, _right, near_wall, _left), station) in enumerate(
        zip(pockets, spec.CLAMP_STATIONS, strict=True), 1
    ):
        dimension_between(
            adapter,
            "origin",
            f"{near_wall}.end",
            "horizontal_distance",
            station - half,
            f"pocket {index} left end",
        )
        dims.record(f"Pocket{index}X", f'"ClampStation{index}" - "PocketLength" / 2')
        if index == 1:
            dimension_between(
                adapter,
                "origin",
                f"{first_left}.start",
                "vertical_distance",
                -near,
                "pocket near wall",
            )
            dims.record("PocketNearWallY", '"PocketNearWallY"')
            dimension_between(
                adapter,
                "origin",
                f"{first_left}.end",
                "vertical_distance",
                -back,
                "pocket back wall",
            )
            dims.record("PocketBackWallY", '"PocketBackWallY"')
    dimension_between(
        adapter,
        f"{last_near}.start",
        f"{last_near}.end",
        "horizontal_distance",
        spec.POCKET_LENGTH,
        "pocket length",
    )
    dims.record("PocketLength", '"PocketLength"')
    ensure_fully_defined(adapter, "pocket sketch")
    check("exit_sketch pockets", adapter.exit_sketch())
    name_last_feature(adapter, "PocketProfile")
    drive_jobs += dims.apply(adapter, "PocketProfile")
    check(
        "cut clamp pockets",
        adapter.create_cut_extrude(ExtrusionParameters(depth=spec.POCKET_DEPTH)),
    )
    name_last_feature(adapter, "ClampPockets")
    (depth,) = name_dimensions(adapter, "ClampPockets", ["PocketDepth"])
    drive_jobs.append((depth, '"PocketDepth"'))
    volume -= spec.V_POCKETS
    volume = volume_check(adapter, "clamp pockets", volume, _V_TOL)

    z = -spec.POCKET_DEPTH / 2.0
    check(
        "round pocket corners",
        adapter.add_fillet(
            spec.CORNER_RADIUS,
            [
                [s + side * half, wall, z]
                for s in spec.CLAMP_STATIONS
                for side in (-1.0, 1.0)
                for wall in (back, near)
            ],
            propagate=False,
        ),
    )
    name_last_feature(adapter, "PocketCorners")
    (radius,) = name_dimensions(adapter, "PocketCorners", ["PocketCornerR"])
    drive_jobs.append((radius, '"CornerRadius"'))
    volume += spec.V_POCKET_CORNERS
    return volume_check(adapter, "pocket corners", volume, _V_TOL)


def _hub(adapter: Any, drive_jobs: list[tuple[str, str]], volume: float) -> float:
    """The hub counterbore down from Z0, located from X0 and Y0."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    dims = SketchDims()
    check("create_sketch hub counterbore", adapter.create_sketch("Front"))
    define_circle(
        adapter,
        spec.HUB_X,
        spec.HUB_Y,
        spec.HUB_CBORE_DIA / 2.0,
        "hub counterbore",
        dims=dims,
        names=("HubX", "HubY", "HubCboreDia"),
        drives=('"HubX"', '"HubY"', '"HubCboreDia"'),
    )
    ensure_fully_defined(adapter, "hub counterbore sketch")
    check("exit_sketch hub counterbore", adapter.exit_sketch())
    name_last_feature(adapter, "HubCboreProfile")
    drive_jobs += dims.apply(adapter, "HubCboreProfile")
    check(
        "cut hub counterbore",
        adapter.create_cut_extrude(ExtrusionParameters(depth=spec.HUB_CBORE_DEPTH)),
    )
    name_last_feature(adapter, "HubCbore")
    (depth,) = name_dimensions(adapter, "HubCbore", ["HubCboreDepth"])
    drive_jobs.append((depth, '"HubCboreDepth"'))
    volume -= spec.V_HUB_CBORE
    return volume_check(adapter, "hub counterbore", volume, _V_TOL)


def _taps(adapter: Any, drive_jobs: list[tuple[str, str]], volume: float) -> float:
    """The four #4-40 clamp taps through from the pocket floors (one native
    feature, the stations driven by the same globals as the pockets) and the
    1/4-20 hub tap through from the counterbore floor."""
    clamp = wizard_holes(
        adapter,
        spec.CLAMP_TAP_SPEC,
        [[s, spec.CLAMP_SCREW_Y, spec.POCKET_FLOOR_Z] for s in spec.CLAMP_STATIONS],
        (0.0, 0.0, 1.0),
        "clamp taps (#4-40 thru)",
        name="ClampTaps",
        placement_dims=[
            (
                (name, f'"ClampStation{index}"'),
                ("ClampTapY", '"ClampTapY"') if index == 1 else SharedCoordinate(0),
            )
            for index, name in enumerate(spec.CLAMP_TAP_X_NAMES, 1)
        ],
    )
    drive_jobs += clamp.placement_drive_jobs
    volume -= spec.V_CLAMP_TAPS
    volume = volume_check(adapter, "clamp taps", volume, _V_TOL)

    hub = wizard_holes(
        adapter,
        spec.HUB_TAP_SPEC,
        [[spec.HUB_X, spec.HUB_Y, spec.COUNTERBORE_FLOOR_Z]],
        (0.0, 0.0, 1.0),
        "hub tap (1/4-20 thru)",
        name="HubTap",
        placement_dims=[(("HubTapX", '"HubX"'), ("HubTapY", '"HubY"'))],
    )
    drive_jobs += hub.placement_drive_jobs
    volume -= spec.V_HUB_TAP
    return volume_check(adapter, "hub tap", volume, _V_TOL)


def build(adapter: Any) -> dict[str, str]:
    check("create_part", adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    for name, value in GLOBALS.items():
        set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []
    _plate(adapter, drive_jobs)
    volume = _floor(adapter, drive_jobs, spec.V_PLATE)
    volume = _notches(adapter, drive_jobs, volume)
    volume = _pockets(adapter, drive_jobs, volume)
    volume = _hub(adapter, drive_jobs, volume)
    volume = _taps(adapter, drive_jobs, volume)
    volume_check(adapter, "sub-plate (analytic)", spec.V_FINISHED, _V_TOL)
    blank_reference_geometry(adapter, ((spec.FACED_TOP_PLANE, "PLANE"),))

    # Deferred drive equations; each evaluates to the value just built, so the
    # volume must not move.
    force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        drive_dimension(adapter, dimension_name, expression)
    force_rebuild(adapter)
    volume_check(adapter, "driven sub-plate (equations neutral)", volume, _V_TOL)

    apply_material(adapter, MATERIAL)
    report_mass_properties(adapter)

    # Explicit bands, each with its function on the sheet: the clamp pocket's
    # back wall seats the TL-VN-50 heel so its knife reaches the blank's edge;
    # the counterbore locates the blank's hub through TL-02. A milled step
    # within 6 in of its datum holds +/-.002 (drawing-guidelines.md, "What
    # the shop holds"); the tolerance carries the nominal's three places.
    set_dimension_symmetric_tolerance(
        adapter,
        "PocketProfile",
        "PocketBackWallY",
        spec.POCKET_BACK_WALL_TOL,
        places=spec.DRAWING_PRECISION_BY_NAME["PocketBackWallY"],
        display_unit=spec.UNIT,
    )
    set_dimension_symmetric_tolerance(
        adapter,
        "HubCboreProfile",
        "HubX",
        spec.HUB_LOCATION_TOL,
        places=spec.DRAWING_PRECISION_BY_NAME["HubX"],
        display_unit=spec.UNIT,
    )
    set_dimension_symmetric_tolerance(
        adapter,
        "HubCboreProfile",
        "HubY",
        spec.HUB_LOCATION_TOL,
        places=spec.DRAWING_PRECISION_BY_NAME["HubY"],
        display_unit=spec.UNIT,
    )
    # Cutter-formed inside corners: the modelled radius is the MAX limit
    # (sharp up to it), above the title block's inside-corner row.
    for feature_name, dimension_name in spec.MAX_RADII:
        set_single_limit(
            adapter,
            feature_name,
            dimension_name,
            limit=spec.CORNER_RADIUS,
            band=(0.0, -spec.CORNER_RADIUS),
            tol_type=SW_TOL_MAX,
        )
    for (feature_name, dimension_name), prefix in spec.DIMENSION_PREFIXES.items():
        set_dimension_prefix(adapter, feature_name, dimension_name, prefix)
    apply_drawing_precision(adapter, spec.DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in spec.DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": spec.ISOMETRIC_VIEW_NOTE}
    )
    artefacts = save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
