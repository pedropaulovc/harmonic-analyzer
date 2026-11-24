r"""Reproduction script: transgear knob cup (MHA-PD-16; ch. 23; 1 used).

The blind brass cup on the knob shaft's rear journal end: its end-milled front
pilot is bonded on the journal with LOCTITE 641 and the MHA-PD-VN-71 #2-56
fillister, its head sunk in the rear pocket, passes the web's #33 hole into
the journal's rear tap (owner ruling 2026-11-20 (Pedro), #2425).  Its front
face runs behind the MHA-PD-28 bush's rear face, the rear stop of the knob's
end float (``pd_transgear_knob_cup_spec``).

Layout: one turned half-section on the Front plane, revolved about local +Y:
the pilot, the O.D. and the rear pocket closed along the axis, so the O.D.,
the length, the pilot's Ø and depth and the pocket's Ø and depth are its
driving dimensions and all print on the drawing's axial section.  The web's
#33 hole is a separate Top-plane cut through everything, sized where it
shows round.  The pilot's and the pocket's floor corners are tangent arcs
in the profile sketch at their R.xxx MAX limits, so their radii import into
the section with the other profile dimensions.  The front face is the Top Plane (y = 0), the rear face
y = LENGTH.  ``Axis1`` is the cup axis (Front Plane ∩ Right Plane).  The
paper-drive assembly mates ``Axis1`` to the knob shaft's axis and the Top
Plane to the shaft's cup-face station.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_transgear_knob_cup.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, set_global
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _document_units import apply_package_model_units
from _part_pmi import author_part_pmi
from _part_properties import part_drawing_unit
from _sketch_circle import define_circle
from pd_transgear_knob_cup_spec import (
    BORE_DIA,
    CBORE_DEPTH,
    CBORE_DIA,
    CLEAR_HOLE_DIA,
    CORNER_SUFFIX,
    CORNER_TOL_TYPE,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    LENGTH,
    OD,
    PILOT_DEPTH,
    PILOT_FLOOR_R_MAX,
    POCKET_FLOOR_R_MAX,
    SURFACE_FINISHES,
    WEB,
)

PART_NAME = "pd-transgear-knob-cup"
MATERIAL = "Brass"  # C36000 free-machining brass (the registry row names it)

CUP_R = OD / 2.0
BORE_R = BORE_DIA / 2.0
CBORE_R = CBORE_DIA / 2.0
HOLE_R = CLEAR_HOLE_DIA / 2.0
V_BODY = math.pi * CUP_R**2 * LENGTH
V_PILOT = math.pi * BORE_R**2 * PILOT_DEPTH
V_CBORE = math.pi * CBORE_R**2 * CBORE_DEPTH
V_TURNED = V_BODY - V_PILOT - V_CBORE
V_HOLE = math.pi * HOLE_R**2 * WEB


def _floor_corner_volume(radius: float, wall_r: float) -> float:
    """Metal a floor corner arc of ``radius`` adds inside a bore wall at
    ``wall_r``: the (1 - pi/4) r^2 spandrel, revolved at its centroid, which
    stands r (10 - 3 pi) / (3 (4 - pi)) in from the wall."""
    centroid_in = radius * (10.0 - 3.0 * math.pi) / (3.0 * (4.0 - math.pi))
    return (1.0 - math.pi / 4.0) * radius**2 * 2.0 * math.pi * (wall_r - centroid_in)


V_CORNERS = _floor_corner_volume(PILOT_FLOOR_R_MAX, BORE_R) + _floor_corner_volume(
    POCKET_FLOOR_R_MAX, CBORE_R
)
V_CUP = V_TURNED - V_HOLE + V_CORNERS


def _corner_max_limits(adapter) -> None:
    """Each floor corner as the single limit "R.xxx MAX": no native
    tolerance, " MAX" its suffix (build_pd_transgear_knob_bush's shoulder
    root), since swTolMAX prints a lowercase "max."."""
    for name in ("PilotFloorR", "PocketFloorR"):
        display, dimension = _named_dimension(adapter, "CupProfile", name)
        # Equation-owned dimensions can read DrivenState 1; IsReference is the
        # native controlling/reference distinction (build_dt_crank_handle_butt_cup).
        if bool(dimension.IsReference()):
            raise RuntimeError(f"{name}@CupProfile: radius is a reference dimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        tolerance.Type = CORNER_TOL_TYPE
        display = _early_bound(display, "IDisplayDimension")
        display.SetText(2, CORNER_SUFFIX)  # swDimensionTextSuffix
        if (
            int(tolerance.Type) != CORNER_TOL_TYPE
            or str(display.GetText(2) or "") != CORNER_SUFFIX
        ):
            raise RuntimeError(f"{name}: the MAX single limit did not persist")


def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    for name, value in (
        ("CupDia", OD),
        ("CupLength", LENGTH),
        ("BoreDia", BORE_DIA),
        ("PilotDepth", PILOT_DEPTH),
        ("CboreDia", CBORE_DIA),
        ("CboreDepth", CBORE_DEPTH),
        ("PilotFloorR", PILOT_FLOOR_R_MAX),
        ("PocketFloorR", POCKET_FLOOR_R_MAX),
        ("HoleDia", CLEAR_HOLE_DIA),
    ):
        set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Turned half-section about local +Y: in along the pilot's floor, round
    # its floor corner, out the pilot's wall to the front face, the O.D., the
    # rear face, down the pocket's wall, round its floor corner and in along
    # its floor, closed on the axis.  Every turned size and both corner radii
    # are profile dimensions that print on the axial section (rule 11).
    rp, rq = PILOT_FLOOR_R_MAX, POCKET_FLOOR_R_MAX
    pocket_floor_y = LENGTH - CBORE_DEPTH
    pilot_floor_end = (BORE_R - rp, PILOT_DEPTH)
    pilot_wall_start = (BORE_R, PILOT_DEPTH - rp)
    pocket_wall_end = (CBORE_R, pocket_floor_y + rq)
    pocket_floor_start = (CBORE_R - rq, pocket_floor_y)
    profile = SketchDims()
    check("create_sketch cup profile", adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check("cup axis", adapter.add_centerline(0.0, 0.0, 0.0, LENGTH))
    (pilot_floor,) = add_line_chain(
        adapter, [(0.0, PILOT_DEPTH), pilot_floor_end], close=False
    )
    # add_arc is CCW: wall (0 deg) -> floor (90 deg) is the quarter arc.
    pilot_round = check(
        "pilot floor round",
        adapter.add_arc(
            BORE_R - rp, PILOT_DEPTH - rp, *pilot_wall_start, *pilot_floor_end
        ),
    )
    outer_points = [
        pilot_wall_start,
        (BORE_R, 0.0),
        (CUP_R, 0.0),
        (CUP_R, LENGTH),
        (CBORE_R, LENGTH),
        pocket_wall_end,
    ]
    outer = add_line_chain(adapter, outer_points, close=False)
    # Floor (270 deg) -> wall (360 deg), CCW.
    pocket_round = check(
        "pocket floor round",
        adapter.add_arc(
            CBORE_R - rq, pocket_floor_y + rq, *pocket_floor_start, *pocket_wall_end
        ),
    )
    inner_points = [pocket_floor_start, (0.0, pocket_floor_y), (0.0, PILOT_DEPTH)]
    cbore_floor, web_axis = add_line_chain(adapter, inner_points, close=False)
    set_sketch_direct_db(adapter, False)
    pilot_wall, front_face, od_line, rear_face, cbore_wall = outer
    for line, relation in (
        (pilot_floor, "horizontal"),
        (pilot_wall, "vertical"),
        (front_face, "horizontal"),
        (od_line, "vertical"),
        (rear_face, "horizontal"),
        (cbore_wall, "vertical"),
        (cbore_floor, "horizontal"),
    ):
        check(
            f"cup profile {relation} {line}",
            adapter.add_sketch_constraint(line, None, relation),
        )
    # The closing edge lies on the axis: collinear with the centerline, so
    # both web-floor points sit on it.
    check(
        "cup web on the axis",
        adapter.add_sketch_constraint(web_axis, axis, "collinear"),
    )
    check(
        "cup axis vertical", adapter.add_sketch_constraint(axis, None, "vertical")
    )
    anchor_point_to_origin(adapter, f"{axis}.start", 0.0, 0.0, "cup axis origin")
    check(
        "cup front face on the Top plane",
        adapter.add_sketch_constraint(
            f"{front_face}.start", "origin", "horizontal_points"
        ),
    )
    add_diametric_linear_dimension(
        adapter, axis, od_line, (CUP_R + 4.0, LENGTH / 2.0), "CupDia"
    )
    profile.record("CupDia", '"CupDia"')
    check(
        "cup length",
        adapter.add_sketch_dimension(od_line, None, "linear", LENGTH),
    )
    profile.record("CupLength", '"CupLength"')
    check(
        "cup axis length",
        adapter.add_sketch_dimension(axis, None, "linear", LENGTH),
    )
    profile.record("AxisLength", '"CupLength"')
    add_diametric_linear_dimension(
        adapter, axis, pilot_wall, (BORE_R - 1.5, PILOT_DEPTH / 2.0), "BoreDia"
    )
    profile.record("BoreDia", '"BoreDia"')
    # Front face to the FLAT floor, not the wall segment the round shortens.
    dimension_between(
        adapter,
        f"{front_face}.start",
        f"{pilot_floor}.start",
        "vertical_distance",
        PILOT_DEPTH,
        "cup pilot depth to the floor",
    )
    profile.record("PilotDepth", '"PilotDepth"')
    add_diametric_linear_dimension(
        adapter,
        axis,
        cbore_wall,
        (CBORE_R - 1.0, LENGTH - CBORE_DEPTH / 2.0),
        "CboreDia",
    )
    profile.record("CboreDia", '"CboreDia"')
    dimension_between(
        adapter,
        f"{rear_face}.start",
        f"{cbore_floor}.start",
        "vertical_distance",
        CBORE_DEPTH,
        "cup pocket depth to the floor",
    )
    profile.record("CboreDepth", '"CboreDepth"')
    for name, arc, radius in (
        ("PilotFloorR", pilot_round, rp),
        ("PocketFloorR", pocket_round, rq),
    ):
        check(
            f"cup {name}", adapter.add_sketch_dimension(arc, None, "radial", radius)
        )
        profile.record(name, f'"{name}"')
    for first, second, label in (
        (pilot_floor, pilot_round, "pilot floor"),
        (pilot_round, pilot_wall, "pilot wall"),
        (cbore_wall, pocket_round, "pocket wall"),
        (pocket_round, cbore_floor, "pocket floor"),
    ):
        check(
            f"floor round tangent to {label}",
            adapter.add_sketch_constraint(first, second, "tangent"),
        )
    ensure_fully_defined(adapter, "cup profile")
    check("exit_sketch cup profile", adapter.exit_sketch())
    name_last_feature(adapter, "CupProfile")
    drive_jobs += profile.apply(adapter, "CupProfile")
    check("revolve cup", adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "CupBody")
    volume_check(adapter, "turned blind cup", V_TURNED + V_CORNERS, 0.01 * V_PILOT)
    bbox_extent_check(adapter, "cup length", "y", LENGTH)
    bbox_extent_check(adapter, "cup O.D.", "x", OD)

    # The web's #33 drill on the axis, cut through everything from the Top
    # plane both ways: it only meets the web between pilot and pocket.
    web_hole = SketchDims()
    check("create_sketch web hole", adapter.create_sketch("Top"))
    define_circle(
        adapter,
        0.0,
        0.0,
        HOLE_R,
        "web hole",
        dims=web_hole,
        names=("HoleCx", "HoleCz", "HoleDia"),
        drives=(None, None, '"HoleDia"'),
    )
    ensure_fully_defined(adapter, "web hole sketch")
    check("exit_sketch web hole", adapter.exit_sketch())
    name_last_feature(adapter, "WebHole")
    drive_jobs += web_hole.apply(adapter, "WebHole")
    check(
        "cut web hole",
        adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * LENGTH + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "WebHoleCut")
    volume_check(adapter, "drilled cup", V_CUP, 0.01 * V_HOLE)

    # The mate axis: the first reference axis, so it is Axis1.
    cup_axis = name_bore_axis(
        adapter, "Front Plane", 0.0, "Right Plane", 0.0, "cup axis"
    )
    if cup_axis != "Axis1":
        raise RuntimeError(f"cup axis came back {cup_axis!r}, not Axis1")

    # Deferred drive equations, then re-check neutrality.
    force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        drive_dimension(adapter, dim_name, expr)
    force_rebuild(adapter)
    volume_check(
        adapter, "driven cup (equations neutral)", V_CUP, 0.01 * V_HOLE
    )

    apply_material(adapter, MATERIAL)
    report_mass_properties(adapter)
    # The pilot's Ø prints REF (made to fit the MHA-PD-08 journal): no band.
    _corner_max_limits(adapter)
    # Every other printed dimension is governed by its places (the spec's
    # DRAWING_PRECISION): no model band.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # The front face: the running face on the bush's rear face.
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(adapter, PART_NAME)
    return save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
