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
* ``HubHole``: one native Hole Wizard counterbore down from Z0 (Ø.500 x
  .185 over the #10-32's #21 drill THRU), placed by HubX and HubY;
  ``HubThread``: the #10-32 cosmetic thread on its drill, THRU.
* ``ClampTaps``: one native #4-40 THRU wizard feature, four instances on the
  pocket floors.
* ``SectionAPlane`` / ``SectionAReference`` and ``SectionBPlane`` /
  ``SectionBReference``: hidden construction-only sketches in the two
  sections' cutting planes (Right-parallel, across the plate), owning every
  size the sections print (PocketNearWallY, PocketBackWallY, PocketDepth,
  PlateThickness; FenceHeight), each driven by the same global as the
  feature size it states.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_strap_tl_sub_plate.py
"""

from __future__ import annotations

import sys
from typing import Any

import ch_rocker_strap_tl_sub_plate_spec as spec
from _appearance import apply_material
from _check import check
from _com import _early_bound, _read_member
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_prefix import set_dimension_prefix
from _drawing_tolerances import set_dimension_symmetric_tolerance
from _feature_tree import _feature_by_name, name_last_feature
from _hole_spec import THREAD_MAJOR_MM
from _holes import SharedCoordinate, wizard_holes
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
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
    (thickness,) = name_dimensions(adapter, "Plate", ["BlankThickness"])
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
    (height,) = name_dimensions(adapter, "PlateTop", ["FloorDepth"])
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

    # The right notch's corner first: the drawing's radius attaches to the
    # first edge, and the right corner's leader runs out through the open
    # notch (farm run 20261118T001932117Z: off the left corner it crossed the
    # whole top view).
    z = spec.FENCE_HEIGHT / 2.0
    check(
        "round notch back corners",
        adapter.add_fillet(
            spec.CORNER_RADIUS,
            [
                [spec.NOTCH_RIGHT_START, depth, z],
                [0.0, depth, z],
                [spec.NOTCH_LEFT_END, depth, z],
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
    for index, (back_wall, _right, near_wall, _left) in enumerate(pockets[1:], 2):
        for ours, theirs, label in (
            (back_wall, first_back, "back wall"),
            (near_wall, first_near, "near wall"),
        ):
            check(
                f"pocket {index} {label} collinear",
                adapter.add_sketch_constraint(ours, theirs, "collinear"),
            )
    for index, (_back, _right, near_wall, _left) in enumerate(pockets[1:], 2):
        check(
            f"pocket {index} length equal",
            adapter.add_sketch_constraint(near_wall, first_near, "equal"),
        )
    # Every location from the origin: each pocket's left end from X0 (an
    # equation of its station, so the station prints once, on its tap), the
    # walls from Y0 on pocket 1, the length on pocket 2 (the drawing prints it
    # over the back edge, the open room under the hub's callout, clear of the
    # taps' X extension lines and of the notch's rows over pocket 1: machinist
    # review r24 read it inside the outline as convenience, rule 14).
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
    second_near = pockets[1][2]
    dimension_between(
        adapter,
        f"{second_near}.start",
        f"{second_near}.end",
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
    (depth,) = name_dimensions(adapter, "ClampPockets", ["PocketCutDepth"])
    drive_jobs.append((depth, '"PocketDepth"'))
    volume -= spec.V_POCKETS
    volume = volume_check(adapter, "clamp pockets", volume, _V_TOL)

    # Pocket 4's right back corner first: the drawing's radius attaches to the
    # first edge and prints right of the plate (farm run 20261118T001932117Z:
    # off pocket 1 its text sat on clamp 1's X extension line).
    z = -spec.POCKET_DEPTH / 2.0
    corners = [
        [s + side * half, wall, z]
        for s in spec.CLAMP_STATIONS
        for side in (-1.0, 1.0)
        for wall in (back, near)
    ]
    first = [spec.CLAMP_STATIONS[-1] + half, back, z]
    corners.remove(first)
    check(
        "round pocket corners",
        adapter.add_fillet(spec.CORNER_RADIUS, [first, *corners], propagate=False),
    )
    name_last_feature(adapter, "PocketCorners")
    (radius,) = name_dimensions(adapter, "PocketCorners", ["PocketCornerR"])
    drive_jobs.append((radius, '"CornerRadius"'))
    volume += spec.V_POCKET_CORNERS
    return volume_check(adapter, "pocket corners", volume, _V_TOL)


def _hub(adapter: Any, drive_jobs: list[tuple[str, str]], volume: float) -> float:
    """The hub hole down from Z0, one native Hole Wizard counterbore located
    from X0 and Y0 (HubX, HubY), its Ø.500 x .185 counterbore over the tap's
    #21 drill through (spec.HUB_HOLE_SPEC), then the #10-32 cosmetic thread on
    the drill (HubThread). Its callout prints drill, counterbore and depth
    together (draw_ch_fulcrum_keeper's foot hole)."""
    from solidworks_mcp.adapters.base import AddThreadParameters

    hub = wizard_holes(
        adapter,
        spec.HUB_HOLE_SPEC,
        [[spec.HUB_X, spec.HUB_Y, spec.PLATE_TOP_Z]],
        (0.0, 0.0, 1.0),
        "hub hole (Ø.500 counterbore over #21 thru)",
        name="HubHole",
        expect_dia_mm=spec.HUB_TAP_DRILL,
        placement_dims=[(("HubX", '"HubX"'), ("HubY", '"HubY"'))],
    )
    for label, actual, nominal in (
        ("counterbore Ø", hub.cbore_dia_mm, spec.HUB_CBORE_DIA),
        ("counterbore depth", hub.cbore_depth_mm, spec.HUB_CBORE_DEPTH),
    ):
        if abs(actual - nominal) > 0.005:
            raise RuntimeError(f"hub hole {label} {actual:.4f} != {nominal:.4f} mm")
    drive_jobs += hub.placement_drive_jobs
    volume -= spec.V_HUB_CBORE + spec.V_HUB_TAP
    volume = volume_check(adapter, "hub hole", volume, _V_TOL)

    major = THREAD_MAJOR_MM[spec.HUB_TAP_THREAD]
    created = check(
        "hub thread (#10-32 thru)",
        adapter.add_thread(
            AddThreadParameters(
                edge_point=[
                    spec.HUB_X + spec.HUB_TAP_DRILL / 2.0,
                    spec.HUB_Y,
                    spec.COUNTERBORE_FLOOR_Z,
                ],
                standard="ansi_inch",
                size=spec.HUB_TAP_THREAD,
                diameter=major,
                end_type="through",
                note=spec.HUB_THREAD_LABEL,
            )
        ),
    )
    # The thread is a sub-feature of HubHole, not the newest top-level
    # feature (farm run r19: name_last_feature renamed HubHole itself), so it
    # is found by the name add_thread returns, as the magnifying lever does.
    created_name = created.get("name")
    if type(created_name) is not str or not created_name:
        raise RuntimeError("hub thread returned no feature name")
    thread = _early_bound(
        _early_bound(adapter.currentModel, "IPartDoc").FeatureByName(created_name),
        "IFeature",
    )
    if thread is None:
        raise RuntimeError(f"hub thread {created_name!r} not found")
    thread.Name = "HubThread"
    definition = _early_bound(thread.GetDefinition(), "ICosmeticThreadFeatureData")
    # swCosmeticEndConditions_e.swEndConditionThrough = 2. Size reads back
    # empty on a seat (farm run r20), so the thread's identity is gated where
    # it prints: the drawing checks the hub callout's resolved 10-32 row.
    if int(definition.EndCondition) != 2:
        raise RuntimeError(
            "hub thread did not read back THRU: "
            f"EndCondition {definition.EndCondition!r}, callout "
            f"{definition.ThreadCallout!r}, diameter {definition.Diameter!r}"
        )
    return volume_check(adapter, "hub thread (cosmetic)", volume, _V_TOL)


def _taps(adapter: Any, drive_jobs: list[tuple[str, str]], volume: float) -> float:
    """The four #4-40 clamp taps through from the pocket floors (one native
    feature, the stations driven by the same globals as the pockets)."""
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
    return volume_check(adapter, "clamp taps", volume, _V_TOL)


def _section_plane(adapter: Any, name: str, x_mm: float) -> None:
    """A cutting plane parallel to the Right Plane at model X ``x_mm``, read
    back against it (build_pd_platen._cbore_section_plane): the same rotation,
    so a sketch on it keeps Right's (u, v) = model (-Z, Y), and an origin
    shifted by exactly ``x_mm`` along X."""
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check(
        f"create plane {name}",
        adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Right Plane", offset=x_mm)
        ),
    )
    name_last_feature(adapter, name)
    right_rotation, right_origin = _plane_frame(adapter, "Right Plane")
    rotation, origin = _plane_frame(adapter, name)
    shift = tuple(o - r for o, r in zip(origin, right_origin, strict=True))
    if any(
        abs(a - b) > 1e-9 for a, b in zip(rotation, right_rotation, strict=True)
    ) or any(abs(s - e) > 1e-6 for s, e in zip(shift, (x_mm, 0.0, 0.0), strict=True)):
        raise RuntimeError(
            f"{name}: rotation {rotation} / origin shift {shift} mm, expected the "
            f"Right plane's {right_rotation} shifted ({x_mm}, 0, 0)"
        )


def _plane_frame(
    adapter: Any, name: str
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """(rotation, origin mm) of a reference plane, from ``IRefPlane.Transform``."""
    feature = _early_bound(_feature_by_name(adapter, name), "IFeature")
    plane = _early_bound(feature.GetSpecificFeature2(), "IRefPlane")
    data = [
        float(v) for v in _read_member(_read_member(plane, "Transform"), "ArrayData")
    ]
    return tuple(data[0:9]), tuple(v * 1000.0 for v in data[9:12])


def _chord(
    adapter: Any, *, y_mm: float, z_from_mm: float, z_to_mm: float, label: str
) -> str:
    """One construction chord along Z in a Right-parallel sketch, at model Y
    ``y_mm`` from model Z ``z_from_mm`` to ``z_to_mm``, held horizontal
    (Right's sketch u is model -Z). The caller locates and sizes it."""
    set_sketch_direct_db(adapter, True)
    line = check(
        f"{label} chord",
        adapter.add_line(-z_from_mm, y_mm, -z_to_mm, y_mm),
    )
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{label} chord did not take the construction flag")
    check(
        f"{label} chord horizontal",
        adapter.add_sketch_constraint(line, None, "horizontal"),
    )
    return line


def _length(
    adapter: Any, dims: SketchDims, line: str, length_mm: float, name: str, drive: str
) -> None:
    dimension_between(
        adapter, f"{line}.start", f"{line}.end", "horizontal_distance", length_mm, name
    )
    dims.record(name, drive)


def _section_references(adapter: Any, drive_jobs: list[tuple[str, str]]) -> None:
    """The sizes the sections print, in hidden construction-only sketches on
    each cutting plane (a section imports no sketch or extrusion size): every
    chord runs along Z, so the top view sees it end-on, and each is held on
    one of the origin's axes by a relation plus one distance from the origin
    (or on the origin itself); its length is the other size.

    Farm runs r13 and r14 (20261118T012253828Z and its successor): B-B
    imported FenceHeight and the counterbore's depth but never FenceWidth,
    PlateThickness or PlateWidth from chords on the back and front faces,
    anchored off the axes (r13) or on them (r14). So the widths print on the
    top view from PlateProfile, and the thickness runs down the fence face's
    line in A-A, where the fence face's own chord imported in B-B.

    A-A (pocket 3): a chord down each pocket wall from Z0, its foot from Y0
    (PocketNearWallY, PocketBackWallY), the back wall's long PocketDepth; a
    chord on Y0 from the fence's top (its height from the origin) through the
    material to the underside, long PlateThickness. B-B (the hub, on its
    axis): the fence face up from the origin (FenceHeight); the hub hole's
    sizes are its wizard callout's."""
    _section_plane(adapter, spec.SECTION_A_PLANE, spec.SECTION_A_X)
    dims = SketchDims()
    check(
        "create_sketch section A-A reference",
        adapter.create_sketch(spec.SECTION_A_PLANE),
    )
    for wall_y, name, chord_name, chord_drive in (
        (spec.POCKET_NEAR_WALL_Y, "PocketNearWallY", "NearWallChord", '"PocketDepth"'),
        (spec.POCKET_BACK_WALL_Y, "PocketBackWallY", "PocketDepth", '"PocketDepth"'),
    ):
        wall = _chord(
            adapter,
            y_mm=wall_y,
            z_from_mm=spec.PLATE_TOP_Z,
            z_to_mm=spec.POCKET_FLOOR_Z,
            label=name,
        )
        anchor_point_to_origin(adapter, f"{wall}.start", 0.0, wall_y, name)
        dims.record(name, f'"{name}"')
        _length(adapter, dims, wall, spec.POCKET_DEPTH, chord_name, chord_drive)
    thickness = _chord(
        adapter,
        y_mm=0.0,
        z_from_mm=spec.FENCE_HEIGHT,
        z_to_mm=spec.UNDERSIDE_Z,
        label="PlateThickness",
    )
    anchor_point_to_origin(
        adapter, f"{thickness}.start", -spec.FENCE_HEIGHT, 0.0, "PlateThickness top"
    )
    dims.record("ThicknessTopZ", '"FenceHeight"')
    _length(
        adapter,
        dims,
        thickness,
        spec.PLATE_THICKNESS,
        "PlateThickness",
        '"PlateThickness"',
    )
    ensure_fully_defined(adapter, "section A-A reference sketch")
    check("exit_sketch section A-A reference", adapter.exit_sketch())
    name_last_feature(adapter, spec.SECTION_A_REFERENCE)
    _require_parent(adapter, spec.SECTION_A_REFERENCE, spec.SECTION_A_PLANE)
    drive_jobs += dims.apply(adapter, spec.SECTION_A_REFERENCE)

    _section_plane(adapter, spec.SECTION_B_PLANE, spec.SECTION_B_X)
    dims = SketchDims()
    check(
        "create_sketch section B-B reference",
        adapter.create_sketch(spec.SECTION_B_PLANE),
    )
    fence = _chord(
        adapter,
        y_mm=0.0,
        z_from_mm=spec.PLATE_TOP_Z,
        z_to_mm=spec.FENCE_HEIGHT,
        label="fence face",
    )
    anchor_point_to_origin(adapter, f"{fence}.start", 0.0, 0.0, "fence face")
    _length(adapter, dims, fence, spec.FENCE_HEIGHT, "FenceHeight", '"FenceHeight"')
    ensure_fully_defined(adapter, "section B-B reference sketch")
    check("exit_sketch section B-B reference", adapter.exit_sketch())
    name_last_feature(adapter, spec.SECTION_B_REFERENCE)
    _require_parent(adapter, spec.SECTION_B_REFERENCE, spec.SECTION_B_PLANE)
    drive_jobs += dims.apply(adapter, spec.SECTION_B_REFERENCE)


def _require_parent(adapter: Any, sketch: str, plane: str) -> None:
    """create_sketch falls back to a standard plane when a named one fails to
    select (build_pd_platen._require_on_section_plane)."""
    feature = _early_bound(_feature_by_name(adapter, sketch), "IFeature")
    parents = [
        str(_early_bound(parent, "IFeature").Name)
        for parent in (feature.GetParents() or ())
    ]
    if plane not in parents:
        raise RuntimeError(f"{sketch} is not on {plane}: parents {parents}")


_TOL_NONE = 0  # swTolType_e.swTolNONE
_TEXT_SUFFIX = 2  # swDimensionTextParts_e.swDimensionTextSuffix


def _max_radius(adapter: Any, feature_name: str, dimension_name: str) -> None:
    """A cutter-formed corner as the single limit "R.07 MAX": the model value
    is the limit itself, the limit word its suffix with no native tolerance
    (build_pd_support_bar._max_limit), since swTolMAX prints a lowercase
    "max." (machinist review mr5)."""
    label = f"{dimension_name}@{feature_name}"
    display, dimension = _named_dimension(adapter, feature_name, dimension_name)
    value = float(dimension.SystemValue) * 1000.0
    if abs(value - spec.CORNER_RADIUS) > 1e-6:
        raise RuntimeError(f"{label}: nominal {value:.7f} is not the MAX limit")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = _TOL_NONE
    display = _early_bound(display, "IDisplayDimension")
    display.SetText(_TEXT_SUFFIX, spec.MAX_SUFFIX)  # void; the readback proves it
    if (
        int(tolerance.Type) != _TOL_NONE
        or str(display.GetText(_TEXT_SUFFIX) or "") != spec.MAX_SUFFIX
    ):
        raise RuntimeError(f"{label}: the MAX suffix did not persist")


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
    _section_references(adapter, drive_jobs)
    blank_reference_geometry(
        adapter,
        (
            (spec.FACED_TOP_PLANE, "PLANE"),
            (spec.SECTION_A_PLANE, "PLANE"),
            (spec.SECTION_B_PLANE, "PLANE"),
        ),
    )

    # Deferred drive equations; each evaluates to the value just built, so the
    # volume must not move.
    force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        drive_dimension(adapter, dimension_name, expression)
    force_rebuild(adapter)
    volume_check(adapter, "driven sub-plate (equations neutral)", volume, _V_TOL)

    apply_material(adapter, MATERIAL)
    report_mass_properties(adapter)

    # Explicit bands, each with its necessity entry: the hub hole's position
    # places the hub screw that centres the washer TL-VN-52 clear of the
    # outline cutter (N-01). A milled step within 6 in of its datum holds
    # +/-.002 (drawing-guidelines.md, "What the shop holds"); the tolerance
    # carries the nominal's three places.
    set_dimension_symmetric_tolerance(
        adapter,
        "HubHole",
        "HubX",
        spec.HUB_LOCATION_TOL,
        places=spec.DRAWING_PRECISION_BY_NAME["HubX"],
        display_unit=spec.UNIT,
    )
    set_dimension_symmetric_tolerance(
        adapter,
        "HubHole",
        "HubY",
        spec.HUB_LOCATION_TOL,
        places=spec.DRAWING_PRECISION_BY_NAME["HubY"],
        display_unit=spec.UNIT,
    )
    # Cutter-formed inside corners: the modelled radius is the MAX limit
    # (sharp up to it), above the title block's inside-corner row.
    for feature_name, dimension_name in spec.MAX_RADII:
        _max_radius(adapter, feature_name, dimension_name)
    for (feature_name, dimension_name), prefix in spec.DIMENSION_PREFIXES.items():
        set_dimension_prefix(adapter, feature_name, dimension_name, prefix)
    apply_drawing_precision(adapter, spec.DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in spec.DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": spec.ISOMETRIC_VIEW_NOTE}
    )
    # Construction-only: saved hidden so no assembly renders them; the
    # drawing shows each in its section (build_pd_platen's CboreFloorReference).
    blank_reference_sketches(
        adapter, (spec.SECTION_A_REFERENCE, spec.SECTION_B_REFERENCE)
    )
    artefacts = save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
