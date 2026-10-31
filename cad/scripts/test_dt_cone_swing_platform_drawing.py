"""Offline manufacturing contracts for the cone-swing-platform package."""

from __future__ import annotations

import ast
import asyncio
import math
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

import _config
import _drawing_detail_projection
import cone_line
import dt_crank_drive_gear_spec as gear64
import dt_cone_swing_platform_crank_axis as crank_axis
import dt_vn_cone_pivot_screw_spec
import build_dt_cone_swing_platform as part
import dt_cone_pivot_post_spec
import dt_cone_swing_platform_drawing_spec as drawing_spec
import dt_cone_swing_platform_geometry as geometry
import dt_cone_swing_platform_spec as spec
import dt_cone_swing_platform_checks as checks
import dt_cone_tip_block_spec as block
import dt_post_mount_stack as post_mount
from dt_cone_post_envelope import BLOCK_DIA
import draw_dt_cone_swing_platform as drawing
import pytest
from _gtol_planar import PlanarFace
from _hole_spec import CLEARANCE_MM, blind_cut_dia_mm
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from _surface_finish import MACHINED_UM, SEAT_UM




def test_every_marked_model_dimension_has_one_view_and_native_precision() -> None:
    assert part.DRAWING_DIMENSIONS is drawing_spec.DRAWING_DIMENSIONS
    marked = set().union(*drawing_spec.DRAWING_DIMENSIONS.values())
    view_sets = (
        set(drawing.PROFILE_KEEP),
        set(drawing.FEATURE_KEEP),
        set(drawing.NOTCH_KEEP),
        set(drawing.SECTION_KEEP),
        set(drawing.DETAIL_KEEP),
    )
    kept = set().union(*view_sets)
    assert kept == marked
    assert sum(len(names) for names in view_sets) == len(kept)
    assert set(drawing_spec.DRAWING_PRECISION_BY_NAME) == marked
    assert drawing_spec.DRAWING_PRECISION_BY_NAME["PlateLenDim"] == 2
    assert set(drawing_spec.DRAWING_PRECISION_BY_NAME.values()) == {2, 3}


def test_pivot_is_the_reamed_h7_bore_on_the_stock_shoulder() -> None:
    """Main ruling 2026-10-10: the plate is reamed Ø6.350 H7 on the 6.3246-6.350
    shoulder, band from config, carried natively on the Hole Wizard feature."""
    import _config

    import dt_cone_swing_platform_pivot_spec as pivot_spec

    assert pivot_spec.PIVOT_HOLE_SPEC.kind == "drilled_fractional"
    assert pivot_spec.PIVOT_HOLE_SPEC.size == "1/4"
    assert pivot_spec.PIVOT_HOLE_SPEC.end == "through_all"
    assert pivot_spec.PIVOT_HOLE_DIA == blind_cut_dia_mm(pivot_spec.PIVOT_HOLE_SPEC)
    assert pivot_spec.PIVOT_HOLE_DIA == pytest.approx(6.350)
    assert pivot_spec.PIVOT_HOLE_BAND == tuple(
        _config.fit("cone_drum_oblique_mesh", "pivot_bore_band_mm")
    ) == (0.0127, 0.0)
    shoulder_max = dt_vn_cone_pivot_screw_spec.SHOULDER_DIA + dt_vn_cone_pivot_screw_spec.SHOULDER_DIA_BAND[0]
    assert pivot_spec.PIVOT_HOLE_DIA + pivot_spec.PIVOT_HOLE_BAND[1] >= shoulder_max


def test_post_mount_pattern_is_derived_from_its_mating_post() -> None:
    assert spec.POST_ATTACHMENT_SPACING == dt_cone_pivot_post_spec.ATTACHMENT_SPACING
    assert spec.POST_BLOCK_DIA == BLOCK_DIA
    assert checks.POST_MOUNT_HALF_PITCH == spec.POST_ATTACHMENT_SPACING / 2.0
    assert math.isclose(
        math.hypot(
            part.POST_MOUNT_WEST_XZ[0] - part.POST_MOUNT_EAST_XZ[0],
            part.POST_MOUNT_WEST_XZ[1] - part.POST_MOUNT_EAST_XZ[1],
        ),
        spec.POST_ATTACHMENT_SPACING,
    )
    assert spec.POST_MOUNT_SPEC.kind == "tapped"
    assert spec.POST_MOUNT_SPEC.size == "1/4-20"
    assert spec.POST_MOUNT_SPEC.end == "through_all"
    assert spec.POST_MOUNT_TAP_DIA == blind_cut_dia_mm(spec.POST_MOUNT_SPEC)


def test_engaged_post_and_plate_hole_axes_coincide_in_machine_coordinates() -> None:
    """Rotating the plate into the engaged pose places its taps under the post."""
    angle = math.radians(geometry.INCLINE_DEG)
    for (local_x, local_z), post_x in (
        (part.POST_MOUNT_WEST_XZ, dt_cone_pivot_post_spec.ATTACHMENT_X),
        (part.POST_MOUNT_EAST_XZ, -dt_cone_pivot_post_spec.ATTACHMENT_X),
    ):
        dz = local_z - geometry.POST_LOCAL_Z
        assert local_x * math.cos(angle) + dz * math.sin(angle) == pytest.approx(post_x)
        assert -local_x * math.sin(angle) + dz * math.cos(angle) == pytest.approx(0.0)


def test_only_sliding_and_locating_surfaces_carry_roughness() -> None:
    by_key = {control.key: control for control in spec.SURFACE_FINISHES}
    assert set(by_key) == {"post_seat", "base_slide"}
    assert by_key["post_seat"].roughness_um == SEAT_UM
    assert by_key["post_seat"].face == PlanarFace(
        (0, 1, 0), spec.PLATE_THICKNESS
    )
    assert by_key["base_slide"].roughness_um == MACHINED_UM
    assert by_key["base_slide"].face == PlanarFace((0, -1, 0), 0.0)


def test_plate_and_nonfit_features_remain_at_general_grade() -> None:
    registry = _config.parts("dt-cone-swing-platform")
    assert registry["tolerance_class"] == "machined_block"
    assert "mil-dtl-13924 class 1" in str(registry["finish"]).lower()
    assert "oil seal" in str(registry["finish"]).lower()
    assert int(registry["quantity"]) == 1
    assert drawing_spec.DRAWING_PRECISION["Plate"]["PlateThk"] == 2
    assert drawing_spec.DRAWING_PRECISION["PivotBearingRelief"]["PivotBearingReliefDepth"] == 3
    assert drawing_spec.DRAWING_PRECISION["PostMountHoles"] == {
        "PostMountWestX": 3,
        "PostMountWestZ": 3,
        "PostMountEastX": 3,
        "PostMountEastZ": 3,
    }






def test_geometry_cascade_and_interference_guards_stay_explicit() -> None:
    assert geometry.POST_LOCAL_Z == cone_line.POST_STATION - cone_line.PIVOT_STATION
    assert geometry.PLATE_SOUTH_Z <= (
        geometry.POST_LOCAL_Z - spec.POST_BLOCK_DIA / 2.0 - geometry.POST_SOUTH_MARGIN
    )
    assert part.PLATE_LEN == pytest.approx(
        geometry.NORTH_OVERHANG - geometry.PLATE_SOUTH_Z
    )
    assert geometry.POST_MAIN_DIA == spec.POST_BLOCK_DIA
    assert checks.POST_FOOT_CONTAINMENT >= 0.25
    assert spec.PIVOT_BEARING_RELIEF_DIAMETER == pytest.approx(10.668)
    assert part.PLATE_T - spec.PIVOT_BEARING_THICKNESS == pytest.approx(
        spec.PIVOT_BEARING_RELIEF_DEPTH
    )
    assert spec.crank_gear_platform_clearance() >= 0.5


def test_stepped_collar_extension_keeps_post_and_tip_attachment_laws() -> None:
    from dt_cone_swing_platform_crank_axis import CRANK_AXIS_OFF

    # The retained 7.5 extension plus the custom collar body's northward shift.
    from cone_shaft_land_bands import TIP_COLLAR_BODY_NORTH_SHIFT_MM

    assert cone_line.TIP_END_EXTENSION_MM == 7.5 + TIP_COLLAR_BODY_NORTH_SHIFT_MM
    assert cone_line.PIVOT_STATION - cone_line.T006_NORTH_FACE == pytest.approx(
        23.0 + cone_line.TIP_END_EXTENSION_MM
    )
    assert cone_line.PIVOT_STATION - block.TIP_BLOCK_NORTH_FACE == pytest.approx(
        block.TIP_BLOCK_NORTH_FACE_PIVOT_OFFSET
    )
    assert block.TIP_BLOCK_PIVOT_OFFSET == pytest.approx(
        block.TIP_BLOCK_NORTH_FACE_PIVOT_OFFSET + block.BLOCK_Z / 2.0
    )
    assert CRANK_AXIS_OFF == pytest.approx(cone_line.PIVOT_XZ[0] - cone_line.X_CRANK)
    assert checks.POST_MOUNT_WEST_XZ[1] == pytest.approx(
        geometry.POST_LOCAL_Z + checks.POST_MOUNT_DZ
    )
    assert checks.POST_MOUNT_EAST_XZ[1] == pytest.approx(
        geometry.POST_LOCAL_Z - checks.POST_MOUNT_DZ
    )


def test_pivot_relief_runs_out_through_the_north_edge() -> None:
    """drawing-guidelines.md rule 17 (walls and webs) W18 (d): no web is left between the relief and the north edge.

    As a closed Ø10.50 spotface 7.0 from the edge it left 1.75 nominal, under
    the 2.0 target.  Open to the edge, the web does not exist; the relief's
    sketch closes PIVOT_RELIEF_RUNOUT past it, and the width still gives the
    stock 3/8 head its radial clearance.
    """
    half = spec.PIVOT_BEARING_RELIEF_DIAMETER / 2.0
    closed_web = part.NORTH_OVERHANG - half
    assert closed_web < 2.0  # positive control: the closed spotface failed
    assert part.PIVOT_RELIEF_RUNOUT > 0.0
    head_dia = dt_vn_cone_pivot_screw_spec.HEAD_DIA
    assert (spec.PIVOT_BEARING_RELIEF_DIAMETER - head_dia) / 2.0 >= (
        spec.PIVOT_HEAD_RADIAL_CLEARANCE - 1e-9
    )
    # The fit names its mate and a checkable acceptance (machinist review r1:
    # "MINIMAL AXIAL PLAY" could not be checked).
    lines = spec.PIVOT_RELIEF_FIT_REQUIREMENT.split("\n")
    flat = " ".join(lines)
    assert "TOP RELIEF" in flat and "FIT DEPTH" in flat
    assert "MHA-DT-VN-52" in flat and "SHOULDER" in flat
    assert "SWINGS FREE" in flat and "NO AXIAL SHAKE" in flat
    assert "UNLOCKED" not in flat and "SCREW:" not in flat
    # Retain the saved layout envelope, without pinning the spec's line breaks.
    assert len(lines) <= 4
    # Only the NW fillet reaches over the 10.50 strip, and only by a sliver.
    overlaps = {
        label: part._north_fillet_relief_overlap(label, r)
        for label, _x, _z, r in part.PLATE_CORNERS
    }
    assert overlaps["NE"] == 0.0 and overlaps["SW"] == 0.0 and overlaps["SE"] == 0.0
    assert 0.0 < overlaps["NW"] < part._corner_fillet_area("NW", 8.0)


def test_corner_arc_count_follows_the_relief_overlap() -> None:
    """The NW fillet's plan arc splits in two where W18's relief crosses it.

    Run d9711228 found two CornerNW arcs.  The count is pinned from the build's
    own overlap check, so a third arc from an unintended cut still fails, and
    arcs that do not share one plan circle fail too.
    """
    assert {
        name: drawing.expected_corner_arcs(name)
        for name in ("CornerNE", "CornerNW", "CornerSW", "CornerSE")
    } == {"CornerNE": 1, "CornerNW": 2, "CornerSW": 1, "CornerSE": 1}
    split = [(0.0065, 0.007, 0.008), (0.0065, 0.007, 0.008)]
    drawing.check_corner_arc_plan("CornerNWR", split, 2)
    with pytest.raises(RuntimeError, match="found 3"):
        drawing.check_corner_arc_plan("CornerNWR", [*split, split[0]], 2)
    with pytest.raises(RuntimeError, match="found 2"):
        drawing.check_corner_arc_plan("CornerNER", split, 1)
    with pytest.raises(RuntimeError, match="one plan circle"):
        drawing.check_corner_arc_plan(
            "CornerNWR", [split[0], (0.0070, 0.007, 0.008)], 2
        )


def test_corner_arc_station_is_the_fillet_centre_in_model_space() -> None:
    """The farm run at 039e557da found 0 CornerSW arcs at a stale sheet station.

    The station is now the model fillet centre: radius r from both edges
    that meet at the corner, so moving the plate on the sheet cannot stale it.
    """
    corners = part.PLATE_CORNERS
    for index, (label, x, z, radius) in enumerate(corners):
        cx, cz = drawing.corner_fillet_centre_mm(label)
        for _n, nx, nz, _r in (corners[index - 1], corners[(index + 1) % len(corners)]):
            cross = (nx - x) * (cz - z) - (nz - z) * (cx - x)
            assert abs(cross) / math.hypot(nx - x, nz - z) == pytest.approx(radius)


@pytest.mark.parametrize("stale", [False, True])
def test_corner_attachment_owns_only_the_arc_at_the_model_fillet_centre(monkeypatch, stale):
    """The gate's real arc search: an owned visible arc of the right radius
    counts only at the fillet's model-space centre; a stale centre finds 0."""
    ns = types.SimpleNamespace
    radius_m = 0.005
    cx, cz = drawing.corner_fillet_centre_mm("SW")
    if stale:
        cx += 1.0
    owner = ns(Name="CornerSW")
    curve = ns(IsCircle=lambda: True, CircleParams=(cx / 1000, 0.00635, cz / 1000, 0, 1, 0, radius_m))
    edge = ns(GetCurve=lambda: curve)
    face = ns(GetFeature=lambda: owner, GetEdges=lambda: [edge])
    owner.GetFaces = lambda: [face]
    dimension = ns(GetFeatureOwner=lambda: owner)
    annotation = ns(
        GetAttachedEntities3=lambda: None, GetAttachedEntityTypes=lambda: None,
        IsDangling=lambda: False,
        GetSpecificAnnotation=lambda: ns(GetDimension2=lambda _i: dimension),
        GetDisplayData=lambda: ns(
            GetArrowHeadCount=lambda: 1, GetArrowHeadAtIndex2=lambda _i: (0.0, 0.0, 0.0),
        ),
    )

    class Reached(Exception):
        pass

    def projected(_adapter, _view, point, *, label):
        raise Reached(point)

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda _a, _item: "CornerSWR")
    monkeypatch.setattr(drawing, "visible_view_entities", lambda *_a, **_k: [edge])
    monkeypatch.setattr(drawing, "model_point_in_view", projected)
    adapter = ns(swApp=ns(IsSame=lambda a, b: int(a is b)))
    with pytest.raises(RuntimeError if stale else Reached, match="found 0" if stale else None):
        drawing._assert_corner_radius_attachment(
            adapter, object(), [annotation],
            name="CornerSWR", feature_name="CornerSW", radius_m=radius_m,
        )


def test_r12_corner_arrow_lands_at_its_arc_middle() -> None:
    """Run 20261010T072401692Z: CornerSER's fixed shelf put its arrow at
    183.3 deg about the R12 centre, past the arc's 178 deg end, on the east
    edge.  The text now derives from the arc's middle; the old station is
    the positive control."""
    px, py = drawing.PROFILE_PIVOT_XY
    corners = {c[0]: c for c in part.PLATE_CORNERS}
    index = [c[0] for c in part.PLATE_CORNERS].index("SE")
    _label, vx, vz, radius = corners["SE"]
    cx, cz = drawing.corner_fillet_centre_mm("SE")
    centre = (px + cx * 0.0005, py - cz * 0.0005)

    def sheet_angle(x, z):
        return math.degrees(math.atan2(-(z - cz), x - cx)) % 360.0

    # The arc's ends are the tangent points on the two edges into the vertex.
    ends = []
    for _n, nx, nz, _r in (
        part.PLATE_CORNERS[index - 1], part.PLATE_CORNERS[(index + 1) % 4]
    ):
        length = math.hypot(nx - vx, nz - vz)
        ux, uz = (nx - vx) / length, (nz - vz) / length
        t = (cx - vx) * ux + (cz - vz) * uz
        ends.append(sheet_angle(vx + t * ux, vz + t * uz))
    low, high = sorted(ends)
    assert high - low < 180.0

    def arrow_angle(text_xy):
        knee = (
            text_xy[0] + drawing.RADIUS_KNEE_FROM_TEXT[0],
            text_xy[1] + drawing.RADIUS_KNEE_FROM_TEXT[1],
        )
        return math.degrees(math.atan2(knee[1] - centre[1], knee[0] - centre[0])) % 360.0

    text = drawing.PROFILE_KEEP["CornerSER"]
    assert arrow_angle(text) == pytest.approx((low + high) / 2.0, abs=1e-6)
    assert not low <= arrow_angle(drawing._planned(0.040, 0.2435)) <= high
    # R12.0 is 11.7 x 3.9 mm round its position (run 20261009T172850508Z):
    # above the 223.4 south witness, below the 24.0 dimension line (2.6 mm
    # under its text), and left of the 24.0 east extension line.
    south_witness_y = py - min(c[2] for c in part.PLATE_CORNERS) * 0.0005
    assert text[1] - 0.00195 > south_witness_y + 0.0015
    assert text[1] + 0.00195 < drawing.PROFILE_KEEP["SouthEastX"][1] - 0.0026 - 0.0015
    assert text[0] + 0.00585 < px + vx * 0.0005 - 0.002


def _notch_cap_native_prediction(text_xy):
    """r15 saved envelope, not a new native readback or a fixed arrow tip.

    Provenance: 20261019T141948095Z-30f07cb95264469d8375a13d452e6414.out/
    reports/layout-audit/dt-cone-swing-platform.json, CapEDia/CapECx/CapECz.
    Original position (285.5,250.5), shelf (275.4545,247.6951), measured
    text x277.042..293.958 mm.  Reflect the shelf offset for left-standing
    text; recompute the radial landing from the moved shelf and source cap.
    The next native drawing/eye proof must confirm the reflected envelope.
    """
    per_mm = drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1] / 1000.0
    pivot = (0.256811, 0.126724)  # r15 notch-view pivot witnesses
    centre = (
        pivot[0] + geometry.SLOT_E_X * per_mm,
        pivot[1] - geometry.SLOT_E_Z * per_mm,
    )
    radius = geometry.SLOT_W / 2.0 * per_mm
    knee = (text_xy[0] + 0.0100455, text_xy[1] - 0.0028049)
    ray = (knee[0] - centre[0], knee[1] - centre[1])
    length = math.hypot(*ray)
    unit = (ray[0] / length, ray[1] / length)
    tip = tuple(centre[i] + radius * unit[i] for i in (0, 1))
    return pivot, centre, radius, knee, unit, tip


def test_notch_diameter_shelf_ray_lands_inside_the_physical_concave_arc() -> None:
    """Prove the retained cap half is not trimmed by the rounded outline.

    Intersections with a full R5 circle are not necessarily on its actual
    fillet arc.  No saved/fixed tip is used for the new landing.
    """
    text = drawing.NOTCH_KEEP["CapEDia"]
    assert text == pytest.approx((0.2355, 0.200))
    pivot, centre, radius, knee, unit, tip = _notch_cap_native_prediction(text)
    scale = drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1] / 1000.0
    mouth = (geometry.SLOT_TX, -geometry.SLOT_TZ)
    # The rectangle removes dot(radial,mouth)>0; its two tangent endpoints
    # bound the physical cap at ~81.216..261.216 degrees on the saved sheet.
    assert sum(unit[i] * mouth[i] for i in (0, 1)) < -math.sin(math.radians(20))
    assert tip[0] < centre[0] and tip[1] < centre[1]
    assert math.dist(tip, centre) == pytest.approx(radius)
    ends = ((-mouth[1], mouth[0]), (mouth[1], -mouth[0]))
    corners = geometry.PLATE_CORNERS
    for index, (label, x, z, fillet_radius) in enumerate(corners):
        next_corner = corners[(index + 1) % len(corners)]
        edge = (next_corner[1] - x, -(next_corner[2] - z))
        norm = math.hypot(*edge)
        inward = (-edge[1] / norm, edge[0] / norm)
        vertex = (pivot[0] + x * scale, pivot[1] - z * scale)
        candidates = list(ends)
        worst = (-inward[0], -inward[1])
        if sum(worst[i] * mouth[i] for i in (0, 1)) <= 0:
            candidates.append(worst)
        clearance = sum((centre[i] - vertex[i]) * inward[i] for i in (0, 1))
        assert clearance + radius * min(
            sum(radial[i] * inward[i] for i in (0, 1)) for radial in candidates
        ) > 0
        # A convex fillet removes material only within its vertex/tangents
        # triangle.  Even the full cap circle's box misses these triangles.
        tangent = fillet_radius / math.tan(part._corner_theta(label) / 2.0)
        triangle = [(x, z)]
        for neighbour in (corners[index - 1], next_corner):
            delta = (neighbour[1] - x, neighbour[2] - z)
            length = math.hypot(*delta)
            triangle.append(
                (
                    x + tangent * delta[0] / length,
                    z + tangent * delta[1] / length,
                )
            )
        cap_centre = (geometry.SLOT_E_X, geometry.SLOT_E_Z)
        cap_radius = geometry.SLOT_W / 2.0
        assert any(
            cap_centre[i] + cap_radius < min(point[i] for point in triangle)
            or cap_centre[i] - cap_radius > max(point[i] for point in triangle)
            for i in (0, 1)
        )
    # The old right-standing shelf crossed 33.00 beside its right arrow.
    old_knee = (0.2754545, 0.2476951)
    old_tip = (0.2736097, 0.2354802)
    line_y = 0.2462219
    crossing_x = old_tip[0] + (old_knee[0] - old_tip[0]) * (
        (line_y - old_tip[1]) / (old_knee[1] - old_tip[1])
    )
    assert 0.273311 < crossing_x < 0.279661
    assert max(knee[1], centre[1] + radius) < line_y - 0.002


def test_notch_diameter_saved_text_envelope_clears_the_actual_left_outline() -> None:
    """Use the native width/height and actual tapered edge, not x248 fiction."""
    text = drawing.NOTCH_KEEP["CapEDia"]
    pivot, _centre, _radius, _knee, _unit, _tip = _notch_cap_native_prediction(text)
    left, right = text[0] - 0.008458, text[0] + 0.008458
    bottom, top = text[1] - 0.0028049, text[1] + 0.0007486
    assert left - drawing.FEATURE_KEEP["PostMountWestZ"][0] >= 0.002
    # NE -> SE is the left edge in this native plan; y grows toward SE.
    scale = drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1] / 1000.0
    corners = {corner[0]: corner[1:] for corner in geometry.PLATE_CORNERS}
    nx, nz, _nr = corners["NE"]
    sx, sz, _sr = corners["SE"]

    def left_outline(sheet_y):
        model_z = (pivot[1] - sheet_y) / scale
        model_x = nx + (sx - nx) * (model_z - nz) / (sz - nz)
        return pivot[0] + model_x * scale

    assert min(left_outline(bottom), left_outline(top)) - right >= 0.002
    # Positive control: the originally proposed high station touches the edge.
    assert left_outline(0.224 + 0.0007486) - (0.237 + 0.008458) < 0.002


def test_disengaged_collar_margin_survives_general_bands() -> None:
    """Linear worst case at the .XX plate outline and the base holes keeps 2.0 mm (U27)."""
    general, base_axis = printed_band_mm(2, unit=spec.UNIT), printed_band_mm(2)
    east_slope = (part.EAST_HALF_S - part.HALF_WIDTH_N) / part.PLATE_LEN
    stop_x = -(part.HALF_WIDTH_N + east_slope * (part.NORTH_OVERHANG - geometry.STOP_LOCAL_Z))
    normal = (-1.0, east_slope)
    norm = math.hypot(*normal)
    lever = abs(geometry.STOP_LOCAL_Z * normal[0] - stop_x * normal[1]) / norm
    stop_gain = geometry.SLOT_R / lever
    east_edge = stop_gain * general
    west_edge = general
    stop_hole = stop_gain * base_axis * (abs(normal[0]) + abs(normal[1])) / norm
    stud_hole = base_axis * (abs(geometry.SLOT_TX) + abs(geometry.SLOT_TZ))
    diameters = 0.35
    worst = geometry.DISENGAGE_HEAD_MARGIN - (
        east_edge + west_edge + stop_hole + stud_hole + diameters
    )
    assert worst >= 2.0
    assert set(drawing_spec.DRAWING_PRECISION["PlateProfile"].values()) == {2}


def _boxes_overlap(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


# Measured on the 81788ce9 render: outside its witnesses the thickness text
# hangs left of the dimension line, right edge on it, centred on the keep y.
# "(6.35)" over one callout line was 49.5 x 9.7 mm (21 characters, 5.5 mm line
# pitch, 3.8 mm glyphs), so a character is ~2.36 mm.
_CHAR_W, _LINE_PITCH, _GLYPH_H = 0.00236, 0.0055, 0.0038


def _plate_thickness_text_box(
    keep: tuple[float, float] | None = None, callout: str | None = None
) -> tuple[float, float, float, float]:
    x, y = keep or drawing.SECTION_KEEP["PlateThk"]
    lines = ["(6.35)", *(callout or spec.PLATE_STOCK_CALLOUT).split("\n")]
    width = max(len(line) for line in lines) * _CHAR_W
    height = (len(lines) - 1) * _LINE_PITCH + _GLYPH_H + 0.0005
    return (x - width, y - height / 2.0, x, y + height / 2.0)


def test_plate_thickness_text_sits_beside_section_a_a() -> None:
    """The (6.35) stock callout stays in the pocket left of section A-A.

    Above it: the notch plan's 205.81 witness (y 0.1379) and the 7.0 arrow at
    x 0.2697, both measured on the 81788ce9 render.  Its keep y must stay
    above the top witness (plate top 0.1265) so SolidWorks keeps the text
    outside, not centred on the line.
    """
    box = _plate_thickness_text_box()
    witness_205 = (0.2690, 0.1374, 0.3060, 0.1384)
    arrow_7 = (0.2692, 0.1280, 0.2702, 0.1379)
    for other in (witness_205, arrow_7):
        assert not _boxes_overlap(box, other), other
    assert drawing.SECTION_KEEP["PlateThk"][1] > 0.1265 + 0.001
    assert box[2] < drawing.SECTION_CENTER[0] - 0.02  # left of the cut edge
    # Positive control: 81788ce9's one-line callout at its old keep crossed
    # the 205.81 witness (and touched the 7.0 arrow).
    old = _plate_thickness_text_box((0.320, 0.135), "1/4 PLATE AS SUPPLIED")
    assert abs((old[2] - old[0]) - 0.0496) < 0.001
    assert _boxes_overlap(old, witness_205)



def _notch_caption_box() -> tuple[float, float, float, float]:
    """The lock-notch caption, 59.7 x 4.8 mm from its upper-left anchor."""
    x, y = drawing.NOTCH_CAPTION_UPPER_LEFT
    return (x, y - 0.0048, x + 0.0597, y)


def test_lock_notch_caption_sits_under_its_own_view() -> None:
    """Centred under the notch plan, under the 7.0 arrow tip (aa9766da:
    y 0.1276), clear of the (6.35) stock text beside section A-A."""
    box = _notch_caption_box()
    assert (box[0] + box[2]) / 2.0 == pytest.approx(drawing.NOTCH_CENTER[0], abs=1e-4)
    assert box[3] <= 0.1276 - 0.0015
    assert not _boxes_overlap(box, _plate_thickness_text_box())


def test_section_a_a_group_stays_inside_the_border() -> None:
    """Shifted 10 mm right, A-A's ink and its audited Ra boxes stay inside.

    aa9766da's A-A group (section, relief fragment, 0.25, Ra 1.6, label) ended
    at x 0.40005 with the border line at 0.4189.  Neither Ra symbol takes the
    shift: the audit boxes a finish 39 mm right of its anchor.
    """
    border = 0.4189
    right = 0.40005 + (drawing.SECTION_SHIFT[0] - 0.020)
    assert border - right >= 0.005
    for anchor in (drawing.SEAT_FINISH_XY, drawing.BASE_SLIDE_FINISH_XY):
        assert anchor[0] + 0.039 <= border - 0.004
    # Positive control: shifting that anchor with the group would box past.
    assert 0.355 + drawing.SECTION_SHIFT[0] + 0.039 > border


def test_section_a_a_finishes_stand_on_their_faces_clear_of_the_caption() -> None:
    """A-A looks south (top face at its head, 0.12635; underside at its foot,
    0.11365): the seat's symbol (Ra 3.2, ~7 mm tall) over the strip right of
    the PlateThk text, the (0.25) text over its upper arrowhead, the base
    slide's (Ra 1.6 under SLIDING FACE, ~10.1 mm tall) under the strip, clear
    of it and of the caption lowered under it."""
    head, foot = 0.12635, 0.11365
    relief_text_bottom = drawing.SECTION_KEEP["PivotBearingReliefDepth"][1] - 0.0015
    assert relief_text_bottom - (head + 0.0039) >= 0.002  # upper arrowhead
    seat_x, seat_y = drawing.SEAT_FINISH_XY
    assert seat_y - head >= 0.005
    assert seat_x - 0.0022 > _plate_thickness_text_box()[2] + 0.002  # vee
    slide_top = drawing.BASE_SLIDE_FINISH_XY[1] + 0.0101
    assert foot - slide_top >= 0.004
    # The caption's top centre: SECTION A-A over SCALE 2:1, ~15 mm tall.
    caption_top = drawing.SECTION_LABEL_XY[1]
    assert drawing.BASE_SLIDE_FINISH_XY[1] - 0.0007 - caption_top >= 0.005
    assert caption_top - 0.015 >= 0.066 + 0.005  # title block
    # Positive control: the caption at its north-looking station (0.100)
    # would sit on the base-slide symbol.
    assert drawing.BASE_SLIDE_FINISH_XY[1] - 0.0007 - drawing._shifted(0.335, 0.085)[1] < 0.0


def test_material_fits_one_title_block_line() -> None:
    """81788ce9 wrapped the long material form onto a second title-block line.

    The printed row is short; the full wording lives in material_specification.
    30 characters is the fleet's one-line budget (Main, 2026-09-24).
    """
    row = _config.parts("dt-cone-swing-platform")
    assert len(str(row["material"])) <= 30
    assert "1018" in str(row["material_specification"])
    assert "flat bar" in str(row["material_specification"])


def test_post_screw_engagement_note_states_the_computed_exception() -> None:
    """Codex review of 68565ace (B1): the sheet must state MHA-DT-VN-61's exception.

    U37 accepts short engagement for the 1/4-20 post screws. The printed worst
    case is the thinnest stock plate (U41 band), less the title block's .010
    tap-entry break and, at the underside, the .005 cut-to-fit allowance plus
    the screw's .010 cut-end break (it outreaches the tap's .010 exit break),
    floored, never under the drawing-guidelines.md rule 18 (thread engagement)
    audit's E7 floor of 0.87D.
    """
    # To the micron, as the spec rounds it, so a float sum a hair under an
    # exact hundredth does not floor one place low.
    worst = round(
        spec.PLATE_THICKNESS
        - spec.PLATE_STOCK_BAND
        - spec.POST_MOUNT_TAP_EDGE_BREAK
        - (spec.POST_SCREW_CUT_TO_FIT_SHORT + 0.254),
        6,
    )
    assert spec.POST_SCREW_CUT_TO_FIT_SHORT + 0.254 > spec.POST_MOUNT_TAP_EDGE_BREAK
    assert spec.POST_MOUNT_ENGAGEMENT_WORST == pytest.approx(worst)
    diameters = worst / (0.25 * 25.4)
    printed = math.floor(diameters * 100.0) / 100.0
    assert printed <= diameters and printed >= 0.87
    assert spec.POST_MOUNT_ENGAGEMENT_PRINTED == printed
    assert spec.POST_MOUNT_ENGAGEMENT_NOTE == (
        f"1/4-20 THREAD ENGAGEMENT {printed:.2f}D MIN."
    )
    # The stated shortfall is declared for the blind reviewer, as a minor.
    from machinist_exceptions import load_exceptions

    (entry,) = load_exceptions(_config.CONFIG_DIR, "dt_cone_swing_platform", "part")
    assert (entry.id, entry.kind) == ("RV-01", "minor")
    assert spec.POST_MOUNT_ENGAGEMENT_NOTE in entry.where
    # The taps take the title block's edge break: no local override rides
    # their callout (Main, 2026-11-01).
    assert spec.POST_MOUNT_TAP_EDGE_BREAK == post_mount.PLATE_TAP_EDGE_BREAK_MM
    assert not any("BREAK" in row for row in drawing.POST_MOUNT_CALLOUT_BELOW)
    # The note sits in the empty band above the title block (2.5 mm text,
    # ~1.93 mm a character, 4.4 mm a line).
    x, y = drawing.ENGAGEMENT_NOTE_XY
    lines = spec.POST_MOUNT_ENGAGEMENT_NOTE.split("\n")
    note = (x, y - 0.0044 * len(lines), x + max(map(len, lines)) * 0.00193, y)
    assert note[0] > 0.2185 + 0.002  # plan caption row
    assert note[3] <= 0.0853 - 0.004  # A-A label bottom (aa9766da render)
    assert note[1] >= 0.066 + 0.004  # title block top
    assert note[2] <= 0.4189 - 0.010  # border


# Detail B's "10.45" (12 x 5 mm, 81788ce9's "11.00") hangs outward from its
# dimension line, centred on the keep y.  The hold-down callout's box follows
# RD1's render (text centred on the requested x, baseline 2.7 mm under the
# requested y, 3.5 mm text): 50 mm wide for "DRILL <MOD-DIAM>3.05 THRU ALL"
# over its counterbore line, 10 mm under to 4 mm over the requested point.
def _holddown_z_text_box() -> tuple[float, float, float, float]:
    x, y = drawing.DETAIL_KEEP["HoldDownZ"]
    return (x - 0.013, y - 0.0025, x, y + 0.0025)


def _holddown_x_text_box() -> tuple[float, float, float, float]:
    """HoldDownX's text frame as the audit read it (run 20260930T041147948Z):
    centred on the keep x, standing on its dimension line."""
    x, y = drawing.DETAIL_KEEP["HoldDownX"]
    w, h = drawing.HOLDDOWN_X_TEXT_SIZE
    line_y = y - drawing.HOLDDOWN_X_LINE_DROP
    return (x - w / 2.0, line_y, x + w / 2.0, line_y + h)


# The hold-down callout's widest row: DRILL Ø3.05 THRU ALL at 50.0 mm (r8),
# or the mate row LOCATES MHA-DT-21, not yet printed (~47..52 mm).  The
# underline's left end, where the leader leaves, stands 1.6 mm before it.
_CALLOUT_HALF_WIDTHS = (0.0250, 0.0262)
_CALLOUT_SHOULDER = 0.0016


def _holddown_callout_box() -> tuple[float, float, float, float]:
    """Four rows centred on the request: r6 boxed them y 0.0523..0.0726 for
    a request y of 0.0625, with the underline's shoulder at their left."""
    x, y = drawing.HOLDDOWN_CALLOUT_XY
    half = max(_CALLOUT_HALF_WIDTHS)
    return (x - half - _CALLOUT_SHOULDER, y - 0.0102, x + half, y + 0.0101)


def _holddown_leader(half: float = 0.0250) -> tuple[tuple[float, float], tuple[float, float]]:
    """The hold-down callout's leader: from its underline's left end (r8:
    the last row's baseline, 11.17 mm under the requested y) to the
    counterbore's sheet-right wall at the underside (r8's tip)."""
    x, y = drawing.HOLDDOWN_CALLOUT_XY
    wall_x = _holddown_hole_x() + spec.HOLDDOWN_CBORE_DIA / 2.0 * _cc_scale()
    start = (x - half - _CALLOUT_SHOULDER, y - 0.011166)
    return (start, (wall_x, drawing.holddown_strip_box()[1]))


def _holddown_strip() -> tuple[float, float, float, float]:
    """Section C-C's cropped outline: its placed strip plus the crop
    fence's margin all round."""
    x0, y0, x1, y1 = drawing.holddown_strip_box()
    pad = drawing.HOLDDOWN_CROP_MARGIN_MM * _cc_scale()
    return (x0 - pad, y0 - pad, x1 + pad, y1 + pad)


def _cc_scale() -> float:
    """Sheet metres per model millimetre in section C-C."""
    ratio = drawing.HOLDDOWN_SECTION_SCALE
    return ratio[0] / ratio[1] / 1000.0


def _holddown_hole_x() -> float:
    return drawing.holddown_hole_sheet_x()


# Face-label text widths the layout audit read at r8 (3.5 mm Century Gothic).
_FACE_LABEL_WIDTHS = {"TOP FACE": 0.0221, "UNDERSIDE": 0.0247}


def _face_labels() -> dict[str, tuple[tuple[float, float], tuple]]:
    """Each face label's estimated tip and text box (_FACE_LABEL_WIDTHS by
    3.6 mm tall), keyed "<view> <text>".  Tips: A-A at 2:1 about the bore
    axis (x 0.372; looking south, top face at its head, y 0.12635 = r5's
    foot 0.11365 + 2 x 6.35 mm); C-C on its placed strip."""
    strip = drawing.holddown_strip_box()
    labels = {}
    for key, text, xs, _y, pick, offset in drawing.FACE_LABELS:
        chosen = (max if pick == "max" else min)(xs)
        if key == "A-A":
            tip = (0.372 + 2 * chosen / 1000.0, 0.12635)
        else:
            tip_x = _holddown_hole_x() + (chosen - spec.HOLDDOWN_LOCAL_X) * _cc_scale()
            tip = (tip_x, strip[3] if text == "TOP FACE" else strip[1])
        x, y = tip[0] + offset[0], tip[1] + offset[1]
        labels[f"{key} {text}"] = (tip, (x, y - 0.0036, x + _FACE_LABEL_WIDTHS[text], y))
    return labels


def _a_a_top_face_box() -> tuple[float, float, float, float]:
    """A-A's TOP FACE label as the layout audit boxes it: text to tip."""
    tip, text = _face_labels()["A-A TOP FACE"]
    return (
        min(text[0], tip[0]),
        min(text[1], tip[1]),
        max(text[2], tip[0]),
        max(text[3], tip[1]),
    )


def _cc_face_label_boxes() -> dict[str, tuple[float, float, float, float]]:
    """C-C's face labels as the layout audit boxes them: text and leader,
    out to the tip on the strip."""
    return {
        name: (
            min(text[0], tip[0]),
            min(text[1], tip[1]),
            max(text[2], tip[0]),
            max(text[3], tip[1]),
        )
        for name, (tip, text) in _face_labels().items()
        if name.startswith("C-C")
    }


def _holddown_label() -> tuple[float, float, float, float]:
    """The native C-C label as printed: 45.9 x 14.6 mm, 2.0 mm left of and
    1.7 mm over its requested lower-left (r8)."""
    lx, ly = drawing.HOLDDOWN_SECTION_LABEL_LOWER_LEFT
    return (lx - 0.0020, ly + 0.0017, lx - 0.0020 + 0.0459, ly + 0.0017 + 0.0146)


def _holddown_label_extent() -> tuple[float, float, float, float]:
    """The native C-C label's GetExtent, which the blocking audit boxes:
    46.2 x 16.45 mm from its requested lower-left (r10)."""
    lx, ly = drawing.HOLDDOWN_SECTION_LABEL_LOWER_LEFT
    return (lx, ly, lx + 0.04616, ly + 0.01645)


def _holddown_padded_outline() -> tuple[float, float, float, float]:
    """C-C's GetOutline once cropped and placed: the strip plus 10.95 mm
    across and 6.86 mm up and down, whatever the fence (r9 at 1.0 mm, r10 at
    0.5 mm: run 20261019T025545367Z, strip lower-left (0.1376, 0.0318),
    outline 0.12665..0.20213 x 0.02494..0.05136)."""
    x0, y0, x1, y1 = drawing.holddown_strip_box()
    return (x0 - 0.01095, y0 - 0.00686, x1 + 0.01095, y1 + 0.00686)


def _segments_cross(a, b) -> bool:
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    d1, d2 = orient(b[0], b[1], a[0]), orient(b[0], b[1], a[1])
    d3, d4 = orient(a[0], a[1], b[0]), orient(a[0], a[1], b[1])
    return d1 * d2 < 0 and d3 * d4 < 0


def _segment_hits_box(segment, box) -> bool:
    if any(box[0] <= x <= box[2] and box[1] <= y <= box[3] for x, y in segment):
        return True
    corners = ((box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3]))
    edges = [(corners[i], corners[(i + 1) % 4]) for i in range(4)]
    return any(_segments_cross(segment, edge) for edge in edges)


def test_holddown_band_clears_border_title_block_and_captions() -> None:
    """Detail B, section C-C, the hold-down callout and C-C's face labels
    share the band under the plan captions without touching each other.

    Extents are the ones the layout audit logged on the farm (runs 2b643c17,
    e86bf319, eaafbc73): the detail label 31.5 x 16.2 mm, the section label
    46.5 x 16.2 mm, a detail's outline its circle plus 10.4 mm a side.
    e86bf319 failed on a label 8.9 mm through the bottom border; its callouts
    also ran under the title block and the plan caption.
    """
    border_bottom, border_left = 0.0127, 0.0127
    title_block = (0.216, 0.0, 0.4318, 0.066)
    captions = (
        (0.0449, 0.0805, 0.1059, 0.0853),
        (0.1497, 0.0805, 0.2185, 0.0853),
    )
    x, y = drawing.ENGAGEMENT_NOTE_XY
    lines = spec.POST_MOUNT_ENGAGEMENT_NOTE.split("\n")
    engagement = (x, y - 0.0044 * len(lines), x + max(map(len, lines)) * 0.00193, y)
    label_x, label_y = drawing.DETAIL_LABEL_LOWER_LEFT
    cx, cy = drawing.DETAIL_CENTER
    r = drawing.DETAIL_SHEET_RADIUS
    pad = drawing.DETAIL_OUTLINE_PAD
    outline = (cx - r - pad, cy - r - pad, cx + r + pad, cy + r + pad)
    assert outline[1] > 0.0097  # the zone border (eaafbc73 crossed it by 0.1)
    ours = {
        "detail label": (label_x, label_y, label_x + 0.0315, label_y + 0.0162),
        "detail outline": outline,
        "10.45": _holddown_z_text_box(),
        "1.00 ±0.1": _holddown_x_text_box(),
        "C-C strip": _holddown_strip(),
        "C-C label": _holddown_label(),
        "hold-down callout": _holddown_callout_box(),
        **_cc_face_label_boxes(),
    }
    for name, box in ours.items():
        if name != "detail outline":
            assert box[1] > border_bottom + 0.001, name
            assert box[0] > border_left + 0.001, name
        assert not _boxes_overlap(box, title_block), name
        assert not _boxes_overlap(box, engagement), name
        for caption in captions:
            assert not _boxes_overlap(box, caption), (name, caption)
    names = list(ours)
    # HoldDownX is detail B's own dimension, so its text may stand in the
    # detail's padded outline (the test below keeps it off the circle); C-C's
    # face labels are its own notes, standing in its padding beside the ink.
    own = {
        ("detail outline", "1.00 ±0.1"),
        ("C-C strip", "C-C UNDERSIDE"),
    }
    for i, first in enumerate(names):
        for second in names[i + 1 :]:
            if (first, second) in own:
                continue
            assert not _boxes_overlap(ours[first], ours[second]), (first, second)
    # The 10.45 text sits outside its own extension-line span (pivot to hole),
    # so SolidWorks hangs it off the line instead of centring the line through
    # it (81788ce9: "11.|00").
    assert ours["10.45"][1] >= drawing.DETAIL_HOLDDOWN_Y > drawing.DETAIL_PIVOT_Y
    # The label lies under its own strip (8783776d printed it 50 mm off).
    label = ours["C-C label"]
    strip = drawing.holddown_strip_box()
    assert strip[0] < (label[0] + label[2]) / 2.0 < strip[2]
    assert label[3] < strip[1] - 0.0025
    # The layout audit holds foreign text out of C-C's padded outline, 2 mm
    # inset (text-on-view), and a view off the title block and detail B's
    # padded outline within 1.5 mm.  The blocking audit holds the native
    # label's extent within 1.5 mm of the padded outline (r10 failed on its
    # 4.2 mm overlap at 2:1).
    inset = 0.002
    padded = _holddown_padded_outline()
    inner = (padded[0] + inset, padded[1] + inset, padded[2] - inset, padded[3] - inset)
    for name in ("10.45", "1.00 ±0.1", "detail label", "C-C label"):
        assert not _boxes_overlap(ours[name], inner), name
    assert padded[2] < title_block[0] + 0.0015
    assert padded[0] > outline[2] - 0.0015
    assert _holddown_label_extent()[3] < padded[1] + 0.0015 - 0.0005
    assert _holddown_label_extent()[1] >= border_bottom - 0.0002
    # Positive control: r10's 2:1 strip and label (0.1376, 0.0318),
    # (0.1507, 0.0126) overlapped by 4.2 mm.
    r10_padded_foot = 0.0318 - 0.00686
    assert (0.0126 + 0.01645) - r10_padded_foot > 0.0015
    # Positive control: the relief note at its old anchor (0.029) meets the
    # C-C label.
    old_relief = (0.120, 0.029 - 0.0133, 0.120 + 0.0947, 0.029)
    assert _boxes_overlap(old_relief, ours["C-C label"])


def test_holddown_callout_leader_drops_through_the_hole_to_its_counterbore() -> None:
    """Machinist review r8 read C-C's counterbore as opening on the top face
    with the leader run across the strip's left piece to the counterbore's
    underside corner.  The leader now leaves the underline's left end up and
    left of the hole and drops through the Ø3.05 hole into the counterbore,
    clear of the hole's left wall at the top face and its right wall at the
    step, whether the underline starts at the widest row (50.0 mm) or the
    shorter mate row."""
    z = spec.HOLDDOWN_LOCAL_Z
    assert drawing.plate_edge_mm(z, 1) > spec.HOLDDOWN_LOCAL_X + spec.HOLDDOWN_CBORE_DIA
    s = _cc_scale()
    hole = _holddown_hole_x()
    narrow = (hole - spec.HOLDDOWN_CLEARANCE_DIA / 2.0 * s, hole + spec.HOLDDOWN_CLEARANCE_DIA / 2.0 * s)
    foot, top = drawing.holddown_strip_box()[1], drawing.holddown_strip_box()[3]
    step = foot + spec.HOLDDOWN_CBORE_DEPTH * s

    def x_at(leader, y):
        (x0, y0), (x1, y1) = leader
        return x0 + (x1 - x0) * (y - y0) / (y1 - y0)

    start, tip = _holddown_leader()
    callout = _holddown_callout_box()
    assert callout[1] > _holddown_strip()[3] + 0.005  # the rows stand over the strip
    for half in (0.0233, *_CALLOUT_HALF_WIDTHS):
        leader = _holddown_leader(half)
        assert leader[1] == tip
        assert x_at(leader, top) > narrow[0] + 0.0005
        assert x_at(leader, step) < narrow[1] - 0.0005
        assert not _segment_hits_box(leader, _holddown_label())
        for box in _cc_face_label_boxes().values():
            assert not _segment_hits_box(leader, box)
    # Positive control, r8 at 1:1: underline from (0.1371, 0.0528), tip on
    # the counterbore wall's underside corner; the line entered the strip's
    # top 11.6 mm left of the hole.
    r8_hole, r8_foot = 0.1622072, 0.041675
    r8 = ((0.1370976, 0.052834), (r8_hole + spec.HOLDDOWN_CBORE_DIA / 2000.0, r8_foot))
    r8_top = r8_foot + spec.PLATE_THICKNESS / 1000.0
    assert x_at(r8, r8_top) < r8_hole - spec.HOLDDOWN_CLEARANCE_DIA / 2000.0 - 0.01


class _CcSection:
    """Section C-C looking south: sheet = Position + scale x model (x, y).

    Uncropped, its outline is the whole plate past the cut (r8: 71 mm wide
    at 1:1); cropped, the fence it was handed, moving with the view."""

    def __init__(self, *, crop_status=1, shrinks=True, moves=True):
        self.Position = (0.150, 0.030)
        self.crop_status, self.shrinks, self.moves = crop_status, shrinks, moves
        self.fence = None
        self.cropped = False
        self.crops: list[tuple] = []

    def project(self, point):
        k = 1000.0 * _cc_scale()
        return (self.Position[0] + k * point[0], self.Position[1] + k * point[1], 0.0)

    def GetOutline(self):  # noqa: N802
        if self.cropped and self.shrinks:
            return self.fence
        x, y = self.Position
        return (x - 0.071, y - 0.0175, x + 0.071, y + 0.0175)

    def GetSketch(self):  # noqa: N802
        return types.SimpleNamespace(ModelToSketchTransform="identity")

    def Crop2(self, *args):  # noqa: N802
        self.crops.append(args)
        self.cropped = self.crop_status == 1
        return self.crop_status

    def IsCropped(self):  # noqa: N802
        return self.cropped

    def UpdateViewDisplayGeometry(self):  # noqa: N802
        return True

    def SetViewPosition(self, xy, _move_children):  # noqa: N802
        if self.moves:
            dx, dy = xy[0] - self.Position[0], xy[1] - self.Position[1]
            self.Position = (xy[0], xy[1])
            if self.fence is not None:
                x0, y0, x1, y1 = self.fence
                self.fence = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        return True


def _crop_seat(monkeypatch, view: _CcSection):
    ns = types.SimpleNamespace

    def point(values):
        return ns(MultiplyTransform=lambda _t: ns(ArrayData=tuple(values)))

    def rectangle(x0, y0, _z0, x1, y1, _z1):
        view.fence = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        return [ns(Select4=lambda *_a: True) for _ in range(4)]

    draw = ns(
        ActivateView=lambda _name: True,
        ClearSelection2=lambda _all: True,
        EditRebuild3=lambda: True,
        SketchManager=ns(AddToDB=False, CreateCornerRectangle=rectangle),
        SelectionManager=ns(GetSelectedObjectCount2=lambda _mark: 4),
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing, "double_array", list)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, _view: "Section View C-C")
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    monkeypatch.setattr(
        drawing, "model_point_in_view", lambda _a, v, p, *, label: v.project(p)
    )
    return ns(currentModel=draw, swApp=ns(GetMathUtility=lambda: ns(CreatePoint=point)))


@pytest.mark.parametrize("defect", [None, "refused", "kept-outline", "ignored-move"])
def test_holddown_section_is_cropped_to_its_strip_and_placed(monkeypatch, defect):
    """Machinist review r8 misread C-C's counterbore at 1:1; enlarged, its
    uncropped outline (the whole plate past the cut) would cross detail B
    and the title block, so the view is cropped to its strip and the strip
    moved onto HOLDDOWN_STRIP_LOWER_LEFT.  A refused crop, a crop that left
    the outline whole and a move that did not take each raise."""
    view = _CcSection(
        crop_status=0 if defect == "refused" else 1,
        shrinks=defect != "kept-outline",
        moves=defect != "ignored-move",
    )
    adapter = _crop_seat(monkeypatch, view)
    if defect is not None:
        with pytest.raises(RuntimeError, match="section C-C"):
            drawing._crop_and_place_holddown_section(adapter, view)
        return
    drawing._crop_and_place_holddown_section(adapter, view)
    assert view.crops == [(False, True, 0)]  # straight fence, no boundary drawn
    strip = drawing.holddown_strip_box()
    pad = drawing.HOLDDOWN_CROP_MARGIN_MM * _cc_scale()
    expected = (strip[0] - pad, strip[1] - pad, strip[2] + pad, strip[3] + pad)
    assert view.GetOutline() == pytest.approx(expected, abs=1e-9)
    assert _holddown_strip() == pytest.approx(expected)
    z = spec.HOLDDOWN_LOCAL_Z
    east = view.project((drawing.plate_edge_mm(z, -1) / 1000.0, 0.0, 0.0))
    assert east[:2] == pytest.approx(drawing.HOLDDOWN_STRIP_LOWER_LEFT, abs=1e-9)
    hole = view.project((spec.HOLDDOWN_LOCAL_X / 1000.0, 0.0, 0.0))
    assert hole[0] == pytest.approx(drawing.holddown_hole_sheet_x())



def test_holddown_section_cuts_through_the_hole_axis_across_the_plate() -> None:
    """Section C-C cuts on the hold-down station, edge to edge, so the whole
    counterbore and clearance hole lie in the cut (8783776d eye-pass)."""
    z = spec.HOLDDOWN_LOCAL_Z
    ends = drawing.holddown_section_line_model_points()
    assert all(end[1:] == (spec.PLATE_THICKNESS / 1000.0, z / 1000.0) for end in ends)
    east, west = drawing.plate_edge_mm(z, -1), drawing.plate_edge_mm(z, +1)
    assert ends[0][0] * 1000.0 < east and ends[1][0] * 1000.0 > west
    # The plate's chord at the hold-down station, 10.45 south of the pivot on
    # #1128's stack (the prism block's centre station).
    fraction = (geometry.NORTH_OVERHANG - spec.HOLDDOWN_LOCAL_Z) / geometry.PLATE_LEN
    assert west - east == pytest.approx(
        geometry.HALF_WIDTH_N
        + geometry.WEST_HALF_N
        + (
            geometry.EAST_HALF_S
            - geometry.HALF_WIDTH_N
            + geometry.WEST_HALF_S
            - geometry.WEST_HALF_N
        )
        * fraction,
        abs=1e-9,
    )
    assert east < spec.HOLDDOWN_LOCAL_X - spec.HOLDDOWN_CBORE_DIA / 2.0
    assert west > spec.HOLDDOWN_LOCAL_X + spec.HOLDDOWN_CBORE_DIA / 2.0


def _cc_arrows_and_letters(line_x_mm):
    """Sheet boxes of C-C's sheet-up arrows and letters on the 1:2 plan.

    Arrows are 12.6 mm with 3 mm heads; each letter sat 15.5..22 mm above
    the line and 5.5 mm wide (the 8783776d render, full-res crop).
    """
    px, py = drawing.PROFILE_PIVOT_XY
    line_y = py - spec.HOLDDOWN_LOCAL_Z * 0.0005
    length, head, half_letter = 0.0126, 0.0015, 0.00275
    arrows, letters = [], []
    for x_mm in line_x_mm:
        x = px + x_mm * 0.0005
        arrows.append((x - head, line_y, x + head, line_y + length))
        letters.append((x - half_letter, line_y + 0.0155, x + half_letter, line_y + 0.022))
    return arrows, letters


def _clears_plate(box, side: int) -> bool:
    """``box`` lies outside the plate's ``side`` edge over its whole height."""
    px, py = drawing.PROFILE_PIVOT_XY
    far_z = -(box[3] - py) / 0.0005  # sheet-up is model -z (south)
    edge = px + drawing.plate_edge_mm(far_z, side) * 0.0005
    return box[2] < edge if side < 0 else box[0] > edge


def test_holddown_section_arrows_clear_the_profile_plan() -> None:
    """C-C's arrows and letters, looking south, stand outside the plate.

    As a +-9 mm partial cut the west letter landed on the plate's sloped west
    edge (8783776d).  Looking north (the default), the west arrow ran 0.5 mm
    beside the 8.0 extension line and through the R8 leader; sheet-up they
    stay clear of the corner radii's leaders and the north-edge witness.
    """
    px, py = drawing.PROFILE_PIVOT_XY
    arrows, letters = _cc_arrows_and_letters(drawing.HOLDDOWN_SECTION_LINE_X_MM)
    for side, arrow, letter in zip((-1, 1), arrows, letters):
        assert _clears_plate(arrow, side) and _clears_plate(letter, side)
    def arc_tip(label, dx, dy):
        # Sheet-up is model -z; the leader meets the arc at 45 degrees.
        cx, cz = drawing.corner_fillet_centre_mm(label)
        radius = {c[0]: c[3] for c in part.PLATE_CORNERS}[label] * 0.0005 / math.sqrt(2.0)
        return (px + cx * 0.0005 + dx * radius, py - cz * 0.0005 + dy * radius)

    r10_x, r10_y = drawing.PROFILE_KEEP["CornerNER"]
    r10_leader = ((r10_x + 0.0088233, r10_y - 0.0027781), arc_tip("NE", -1.0, -1.0))
    r8_leader = (drawing.PROFILE_KEEP["CornerNWR"], arc_tip("NW", 1.0, -1.0))
    north_edge_y = py - part.NORTH_OVERHANG * 0.0005
    nw_x = px + part.WEST_HALF_N * 0.0005
    nw_extension = ((nw_x, drawing._planned(0.0, 0.113)[1]), (nw_x, north_edge_y))
    for box in (*arrows, *letters):
        for line in (r10_leader, r8_leader, nw_extension):
            assert not _segment_hits_box(line, box)
        assert box[1] > north_edge_y
    # Positive control: 8783776d's +-9 mm ends put the west letter on the edge.
    _old_arrows, old_letters = _cc_arrows_and_letters((-9.0, 9.0))
    assert not _clears_plate(old_letters[1], 1)
    half = 9.0 * 0.0005
    length, head = 0.0126, 0.0015
    line_y = py - spec.HOLDDOWN_LOCAL_Z * 0.0005
    # Positive control: the default north-looking arrows hit the R8 leader
    # and the 8.0 extension line.
    down = (px + half - head, line_y - length, px + half + head, line_y)
    assert _segment_hits_box(nw_extension, down)
    old_r8_leader = (drawing._planned(0.135, 0.118), arc_tip("NW", 1.0, -1.0))
    assert _segment_hits_box(old_r8_leader, down)


def test_holddown_hole_is_the_ruled_counterbore_for_the_tip_block_screw() -> None:
    """One #4 socket-head counterbore, close clearance, drilled from under,
    .409 south of the pivot and .04 to -x of the cone axis, the block's
    foot tap offset the same way, so the block itself stays centred."""
    import dt_cone_tip_block_spec as block

    hole = spec.HOLDDOWN_HOLE_SPEC
    assert (hole.kind, hole.size) == ("counterbore_socket", "#4")
    assert dict(hole.overrides_mm) == {
        "HoleDiameter": CLEARANCE_MM[("#4", "close")],
        "CounterBoreDiameter": spec.HOLDDOWN_CBORE_DIA,
        "CounterBoreDepth": spec.HOLDDOWN_CBORE_DEPTH,
    }
    assert spec.HOLDDOWN_CLEARANCE_DIA == pytest.approx(3.048)
    assert spec.HOLDDOWN_LOCAL_X == -1.016
    assert spec.HOLDDOWN_LOCAL_Z == -block.TIP_BLOCK_PIVOT_OFFSET
    assert spec.HOLDDOWN_LOCAL_Z == pytest.approx(-10.3886)
    assert block.FOOT_TAP_OFFSET_X == spec.HOLDDOWN_LOCAL_X


def test_holddown_x_is_a_banded_dimension_hanging_right_of_detail_b() -> None:
    """User ruling 2026-09-29: the hole's lateral station prints as HoldDownX
    at .XX with +/-0.10, in detail B.  Its 2 mm span cannot hold the text,
    and inside the circle the text either ran out through the outline (run
    20260930T030604208Z) or under the plate's east edge (run
    20260930T041147948Z), so it hangs sheet-right OUTSIDE the circle (user
    ruling 2026-09-30): every corner off the circle, clear of section C-C's
    strip and label, its line clear of the hole's rim and the pivot relief."""
    assert drawing_spec.DRAWING_PRECISION["HoldDownHole"] == {
        "HoldDownX": 2,
        "HoldDownZ": 3,
    }
    assert spec.HOLDDOWN_STATION_TOL_MM == 0.1016
    text = _holddown_x_text_box()
    cx, cy = drawing.DETAIL_CENTER
    for corner_x in (text[0], text[2]):
        for corner_y in (text[1], text[3]):
            assert (
                math.dist((corner_x, corner_y), (cx, cy))
                >= drawing.DETAIL_SHEET_RADIUS + 0.001 - 1e-9
            )
    # Section C-C's cropped outline starts 2 mm or more past the text's end
    # (the uncropped 1:1 view's box, 26 mm left of its centre, run
    # 20260930T041147948Z, set this margin).
    assert text[2] <= _holddown_strip()[0] - 0.002
    assert text[1] >= drawing.HOLDDOWN_SECTION_LABEL_LOWER_LEFT[1] + 0.0162 + 0.004
    s = drawing._DETAIL_S
    line_y = text[1]
    rim_bottom = drawing.DETAIL_HOLDDOWN_Y - spec.HOLDDOWN_CLEARANCE_DIA / 2.0 * s
    relief_top = drawing.DETAIL_PIVOT_Y + spec.PIVOT_BEARING_RELIEF_DIAMETER / 2.0 * s
    arrow_half = 0.0005
    assert relief_top + arrow_half < line_y < rim_bottom - arrow_half


def test_holddown_print_worst_stack_keeps_its_margins() -> None:
    """At the counterbore callout's .XXX and the drilled oversize: head recess
    under the slide face, head clearance, bearing beside the hole, the
    counterbore-floor ledge and every web to a neighbour (the wall target)."""
    xxx = printed_band_mm(3, unit=spec.UNIT)
    head_d, head_h = 0.183 * 25.4, 0.112 * 25.4
    assert spec.HOLDDOWN_CBORE_DEPTH - xxx - head_h >= 0.1
    assert spec.HOLDDOWN_CBORE_DIA - xxx - head_d >= 0.25
    drilled = drilled_oversize_mm(unit=spec.UNIT)
    assert (head_d - (spec.HOLDDOWN_CLEARANCE_DIA + drilled)) / 2.0 >= 0.5
    ledge_min = (
        spec.PLATE_THICKNESS - spec.PLATE_STOCK_BAND - (spec.HOLDDOWN_CBORE_DEPTH + xxx)
    )
    assert spec.HOLDDOWN_LEDGE_RANGE[0] == pytest.approx(ledge_min)
    assert ledge_min >= WALL_TARGET_MM
    assert min(checks.HOLDDOWN_WEBS.values()) >= WALL_TARGET_MM


def _exec_mutated(module, replacements: dict[str, str]):
    """Run ``module``'s source with literal ``replacements`` in a fresh namespace."""
    path = Path(module.__file__)
    source = path.read_text(encoding="utf-8")
    for old, new in replacements.items():
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    mutated = types.ModuleType(module.__name__)
    mutated.__file__ = str(path)
    exec(compile(source, str(path), "exec"), mutated.__dict__)
    return mutated


@pytest.mark.parametrize(
    ("replacements", "message"),
    [
        ({"HOLDDOWN_CBORE_DEPTH = 3.5052": "HOLDDOWN_CBORE_DEPTH = 3.00"}, "stand proud"),
        ({"HOLDDOWN_CBORE_DIA = 5.5626": "HOLDDOWN_CBORE_DIA = 4.90"}, "does not clear"),
        ({"HOLDDOWN_SCREW_HEAD_DIA = 0.183": "HOLDDOWN_SCREW_HEAD_DIA = 0.160"}, "bears on"),
        ({"HOLDDOWN_CBORE_DEPTH = 3.5052": "HOLDDOWN_CBORE_DEPTH = 4.20"}, "ledge"),
    ],
)
def test_holddown_guards_refuse_a_spec_that_fails_at_print_worst(
    replacements: dict[str, str], message: str
) -> None:
    _exec_mutated(spec, {})  # positive control: the shipped spec passes
    with pytest.raises(AssertionError, match=message):
        _exec_mutated(spec, replacements)


@pytest.mark.parametrize(
    "replacement",
    [
        (
            "HOLDDOWN_LOCAL_Z = -dt_cone_tip_block_spec.TIP_BLOCK_PIVOT_OFFSET",
            "HOLDDOWN_LOCAL_Z = -6.00",
        ),  # onto the pivot
        ("HOLDDOWN_LOCAL_X = -1.016", "HOLDDOWN_LOCAL_X = 6.0"),  # to the west edge
    ],
)
def test_holddown_web_guard_refuses_a_station_that_crowds_a_neighbour(
    monkeypatch: pytest.MonkeyPatch, replacement: tuple[str, str]
) -> None:
    """Moved toward the pivot bore or the plate's west edge, the web check fires."""
    _exec_mutated(checks, {})  # positive control: the shipped station passes
    mutated = _exec_mutated(spec, dict([replacement]))
    monkeypatch.setitem(sys.modules, spec.__name__, mutated)
    with pytest.raises(AssertionError, match="hold-down leaves a web"):
        _exec_mutated(checks, {})


def test_relief_width_text_sits_between_its_neighbours() -> None:
    """The 10.50 relief text clears the 195.09 line and the plate's west edge.

    8783776d: centred at x 0.150, "OPEN TO NORTH EDGE" (50.4 mm, 2.8 mm a
    character) ran through the 195.09 line (x 0.1300) and the plate's west
    edge (x 0.1679 at that height).  Short lines keep the block ~34 mm wide
    at most; five of them still clear the 13.12 row above.
    """
    lines = ("10.50", *drawing.RELIEF_WIDTH_CALLOUT.split("\n"))
    line_195, west_edge, char_w = 0.1300, 0.1679, 0.0028

    def block(x: float, texts) -> tuple[float, float]:
        width = max(len(text) for text in texts) * char_w
        return (x - width / 2.0, x + width / 2.0)

    x = drawing.FEATURE_KEEP["PivotBearingReliefDia"][0]
    left, right = block(x, lines)
    assert line_195 + 0.002 < left and right < west_edge - 0.002
    # Positive control: 8783776d's three lines at x 0.150 hit both.
    old_left, old_right = block(0.150, ("10.50", "TOP RELIEF", "OPEN TO NORTH EDGE"))
    assert old_left < line_195 and old_right > west_edge
    # The block stands on its shelf and grows up (aa9766da render: shelf
    # 0.1438, 5.6 mm a line); the five lines top out under the 13.12 row's
    # dimension line (0.1821) with 5 mm to spare.
    shelf, pitch, row_13_12 = 0.1438, 0.0056, 0.1821
    top = shelf + len(lines) * pitch
    assert len(lines) == 5 and top <= row_13_12 - 0.005
    # No compass word: sheet-down is model north (codex B2 on 68565ace).
    assert not any(word in drawing.RELIEF_WIDTH_CALLOUT for word in ("NORTH", "SOUTH"))
    assert "PIVOT" in drawing.RELIEF_WIDTH_CALLOUT.split("\n")[-1]


def test_crank_axis_follows_the_actual_train() -> None:
    assert crank_axis.CRANK_AXIS_OFF == cone_line.PIVOT_XZ[0] - cone_line.X_CRANK
    assert crank_axis.CRANK_AXIS_Y == cone_line.Y_CRANK - cone_line.Y_BASE_TOP
    assert crank_axis.CRANK_PLANE_ANGLE == cone_line.INCLINE_DEG
    assert spec.POST_CONE_BORE_HEIGHT > gear64.OUTSIDE_DIA / 2.0
    assert spec.crank_gear_platform_clearance() >= 0.5
    assert len(drawing.SHEET_NAMES) == 1
    assert drawing.SHEET_SCALES == {drawing.SHEET_NAMES[0]: drawing.SHEET_SCALE}


def test_nominal_crank_axis_follows_the_post_station_and_the_swing() -> None:
    at_chain = crank_axis.crank_axis_nominal_xy_mm(-155.7)
    assert at_chain == pytest.approx((cone_line.X_CRANK, cone_line.Y_CRANK))
    swung = crank_axis.crank_axis_nominal_xy_mm(-155.7, 3.0)
    farther = crank_axis.crank_axis_nominal_xy_mm(-175.7, 3.0)
    assert farther[0] - swung[0] == pytest.approx(-20.0 * math.tan(math.radians(3.0)))
    assert farther[1] == swung[1]
    with pytest.raises(ValueError, match="parallel"):
        crank_axis.crank_axis_nominal_xy_mm(-155.7, 90.0)


def test_unrelieved_plate_budget_spends_all_booked_sources() -> None:
    import dt_cone_pivot_post_spec as post

    budget = spec.crank_gear_platform_budget()
    assert set(budget) == {
        "printed journal height", "journal height lower band",
        "printed maximum tip radius", "gear seat eccentricity",
        "shaft running float and tilt", "relative-crank FCF air reserve (not a cone-axis grade)",
        "conservative angular air reserve (not a BASIC-angle grade)", "tooth cutting runout",
        "local platform stock variation",
    }
    assert budget["journal height lower band"] == -post.JOURNAL_AXIS_HEIGHT_TOLERANCE_MM
    assert budget["local platform stock variation"] == -2 * spec.PLATE_STOCK_BAND
    assert budget["tooth cutting runout"] == -gear64.TOOTH_RUNOUT_TIR_MM / 2
    assert all(value < 0 for name, value in budget.items() if name != "printed journal height")
    assert spec.crank_gear_platform_clearance() == pytest.approx(sum(budget.values()))
    assert spec.cone_shaft.JOURNAL_SUPPORT_SPAN_MIN_MM < post.CONE_BOSS_LENGTH


def test_platform_air_uses_actual_contact_span(monkeypatch) -> None:
    initial = spec.crank_gear_platform_budget()["shaft running float and tilt"]
    monkeypatch.setattr(
        spec.cone_shaft, "JOURNAL_SUPPORT_SPAN_MIN_MM",
        spec.cone_shaft.JOURNAL_SUPPORT_SPAN_MIN_MM / 2.0,
    )
    assert spec.crank_gear_platform_budget()["shaft running float and tilt"] < initial


@pytest.mark.parametrize("air", (0.0, 0.49))
def test_unrelieved_plate_preflight_refuses_below_floor(monkeypatch, air) -> None:
    monkeypatch.setattr(part, "crank_gear_platform_clearance", lambda: 0.5)
    part.require_crank_gear_platform_clearance()
    monkeypatch.setattr(part, "crank_gear_platform_clearance", lambda: air)
    with pytest.raises(AssertionError, match="unrelieved platform air"):
        part.require_crank_gear_platform_clearance()
    adapter = types.SimpleNamespace(create_part=AsyncMock())
    with pytest.raises(AssertionError, match="unrelieved platform air"):
        asyncio.run(part.build(adapter))
    adapter.create_part.assert_not_awaited()


def test_lower_journal_and_larger_tip_close_air_without_changing_bands(monkeypatch) -> None:
    import dt_cone_pivot_post_spec as post

    before = spec.crank_gear_platform_clearance()
    # .080 in: whole steps of the 64T's inch print grid.
    monkeypatch.setattr(gear64, "OUTSIDE_DIA", gear64.OUTSIDE_DIA + 2.032)
    assert spec.crank_gear_platform_clearance() == pytest.approx(before - 1.016)
    monkeypatch.setattr(post, "BORE_HEIGHT", post.BORE_HEIGHT - 3.0)
    assert spec.crank_gear_platform_clearance() < 0.5


class _PixelDrawing:
    """A drawing window whose note extents read to the pixel of its zoom.

    The failed detail-B seat: a 405x470 px view window fitted to the sheet
    at 0.951 px/mm.  ``ViewZoomTo2`` fits a sheet box into the window,
    ``ViewZoomtofit2`` restores the fit, and each ``GetExtent`` floors the
    note's true box to the current pixel grid.
    """

    WINDOW_PX = (405, 470)
    FIT_PX_PER_M = 951.0

    def __init__(self) -> None:
        self.px_per_m = self.FIT_PX_PER_M
        self.zooms: list[tuple[float, ...]] = []
        self.sheet = types.SimpleNamespace(SetScale=lambda *_args: True)

    def GetCurrentSheet(self):  # noqa: N802
        return self.sheet

    def ViewZoomTo2(self, x0, y0, _z0, x1, y1, _z1):  # noqa: N802
        self.zooms.append((x0, y0, x1, y1))
        self.px_per_m = min(
            self.WINDOW_PX[0] / (x1 - x0), self.WINDOW_PX[1] / (y1 - y0)
        )

    def ViewZoomtofit2(self):  # noqa: N802
        self.px_per_m = self.FIT_PX_PER_M

    def EditRebuild3(self):  # noqa: N802
        return True


class _PixelLabel:
    """A native view label: an anchor, and a box a fixed offset from it."""

    def __init__(self, window: _PixelDrawing, anchor, corner_offset, size) -> None:
        self.window = window
        self.anchor = list(anchor)
        self.corner_offset = corner_offset
        self.size = size
        self.read_px_per_m: list[float] = []

    def true_lower_left(self) -> tuple[float, float]:
        return tuple(a + o for a, o in zip(self.anchor, self.corner_offset))

    def GetText(self):  # noqa: N802
        return "DETAIL B\nSCALE 2 : 1"

    def GetExtent(self):  # noqa: N802
        px = self.window.px_per_m
        self.read_px_per_m.append(px)
        x0, y0 = self.true_lower_left()
        corners = (x0, y0, x0 + self.size[0], y0 + self.size[1])
        x0, y0, x1, y1 = (math.floor(value * px) / px for value in corners)
        return (x0, y0, 0.0, x1, y1, 0.0)

    def GetAnnotation(self):  # noqa: N802
        return self

    def GetPosition(self):  # noqa: N802
        return (*self.anchor, 0.0)

    def SetPosition2(self, x, y, _z):  # noqa: N802
        self.anchor = [x, y]
        return True


def test_detail_label_is_placed_and_read_zoomed_onto_its_box(monkeypatch) -> None:
    """Detail B's label lands on its request on a small, fitted seat window.

    At 0.951 px/mm a pixel is 1.05 mm, so the fitted readback could not
    resolve the 0.5 mm landing check: run f08e23d0b1b6 read the box
    0.70/-0.39 mm off after both corrections.  Zoomed onto the box, every
    readback that moves or judges the label resolves a tenth of a
    millimetre, and the fit is restored afterwards.
    """
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    window = _PixelDrawing()
    target = drawing.DETAIL_LABEL_LOWER_LEFT
    # Measured on the green builds: the box's lower-left sits (-15.85, -16.37)
    # mm from the label's anchor and the box is 31.45 x 16.68 mm.
    label = _PixelLabel(
        window,
        anchor=(target[0] + 0.0172, target[1] + 0.0158),
        corner_offset=(-0.01585, -0.01637),
        size=(0.03145, 0.01668),
    )
    # Section C-C also carries the script's face labels (r4 failed on them).
    face_label = types.SimpleNamespace(GetText=lambda: "UNDERSIDE")
    view = types.SimpleNamespace(GetNotes=lambda: (face_label, label))
    adapter = types.SimpleNamespace(currentModel=window)

    drawing._position_view_label(adapter, view, target, label="detail B label")

    assert max(abs(a - b) for a, b in zip(label.true_lower_left(), target)) < 0.0002
    assert len(window.zooms) == 1
    x0, y0, x1, y1 = window.zooms[0]
    assert x0 < target[0] and y0 < target[1]
    assert x1 > target[0] + label.size[0] and y1 > target[1] + label.size[1]
    assert all(px >= 5000.0 for px in label.read_px_per_m[1:])
    assert window.px_per_m == window.FIT_PX_PER_M


class _SeatDetailB:
    """Detail B as leaf 20261013T033510Z-1-11767ee6 read it.

    The outline and Position readbacks are the leaf's own; SetViewPosition
    moves both by the requested shift.  The transform stays in the frame the
    view had before it was recentred, through any number of rebuilds, until
    UpdateViewDisplayGeometry refreshes it (``barrier_refreshes``)."""

    STALE = (0.07792919217322382, -0.05755193679034118)
    CURRENT = (0.08349998709459218, 0.04499996678531765)

    def __init__(self, *, barrier_refreshes: bool) -> None:
        self.barrier_refreshes = barrier_refreshes
        self.Position = (0.09059908135529601, 0.14789132832482269)
        self.outline = (
            0.06439455575742567,
            0.02535145368125846,
            0.10243332384123646,
            0.06532739581706931,
        )
        self.current = False
        self.reads: list[tuple[float, float]] = []

    def GetOutline(self):
        return self.outline

    def SetViewPosition(self, moved, _keep) -> bool:
        dx, dy = moved[0] - self.Position[0], moved[1] - self.Position[1]
        x0, y0, x1, y1 = self.outline
        self.outline = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        self.Position = tuple(moved)
        self.current = False
        return True

    def UpdateViewDisplayGeometry(self) -> None:
        self.current = self.current or self.barrier_refreshes

    def project(self) -> tuple[float, float]:
        self.reads.append(self.CURRENT if self.current else self.STALE)
        return self.reads[-1]


def _detail_b_on_seat(monkeypatch, *, barrier_refreshes: bool):
    detail = _SeatDetailB(barrier_refreshes=barrier_refreshes)
    parent = types.SimpleNamespace(
        GetSketch=lambda: types.SimpleNamespace(ModelToSketchTransform=None)
    )
    selection = types.SimpleNamespace(View=None)
    draw = types.SimpleNamespace(
        ActivateView=lambda _name: True,
        ClearSelection2=lambda _all: None,
        SketchManager=types.SimpleNamespace(
            AddToDB=False,
            CreateCircle=lambda *_points: types.SimpleNamespace(
                Select4=lambda _append, _data: True
            ),
        ),
        SelectionManager=types.SimpleNamespace(CreateSelectData=lambda: selection),
        CreateDetailViewAt4=lambda *_args: detail,
    )
    math_utility = types.SimpleNamespace(
        CreatePoint=lambda xyz: types.SimpleNamespace(
            MultiplyTransform=lambda _transform: types.SimpleNamespace(ArrayData=xyz)
        )
    )
    adapter = types.SimpleNamespace(
        currentModel=draw,
        swApp=types.SimpleNamespace(GetMathUtility=lambda: math_utility),
    )
    clock = [0.0]

    def rebuild(_adapter, *, label):
        clock[0] += 0.15

    def point_in_view(_adapter, view, xyz, *, label):
        if view is detail:
            return detail.project()
        return (0.1768110126543147 + xyz[0], 0.13872403990850002)

    for module in (drawing, _drawing_detail_projection):
        monkeypatch.setattr(module, "_early_bound", lambda obj, _interface: obj)
        monkeypatch.setattr(module, "model_point_in_view", point_in_view)
        monkeypatch.setattr(module, "rebuild_drawing", rebuild)
    monkeypatch.setattr(
        drawing,
        "_sw_type_info",
        types.SimpleNamespace(early_bound_or_flag=lambda obj, *_members: obj),
    )
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, _view: "Drawing View1")
    monkeypatch.setattr(drawing, "double_array", list)
    monkeypatch.setattr(
        _drawing_detail_projection,
        "time",
        types.SimpleNamespace(perf_counter=lambda: clock[0]),
    )
    built = drawing._create_detail_view(
        adapter,
        parent,
        model_center_mm=(0.0, spec.PLATE_THICKNESS, drawing.DETAIL_MODEL_Z),
        radius_mm=drawing.DETAIL_RADIUS_MM,
        view_xy=drawing.DETAIL_CENTER,
        detail_label="B",
        scale=drawing.DETAIL_SCALE,
        label="hold-down station detail",
    )
    return built, detail


def test_detail_b_projects_behind_the_display_barrier_on_the_failing_seat(
    monkeypatch,
) -> None:
    """#1336: on 4 of 41 leaves three settle rebuilds left detail B's transform
    in its pre-recentre frame, projecting the centre 102.55 mm below the ink.
    Read behind UpdateViewDisplayGeometry, the same seat settles at once."""
    built, detail = _detail_b_on_seat(monkeypatch, barrier_refreshes=True)
    assert built is detail
    assert detail.reads == [_SeatDetailB.STALE, _SeatDetailB.CURRENT]
    assert detail.Position == pytest.approx((0.09068514155596494, 0.1475519035756588))


def test_a_detail_b_transform_that_never_refreshes_still_fails(monkeypatch) -> None:
    with pytest.raises(RuntimeError) as failure:
        _detail_b_on_seat(monkeypatch, barrier_refreshes=False)
    message = str(failure.value)
    assert message.startswith(
        "detail B projects its centre to (0.07792919217322382, -0.05755193679034118) "
        "while its outline is centred on (0.08349999999999999, 0.04500000000000001)"
    )
    assert "34 rebuilds and 5.10 s" in message


_CBORE_PARTS = {
    5: "<HOLE-CBORE><MOD-DIAM><hw-cbdia> <HOLE-DEPTH><hw-cbdepth>",
    6: "",
    7: "<MOD-DIAM><hw-diam> THRU ALL",
    8: "",
}


def test_holddown_callout_drills_in_its_thru_row_and_names_face_and_mate() -> None:
    """Machinist review r1: "DRILL ⌴ Ø5.56" read as drilling the counterbore,
    and the +-0.1 stations of detail B named no mate (rule 4)."""
    updated = drawing.holddown_callout_definitions(dict(_CBORE_PARTS))
    assert updated[5] == _CBORE_PARTS[5]
    assert updated[7] == "DRILL <MOD-DIAM><hw-diam> THRU ALL"
    assert updated[8] == "FROM UNDERSIDE\nLOCATES MHA-DT-21"
    counted = drawing.holddown_callout_definitions(
        {**_CBORE_PARTS, 7: "<NUM_INST>X <MOD-DIAM><hw-diam> THRU ALL"}
    )
    assert counted[7] == "<NUM_INST>X DRILL <MOD-DIAM><hw-diam> THRU ALL"
    # Fail closed on a layout the rewrite was not written for.
    with pytest.raises(RuntimeError, match="already prints below"):
        drawing.holddown_callout_definitions({**_CBORE_PARTS, 8: "X"})
    with pytest.raises(RuntimeError, match="not one upper part"):
        drawing.holddown_callout_definitions({**_CBORE_PARTS, 5: "THRU", 7: "THRU"})
    with pytest.raises(RuntimeError, match="unexpected hole callout parts"):
        drawing.callout_below_definitions({5: "", 6: "", 7: ""}, ("A",))


@pytest.mark.parametrize("stale", [None, "definition", "resolved"])
def test_post_mount_class_override_preserves_native_thread_rows(monkeypatch, stale) -> None:
    import _hole_callout_thread_class as thread_class

    original = {
        5: "<NUM_INST>X <hw-threaddesc> - <hw-threadclass> THRU ALL",
        6: "<HOLE-DEPTH><hw-threaddepth>",
        7: "<MOD-DIAM><hw-diam> <HOLE-DEPTH><hw-depth>",
        8: "\n".join(drawing.POST_MOUNT_CALLOUT_BELOW),
    }
    expected = {**original, 5: "<NUM_INST>X <hw-threaddesc> THRU ALL"}

    class NativeCallout:
        def __init__(self):
            self.definitions = dict(original)
            self.writes = []

        def IsHoleCallout(self):
            return True

        def GetText(self, part):
            if part >= 5:
                return self.definitions[part]
            definition = self.definitions[part + 4]
            resolved = definition.replace("<hw-threadclass>", "2B")
            if stale == "resolved" and part == 1:
                resolved += " - 2B"
            return resolved

        def SetText(self, part, text):
            self.writes.append((part, text))
            if stale != "definition":
                self.definitions[part + 4] = text

    native = NativeCallout()
    monkeypatch.setattr(thread_class, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    if stale:
        with pytest.raises(RuntimeError, match="kept its thread class|still prints its class"):
            drawing._omit_post_mount_thread_class(native)
    else:
        drawing._omit_post_mount_thread_class(native)
        assert native.definitions == expected
    assert native.writes == [(1, expected[5])]
    assert spec.POST_MOUNT_SPEC.thread_class == "2B"
    # Keep the native count/designation/size/depth/break/mate definitions,
    # and ensure the production build applies this part-local override.
    source = ast.parse(Path(drawing.__file__).read_text())
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_omit_post_mount_thread_class"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "post_mount_callout"
        for node in ast.walk(source)
    )


def test_post_mount_class_override_refuses_a_nondefault_class_before_native_edit(
    monkeypatch,
) -> None:
    monkeypatch.setattr(drawing, "POST_MOUNT_SPEC", types.SimpleNamespace(thread_class="3B"))

    def forbidden_omission(*_args, **_kwargs):
        raise AssertionError("nondefault class must not reach native class omission")

    monkeypatch.setattr(drawing, "omit_title_block_thread_class", forbidden_omission)
    with pytest.raises(RuntimeError, match="only title-block default class 2B"):
        drawing._omit_post_mount_thread_class(object())


def test_tight_bands_name_their_mates_on_their_callouts() -> None:
    """Rule 4: the reamed bore and both +-0.1 hole groups name the part that
    makes the tolerance necessary, each at its own callout (r1 blocker)."""
    assert drawing.PIVOT_BORE_CALLOUT_BELOW == ("RUNNING FIT ON MHA-DT-VN-52 SHOULDER",)
    assert "MHA-DT-05" in drawing.POST_MOUNT_CALLOUT_BELOW[0]
    assert "MHA-DT-21" in drawing.HOLDDOWN_CALLOUT_BELOW[1]
    pivot = drawing.callout_below_definitions(
        {5: "REAM <MOD-DIAM><hw-diam>", 6: "", 7: "", 8: ""},
        drawing.PIVOT_BORE_CALLOUT_BELOW,
    )
    assert pivot == {
        5: "REAM <MOD-DIAM><hw-diam>",
        6: "",
        7: "",
        8: "RUNNING FIT ON MHA-DT-VN-52 SHOULDER",
    }
    # SolidWorks drops multi-line text above a dimension; every added row is
    # below, and the tallest callout's rows stay in their free fields.
    for rows in (
        drawing.PIVOT_BORE_CALLOUT_BELOW,
        drawing.POST_MOUNT_CALLOUT_BELOW,
        drawing.HOLDDOWN_CALLOUT_BELOW,
    ):
        assert all("\n" not in row for row in rows)
    # ~2.4 mm a character at 3.5 mm: the hold-down's mate row, centred on its
    # requested x, ends left of the title block.
    width = len(drawing.HOLDDOWN_CALLOUT_BELOW[1]) * 0.0024
    assert drawing.HOLDDOWN_CALLOUT_XY[0] + width / 2.0 < 0.216


def test_relief_fit_note_stands_over_section_a_a_clear_of_its_neighbours() -> None:
    """Rule 7: the relief fit is flagged by a leader at the relief on A-A
    (machinist review r1 read the note under C-C as C-C's)."""
    x, y = drawing.RELIEF_NOTE_XY
    lines = spec.PIVOT_RELIEF_FIT_REQUIREMENT.split("\n")
    # r2 measured the note's rows at 2.8 mm a character, ~4.2 mm a row.
    right = x + max(map(len, lines)) * 0.0028
    bottom = y - len(lines) * 0.0042
    assert x > 0.296 + 0.002  # 213.56 dimension line (CapECz)
    assert 0.1692 - y > 0.00357  # r11 CapECz text bottom vs note top
    assert bottom > 0.1366 + 0.002  # A-A's PlateThk text
    assert y < drawing.ISO_CAPTION_UPPER_LEFT[1] - 0.0048 - 0.002  # iso caption
    assert drawing.ISO_CAPTION_UPPER_LEFT[1] < 0.189 - 0.002  # isometric's ink
    assert drawing.RELIEF_TIP_INSET_MM < spec.PIVOT_BEARING_RELIEF_DIAMETER / 2.0
    # A-A looks south, so the relief stands at the strip's head (top face
    # y 0.12635, floor 0.5 mm under it).  The leader leaves the top row's
    # right end and falls to the left-hand piece's floor: at the top face it
    # passes through the relief's opening (x 0.3615..0.36565), not the hatch;
    # it passes between the seat's Ra text and the TOP FACE label's box.
    scale = 2.0 / 1000.0
    head = 0.12635
    floor = head - spec.PIVOT_BEARING_RELIEF_DEPTH * scale
    bore = drawing.PIVOT_HOLE_DIA / 2.0
    relief = spec.PIVOT_BEARING_RELIEF_DIAMETER / 2.0

    def tip_at(side: int) -> tuple[float, float]:
        return (0.372 + side * (bore + drawing.RELIEF_TIP_INSET_MM) * scale, floor)

    start, tip = (right, y - 0.0015), tip_at(-1)

    def x_at(row_y: float) -> float:
        return start[0] + (tip[0] - start[0]) * (start[1] - row_y) / (start[1] - tip[1])

    assert 0.372 - relief * scale < tip[0] < 0.372 - bore * scale
    assert 0.372 - relief * scale < x_at(head) < 0.372 - bore * scale
    seat_text_right = drawing.SEAT_FINISH_XY[0] + 0.0164  # r2: Ra 3.2 ends +16.4 mm
    for row in (drawing.SEAT_FINISH_XY[1], drawing.SEAT_FINISH_XY[1] + 0.0061):
        assert x_at(row) > seat_text_right + 0.005
    # The layout audit boxes each note from its text to its tip (r2: the
    # TOP FACE label on the left-hand piece lay inside this note's box).
    note_box = (x, tip[1], max(right, tip[0]), y)
    assert not _boxes_overlap(note_box, _a_a_top_face_box())
    old_tip = (0.372 - 2 * 6.8 / 1000.0, head)
    old_box = (old_tip[0] - 0.024, head, old_tip[0], head + 0.0086)
    assert _boxes_overlap(note_box, old_box)


def test_both_sections_name_their_faces() -> None:
    """Machinist review r3 blocker: neither section named a face.  Both look
    south, top face at the head (machinist review of e04fd60).  A-A names
    its top face, over its strip; C-C its underside, the face its callout's
    FROM UNDERSIDE names (enlarged, no field right of its strip holds a TOP
    FACE label short of the title block)."""
    labels = {(key, text) for key, text, *_ in drawing.FACE_LABELS}
    assert labels == {("A-A", "TOP FACE"), ("C-C", "UNDERSIDE")}
    assert "FROM UNDERSIDE" in drawing.HOLDDOWN_CALLOUT_BELOW
    for _key, text, _xs, model_y, pick, _offset in drawing.FACE_LABELS:
        assert model_y == (spec.PLATE_THICKNESS if text == "TOP FACE" else 0.0)
        assert pick in {"max", "min"}
    labels = _face_labels()
    # Each tip stands beyond one end of its text, so the leader does not run
    # back through the letters (r6: two leader-through-own-text).
    for name, (tip, text) in labels.items():
        assert tip[0] < text[0] - 0.0015 or tip[0] > text[2] + 0.0015, name
    # A-A's label over the right-hand piece's top face outboard of the
    # relief, right of the relief note's text-to-tip box, over (0.25).
    tip, top = labels["A-A TOP FACE"]
    relief_edge = 0.372 + spec.PIVOT_BEARING_RELIEF_DIAMETER / 1000.0
    assert relief_edge < tip[0] < 0.3899  # r2: right-hand piece ends 0.3899
    assert top[1] > tip[1] + 0.004  # strip head
    assert top[1] > 0.1352 + 0.004  # (0.25) text top (r2)
    assert top[0] > 0.3637 + 0.002  # relief note's tip (r2)
    assert top[2] < 0.4149  # border less the audit's 4 mm
    # C-C's UNDERSIDE: its tip on the solid underside left of the
    # counterbore, its text clear of the native label by more than the
    # audit's separation (3.57 mm; r8 advisory at 2.26).
    tip, under = labels["C-C UNDERSIDE"]
    strip = drawing.holddown_strip_box()
    cbore_left = _holddown_hole_x() - spec.HOLDDOWN_CBORE_DIA / 2.0 * _cc_scale()
    assert strip[0] + 0.001 < tip[0] < cbore_left - 0.001
    assert tip[1] == pytest.approx(strip[1])
    assert _holddown_label()[0] - under[2] > 0.0036
    assert under[3] < strip[1] - 0.002


@pytest.mark.parametrize("defect", [None, "south", "refused", "rotated"])
def test_sections_turn_to_look_south_top_face_up(monkeypatch, defect) -> None:
    """Machinist review of e04fd60: A-A, looking north, drew the top face at
    its foot, opposite to C-C.  A north-looking cut is reversed once and must
    then read model +x sheet-right and +y sheet-up; a reversal that does not
    persist, or a south-looking view turned 180 degrees, is refused."""
    state = {"reversed": False, "sets": 0}

    def set_reversed(value):
        state["sets"] += 1
        if defect != "refused":
            state["reversed"] = value

    cut = types.SimpleNamespace(
        GetReversedCutDirection=lambda: state["reversed"],
        SetReversedCutDirection=set_reversed,
        GetArrowInfo=lambda: (),
        GetTextInfo=lambda: (),
    )
    parent = types.SimpleNamespace(GetSectionLineInfo2=lambda: ())

    def project(_adapter, _view, point, **_kwargs):
        east, up = (1.0, -1.0)
        if defect == "south" or state["reversed"]:
            east, up = (-1.0, -1.0) if defect == "rotated" else (1.0, 1.0)
        return (east * point[0], up * point[1])

    monkeypatch.setattr(drawing, "model_point_in_view", project)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "_early_bound", lambda item, _interface: item)

    def look() -> None:
        drawing._look_section_south(
            object(), parent, object(), cut, z_mm=0.0, label="A-A"
        )

    if defect in {None, "south"}:
        look()
        assert state["sets"] == (0 if defect == "south" else 1)
        assert state["reversed"] is (defect is None)
    else:
        message = "did not persist" if defect == "refused" else "top face up"
        with pytest.raises(RuntimeError, match=message):
            look()


@pytest.mark.parametrize("defect", [None, "refused", "ignored"])
def test_broad_face_finishes_take_the_any_process_symbol(monkeypatch, defect):
    """Machinist review of 8c9acd48 (blocker, r2+r3): material-removal-
    required symbols on both broad faces contradicted "1/4 PLATE AS
    SUPPLIED" (U41).  The stock faces take the any-process symbol, read back."""
    state = {"symbol": 1}

    def set_symbol(kind, texture, all_around):
        assert (texture, all_around) == (0, False)
        if defect == "refused":
            return False
        if defect != "ignored":
            state["symbol"] = kind
        return True

    symbol = types.SimpleNamespace(
        SetSymbol=set_symbol, GetSymbol=lambda: state["symbol"]
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda item, _interface: item)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    if defect is None:
        drawing._set_any_process_finish(object(), symbol, label="seat")
        assert state["symbol"] == drawing.SF_ANY_PROCESS == 0
    else:
        message = "failed to set" if defect == "refused" else "did not persist"
        with pytest.raises(RuntimeError, match=message):
            drawing._set_any_process_finish(object(), symbol, label="seat")


def _fake_pivot_section(monkeypatch, *, origin, ignored=False):
    state = {"origin": origin}

    def move(position, _snap):
        if not ignored:
            ox, oy = state["origin"]
            state["origin"] = (ox + position[0] - 0.365, oy + position[1] - 0.120)
        return True

    def project(_adapter, _view, point, **_kwargs):
        ox, oy = state["origin"]
        return (ox + 2 * point[0], oy + 2 * point[1])

    view = types.SimpleNamespace(
        Position=(0.365, 0.120), SetViewPosition=move, GetOutline=lambda: ()
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda item, _interface: item)
    monkeypatch.setattr(drawing, "double_array", list)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "model_point_in_view", project)
    return state, view


@pytest.mark.parametrize("ignored", [False, True])
def test_reversed_pivot_section_is_moved_back_onto_its_station(monkeypatch, ignored):
    """Run 20261023T181910549Z: reversed, A-A kept its underside at 0.12635
    and grew 12.7 mm upward, so one PlateThk witness missed its level.  The
    view is moved until the bore axis at the underside reads
    PIVOT_SECTION_BORE_XY; a move SolidWorks ignores is refused."""
    state, view = _fake_pivot_section(
        monkeypatch, origin=(0.3725, 0.12635), ignored=ignored
    )
    assert drawing.PIVOT_SECTION_BORE_XY == pytest.approx((0.372, 0.11365))
    if ignored:
        with pytest.raises(RuntimeError, match="landed at"):
            drawing._place_pivot_section(object(), view)
        return
    drawing._place_pivot_section(object(), view)
    assert state["origin"] == pytest.approx(drawing.PIVOT_SECTION_BORE_XY)


def test_pivot_section_is_cropped_to_its_strip_after_its_dimensions(monkeypatch):
    """Run 20261023T182942818Z: looking south, A-A's outline was the whole
    plate south of the cut, 28.2 mm past the border, so it is cropped to its
    strip -- after its dimensions are curated: cropped first, PlateThk found
    nothing to import onto (run 20261023T185029293Z)."""
    state, view = _fake_pivot_section(monkeypatch, origin=drawing.PIVOT_SECTION_BORE_XY)
    fences = []
    monkeypatch.setattr(
        drawing,
        "_crop_section_to_fence",
        lambda _adapter, _view, fence, *, label: fences.append((label, fence)),
    )
    drawing._crop_pivot_section(object(), view)
    assert state["origin"] == pytest.approx(drawing.PIVOT_SECTION_BORE_XY)
    [(label, fence)] = fences
    x0, y0 = drawing.PIVOT_SECTION_BORE_XY
    margin = drawing.PIVOT_CROP_MARGIN_MM * 2 / 1000.0
    assert label == "A-A"
    assert fence == pytest.approx(
        (
            x0 + 2 * drawing.plate_edge_mm(0.0, -1) / 1000.0 - margin,
            y0 - margin,
            x0 + 2 * drawing.plate_edge_mm(0.0, 1) / 1000.0 + margin,
            y0 + 2 * spec.PLATE_THICKNESS / 1000.0 + margin,
        )
    )
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    curated = next(
        node.lineno
        for node in build.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "section_annotations"
    )
    cropped = next(
        node.lineno
        for node in build.body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and getattr(node.value.func, "id", None) == "_crop_pivot_section"
    )
    assert curated < cropped


@pytest.mark.parametrize(
    ("accepted", "persisted", "error"),
    (
        (True, 1, None),
        (False, 1, "failed to set"),
        (True, 0, "did not persist"),
    ),
)
def test_section_line_style_refuses_a_failed_native_setting(
    monkeypatch, accepted, persisted, error
) -> None:
    extension = types.SimpleNamespace(
        SetUserPreferenceInteger=lambda *_: accepted,
        GetUserPreferenceInteger=lambda *_: persisted,
    )
    document = types.SimpleNamespace(Extension=extension)
    monkeypatch.setattr(drawing, "_early_bound", lambda item, _interface: item)
    if error is None:
        drawing._set_end_only_section_lines(document)
    else:
        with pytest.raises(RuntimeError, match=error):
            drawing._set_end_only_section_lines(document)


@pytest.mark.parametrize(
    "readback",
    (
        drawing.DETAIL_PARENT_LETTER_XY,
        (0.184923, 0.1339812),
        (float("nan"), 0.145),
        (0.188,),
    ),
)
def test_detail_parent_letter_requires_a_finite_persisted_position(monkeypatch, readback):
    circle = types.SimpleNamespace(
        GetLabel=lambda: "B",
        SetLabelPosition=lambda *_: None,
        GetLabelPosition=lambda: readback,
    )
    parent = types.SimpleNamespace(GetDetailCircles=lambda: (circle,))
    monkeypatch.setattr(drawing, "_early_bound", lambda item, _interface: item)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    if readback == drawing.DETAIL_PARENT_LETTER_XY:
        drawing._place_detail_parent_letter(object(), parent)
    else:
        with pytest.raises(RuntimeError, match="did not persist"):
            drawing._place_detail_parent_letter(object(), parent)


def test_detail_parent_letter_clears_the_relief_arrow_and_station_witness():
    # r11 native letter anchor and printed box; translating this fixture is
    # an offline placement calculation, not evidence of the new native print.
    old_anchor = (0.184923, 0.1339812)
    old_box = (0.1861, 0.1273, 0.1897, 0.1335)
    dx, dy = (
        drawing.DETAIL_PARENT_LETTER_XY[i] - old_anchor[i] for i in range(2)
    )
    x0, y0, x1, y1 = (
        old_box[0] + dx, old_box[1] + dy, old_box[2] + dx, old_box[3] + dy
    )
    assert x0 > 0.1858 + 0.002  # relief-width arrow's former near-text finding
    assert y0 > 0.1267 + 0.002  # pivot baseline witness
    assert x0 > 0.182811 + 0.002  # detail circle's right edge
    assert x1 < 0.225 - 0.002 and y1 < 0.1732 - 0.002  # other stations


def test_pivot_callout_has_a_full_text_height_between_the_identifier_and_caption():
    # r11 printed box at y92.6..106.3 mm for the 99 mm anchor.
    shift = drawing.PIVOT_BORE_CALLOUT_XY[1] - 0.099
    assert 0.1084 - (0.1063 + shift) > 0.00357
    assert (0.0926 + shift) - 0.085 > 0.00357


def test_pivot_section_uses_profile_station_and_native_end_only_style():
    """Pin the actual A-A dataflow, not merely the presence of 'profile'."""
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "build")
    assignments = {
        node.targets[0].id: node
        for node in build.body
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
    }
    aa = assignments["section"]
    cc = assignments["holddown_section"]
    style = next(
        node for node in build.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "_set_end_only_section_lines"
    )
    assert style.lineno < aa.lineno < cc.lineno
    assert ast.unparse(cc.value.args[1]) == "profile"
    assert ast.unparse(assignments["detail"].value.args[1]) == "feature"
    assert "PostMount" not in " ".join(drawing.PROFILE_KEEP)
    assert {"PostMountWestZ", "PostMountEastZ"} <= drawing.FEATURE_KEEP.keys()

    profile = object()
    projections = []

    def project(_adapter, view, point, **_kwargs):
        projections.append((view, point))
        return (0.071811, 0.126724)

    namespace = {
        "adapter": object(), "profile": profile,
        "model_point_in_view": project, "SECTION_CENTER": drawing.SECTION_CENTER,
        "PROFILE_CENTER": drawing.PROFILE_CENTER,
        "create_section_view": lambda *args, **kwargs: (args, kwargs),
    }
    selected = [
        assignments[name] for name in (
            "profile_section_pivot", "section"
        )
    ]
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(drawing.__file__), "exec"), namespace)
    args, kwargs = namespace["section"]
    assert projections == [(profile, (0.0, 0.0, 0.0))]
    assert args[1] is profile
    assert kwargs.pop("line_start") == pytest.approx((0.029, 0.126724))
    assert kwargs.pop("line_end") == pytest.approx((0.094, 0.126724))
    assert kwargs == {
        "view_xy": drawing.SECTION_CENTER, "section_label": "A",
        "scale": (2, 1), "label": "pivot bearing section",
    }


def test_profile_a_a_saved_envelope_clears_post_mount_witnesses():
    """r13/90da07a1: place the saved 6 mm end-only stubs outside the radii.

    Offline envelope arithmetic only; the new saved native drawing must
    still prove the actual section line, arrows, and attachment geometry.
    """
    left = drawing.PROFILE_CENTER[0] - 0.046
    right = drawing.PROFILE_CENTER[0] + 0.019
    stubs = ((left, left + 0.006), (right - 0.006, right))
    old_stubs = ((0.1574343, 0.1634343), (0.1965657, 0.2025657))
    witnesses = ((0.129, 0.1806485), (0.1806485, 0.226))
    for old_stub, witness in zip(old_stubs, witnesses):
        assert min(old_stub[1], witness[1]) - max(old_stub[0], witness[0]) == pytest.approx(0.006)
    for stub in stubs:
        for start, end in witnesses:
            assert stub[1] < start or stub[0] > end
    # Looking south, each end's arrow rises to its letter (31547443 render:
    # the left end at x 0.029 printed its A over x 0.0262..0.0322).  At x
    # 0.123 the right letter stood beside HOLE LOCATIONS' 202.84 line
    # (x 0.1294) and read as that view's cut (machinist review, confirmed);
    # now it stands by the plate, clear of C-C's right arrow (x 0.0834).
    letter = (right - 0.0028, right + 0.0032)
    assert witnesses[0][0] - letter[1] > 0.02
    assert letter[0] - 0.0834 > 0.005
    assert 0.1294 - (0.123 + 0.0032) < 0.005  # positive control: old end


def test_profile_radius_saved_envelopes_clear_a_a_and_c_c():
    """r13 circle centres/text offsets predict the new shelves and rays.

    Recompute each arrow from the circle-to-knee ray: moving the annotation
    does not preserve the saved arrow tip. Native trimmed-arc proof remains
    the farm attachment gate's job.
    """
    r10 = drawing.PROFILE_KEEP["CornerNER"]
    r8 = drawing.PROFILE_KEEP["CornerNWR"]
    assert r10 == pytest.approx((0.045, 0.130))
    assert r8 == pytest.approx((0.137, 0.101))
    r10_box = (r10[0] - 0.0072358, r10[1] - 0.0027781,
               r10[0] + 0.0072357, r10[1] + 0.0007219)
    left = drawing.PROFILE_CENTER[0] - 0.046
    right = drawing.PROFILE_CENTER[0] + 0.019
    assert r10_box[0] - (left + 0.006) > 0.002
    # Positive control: the original profile end would nearly touch R10.
    assert 0.0524343 - r10_box[2] < 0.002

    def ray(center, knee, radius):
        dx, dy = knee[0] - center[0], knee[1] - center[1]
        length = math.hypot(dx, dy)
        tip = (center[0] + radius * dx / length, center[1] + radius * dy / length)
        return (tip, knee), (dx, dy)

    r10_center = (0.0686409, 0.128224)
    r8_center = (0.0722816, 0.127224)
    r10_knee = (r10[0] + 0.0088233, r10[1] - 0.0027781)
    r8_knee = (r8[0] - 0.0075302, r8[1] - 0.0027781)
    r10_leader, (dx10, dy10) = ray(r10_center, r10_knee, 0.005)
    r8_leader, (dx8, dy8) = ray(r8_center, r8_knee, 0.004)
    assert dx10 < 0 and dy10 < 0  # NE radius must point down/left.
    assert dx8 > 0 and dy8 < 0  # NW radius must point down/right.
    # Positive controls: elevated shelves put rays on the wrong quadrants.
    assert 0.136 - 0.0027781 > r10_center[1]
    assert 0.142 - 0.0027781 > r8_center[1]
    # A-A looks south: r13's sheet-down arrow envelopes mirrored about the
    # cutting line (y 0.126724) to sheet-up.
    line_y = 0.126724
    foot, head = 2 * line_y - 0.127486, 2 * line_y - 0.108374
    aa_left = (left - 0.000762, foot, left + 0.006, head)
    aa_right = (right - 0.006, foot, right + 0.0032523, head)
    assert not _boxes_overlap(aa_left, r10_box)
    cc_left = (0.058049, 0.131949, 0.059573, 0.143949)
    cc_right = (0.083049, 0.131949, 0.084573, 0.143949)
    for leader in (r10_leader, r8_leader):
        for box in (aa_left, aa_right, cc_left, cc_right):
            assert not _segment_hits_box(leader, box)
    # The 8.0 row extends right only to x104.5257 in the saved audit.
    eight_row = (0.065461, 0.1032219, 0.1045257, 0.1067219)
    assert not _segment_hits_box(r8_leader, eight_row)
    old_leader = ((0.07602, 0.1258014), (0.1274698, 0.1062219))
    old_aa_right = (0.0915657, 0.114724, 0.0983277, 0.127486)
    assert _segment_hits_box(old_leader, old_aa_right)


@pytest.mark.parametrize("index", range(4))
def test_virtual_sharp_supports_use_source_lines_and_nearest_notch_segment(
    monkeypatch, index
):
    monkeypatch.setattr(drawing, "_early_bound", lambda item, _kind: item)
    corners = part.PLATE_CORNERS
    _label, x, z, _radius = corners[index]

    def edge(neighbour, near, far, *, line=True, height=spec.PLATE_THICKNESS):
        dx, dz = neighbour[1] - x, neighbour[2] - z
        length = math.hypot(dx, dz)
        points = [
            (
                (x + distance * dx / length) / 1000,
                height / 1000,
                (z + distance * dz / length) / 1000,
            )
            for distance in (near, far)
        ]
        return types.SimpleNamespace(
            GetCurve=lambda: types.SimpleNamespace(IsLine=lambda: line),
            GetStartVertex=lambda: types.SimpleNamespace(GetPoint=lambda: points[0]),
            GetEndVertex=lambda: types.SimpleNamespace(GetPoint=lambda: points[1]),
        )

    neighbours = (corners[index - 1], corners[(index + 1) % len(corners)])
    selected = tuple(edge(neighbour, 12, 18) for neighbour in neighbours)
    distractors = [
        edge(neighbours[0], 20, 30),  # same support, farther notch-split segment
        edge(neighbours[0], 1, 3, line=False),  # arc is not a support
        edge(neighbours[1], 1, 3, height=0),  # underside is not top-face support
    ]
    monkeypatch.setattr(
        drawing,
        "visible_view_entities",
        lambda *_args, **_kw: [*distractors, *selected],
    )
    adapter = types.SimpleNamespace(
        swApp=types.SimpleNamespace(IsSame=lambda a, b: int(a is b))
    )
    assert drawing._profile_corner_edges(adapter, object(), index) == selected
    adapter.swApp.IsSame = lambda _a, _b: -1
    with pytest.raises(RuntimeError, match="two different supports"):
        drawing._profile_corner_edges(adapter, object(), index)
    monkeypatch.setattr(
        drawing, "visible_view_entities", lambda *_args, **_kw: distractors[1:]
    )
    with pytest.raises(RuntimeError, match="missing actual straight"):
        drawing._profile_corner_edges(adapter, object(), index)


@pytest.mark.parametrize("creation_toggle", [False, True])
@pytest.mark.parametrize(
    "failure",
    [
        None,
        "activate",
        "select",
        "count",
        "misselected",
        "unknown",
        "missing",
        "null",
        "returned_identity",
        "multiple",
        "multiple_sharps",
        "extra_ordinary",
        "single_sharp",
        "cleanup_return_identity",
        "cleanup_select",
        "cleanup_count",
        "cleanup_identity",
        "cleanup_delete",
        "cleanup_keeper",
        "cleanup_old",
        "cleanup_noop",
        "cleanup_replaced",
        "cleanup_type",
        "cleanup_coordinate",
        "cleanup_owner",
        "cleanup_witness",
        "removed",
        "renumbered",
        "clear_lifecycle",
        "rebuild_lifecycle",
        "type",
        "owner",
        "coordinate",
        "witness",
        "witness_size",
        "single_witness",
    ],
)
def test_native_virtual_sharp_requires_type_owner_source_and_native_geometry(
    monkeypatch, capsys, failure, creation_toggle
):
    state = {"inserted": False, "selected": [], "factory_calls": 0, "phase": "before"}
    state.update(deleted=False, delete_calls=0)
    has_trigger = failure not in {"single_sharp", "null"}
    creation_reads = []
    import _drawing_detail_crop as native_crop

    math_inputs = []
    monkeypatch.setattr(native_crop, "_early_bound", lambda item, _kind: item)
    monkeypatch.setattr(native_crop, "double_array", lambda values: values)

    def creation_preference(name):
        assert name == "swDisplayVirtualSharps"
        return 8765  # fake SDK metadata, not an implementation ordinal

    def get_creation_toggle(key):
        assert key == 8765
        creation_reads.append(key)
        return creation_toggle

    monkeypatch.setattr(drawing._sw_type_info, "constant", creation_preference)
    index = 2  # the 37.0 station: source SW vertex, not a saved paper coordinate
    _label, x, z, _radius = part.PLATE_CORNERS[index]
    source = (x / 1000, spec.PLATE_THICKNESS / 1000, z / 1000)
    expected = (
        0.0718 + source[0] / 2,
        0.1267 - source[2] / 2,
    )  # Real projection is XY.
    inverse = object()
    forward = types.SimpleNamespace(Inverse=lambda: inverse)
    factory_coordinates = (expected[0] * 2 - 0.11, expected[1] * 3 + 0.025, 0.0)
    sketch = types.SimpleNamespace(
        ModelToSketchTransform=forward,
    )
    point = types.SimpleNamespace(
        GetID=lambda: (7, 19),
        Type=1 if failure == "type" else 4,
        X=factory_coordinates[0] + (0.001 if failure == "coordinate" else 0),
        Y=factory_coordinates[1],
        Z=factory_coordinates[2],
        GetSketch=lambda: (
            object()
            if failure == "owner" or (failure == "cleanup_owner" and state["deleted"])
            else sketch
        ),
    )
    existing = types.SimpleNamespace(
        Type=1,
        GetID=lambda: (
            (2, 4) if state["inserted"] and failure == "renumbered" else (2, 3)
        ),
    )
    extra = types.SimpleNamespace(
        GetID=lambda: (7, 20),
        Type=4 if failure == "multiple_sharps" else 1,
        X=point.X,
        Y=point.Y,
        Z=point.Z,
    )
    trigger = types.SimpleNamespace(GetID=lambda: (9, 10), Type=1)
    replacement = types.SimpleNamespace(
        GetID=point.GetID,
        Type=4,
        X=point.X,
        Y=point.Y,
        Z=point.Z,
    )

    def enumerated_points():
        if not state["inserted"]:
            return [existing]
        if state["deleted"]:
            kept = (
                []
                if failure == "cleanup_keeper"
                else [replacement if failure == "cleanup_replaced" else point]
            )
            old = [] if failure == "cleanup_old" else [existing]
            remaining_trigger = [trigger] if failure == "cleanup_noop" else []
            return old + kept + remaining_trigger
        retained = [] if failure == "removed" else [existing]
        lost = (failure == "clear_lifecycle" and state["phase"] != "immediate") or (
            failure == "rebuild_lifecycle" and state["phase"] == "rebuilt"
        )
        created = [] if failure in {"missing", "null"} or lost else [point]
        return (
            retained
            + created
            + ([trigger] if has_trigger else [])
            + (
                [extra]
                if failure in {"multiple", "multiple_sharps", "extra_ordinary"}
                else []
            )
        )

    sketch.GetSketchPoints2 = enumerated_points

    def witness_lines():
        if not state["inserted"] or failure == "witness":
            return []
        if state["deleted"] and failure == "cleanup_witness":
            return []
        if failure == "clear_lifecycle" and state["phase"] != "immediate":
            return []
        if failure == "rebuild_lifecycle" and state["phase"] == "rebuilt":
            return []
        lines = [(0.0, 0.0, 0.0, 0.01, 0.0, 0.0)]
        if failure != "single_witness":
            lines.append((0.0, 0.0, 0.0, 0.0, 0.01, 0.0))
        return lines

    def raw_witness():
        if state["phase"] == "immediate":
            assert state["selected"] == list(edges)
        lines = witness_lines()
        if not lines:
            return ()
        return (
            0.0,
            -1.0,
            -1.0,
            -1.0,
            0.0,
            0.0,
            float(len(lines)),
            *(coordinate for line in lines for coordinate in line),
        )

    def witness_count():
        size = len(raw_witness())
        if failure == "witness_size" and state["phase"] == "rebuilt":
            size += 1
        return len(witness_lines()), size

    view = types.SimpleNamespace(
        GetSketch=lambda: sketch,
        UpdateViewDisplayGeometry=lambda: None,
        GetWitnessEntitiesCount=witness_count,
        GetWitnessGeomInfo=raw_witness,
    )
    manager = types.SimpleNamespace(
        CreateSelectData=lambda: types.SimpleNamespace(View=None),
        GetSelectedObjectCount2=lambda _mark: (
            1
            if failure == "count"
            else (
                2
                if failure == "cleanup_count" and state["selected"] == [trigger]
                else len(state["selected"])
            )
        ),
        GetSelectedObject6=lambda index, _mark: (
            object()
            if failure == "misselected"
            or (failure == "cleanup_identity" and state["selected"] == [trigger])
            else state["selected"][index - 1]
        ),
    )

    def select(edge, append, data):
        assert data.View is view
        assert append is bool(state["selected"])
        if failure == "select":
            return False
        state["selected"].append(edge)
        return True

    def select_trigger(append, data):
        assert append is False and data.View is view and not state["selected"]
        if failure == "cleanup_select":
            return False
        state["selected"].append(trigger)
        return True

    trigger.Select4 = select_trigger

    def delete_trigger(options):
        assert options == 0 and state["selected"] == [trigger]
        state["delete_calls"] += 1
        if failure == "cleanup_delete":
            return False
        state["deleted"] = True
        if failure == "cleanup_type":
            point.Type = (
                1  # Simulate a native side effect; production never assigns Type.
            )
        if failure == "cleanup_coordinate":
            point.X += 0.001
        return True

    def create_point(*coordinates):
        # Hypothetical native outputs exercise the proof gate; the SDK does not
        # promise that selected-edge CreatePoint produces a Type4 point.
        assert coordinates == factory_coordinates
        assert state["selected"] == list(edges)
        state["factory_calls"] += 1
        state["inserted"] = True
        state["phase"] = "immediate"
        if failure == "null":
            return None
        if failure == "returned_identity":
            return types.SimpleNamespace(GetID=point.GetID, Type=point.Type)
        if failure == "cleanup_return_identity":
            return types.SimpleNamespace(GetID=trigger.GetID, Type=1)
        if has_trigger:
            return trigger
        return point

    def clear(_all):
        state["selected"].clear()
        if state["inserted"]:
            state["phase"] = "cleared"

    def rebuild(*_args, **_kw):
        assert state["phase"] == "cleared"
        state["phase"] = "rebuilt"

    draw = types.SimpleNamespace(
        # ActivateView intentionally exists only on the IDrawingDoc fake below.
        SelectionManager=manager,
        ClearSelection2=clear,
        SketchManager=types.SimpleNamespace(CreatePoint=create_point),
        Extension=types.SimpleNamespace(DeleteSelection2=delete_trigger),
    )
    adapter = types.SimpleNamespace(
        currentModel=draw,
        swApp=types.SimpleNamespace(
            IsSame=lambda a, b: -1 if failure == "unknown" else int(a is b),
            GetMathUtility=lambda: types.SimpleNamespace(CreatePoint=math_point),
            GetUserPreferenceToggle=get_creation_toggle,
        ),
    )
    ddoc = types.SimpleNamespace(ActivateView=lambda _name: failure != "activate")

    def bind(item, kind):
        return ddoc if item is draw and kind == "IDrawingDoc" else item

    monkeypatch.setattr(drawing, "_early_bound", bind)
    monkeypatch.setattr(drawing, "view_name", lambda *_args: "profile")
    edges = (types.SimpleNamespace(), types.SimpleNamespace())
    for edge in edges:
        edge.Select4 = lambda append, data, edge=edge: select(edge, append, data)
    monkeypatch.setattr(drawing, "_profile_corner_edges", lambda *_args: edges)
    monkeypatch.setattr(drawing, "rebuild_drawing", rebuild)

    def math_point(values):
        xyz = tuple(values)
        assert len(xyz) == 3  # IMathUtility.CreatePoint requires XYZ, never bare XY.
        math_inputs.append(xyz)

        def multiply(actual_transform):
            if actual_transform is forward:
                assert xyz == (*expected, 0.0)
                transformed = factory_coordinates
            else:
                assert actual_transform is inverse
                assert xyz == (point.X, point.Y, point.Z)
                transformed = ((xyz[0] + 0.11) / 2, (xyz[1] - 0.025) / 3, 0.0)
            return types.SimpleNamespace(ArrayData=transformed)

        return types.SimpleNamespace(MultiplyTransform=multiply)

    def project(_adapter, actual_view, xyz, **_kw):
        assert actual_view is view and xyz == source
        return expected

    monkeypatch.setattr(drawing, "model_point_in_view", project)
    early_failures = {"activate", "select", "count", "misselected", "unknown"}
    if failure:
        with pytest.raises(RuntimeError) as caught:
            drawing._insert_profile_virtual_sharp(adapter, view, index)
        message = str(caught.value)
        expected_error = {
            "activate": "cannot activate profile",
            "select": "cannot select native virtual sharp support",
            "count": "exactly two selected edges",
            "misselected": "failed native identity readback",
            "unknown": "failed native identity readback",
            "null": "CreatePoint returned null",
            "returned_identity": "CreatePoint return differs from the new Type1 trigger",
            "cleanup_return_identity": "not the native Type1 CreatePoint return",
            "cleanup_select": "cannot select returned trigger point",
            "cleanup_count": "trigger selection identity/count failed",
            "cleanup_identity": "trigger selection identity/count failed",
            "cleanup_delete": "cannot delete returned trigger point",
            "cleanup_keeper": "cleanup changed unexpected profile point IDs",
            "cleanup_old": "cleanup changed unexpected profile point IDs",
            "cleanup_noop": "cleanup changed unexpected profile point IDs",
            "cleanup_replaced": "cleanup replaced the native virtual sharp",
            "cleanup_type": "not naturally a native virtual sharp",
            "cleanup_coordinate": "misses source corner",
            "coordinate": "misses source corner",
            "cleanup_owner": "not owned by the profile sketch",
            "owner": "not owned by the profile sketch",
            "cleanup_witness": "no genuine witness lines",
            "witness": "no genuine witness lines",
            "single_witness": "no genuine witness lines",
            "witness_size": "invalid size/values",
        }.get(failure, "expected exactly one new native virtual sharp point")
        assert expected_error in message
        if failure not in early_failures:
            assert (
                "before={'point_count': 1, 'point_ids_types': [((2, 3), 1)]" in message
            )
            assert "immediately_after_CreatePoint=" in message
            assert "after_rebuild=" in message
            assert "'raw_witness':" in message and "'virtual_sharp_xyz':" in message
            assert f"'display_virtual_sharps': {creation_toggle}" in message
            if failure == "null":
                assert "returned=None" in message
            else:
                returned_id = (
                    (9, 10)
                    if has_trigger and failure != "returned_identity"
                    else (7, 19)
                )
                assert f"returned={{'id': {returned_id}," in message
        if state["deleted"]:
            assert "after_trigger_cleanup=" in message
        if failure == "single_sharp":
            assert state["delete_calls"] == 0
    else:
        drawing._insert_profile_virtual_sharp(adapter, view, index)
        output = capsys.readouterr().out
        assert "immediately_after_CreatePoint" not in output
        assert "raw_witness" not in output
        assert state["delete_calls"] == 1
        assert enumerated_points() == [existing, point]
        assert math_inputs == [(*expected, 0.0), (point.X, point.Y, point.Z)]
    assert state["delete_calls"] == (
        1 if state["deleted"] or failure == "cleanup_delete" else 0
    )
    assert not state["selected"]
    assert state["factory_calls"] == (
        0 if failure in {"activate", "select", "count", "misselected", "unknown"} else 1
    )
    assert len(creation_reads) == (
        0
        if failure == "activate"
        else 1
        if failure in {"select", "count", "misselected", "unknown"}
        else 4
        if state["deleted"]
        else 3
    )


@pytest.mark.parametrize("groups", [1, 2, 4])
def test_virtual_sharp_witness_parser_reads_observed_native_line_only_groups(groups):
    # Exact r23 native payload: header5 + tag0/count2 + two six-value lines.
    record = (
        4294967295,
        -1,
        -1,
        -1,
        31,
        0,
        2,
        -0.013718149724612275,
        -0.115551920153,
        0,
        -0.023377974695370556,
        -0.115551920153,
        0,
        -0.022677567850886055,
        -0.10689727905903555,
        0,
        -0.022343378943547956,
        -0.11655132154080962,
        0,
    )
    raw = record * groups
    view = types.SimpleNamespace(
        GetWitnessEntitiesCount=lambda: (2 * groups, len(raw)),
        GetWitnessGeomInfo=lambda: raw,
    )
    assert drawing._virtual_sharp_witness_groups(view) == [
        [record[7:13], record[13:19]] for _ in range(groups)
    ]


@pytest.mark.parametrize(
    "defect",
    [
        "size",
        "fractional_size",
        "negative_size",
        "infinite_size",
        "entity_count",
        "fractional_count",
        "negative_count",
        "infinite_count",
        "line_count",
        "negative_lines",
        "infinite_lines",
        "nan_coordinates",
        "arc",
        "arc_trailer",
        "truncated_header",
        "truncated_line",
    ],
)
def test_virtual_sharp_witness_parser_rejects_invalid_native_line_only_records(defect):
    raw = [
        0.0,
        -1.0,
        -1.0,
        -1.0,
        0.0,
        0.0,
        2.0,
        0.0,
        0.0,
        0.0,
        0.01,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.01,
        0.0,
    ]
    count = 2
    if defect == "line_count":
        raw[6] = 1.5
    elif defect == "negative_lines":
        raw[6] = -1
    elif defect == "infinite_lines":
        raw[6] = math.inf
    elif defect == "nan_coordinates":
        raw[7] = math.nan
    elif defect == "arc":
        raw[5] = 1
    elif defect == "arc_trailer":
        raw += [1.0, 0.0]
    elif defect == "truncated_header":
        raw = raw[:6]
    elif defect == "truncated_line":
        raw = raw[:-1]
    elif defect == "entity_count":
        count = 1  # SDK counts line entities, not the single group.
    elif defect == "fractional_count":
        count = 1.5
    elif defect == "negative_count":
        count = -1
    elif defect == "infinite_count":
        count = math.inf
    size = {
        "size": len(raw) + 1,
        "fractional_size": len(raw) + 0.5,
        "negative_size": -1,
        "infinite_size": math.inf,
    }.get(defect, len(raw))
    view = types.SimpleNamespace(
        GetWitnessEntitiesCount=lambda: (count, size),
        GetWitnessGeomInfo=lambda: raw,
    )
    with pytest.raises(RuntimeError):
        drawing._virtual_sharp_witness_groups(view)


@pytest.mark.parametrize("failure", [None, "sdk", "set", "read"])
def test_all_four_virtual_width_endpoints_require_native_document_witness_style(
    monkeypatch, failure
):
    ordinal = 9876  # fake SDK-provided id, never an implementation ordinal
    calls = []
    monkeypatch.setattr(drawing, "_early_bound", lambda item, _kind: item)

    def constant(name):
        assert name == "swDetailingVirtualSharpStyle"
        if failure == "sdk":
            raise RuntimeError("SolidWorks named constant unavailable")
        return ordinal

    monkeypatch.setattr(drawing._sw_type_info, "constant", constant)
    extension = types.SimpleNamespace(
        SetUserPreferenceInteger=lambda key, scope, style: (
            calls.append((key, scope, style)) or failure != "set"
        ),
        GetUserPreferenceInteger=lambda key, scope: 0 if failure == "read" else 3,
    )
    adapter = types.SimpleNamespace(
        currentModel=types.SimpleNamespace(Extension=extension)
    )
    view = object()
    marked = []
    monkeypatch.setattr(
        drawing,
        "_insert_profile_virtual_sharp",
        lambda _adapter, actual_view, index: marked.append((actual_view, index)),
    )
    if failure:
        with pytest.raises(RuntimeError):
            drawing._add_profile_virtual_sharps(adapter, view)
        assert not marked
    else:
        drawing._add_profile_virtual_sharps(adapter, view)
        assert calls == [(ordinal, 0, 3)]
        assert marked == [(view, index) for index in range(4)]


def test_virtual_sharp_preference_reads_sdk_metadata_with_real_adapter_constant_shape(
    monkeypatch,
):
    """r20: sldworks wrapper loading does not populate swconst globals.

    Exercise the real SDK resolver's typelib enumeration, not a prefilled
    win32com constant or a fabricated adapter preference entry.
    """
    import _preferences

    name = "swDetailingVirtualSharpStyle"
    toggle_name = "swDisplayVirtualSharps"
    sdk_ordinal = 9876  # fake TYPELIB metadata value, not a production fallback
    toggle_ordinal = 8765
    metadata = [(name, sdk_ordinal), (toggle_name, toggle_ordinal)]
    path = Path("installed-sdk") / "swconst.tlb"
    loads = []
    writes = []
    marks = []
    info = types.SimpleNamespace(
        GetTypeAttr=lambda: types.SimpleNamespace(cVars=len(metadata)),
        GetVarDesc=lambda index: (index, metadata[index][1]),
        GetNames=lambda memid: (metadata[memid][0],),
    )
    typelib = types.SimpleNamespace(
        GetTypeInfoCount=lambda: 1,
        GetTypeInfoType=lambda _index: 0,
        GetTypeInfo=lambda _index: info,
    )
    pythoncom = types.SimpleNamespace(
        TKIND_ENUM=0,
        LoadTypeLib=lambda actual_path: loads.append(actual_path) or typelib,
    )
    client = types.SimpleNamespace(constants=types.SimpleNamespace())
    monkeypatch.setitem(sys.modules, "pythoncom", pythoncom)
    monkeypatch.setitem(sys.modules, "win32com", types.SimpleNamespace(client=client))
    monkeypatch.setitem(sys.modules, "win32com.client", client)
    sdk = drawing._sw_type_info
    monkeypatch.setattr(sdk, "PYWIN32_AVAILABLE", True)
    monkeypatch.setattr(sdk, "_constants", None)

    def find_library(filename):
        assert filename == "swconst.tlb"
        return path

    monkeypatch.setattr(sdk, "_find_aux_tlb", find_library)
    extension = types.SimpleNamespace(
        SetUserPreferenceInteger=lambda key, scope, value: (
            writes.append((key, scope, value)) or True
        ),
        GetUserPreferenceInteger=lambda _key, _scope: 3,
    )

    adapter = types.SimpleNamespace(
        # Same legacy-table shape as PyWin32Adapter: no general SDK enum map.
        constants={"swDocDRAWING": 3, "swSketchAcceptNumericInput": 372},
        currentModel=types.SimpleNamespace(Extension=extension),
    )
    assert _preferences._preference_id(adapter, name) is None  # r20 positive control
    assert _preferences._preference_id(adapter, toggle_name) is None
    monkeypatch.setattr(drawing, "_early_bound", lambda item, _kind: item)
    monkeypatch.setattr(
        drawing,
        "_insert_profile_virtual_sharp",
        lambda _adapter, _view, index: marks.append(index),
    )
    drawing._add_profile_virtual_sharps(adapter, object())
    assert sdk.constant(toggle_name) == toggle_ordinal
    assert loads == [str(path)]
    assert writes == [(sdk_ordinal, 0, 3)]
    assert marks == list(range(4))
