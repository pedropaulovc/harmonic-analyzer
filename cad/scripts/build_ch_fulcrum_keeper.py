r"""Reproduction script: fulcrum-shaft end keeper (book ch. 17 p. 40; 2 used).

The black bracket at each end of the top-lever fulcrum shaft (ch. 17 p. 40
bottom-left closeup and p. 2 img08; ch. 30 top view corners + eight-views
p008): a stubby straight L. The upright round-topped lug sits against the
outermost lever hub and carries the plain Ø6.35 fulcrum shaft in an F-drilled
bore, the shaft's domed end proud of its outer face; a #1-72 cup-point set
screw (MHA-CH-VN-55) in the crown tap bears on the shaft's flat and fixes it.
The short straight foot points OUTBOARD, stepped down to .227 (#3744 Panel F)
so one slotted #2-56 fillister frame-side screw (MHA-CH-VN-52) seats on the
open step with its head flush at .310; the foot-to-lug inside corner is
filleted at R.02 MAX (``CornerFillet``) so the screw head clears the root.

Layout (part frame): +X along the shaft, OUTBOARD (away from the lever
bank; the lug mid-plane / set-screw axis is x = 0); +Y up from the seat
(y = 0 lands on the rail top face, machine 1036.2); +Z across the 14 width.
The lug spans x -4..+4 from the seat up; the foot runs outboard from the
lug's outer face to x = +12.5, and the whole underside x -4..+12.5 is the
flat seat.

One part serves both ends: the assembly places the +Z (rear) end keeper
part-X -> machine +Z and the front keeper flipped Ry180.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_fulcrum_keeper.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _appearance import PANEL_BLACK, apply_color, apply_material
from _check import check
from _com import _early_bound, _read_member
from _dimensions import (
    drive_dimension,
    name_dimensions,
    set_global,
)
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _single_limit_tolerance import set_single_limit
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
from _drawing_precision import apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _hole_spec import blind_cut_dia_mm
from _holes import cross_hole_volume_mm3, wizard_hole_on_cylinder, wizard_holes
from ch_vn_frame_side_screw_spec import HEAD_DIA as FRAME_SIDE_HEAD_DIA
from ch_vn_frame_side_screw_spec import HEAD_H as FRAME_SIDE_HEAD_H
from ch_vn_frame_side_screw_spec import SHANK_DIA as FRAME_SIDE_SHANK_DIA
from ch_vn_frame_side_screw_spec import THREAD as FRAME_SIDE_THREAD
from ch_fulcrum_keeper_notes import DRAWING_NOTES
from ch_fulcrum_keeper_spec import (
    BORE_DIA,
    BORE_FROM_SIDE,
    CORNER_R_BAND,
    CORNER_R_MAX,
    CORNER_R_TOL_TYPE,
    CROWN_R,
    CROWN_TOP_Y,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FOOT_H,
    FOOT_L,
    FOOT_SCREW_HEAD_DIA_MM,
    FOOT_SCREW_HEAD_H_MM,
    FOOT_SCREW_SHANK_DIA_MM,
    FOOT_SCREW_THREAD,
    FOOT_TIP_X,
    FOOT_UNSTEPPED_H,
    HOLE_DIA_MM,
    ISOMETRIC_VIEW_NOTE,
    KEEPER_WIDTH,
    LUG_HALF_T,
    OVERALL_LENGTH,
    REFERENCE_SKETCHES,
    SCREW_FROM_SIDE,
    SCREW_FROM_TIP,
    SCREW_X,
    SCREW_HOLE_SPEC,
    SET_SCREW_HOLE_SPEC,
    SHAFT_AXIS_H,
)

PART_NAME = "ch-fulcrum-keeper"
MATERIAL = "Plain Carbon Steel"  # see _appearance.apply_material docstring

LUG_T = 2.0 * LUG_HALF_T  # 8.0 lug thickness along X
# Mid-plane through-cut total (both_directions splits the depth half per side
# of the sketch plane): past the lug's +-4 X extent, clear of the foot below.
BORE_CUT_DEPTH = 2.0 * LUG_T

# The keeper's foot screw seats on the .227 open foot step (#3744 Panel F),
# which steps down from .310 by the exact stock head height so the head top
# stays flush at .310.
if FOOT_SCREW_THREAD != FRAME_SIDE_THREAD:
    raise AssertionError("keeper foot screw thread drifted from MHA-CH-VN-52")
if FOOT_SCREW_SHANK_DIA_MM != FRAME_SIDE_SHANK_DIA:
    raise AssertionError("keeper foot screw shank drifted from MHA-CH-VN-52")
if FOOT_SCREW_HEAD_DIA_MM != FRAME_SIDE_HEAD_DIA:
    raise AssertionError("keeper foot screw head diameter drifted from MHA-CH-VN-52")
if FOOT_SCREW_HEAD_H_MM != FRAME_SIDE_HEAD_H:
    raise AssertionError("keeper foot screw head height drifted from MHA-CH-VN-52")
if HOLE_DIA_MM <= FRAME_SIDE_SHANK_DIA:
    raise AssertionError("standard #2 keeper clearance binds on the stock screw")
if HOLE_DIA_MM >= FRAME_SIDE_HEAD_DIA:
    raise AssertionError("keeper foot hole does not support the stock screw head")
if abs(FOOT_UNSTEPPED_H - FOOT_H - FRAME_SIDE_HEAD_H) > 1e-9:
    raise AssertionError("keeper foot step depth is not the stock head height")
# The crown tap's drill must stay inside the lug thickness, or the cross-hole
# volume below (a full crown cylinder across the drill) does not hold.
if blind_cut_dia_mm(SET_SCREW_HOLE_SPEC) >= LUG_T:
    raise AssertionError("crown tap drill breaks out of the lug faces")
# The foot-to-lug inside corner's fillet adds its spandrel, (1 - pi/4) R^2,
# along the keeper's width.
V_CORNER = (1.0 - math.pi / 4.0) * CORNER_R_MAX**2 * KEEPER_WIDTH

# The drawing-reference lines (ch_fulcrum_keeper_spec.REFERENCE_SKETCHES):
# (sketch, plane, dimension, start, end, orientation, value, drives), the
# dt_arbor_pedestal pattern. Each line starts on the feature it is measured
# from (drawing-guidelines.md rule 10 (dimension from a real feature)): the
# set-screw tap's runs on the seat (Top plane: sketch u = model X, v = -model
# Z) along the lug mid-width from the inner lug face -- the face the fit-up
# sets -- to the tap axis, so the plan dimensions it from the inner face's
# edge; the foot screw's two run on the seat from the foot-tip/-Z
# side corner along the side face to the screw station and down the tip
# face to the screw axis, so their extension lines leave the plan's outline
# without crossing; the bore's runs on the Right plane
# (the end view's frame) from a side face to the bore axis; the finished
# height's runs up the lug's inner face from the seat to the crown top; the
# overall length's along the seat from the inner lug face to the foot tip.
# ``drives`` binds the value dimension, then the start point's origin
# anchors, to the part's globals.
REFERENCE_LINES = (
    (
        "SetScrewReference",
        "Top",
        "SetScrewLocation",
        (-LUG_HALF_T, 0.0),
        (0.0, 0.0),
        "horizontal",
        LUG_HALF_T,
        ('"LugT" / 2', '"LugT" / 2'),
    ),
    (
        "FootScrewReference",
        "Top",
        "ScrewFromTip",
        (FOOT_TIP_X, SCREW_FROM_SIDE),
        (SCREW_X, SCREW_FROM_SIDE),
        "horizontal",
        SCREW_FROM_TIP,
        ('"FootScrewFromTip"', '"LugT" / 2 + "FootL"', '"KeeperWidth" / 2'),
    ),
    (
        "FootScrewSideReference",
        "Top",
        "ScrewFromSide",
        (FOOT_TIP_X, SCREW_FROM_SIDE),
        (FOOT_TIP_X, 0.0),
        "vertical",
        SCREW_FROM_SIDE,
        ('"KeeperWidth" / 2', '"LugT" / 2 + "FootL"', '"KeeperWidth" / 2'),
    ),
    (
        "BoreSideReference",
        "Right",
        "BoreFromSide",
        (BORE_FROM_SIDE, SHAFT_AXIS_H),
        (0.0, SHAFT_AXIS_H),
        "horizontal",
        BORE_FROM_SIDE,
        ('"KeeperWidth" / 2', '"KeeperWidth" / 2', '"ShaftAxisH"'),
    ),
    (
        "OverallHeightReference",
        "Front",
        "OverallHeight",
        (-LUG_HALF_T, 0.0),
        (-LUG_HALF_T, CROWN_TOP_Y),
        "vertical",
        CROWN_TOP_Y,
        ('"ShaftAxisH" + "CrownR"', '"LugT" / 2'),
    ),
    (
        "OverallLengthReference",
        "Front",
        "OverallLength",
        (-LUG_HALF_T, 0.0),
        (FOOT_TIP_X, 0.0),
        "horizontal",
        OVERALL_LENGTH,
        ('"LugT" + "FootL"', '"LugT" / 2'),
    ),
)
if tuple(row[0] for row in REFERENCE_LINES) != REFERENCE_SKETCHES:
    raise AssertionError("REFERENCE_LINES and REFERENCE_SKETCHES disagree")


def _as_construction(adapter, entity_id: str) -> None:
    """Flag a registered sketch line as construction geometry (the setter is
    on ISketchSegment, not the ISketchLine the registry binds)."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


def _reference_line(
    adapter, sketch, plane, dimension, start, end, orientation, value, drives
) -> list[tuple[str, str]]:
    """One hidden-reference sketch: a construction line whose driving
    dimension IS ``value``; returns its deferred drive jobs."""
    check(f"create_sketch {sketch}", adapter.create_sketch(plane))
    # Direct-to-DB: the line lies on an outline station along a sketch axis
    # direction, so creation-time inference would over-define the sketch.
    set_sketch_direct_db(adapter, True)
    line = check(f"{sketch} line", adapter.add_line(*start, *end))
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, line)
    check(
        f"{sketch} {orientation}",
        adapter.add_sketch_constraint(line, None, orientation),
    )
    dimension_between(
        adapter,
        f"{line}.start",
        f"{line}.end",
        f"{orientation}_distance",
        value,
        sketch,
    )
    anchor_point_to_origin(adapter, f"{line}.start", *start, sketch)
    names = [dimension, *(f"{dimension}Anchor{i}" for i in range(1, len(drives)))]
    ensure_fully_defined(adapter, f"{sketch} sketch")
    check(f"exit_sketch {sketch}", adapter.exit_sketch())
    name_last_feature(adapter, sketch)
    full = name_dimensions(adapter, sketch, names)
    measured = (
        float(
            _early_bound(
                adapter.currentModel.Parameter(full[0]), "IDimension"
            ).SystemValue
        )
        * 1000.0
    )
    if abs(measured - value) > 1e-6:
        raise RuntimeError(f"{full[0]} measures {measured:g} mm, expected {value:g} mm")
    return list(zip(full, drives, strict=True))


@_telemetry.traced("appearance.hide_reference_sketches")
def _hide_reference_sketches(adapter) -> None:
    """Blank the drawing-reference sketches and prove each one reads hidden."""
    for name in REFERENCE_SKETCHES:
        blank_sketch(adapter, name)
    part = _early_bound(adapter.currentModel, "IPartDoc")
    shown = {
        name: visible
        for name in REFERENCE_SKETCHES
        # swVisibilityState_e: 1 hidden
        if (visible := int(_read_member(part.FeatureByName(name), "Visible"))) != 1
    }
    if shown:
        raise RuntimeError(f"reference sketches still visible after blanking: {shown}")


def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH
    # document; the equation manager reads bare numbers in document units).
    set_global(adapter, "FootL", f"{FOOT_L}mm")
    set_global(adapter, "FootH", f"{FOOT_H}mm")
    set_global(adapter, "KeeperWidth", f"{KEEPER_WIDTH}mm")
    set_global(adapter, "LugT", f"{LUG_T}mm")
    set_global(adapter, "ShaftAxisH", f"{SHAFT_AXIS_H}mm")
    set_global(adapter, "CrownR", f"{CROWN_R}mm")
    set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    set_global(adapter, "CornerR", f"{CORNER_R_MAX}mm")
    set_global(adapter, "FootScrewFromTip", f"{SCREW_FROM_TIP}mm")

    drive_jobs: list[tuple[str, str]] = []

    # --- Lug: end-profile rectangle on Right (ZY), extruded +-X -----------
    # From the seat up to the shaft axis; the crown rounds it off above.
    lug = SketchDims()
    check("create_sketch lug", adapter.create_sketch("Right"))
    half_w = KEEPER_WIDTH / 2.0
    lug_pts = [
        (-half_w, 0.0),
        (half_w, 0.0),
        (half_w, SHAFT_AXIS_H),
        (-half_w, SHAFT_AXIS_H),
    ]
    lug_lines = add_line_chain(adapter, lug_pts)
    define_rectilinear_chain(
        adapter,
        lug_lines,
        lug_pts,
        label="lug profile",
        dims=lug,
        names=["LugWidth", "LugRise", "LugAnchorZ"],
        drives=['"KeeperWidth"', '"ShaftAxisH"', '"KeeperWidth" / 2'],
    )
    ensure_fully_defined(adapter, "lug profile")
    check("exit_sketch lug", adapter.exit_sketch())
    name_last_feature(adapter, "LugProfile")
    drive_jobs += lug.apply(adapter, "LugProfile")
    check(
        "extrude lug",
        adapter.create_extrusion(
            ExtrusionParameters(depth=LUG_T, both_directions=True)
        ),
    )
    name_last_feature(adapter, "LugBody")
    lug_depth = name_dimensions(adapter, "LugBody", ["LugThickness"])
    drive_jobs += [(lug_depth[0], '"LugT"')]
    v_lug = KEEPER_WIDTH * SHAFT_AXIS_H * LUG_T
    volume = volume_check(adapter, "lug", v_lug, 0.005 * v_lug)

    # --- Foot: side-profile rectangle on Front (XY), extruded +-Z ---------
    # Outboard of the lug's outer face, x +4..+12.5, y 0..5.77; its underside
    # is coplanar with the lug's, so the two make one flat seat.
    foot = SketchDims()
    check("create_sketch foot", adapter.create_sketch("Front"))
    pts = [
        (LUG_HALF_T, 0.0),
        (FOOT_TIP_X, 0.0),
        (FOOT_TIP_X, FOOT_H),
        (LUG_HALF_T, FOOT_H),
    ]
    lines = add_line_chain(adapter, pts)
    define_rectilinear_chain(
        adapter,
        lines,
        pts,
        label="foot profile",
        dims=foot,
        names=["FootLength", "FootRise", "FootAnchorX"],
        drives=['"FootL"', '"FootH"', '"LugT" / 2'],
    )
    ensure_fully_defined(adapter, "foot profile")
    check("exit_sketch foot", adapter.exit_sketch())
    name_last_feature(adapter, "FootProfile")
    drive_jobs += foot.apply(adapter, "FootProfile")
    check(
        "extrude foot",
        adapter.create_extrusion(
            ExtrusionParameters(depth=KEEPER_WIDTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Foot")
    depth_dim = name_dimensions(adapter, "Foot", ["Depth"])
    drive_jobs += [(depth_dim[0], '"KeeperWidth"')]
    v_foot = FOOT_L * FOOT_H * KEEPER_WIDTH
    volume = volume_check(adapter, "foot", volume + v_foot, 0.005 * v_foot)

    # Foot-to-lug inside corner (drawing-guidelines.md rule 16; #3744 Panel F):
    # the edge where the .227 foot top meets the lug's outer face, modelled at
    # R.02 MAX (CORNER_R_MAX) so the Ø.140 fillister head clears the root.
    check(
        "fillet foot-to-lug corner",
        adapter.add_fillet(
            CORNER_R_MAX, [[LUG_HALF_T, FOOT_H, 0.0]], propagate=False
        ),
    )
    name_last_feature(adapter, "CornerFillet")
    corner_dim = name_dimensions(adapter, "CornerFillet", ["CornerRadius"])
    drive_jobs.append((corner_dim[0], '"CornerR"'))
    volume = volume_check(
        adapter, "foot-to-lug corner fillet", volume + V_CORNER, 0.1 * V_CORNER
    )

    # --- Crown: full-round lug top, concentric with the shaft axis --------
    crown = SketchDims()
    check("create_sketch crown", adapter.create_sketch("Right"))
    define_circle(
        adapter,
        0.0,
        SHAFT_AXIS_H,
        CROWN_R,
        "lug crown",
        dims=crown,
        names=("CrownCz", "ShaftAxisH", "CrownRadius"),
        drives=(None, '"ShaftAxisH"', '"CrownR"'),
        size_dimension="radius",
    )
    ensure_fully_defined(adapter, "lug crown sketch")
    check("exit_sketch crown", adapter.exit_sketch())
    name_last_feature(adapter, "LugCrownProfile")
    drive_jobs += crown.apply(adapter, "LugCrownProfile")
    check(
        "extrude crown",
        adapter.create_extrusion(
            ExtrusionParameters(depth=LUG_T, both_directions=True)
        ),
    )
    name_last_feature(adapter, "LugCrown")
    crown_depth = name_dimensions(adapter, "LugCrown", ["Depth"])
    drive_jobs += [(crown_depth[0], '"LugT"')]
    r_c = CROWN_R
    # The crown circle's lower half merges into the lug rectangle (its centre
    # sits ON the lug top edge and its bottom, y 18.2, is inside the lug), so
    # only the upper half adds metal.
    v_crown = 0.5 * math.pi * r_c * r_c * LUG_T
    volume = volume_check(adapter, "lug crown", volume + v_crown, 0.01 * v_crown)

    # --- Shaft bore: plain F-drilled Ø.257 through the lug on the axis ------
    bore = SketchDims()
    check("create_sketch bore", adapter.create_sketch("Right"))
    define_circle(
        adapter,
        0.0,
        SHAFT_AXIS_H,
        BORE_DIA / 2.0,
        "shaft bore",
        dims=bore,
        names=("BoreCz", "BoreH", "BoreDia"),
        drives=(None, '"ShaftAxisH"', '"BoreDia"'),
    )
    ensure_fully_defined(adapter, "shaft bore sketch")
    check("exit_sketch bore", adapter.exit_sketch())
    name_last_feature(adapter, "ShaftBoreProfile")
    drive_jobs += bore.apply(adapter, "ShaftBoreProfile")
    check(
        "cut bore",
        adapter.create_cut_extrude(
            ExtrusionParameters(depth=BORE_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ShaftBore")
    # Coaxial cylinder through the 8.0 lug only: the bore (y 22.0..28.4)
    # lies wholly inside the lug + crown and well above the foot (y <= 5.77).
    v_bore = math.pi * (BORE_DIA / 2.0) ** 2 * LUG_T
    volume = volume_check(adapter, "shaft bore", volume - v_bore, 0.01 * v_bore)

    # --- Foot screw hole: #2 close-clearance through the .227 foot ----------
    screw_hole = wizard_holes(
        adapter,
        SCREW_HOLE_SPEC,
        [[SCREW_X, FOOT_H, 0.0]],
        (0.0, 1.0, 0.0),
        "keeper foot screw hole (#2 close clearance)",
        expect_dia_mm=HOLE_DIA_MM,
        name="FootScrewHole",
    )
    v_thru = math.pi * (screw_hole.hole_dia_mm / 2.0) ** 2 * FOOT_H
    volume = volume_check(
        adapter, "foot screw hole", volume - v_thru, 0.01 * v_thru
    )

    # --- Crown set-screw tap: #1-72 down through the crown top ------------
    # ONE native tapped hole drilled radially into the crown cylinder at its
    # apex on the lug mid-plane and stopped at the next surface -- the shaft
    # bore -- so it never runs on through the lug (the dt_arbor_pedestal
    # apex-tap idiom). Right Plane (x = 0) and Front Plane (z = 0) pin the
    # 3D placement point onto the apex.
    wizard_hole_on_cylinder(
        adapter,
        SET_SCREW_HOLE_SPEC,
        [0.0, CROWN_TOP_Y, 0.0],
        f"crown set-screw tap ({SET_SCREW_HOLE_SPEC.size})",
        name="SetScrewTap",
        point_planes=("Right Plane", "Front Plane"),
    )
    # The tap drill removes the crown wall between the crown and the bore:
    # half of each perpendicular cross-hole volume, crown minus bore (the
    # drill's +-0.76 footprint along X stays inside the 8.0 lug, so the crown
    # is a full cylinder across it).
    tap_dia = blind_cut_dia_mm(SET_SCREW_HOLE_SPEC)
    v_tap = (
        cross_hole_volume_mm3(tap_dia, 2.0 * CROWN_R)
        - cross_hole_volume_mm3(tap_dia, BORE_DIA)
    ) / 2.0
    volume = volume_check(
        adapter, "crown set-screw tap", volume - v_tap, 0.03 * v_tap
    )

    # The tap station's drawing-reference line (no metal).
    for row in REFERENCE_LINES:
        drive_jobs += _reference_line(adapter, *row)

    # Deferred drive equations, then re-check neutrality (each evaluates to
    # the as-built value, so the geometry must not move).
    force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        drive_dimension(adapter, dim_name, expr)
    force_rebuild(adapter)
    volume_check(
        adapter, "driven keeper (equations neutral)", volume, 0.005 * volume
    )
    _hide_reference_sketches(adapter)
    # Decimal places are the tolerance statement, so the PART carries them;
    # the F-drilled bore takes the DRILLED HOLES row (owner ruling
    # 2026-11-24, fit audit question 1): no native band.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    set_single_limit(
        adapter,
        "CornerFillet",
        "CornerRadius",
        limit=CORNER_R_MAX,
        band=CORNER_R_BAND,
        tol_type=CORNER_R_TOL_TYPE,
    )

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)

    apply_material(adapter, MATERIAL)
    apply_color(adapter, PANEL_BLACK)
    report_mass_properties(adapter)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
