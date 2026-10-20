r"""Reproduction script: connecting rod (book ch. 13 pp. 22-25 / ch. 14 p. 29; 20 used).

Black rod machined from 1018 low-carbon steel plate, converting each cam's
rotation into the rocker arm's see-saw: a full ring (strap) riding the Ø30.6
eccentric cam (cast integral with each cylinder gear), a thin flat shank, and a
U-shaped FORK (clevis; the Y-shaped upper end of the ch14 fan photo) whose two
tines straddle the rocker arm's 2.500 strap and carry the pressed pivot pin
(MHA-CH-10, ch_rod_pivot_pin_spec) through the arm's rod-pin hole near its
rod-side tip. The centre distance follows the actual phased cam centre and the
level rocker's pin, including the common raised drive-axis height. The ch14
end views show the 0-crank tip row level (cos-mode home = top of stroke, cam
lobe UP); the rod length closes that link without moving the rocker bank.

The rod is FLAT: ring, shank and fork share one mid-plane, which is the cam
plane and the arm plane (rocker_bank_layout.ARM_MID_DZ = CAM_MID_DZ), so the
arm runs centred in the fork slot. The fork is 10 wide with a full-round
crown on the pin; its two 1.700 +/-0.05 tines straddle a 2.675 +/-0.05 slot
(Main ruling 2026-10, option b): each inter-arm gap holds one tine of each
neighbouring rod, so tines, slot and the ring/shank faces are model bands
located from one finished fork face (#982). The pin is pressed into a
hole reamed through both tines and dressed flush (user ruling 2026-10-09, PR
#1292 review F1, reversing the #746 reconstruction choice of peening it into
countersinks): the photos show two rod cheeks round each rocker, not the
original fastener.

Dimensions: cad/config/dimensions.yaml "Chapter 13" rod rows - centre distance
derived (high), ring bore derived from the cam OD + confirmed on the p.25
overlay (med), fork proportions photo-scaled vs the 16 mm arm-depth callout
and sized to the joint budget (ch_rod_pivot_pin_spec), everything else
photo-scaled (low).

Layout: ring centre at the origin, shank rising +Y to the fork; thicknesses
extruded mid-plane in Z. Build order matters: the plate (ring and shank, one
outline) and the fork are bossed first, the slot is cut through the fork,
then the bore.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_connecting_rod.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import _feature_by_name, name_last_feature
from _part_checks import report_mass_properties, volume_check
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
from _sketch_circle import define_circle
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _drawing_tolerances import set_dimension_bilateral_tolerance, set_dimension_symmetric_tolerance
from _fit_deviations import deviations
from _part_pmi import author_part_pmi
import _telemetry
from _saved_part_guard import require_saved_drawing_properties
from ch_connecting_rod_notes import DRAWING_NOTES, ISOMETRIC_VIEW_NOTE
from ch_connecting_rod_notes import DRAWING_DIMENSIONS, DRAWING_PRECISION
from ch_connecting_rod_spec import (
    CENTER_DISTANCE,
    FORK_BASE_BELOW_PIN,
    FORK_BASE_Y,
    FORK_CROTCH_BELOW_PIN,
    FORK_CROTCH_Y,
    FORK_CROWN_RADIUS,
    FORK_SLOT_BAND,
    FORK_SLOT_WIDTH,
    FORK_THICKNESS,
    FORK_TOP_Y,
    FORK_WIDTH,
    INSIDE_CORNER_BAND,
    INSIDE_CORNER_R,
    INSIDE_CORNER_TOL_TYPE,
    PIN_HOLE_BAND,
    PIN_HOLE_DIA,
    RING_BORE_DIA,
    RING_BORE_DIA_BAND,
    RING_FACE_BAND,
    RING_FACE_NEAR,
    RING_OUTER_RADIUS,
    RING_THICKNESS,
    RING_THICKNESS_BAND,
    RING_WALL,
    ROOT_RELIEF_ANGLE_DEG,
    ROOT_RELIEF_BAND,
    ROOT_RELIEF_SIZE,
    SHANK_THICKNESS,
    SHANK_WIDTH,
    SURFACE_FINISHES,
    TINE_BAND,
    TINE_THICKNESS,
)

PART_NAME = "ch-connecting-rod"
# AISI 1018 plate (the registry row's material_specification); SOLIDWORKS's
# library carries it as Plain Carbon Steel -- see _appearance.apply_material.
MATERIAL = "Plain Carbon Steel"

# Cam ring centre -> rocker pin, VERTICAL rod: the
# pin rides the arm's rod-pin hole 133.067 out from the pivot -- directly
# above the phased cam LOBE (shared drive height plus the eccentricity
# rotated by the configured tooth phase),
# lobe UP at the cos-mode home; the Ry180 axial flip preserves local +Y;
# ch30 photos + GT rocker-corner triangulation put the arm's rod-side end over
# the drum). Solved so the rocker rests LEVEL (arm tilt 0 -- the ch14 end views
# show the 0-crank tip row flat at the TOP of the stroke) with the rod plumb
# (rod tilt 0 by construction). Supersedes 144.75, the same closure at the
# pre-ROM-fit lobe-down phase and -7.82 deg tilt. build_ch_channel_assembly
# imports this as ROD_C2C (imported, NOT copied). Nominal geometry lives in
# ch_connecting_rod_spec so the part, channel and drawing move as one recipe.
# The fork (the "Y" upper end of the ch14 fan photo, read as two cheeks round
# each rocker): a U-shaped clevis whose tines straddle the rocker strap and
# hold the pressed pivot pin. Its proportions live in ch_connecting_rod_spec;
# the slot cut runs out SLOT_RUNOUT above the crown so the crown alone shapes
# the tine tops.
SLOT_RUNOUT = 1.0  # unprinted
# The ring/shank near-face reference runs this far down the shank from the
# fork root, so its ordinate prints below the fork in its side detail.
RING_FACE_REF_RUN = 2.0  # unprinted
# The rocker pivot pin hole is a reamed press hole; its size and band live in
# ch_connecting_rod_spec.
THROUGH_CUT_DEPTH = 20.0  # mid-plane total; > any local thickness or width

FORK_BOSS_LENGTH = FORK_TOP_Y - FORK_BASE_Y  # crown top -> root step (18.0)
SLOT_DEPTH = FORK_TOP_Y - FORK_CROTCH_Y  # crown top -> slot floor (14.75)
SLOT_CUT_HEIGHT = SLOT_DEPTH + SLOT_RUNOUT


def _circle_cap_area(radius: float, half_width: float) -> float:
    """Area under y = sqrt(R^2 - x^2) for |x| <= half_width."""
    return half_width * math.sqrt(radius**2 - half_width**2) + radius**2 * math.asin(
        half_width / radius
    )


def fork_outline_area(from_y: float) -> float:
    """Front-plane area of the fork outline (the root rectangle plus the crown
    semicircle on the pin) at and above ``from_y`` (FORK_BASE_Y..pin)."""
    return FORK_WIDTH * (CENTER_DISTANCE - from_y) + math.pi * FORK_CROWN_RADIUS**2 / 2.0


def boss_volume() -> float:
    """Plate (ring disc and shank, one outline) + fork boss before any cut:
    the shank counts only its run from the ring OD to the fork root."""
    shank_area = SHANK_WIDTH * FORK_BASE_Y - _circle_cap_area(
        RING_OUTER_RADIUS, SHANK_WIDTH / 2.0
    )
    return (
        math.pi * RING_OUTER_RADIUS**2 * RING_THICKNESS
        + shank_area * SHANK_THICKNESS
        + fork_outline_area(FORK_BASE_Y) * FORK_THICKNESS
    )


def slot_volume() -> float:
    """The slot runs through the fork's width above the crotch."""
    return fork_outline_area(FORK_CROTCH_Y) * FORK_SLOT_WIDTH


def strap_bore_volume() -> float:
    return math.pi * (RING_BORE_DIA / 2.0) ** 2 * RING_THICKNESS


def root_relief_volume() -> float:
    """One conical bore-mouth wedge, minus its original straight bore."""
    # At the authored 45 degrees both physical legs equal native Width;
    # the tolerance envelope in the spec bounds either leg ordering.
    radial = ROOT_RELIEF_SIZE
    axial = radial * math.tan(math.radians(ROOT_RELIEF_ANGLE_DEG))
    return math.pi * axial * (RING_BORE_DIA / 2.0 * radial + radial**2 / 3.0)


def pin_hole_volume() -> float:
    """The reamed hole crosses the slot, so it only cuts the two tines."""
    return math.pi * (PIN_HOLE_DIA / 2.0) ** 2 * (FORK_THICKNESS - FORK_SLOT_WIDTH)


def _fillet_area(radius: float, opening: float) -> float:
    """Section area a radius adds in a straight concave corner whose walls
    meet at ``opening`` radians across the air."""
    return radius**2 * (1.0 / math.tan(opening / 2.0) - (math.pi - opening) / 2.0)


# The shank's flank meets the ring's OD at its tangent's angle: the air
# between them opens past square by the flank's angle on the circle.
SHANK_RING_OPENING = math.pi / 2.0 + math.asin(SHANK_WIDTH / 2.0 / RING_OUTER_RADIUS)


def inside_corner_volume() -> float:
    """The inside-corner fillets: the slot floor's two corners across the
    fork's width, the root step's loop round the shank's end (two corners
    across its width, two through its thickness), and the shank's two
    flanks onto the ring through the plate. The loop's four meeting corners
    add only an R^3 sliver, inside the gate's allowance."""
    square = _fillet_area(INSIDE_CORNER_R, math.pi / 2.0)
    straight = 2.0 * FORK_WIDTH + 2.0 * SHANK_WIDTH + 2.0 * SHANK_THICKNESS
    ring = _fillet_area(INSIDE_CORNER_R, SHANK_RING_OPENING) * 2.0 * SHANK_THICKNESS
    return square * straight + ring


def finished_volume() -> float:
    return (
        boss_volume()
        - slot_volume()
        + inside_corner_volume()
        - strap_bore_volume()
        - root_relief_volume()
        - pin_hole_volume()
    )


def _inside_corner_max_limit(adapter) -> None:
    """InsideCornerR as a MAX single limit carrying the band's deviations
    (build_pn_pen_rod._shoulder_fillet_max_limit's recipe)."""
    lower, upper = deviations(INSIDE_CORNER_BAND)
    _, dimension = _named_dimension(adapter, "InsideCorners", "InsideCornerR")
    label = "InsideCornerR@InsideCorners"
    value = float(dimension.SystemValue)
    if not math.isclose(value, INSIDE_CORNER_R / 1000.0, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: nominal {value * 1000.0:.7f} is not the band's max "
            f"{INSIDE_CORNER_R}"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = INSIDE_CORNER_TOL_TYPE
    if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
    if (
        int(tolerance.Type) != INSIDE_CORNER_TOL_TYPE
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: MAX-limit tolerance readback changed")
    _telemetry.success(f"{label}: single limit {INSIDE_CORNER_R:g} MAX")


def tolerance_at_dimension_places(
    adapter, feature_name: str, dimension_name: str
) -> int:
    """Print one dimension's band at the dimension's own decimal places.

    The shared tolerance setters print a band at the fewest places that hold
    it, so PinHoleDia's +0.010/0 read "Ø1.968 +0.01/0.00" (PR #1292 render at
    1b1f2f7fd): a three-place reamed size with a two-place band.  The places
    come from DRAWING_PRECISION, the same entry that sets the value's places,
    and are set here on the model so the drawing imports them verbatim (the
    pattern build_dt_pinion_bracket uses for PinSeatCz)."""
    places = DRAWING_PRECISION[feature_name][dimension_name]
    display, _dimension = _named_dimension(adapter, feature_name, dimension_name)
    display = _early_bound(display, "IDisplayDimension")
    do_not_change = -1  # swDimensionPrecisionSettings_e
    display.SetPrecision3(do_not_change, do_not_change, places, do_not_change)
    applied = int(display.GetPrimaryTolPrecision2())
    if applied != places:
        raise RuntimeError(
            f"{dimension_name}@{feature_name}: tolerance places did not persist: "
            f"requested {places}, dimension reports {applied}"
        )
    _telemetry.success(
        f"tolerance places {dimension_name}@{feature_name}: {places} decimals"
    )
    return places


def _mouth_circle(
    edge, *, centre=(0.0, 0.0), label: str = "cam-root relief"
) -> tuple[float, float] | None:
    """A full circle on the Z axis through ``centre`` (mm) as (radius, local
    Z), in mm; None for a non-circular boundary (a cylinder's straight seam)."""
    edge = _early_bound(edge, "IEdge")
    curve = _early_bound(edge.GetCurve(), "ICurve")
    if not curve.IsCircle():
        return None
    values = tuple(float(value) for value in curve.CircleParams)
    params = tuple(float(value) for value in edge.GetCurveParams2())
    if (
        len(values) != 7
        or not all(math.isfinite(value) for value in values)
        or math.hypot(
            values[0] - centre[0] / 1000.0, values[1] - centre[1] / 1000.0
        ) > 1e-9
        or math.hypot(values[3], values[4]) > 1e-9
        or abs(abs(values[5]) - 1.0) > 1e-9
        or len(params) != 11
        or not math.isclose(abs(params[7] - params[6]), math.tau, abs_tol=1e-8)
    ):
        raise RuntimeError(f"{label}: edge is not a full coaxial circle")
    return values[6] * 1000.0, values[2] * 1000.0


def _assert_pin_hole_seam(edge, *, radius: float, centre, bounds) -> None:
    """A land's only non-circular boundary is the cylinder's straight seam,
    on the hole's surface and ending on its two mouths."""
    edge = _early_bound(edge, "IEdge")
    if not _early_bound(edge.GetCurve(), "ICurve").IsLine():
        raise RuntimeError("pin hole: a land boundary is neither a mouth nor a seam")
    params = tuple(float(value) for value in edge.GetCurveParams2())
    if len(params) != 11 or any(
        abs(math.hypot(x * 1000.0 - centre[0], y * 1000.0 - centre[1]) - radius) > 1e-6
        or not (bounds[0] - 1e-6 <= abs(z) * 1000.0 <= bounds[1] + 1e-6)
        for x, y, z in (params[0:3], params[3:6])
    ):
        raise RuntimeError("pin hole: seam leaves the hole's surface or its tine")


def _assert_pin_hole_lands(adapter) -> None:
    """Prove the reamed hole runs straight through BOTH full tines: PinHole
    owns exactly two native cylinders of the hole's radius on the pin axis,
    each bounded by full circles on the fork's outer face and its slot wall,
    so each land is the whole tine -- no chamfer, countersink, breakout or
    shortened tine. Exact radius and mouth positions already exclude a finite
    mouth break, so no adjacent-face reads are needed."""
    feature = _early_bound(_feature_by_name(adapter, "PinHole"), "IFeature")
    radius, centre = PIN_HOLE_DIA / 2.0, (0.0, CENTER_DISTANCE)
    wall, outer = FORK_SLOT_WIDTH / 2.0, FORK_THICKNESS / 2.0
    lands = []
    for raw_face in feature.GetFaces() or ():
        face = _early_bound(raw_face, "IFace2")
        surface = _early_bound(face.GetSurface(), "ISurface")
        if not surface.IsCylinder():
            continue  # a trimmed tine face the kernel may also credit to the cut
        cylinder = tuple(float(value) for value in surface.CylinderParams)
        if (
            len(cylinder) != 7
            or not all(math.isfinite(value) for value in cylinder)
            or math.hypot(
                cylinder[0] - centre[0] / 1000.0, cylinder[1] - centre[1] / 1000.0
            ) > 1e-9
            or math.hypot(cylinder[3], cylinder[4]) > 1e-9
            or abs(abs(cylinder[5]) - 1.0) > 1e-9
            or abs(cylinder[6] * 1000.0 - radius) > 1e-6
        ):
            raise RuntimeError(
                f"pin hole: native cylinder {cylinder} is not the Ø{PIN_HOLE_DIA:g} "
                "hole on the pin axis"
            )
        ends = []
        for raw_edge in face.GetEdges() or ():
            circle = _mouth_circle(raw_edge, centre=centre, label="pin hole")
            if circle is None:
                _assert_pin_hole_seam(
                    raw_edge, radius=radius, centre=centre, bounds=(wall, outer)
                )
                continue
            if abs(circle[0] - radius) > 1e-6:
                raise RuntimeError(f"pin hole: mouth radius {circle[0]} != {radius}")
            ends.append(round(circle[1], 6))
        lands.append(tuple(sorted(ends)))
    for land in lands:
        if len(land) != 2 or not math.isclose(
            land[1] - land[0], TINE_THICKNESS, abs_tol=1e-6
        ):
            raise RuntimeError(
                f"pin hole: land {land} is not one straight {TINE_THICKNESS:g} tine"
            )
    expected = [
        (round(-outer, 6), round(-wall, 6)),
        (round(wall, 6), round(outer, 6)),
    ]
    if sorted(lands) != expected:
        raise RuntimeError(
            f"pin hole: tine lands {sorted(lands)} != both full tines {expected}"
        )
    _telemetry.success(
        f"pin hole: Ø{PIN_HOLE_DIA:g} straight through BOTH full {TINE_THICKNESS:g} mm "
        f"tines, mouths on the fork faces +/-{outer:g} and the slot walls +/-{wall:g}"
    )


def _root_relief_dimensions(adapter) -> tuple[object, object, object]:
    display, size = _named_dimension(adapter, "CamRootRelief", "RootReliefSize")
    display = _early_bound(display, "IDisplayDimension")
    # A chamfer's SECOND model dimension is its angle, not a second display
    # dimension in the feature's creation-order list (GetDimension2 docs).
    angle = display.GetDimension2(1)
    if angle is None or int(display.Type2) != 10:  # swChamferDimension
        raise RuntimeError("cam-root relief: native compound chamfer dimension missing")
    angle = _early_bound(angle, "IDimension")
    if (
        not math.isclose(float(size.SystemValue) * 1000.0, ROOT_RELIEF_SIZE, abs_tol=1e-6)
        or not math.isclose(
            float(angle.SystemValue), math.radians(ROOT_RELIEF_ANGLE_DEG), abs_tol=1e-10
        )
    ):
        raise RuntimeError("cam-root relief: native size/angle dimensions changed")
    return display, size, angle


async def _cam_root_relief(adapter) -> list[tuple[str, str]]:
    """Select exactly the local -Z bore mouth, never a whole annular face."""
    from solidworks_mcp.adapters.solidworks.features import _select_edges_geometric

    points = [[RING_BORE_DIA / 2.0, 0.0, -RING_THICKNESS / 2.0]]
    if _select_edges_geometric(adapter, points, tol_mm=0.001) is not True:
        raise RuntimeError("cam-root relief: local -Z bore edge did not resolve")
    check(
        "one web-facing strap-mouth chamfer",
        await adapter.add_chamfer(ROOT_RELIEF_SIZE, points, tangent_propagation=False),
    )
    name_last_feature(adapter, "CamRootRelief")
    name_dimensions(adapter, "CamRootRelief", ["RootReliefSize"])
    _display, _size, angle = _root_relief_dimensions(adapter)
    angle.Name = "RootReliefAngle"
    if str(angle.Name) != "RootReliefAngle":
        raise RuntimeError("cam-root relief: native angle name did not persist")
    return [
        ("RootReliefSize@CamRootRelief", '"RootReliefSize"'),
        ("RootReliefAngle@CamRootRelief", f"{ROOT_RELIEF_ANGLE_DEG}deg"),
    ]


def _assert_cam_root_relief(adapter, *, marked: bool = False) -> None:
    """Prove selected edge, cone legs and unchanged opposite running mouth."""
    feature = _early_bound(_feature_by_name(adapter, "CamRootRelief"), "IFeature")
    definition = _early_bound(feature.GetDefinition(), "IChamferFeatureData2")
    if (
        int(definition.Type) != 1  # swChamferAngleDistance
        or bool(definition.TangentPropagation)
        or not math.isclose(
            float(definition.GetEdgeChamferDistance(0)) * 1000.0,
            ROOT_RELIEF_SIZE, abs_tol=1e-6,
        )
        or not math.isclose(
            float(definition.EdgeChamferAngle),
            math.radians(ROOT_RELIEF_ANGLE_DEG), abs_tol=1e-10,
        )
    ):
        raise RuntimeError("cam-root relief: native angle-distance definition changed")
    # AccessSelections rolls back; always restore before inspecting final faces.
    if not definition.AccessSelections(adapter.currentModel, None):
        raise RuntimeError("cam-root relief: cannot inspect selected native mouth")
    try:
        edges = tuple(definition.Edges or ())
        if int(definition.GetEdgeCount()) != 1 or len(edges) != 1:
            raise RuntimeError("cam-root relief: exactly ONE bore edge is required")
        if int(definition.GetFaceCount()) != 0:
            raise RuntimeError("cam-root relief: a whole face was selected")
        selected = _mouth_circle(edges[0])
        expected = (RING_BORE_DIA / 2.0, -RING_THICKNESS / 2.0)
        if selected is None or math.dist(selected, expected) > 1e-6:
            raise RuntimeError(
                f"cam-root relief: selected {selected}, not -Z mouth {expected}"
            )
    finally:
        definition.ReleaseSelectionAccess()
    display, size, angle = _root_relief_dimensions(adapter)
    if (
        int(display.ChamferTextStyle) != 2  # swDetailChamferDimDistAng
        or int(display.GetPrimaryPrecision2()) != 1
        or int(display.GetPrimaryTolPrecision2()) != 1
        or int(display.ChamferPrecision(0)) != 1
        or int(display.ChamferPrecision(1)) != 0
        or (marked and not bool(display.MarkedForDrawing))
    ):
        raise RuntimeError("cam-root relief: native display/precision/drawing mark changed")
    if int(angle.Tolerance.Type) != 0:
        raise RuntimeError("cam-root relief: angle must retain title-block tolerance")
    tolerance = _early_bound(size.Tolerance, "IDimensionTolerance")
    if (
        int(tolerance.Type) != 4  # swTolSYMMETRIC
        or not math.isclose(
            float(tolerance.GetMinValue()) * 1000.0, ROOT_RELIEF_BAND[1], abs_tol=1e-9
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()) * 1000.0, ROOT_RELIEF_BAND[0], abs_tol=1e-9
        )
    ):
        raise RuntimeError("cam-root relief: native size band changed")
    circles = set()
    for raw_face in feature.GetFaces() or ():
        face = _early_bound(raw_face, "IFace2")
        if not _early_bound(face.GetSurface(), "ISurface").IsCone():
            continue
        for raw_edge in face.GetEdges() or ():
            circle = _mouth_circle(raw_edge)
            if circle is not None:
                circles.add(tuple(round(value, 6) for value in circle))
    radius, face_z = RING_BORE_DIA / 2.0, -RING_THICKNESS / 2.0
    # At nominal 45 degrees, geometric readbacks prove BOTH legs; they do not
    # establish which face native Width controls away from 45 degrees.
    expected_circles = {
        (round(radius + ROOT_RELIEF_SIZE, 6), round(face_z, 6)),
        (round(radius, 6), round(face_z + ROOT_RELIEF_SIZE, 6)),
    }
    if circles != expected_circles:
        raise RuntimeError(
            f"cam-root relief: actual cone boundaries {circles} != {expected_circles}"
        )
    bore = _early_bound(_feature_by_name(adapter, "StrapBore"), "IFeature")
    lands = []
    for raw_face in bore.GetFaces() or ():
        face = _early_bound(raw_face, "IFace2")
        surface = _early_bound(face.GetSurface(), "ISurface")
        if not surface.IsCylinder():
            continue
        cylinder = tuple(float(value) for value in surface.CylinderParams)
        if not math.isclose(cylinder[6] * 1000.0, radius, abs_tol=1e-6):
            continue
        ends = [_mouth_circle(edge) for edge in face.GetEdges() or ()]
        lands.append(
            {tuple(round(v, 6) for v in end) for end in ends if end is not None}
        )
    expected_land = {
        (round(radius, 6), round(face_z + ROOT_RELIEF_SIZE, 6)),
        (round(radius, 6), round(RING_THICKNESS / 2.0, 6)),
    }
    if lands != [expected_land]:
        raise RuntimeError(
            f"cam-root relief: running bore/opposite mouth changed: {lands}"
        )
    _telemetry.success(
        f"cam-root relief: ONE local -Z mouth; cone {sorted(circles)}; "
        f"straight native bore land {RING_THICKNESS - ROOT_RELIEF_SIZE:g} mm; "
        "opposite mouth unchanged (general edge break remains applicable)"
    )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations) for every module constant; derived spans
    # (ring outer radius, the shank/block start heights) are equations of those
    # primitives, so a knob edit keeps the strap-to-pin geometry consistent. The
    # mm suffix is load-bearing -- this is an INCH document and the equation
    # manager reads BARE numbers in document units (an unsuffixed 127 = 127 in,
    # blowing the part up 25.4x).
    await set_global(adapter, "CenterDistance", f"{CENTER_DISTANCE}mm")
    await set_global(adapter, "RingBoreDia", f"{RING_BORE_DIA}mm")
    await set_global(adapter, "RingWall", f"{RING_WALL}mm")
    await set_global(adapter, "RingThickness", f"{RING_THICKNESS}mm")
    await set_global(adapter, "ShankWidth", f"{SHANK_WIDTH}mm")
    await set_global(adapter, "ShankThickness", f"{SHANK_THICKNESS}mm")
    await set_global(adapter, "ForkWidth", f"{FORK_WIDTH}mm")
    await set_global(adapter, "ForkTine", f"{TINE_THICKNESS}mm")
    await set_global(adapter, "ForkSlotWidth", f"{FORK_SLOT_WIDTH}mm")
    await set_global(adapter, "ForkThickness", '2 * "ForkTine" + "ForkSlotWidth"')
    await set_global(adapter, "ForkCrotchBelowPin", f"{FORK_CROTCH_BELOW_PIN}mm")
    await set_global(adapter, "ForkBaseBelowPin", f"{FORK_BASE_BELOW_PIN}mm")
    await set_global(adapter, "SlotRunout", f"{SLOT_RUNOUT}mm")
    await set_global(adapter, "PinHoleDia", f"{PIN_HOLE_DIA}mm")
    await set_global(adapter, "InsideCornerR", f"{INSIDE_CORNER_R}mm")
    await set_global(adapter, "RootReliefSize", f"{ROOT_RELIEF_SIZE}mm")
    await set_global(adapter, "RingOuterRadius", '"RingBoreDia" / 2 + "RingWall"')
    await set_global(adapter, "ForkBaseY", '"CenterDistance" - "ForkBaseBelowPin"')
    await set_global(
        adapter, "RingFaceNear", '("ForkThickness" - "RingThickness") / 2'
    )

    # Each sketch records its dim names + drive equations into a per-sketch
    # SketchDims in helper emission order; the drives are collected and applied in
    # one deferred batch at the end (every target resolves against the finished
    # model).
    drive_jobs: list[tuple[str, str]] = []

    # Plate: the ring disc and the shank as ONE closed outline extruded once
    # -- the ring OD's major arc from the shank's left flank round the bottom
    # to its right flank, the flanks up to the fork's root step, and the root
    # line. Two coplanar bosses (a disc, then a shank dipping into it) left
    # the shank's flanks as seams across the ring's faces in the front view
    # (#982 review r2), reading as a step the side view does not show. Dim
    # EMISSION ORDER: ring OD, shank width, root height, right flank x; the
    # arc centre is a coincident relation. 9 DOF (arc 5, the root's two
    # corners 4) = 3 relations + 4 dims + the centre's 2, the flanks' feet
    # held to the arc's ends by coincident relations.
    plate = SketchDims()
    check("create_sketch plate", await adapter.create_sketch("Front"))
    shank_x = SHANK_WIDTH / 2.0
    junction_y = math.sqrt(RING_OUTER_RADIUS**2 - shank_x**2)
    set_sketch_direct_db(adapter, True)
    ring_arc = check(
        "ring OD major arc",
        await adapter.add_arc(0.0, 0.0, -shank_x, junction_y, shank_x, junction_y),
    )
    flank_r, root, flank_l = await add_line_chain(
        adapter,
        [
            (shank_x, junction_y),
            (shank_x, FORK_BASE_Y),
            (-shank_x, FORK_BASE_Y),
            (-shank_x, junction_y),
        ],
        close=False,
    )
    set_sketch_direct_db(adapter, False)
    for label, first, second, relation in (
        ("ring centre", f"{ring_arc}.center", "origin", "coincident"),
        ("right flank foot", f"{flank_r}.start", f"{ring_arc}.end", "coincident"),
        ("left flank foot", f"{flank_l}.end", f"{ring_arc}.start", "coincident"),
        ("right flank", flank_r, None, "vertical"),
        ("left flank", flank_l, None, "vertical"),
        ("shank root", root, None, "horizontal"),
    ):
        check(f"plate {label}", await adapter.add_sketch_constraint(first, second, relation))
    check(
        "ring outer diameter",
        await adapter.add_sketch_dimension(
            ring_arc, None, "diameter", 2.0 * RING_OUTER_RADIUS
        ),
    )
    plate.record("RingOuterDia", '2 * "RingOuterRadius"')
    check(
        "shank width",
        await adapter.add_sketch_dimension(root, None, "linear", SHANK_WIDTH),
    )
    plate.record("ShankWidthDim", '"ShankWidth"')
    await dimension_between(
        adapter, f"{root}.start", "origin", "vertical_distance", FORK_BASE_Y,
        "shank root height",
    )
    plate.record("ShankRootY", '"ForkBaseY"')
    await dimension_between(
        adapter, f"{flank_r}.start", "origin", "horizontal_distance", shank_x,
        "shank right flank x",
    )
    plate.record("ShankSideX", '"ShankWidth" / 2')
    await ensure_fully_defined(adapter, "plate sketch")
    check("exit_sketch plate", await adapter.exit_sketch())
    name_last_feature(adapter, "PlateProfile")
    drive_jobs += plate.apply(adapter, "PlateProfile")
    check(
        "extrude plate",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Plate")
    # The plate's thickness prints at the ring in the side view (#982 review
    # r1): named so its band and the drawing select it by name.
    ring_thick_dim = name_dimensions(adapter, "Plate", ["RingThick"])
    drive_jobs.append((ring_thick_dim[0], '"RingThickness"'))

    # Fork boss: a tombstone outline -- the root step at FORK_BASE_Y, two
    # vertical sides, and a semicircular crown centred on the pin (R =
    # ForkWidth/2, tangent to the sides -- add_arc runs CCW start->end, so
    # right-side-top -> left-side-top bows over the TOP). Because the crown
    # centre sits on the sketch axis with radius = the side half-width, each
    # side-top lands on the crown's equator by construction. Extruded mid-plane
    # to the full fork thickness; the slot cut below splits it into two tines.
    # Dim EMISSION ORDER (each recorded as its display dim is created): root
    # width, crown radius, crown-centre height (x on-axis, so
    # anchor_point_to_origin emits ONE dim), right-side length, right-side x.
    # Root horizontal + side verticals are RELATIONS: 9 DOF (four corners and
    # the centre, less the arc's equal radius) = 3 relations + the on-axis
    # alignment + 5 dims, no redundancy.
    fork_sd = SketchDims()
    check("create_sketch fork", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    fw = FORK_WIDTH / 2.0
    fork_root = check(
        "fork root",
        await adapter.add_line(-fw, FORK_BASE_Y, fw, FORK_BASE_Y),
    )
    fork_side_r = check(
        "fork side right",
        await adapter.add_line(fw, FORK_BASE_Y, fw, CENTER_DISTANCE),
    )
    fork_crown = check(
        "fork crown",
        await adapter.add_arc(
            0.0, CENTER_DISTANCE, fw, CENTER_DISTANCE, -fw, CENTER_DISTANCE
        ),
    )
    fork_side_l = check(
        "fork side left",
        await adapter.add_line(-fw, CENTER_DISTANCE, -fw, FORK_BASE_Y),
    )
    set_sketch_direct_db(adapter, False)
    for ent, relation in (
        (fork_root, "horizontal"),
        (fork_side_r, "vertical"),
        (fork_side_l, "vertical"),
    ):
        check(f"fork {relation}", await adapter.add_sketch_constraint(ent, None, relation))
    check(
        "dimension fork width",
        await adapter.add_sketch_dimension(fork_root, None, "linear", FORK_WIDTH),
    )
    fork_sd.record("ForkWidthDim", '"ForkWidth"')
    check(
        "dimension fork crown radius",
        await adapter.add_sketch_dimension(fork_crown, None, "radial", fw),
    )
    fork_sd.record("ForkCrownR", '"ForkWidth" / 2')
    await anchor_point_to_origin(
        adapter, f"{fork_crown}.center", 0.0, CENTER_DISTANCE, "fork crown centre"
    )
    fork_sd.record("ForkPinY", '"CenterDistance"')
    await dimension_between(
        adapter,
        f"{fork_side_r}.start",
        f"{fork_side_r}.end",
        "vertical_distance",
        FORK_BASE_BELOW_PIN,
        "fork side length",
    )
    fork_sd.record("ForkSideLength", '"ForkBaseBelowPin"')
    await dimension_between(
        adapter, f"{fork_side_r}.start", "origin", "horizontal_distance", fw,
        "fork side x",
    )
    fork_sd.record("ForkSideX", '"ForkWidth" / 2')
    await ensure_fully_defined(adapter, "fork sketch")
    check("exit_sketch fork", await adapter.exit_sketch())
    name_last_feature(adapter, "ForkProfile")
    drive_jobs += fork_sd.apply(adapter, "ForkProfile")
    check(
        "extrude fork",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=FORK_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ForkBoss")
    # The fork thickness prints as a reference at three places (two tines and
    # the slot own its limits): named so the precision and the drawing select
    # it by name.
    fork_thickness_dim = name_dimensions(adapter, "ForkBoss", ["ForkThick"])
    drive_jobs.append((fork_thickness_dim[0], '"ForkThickness"'))
    v_expected = boss_volume()
    await volume_check(adapter, "ring, shank and fork bosses", v_expected, 0.002 * v_expected)

    # Fork slot: a Right-plane rectangle (sketch x = model -Z) centred on the
    # rod mid-plane, from the crotch up past the crown, cut through the fork's
    # width. Every side-view location runs from ONE finished face, the fork's
    # outer face at sketch +x (model -Z; the left face in the side view): a
    # construction line on that face, from the fork's root step to its crown
    # top, carries the boss length and the slot depth from the crown top, the
    # near tine (face to slot wall) and the plate's near-face ordinate. A
    # short construction line on the plate's near face runs down the shank
    # from the root step, so that ordinate prints below the fork; the plate's
    # thickness prints at the ring (RingThick@Plate). Every reference is
    # driven by the same knobs as the solid features, so it always lies on the
    # modelled face. Dim EMISSION ORDER: face x and root height (general
    # anchor, TWO dims), boss length, slot width, cut height, near tine, slot
    # depth, then the near face's ordinate and its run.
    # 16 DOF = face line: vertical + 2 anchor dims + boss length; rectangle:
    # four relations + 4 dims; the near-face line: vertical + level with the
    # face line's root end + ordinate + run.
    slot_sd = SketchDims()
    check("create_sketch fork slot", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    face_x = FORK_THICKNESS / 2.0
    face_ref = check(
        "fork face reference",
        await adapter.add_centerline(face_x, FORK_BASE_Y, face_x, FORK_TOP_Y),
    )
    sh = FORK_SLOT_WIDTH / 2.0
    slot_rect = [
        (-sh, FORK_CROTCH_Y),
        (sh, FORK_CROTCH_Y),
        (sh, FORK_CROTCH_Y + SLOT_CUT_HEIGHT),
        (-sh, FORK_CROTCH_Y + SLOT_CUT_HEIGHT),
    ]
    slot = await add_line_chain(adapter, slot_rect)
    ring_face = check(
        "ring face reference",
        await adapter.add_centerline(
            RING_THICKNESS / 2.0,
            FORK_BASE_Y,
            RING_THICKNESS / 2.0,
            FORK_BASE_Y - RING_FACE_REF_RUN,
        ),
    )
    set_sketch_direct_db(adapter, False)
    check(
        "fork face reference vertical",
        await adapter.add_sketch_constraint(face_ref, None, "vertical"),
    )
    await anchor_point_to_origin(
        adapter, f"{face_ref}.start", face_x, FORK_BASE_Y, "fork face reference"
    )
    slot_sd.record("ForkFaceX", '"ForkThickness" / 2')
    slot_sd.record("ForkRootY", '"ForkBaseY"')
    await dimension_between(
        adapter,
        f"{face_ref}.start",
        f"{face_ref}.end",
        "vertical_distance",
        FORK_BOSS_LENGTH,
        "fork boss length",
    )
    slot_sd.record("ForkBossLength", '"ForkWidth" / 2 + "ForkBaseBelowPin"')
    for line, (x1, y1), (x2, y2) in zip(
        slot, slot_rect, slot_rect[1:] + slot_rect[:1], strict=True
    ):
        direction = "horizontal" if y1 == y2 else "vertical"
        check(
            f"slot {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    await dimension_between(
        adapter, f"{slot[0]}.start", f"{slot[0]}.end", "horizontal_distance",
        FORK_SLOT_WIDTH, "slot width",
    )
    slot_sd.record("SlotWidth", '"ForkSlotWidth"')
    await dimension_between(
        adapter, f"{slot[1]}.start", f"{slot[1]}.end", "vertical_distance",
        SLOT_CUT_HEIGHT, "slot cut height",
    )
    slot_sd.record(
        "SlotCutHeight", '"ForkWidth" / 2 + "ForkCrotchBelowPin" + "SlotRunout"'
    )
    # The near tine: the datum face to the slot's near wall, at the tine top.
    await dimension_between(
        adapter, f"{face_ref}.end", f"{slot[0]}.end", "horizontal_distance",
        TINE_THICKNESS, "near tine",
    )
    slot_sd.record("TineNear", '"ForkTine"')
    await dimension_between(
        adapter, f"{slot[0]}.start", f"{face_ref}.end", "vertical_distance",
        SLOT_DEPTH, "slot depth",
    )
    slot_sd.record("SlotDepth", '"ForkWidth" / 2 + "ForkCrotchBelowPin"')
    check(
        "RingFaceNear reference vertical",
        await adapter.add_sketch_constraint(ring_face, None, "vertical"),
    )
    check(
        "RingFaceNear reference level with the fork root",
        await adapter.add_sketch_constraint(
            f"{ring_face}.start", f"{face_ref}.start", "horizontal_points"
        ),
    )
    await dimension_between(
        adapter, f"{face_ref}.start", f"{ring_face}.end", "horizontal_distance",
        RING_FACE_NEAR, "RingFaceNear",
    )
    slot_sd.record("RingFaceNear", '"RingFaceNear"')
    await dimension_between(
        adapter, f"{ring_face}.start", f"{ring_face}.end", "vertical_distance",
        RING_FACE_REF_RUN, "RingFaceNear reference run",
    )
    slot_sd.record("RingFaceNearRun")
    await ensure_fully_defined(adapter, "fork slot sketch")
    check("exit_sketch fork slot", await adapter.exit_sketch())
    name_last_feature(adapter, "ForkSlotProfile")
    drive_jobs += slot_sd.apply(adapter, "ForkSlotProfile")
    check(
        "cut fork slot",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ForkSlot")
    v_expected -= slot_volume()
    await volume_check(adapter, "fork slot", v_expected, 0.01 * slot_volume() + 0.05)

    # Every inside corner gets the one radius, printed R MAX
    # (drawing-guidelines.md rule 16; ch_connecting_rod_spec). The FIRST edge
    # is the shank's +X flank onto the ring: an imported fillet dimension
    # attaches to its feature's first edge (build_pn_pen_hanger), and the
    # front view carries the radius off that corner. Then the -X flank onto
    # the ring, the root step's loop round the shank's end (the flanks'
    # corners, then the plate faces'), and the slot floor's two corners.
    shank_x = SHANK_WIDTH / 2.0
    junction_y = math.sqrt(RING_OUTER_RADIUS**2 - shank_x**2)
    plate_z = SHANK_THICKNESS / 2.0
    corner_edges = [
        [shank_x, junction_y, 0.0],
        [-shank_x, junction_y, 0.0],
        [shank_x, FORK_BASE_Y, 0.0],
        [-shank_x, FORK_BASE_Y, 0.0],
        [0.0, FORK_BASE_Y, plate_z],
        [0.0, FORK_BASE_Y, -plate_z],
        [0.0, FORK_CROTCH_Y, FORK_SLOT_WIDTH / 2.0],
        [0.0, FORK_CROTCH_Y, -FORK_SLOT_WIDTH / 2.0],
    ]
    check(
        "fillet inside corners",
        await adapter.add_fillet(INSIDE_CORNER_R, corner_edges, propagate=False),
    )
    name_last_feature(adapter, "InsideCorners")
    corner_dim = name_dimensions(adapter, "InsideCorners", ["InsideCornerR"])
    drive_jobs.append((corner_dim[0], '"InsideCornerR"'))
    v_corners = inside_corner_volume()
    v_expected += v_corners
    await volume_check(adapter, "inside corner fillets", v_expected, 0.1 * v_corners + 0.05)

    # Strap bore - rides the eccentric cam. On-axis circle: diameter only.
    bore_sd = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, RING_BORE_DIA / 2.0, "strap bore", dims=bore_sd,
        names=("StrapBoreCx", "StrapBoreCz", "StrapBoreDia"),
        drives=(None, None, '"RingBoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "StrapBoreProfile")
    drive_jobs += bore_sd.apply(adapter, "StrapBoreProfile")
    check(
        "cut strap bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "StrapBore")
    v_expected -= strap_bore_volume()
    v_before_relief = await volume_check(
        adapter, "strap bore", v_expected, 0.002 * v_expected
    )
    drive_jobs += await _cam_root_relief(adapter)
    v_relief = root_relief_volume()
    v_expected -= v_relief
    await volume_check(
        adapter, "single web-facing cam-root relief",
        v_before_relief - v_relief, 1e-4 * v_before_relief,
    )

    # Pivot pin hole on the rod axis, reamed through both tines (the slot
    # between them is air). The pin RUNS in the arm's #47 hole and is PRESSED
    # here, its ends dressed flush (ch_rod_pivot_pin_spec). No countersink: the
    # hole runs straight through each tine, so the pin bears on the whole tine.
    pin_hole = SketchDims()
    check("create_sketch rocker pin hole", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        CENTER_DISTANCE,
        PIN_HOLE_DIA / 2.0,
        "rocker pin hole",
        dims=pin_hole,
        names=(None, "PinHoleY", "PinHoleDia"),
        drives=(None, '"CenterDistance"', '"PinHoleDia"'),
    )
    await ensure_fully_defined(adapter, "rocker pin hole sketch")
    check("exit_sketch rocker pin hole", await adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    drive_jobs += pin_hole.apply(adapter, "PinHoleProfile")
    check(
        "cut rocker pin hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PinHole")
    v_pin = pin_hole_volume()
    v_expected -= v_pin
    v_built = await volume_check(
        adapter, "pin hole through both tines", v_expected, 0.03 * v_pin + 0.05
    )

    # Named bore axes for assembly mates (view-independent name selection):
    # Axis1 = strap bore on the cam (origin), Axis2 = pivot pin bore (0, CD).
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "strap bore")
    await name_bore_axis(
        adapter,
        "Right Plane",
        0.0,
        "Top Plane",
        CENTER_DISTANCE,
        "rod pin bore",
        drive_b='"CenterDistance"',
        drive_jobs=drive_jobs,
    )

    # Apply the deferred drive equations after the whole model + a rebuild exists,
    # so every target resolves. Each equation evaluates to the as-built value, so
    # the neutrality gate asserts the post-drive volume equals the as-built
    # volume: geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven connecting rod (equations neutral)", v_built, 0.001 * v_built
    )
    set_dimension_bilateral_tolerance(
        adapter,
        "StrapBoreProfile",
        "StrapBoreDia",
        *deviations(RING_BORE_DIA_BAND),
    )
    # The fork straddles the rocker strap inside one station pitch (Main
    # ruling 2026-10, option b), and the ring must ride its cam slot while the
    # fork rides the arm (test_channel_axial_budget): the near tine, the slot
    # and the plate's near face print natively, located from the fork's datum
    # face, and the plate's thickness at the ring, each band symmetric so it
    # prints +/-. The fork over the tines is a reference (two tines and the
    # slot set it).
    tine_lower, tine_upper = deviations(TINE_BAND)
    slot_lower, slot_upper = deviations(FORK_SLOT_BAND)
    face_lower, face_upper = deviations(RING_FACE_BAND)
    thick_lower, thick_upper = deviations(RING_THICKNESS_BAND)
    if (tine_lower, slot_lower, face_lower, thick_lower) != (
        -tine_upper, -slot_upper, -face_upper, -thick_upper
    ):
        raise AssertionError("the fork side-view bands must be symmetric")
    set_dimension_symmetric_tolerance(adapter, "ForkSlotProfile", "TineNear", tine_upper)
    set_dimension_symmetric_tolerance(adapter, "ForkSlotProfile", "SlotWidth", slot_upper)
    set_dimension_symmetric_tolerance(
        adapter, "ForkSlotProfile", "RingFaceNear", face_upper
    )
    set_dimension_symmetric_tolerance(adapter, "Plate", "RingThick", thick_upper)
    relief_lower, relief_upper = deviations(ROOT_RELIEF_BAND)
    if relief_lower != -relief_upper:
        raise AssertionError("the cam-root relief's native size band must be symmetric")
    set_dimension_symmetric_tolerance(
        adapter, "CamRootRelief", "RootReliefSize", relief_upper
    )
    relief_display, _relief_size, _relief_angle = _root_relief_dimensions(adapter)
    relief_display.ChamferTextStyle = 2  # swDetailChamferDimDistAng
    _inside_corner_max_limit(adapter)
    # The reamed press hole's band rides natively on its diameter, which the
    # front view imports at three places (DRAWING_PRECISION); its band prints
    # at the same three places (+0.010/0.000), not the fewest that hold it.
    set_dimension_bilateral_tolerance(
        adapter, "PinHoleProfile", "PinHoleDia", *deviations(PIN_HOLE_BAND)
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    # ChamferPrecision is indexed in the native SDK: 0 distance, 1 angle.
    # Author on the MODEL, never rewrite precision on the drawing import.
    relief_display.SetChamferPrecision(
        0, DRAWING_PRECISION["CamRootRelief"]["RootReliefSize"]
    )
    relief_display.SetChamferPrecision(1, 0)
    tolerance_at_dimension_places(adapter, "PinHoleProfile", "PinHoleDia")
    _assert_cam_root_relief(adapter)
    _assert_pin_hole_lands(adapter)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number", "Material Specification", "Finish", "Quantity",
            "Manufacturing Notes", "Isometric View Note",
        ),
    )
    _assert_cam_root_relief(adapter, marked=True)
    _assert_pin_hole_lands(adapter)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
