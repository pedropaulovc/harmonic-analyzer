"""Offline manufacturing contracts for the cone-swing-platform package."""

from __future__ import annotations

import dataclasses
import inspect
import math
from pathlib import Path

import _config
import _drawing_leaders
import build_cone_lock_knob
import build_cone_pivot_screw
import build_cone_swing_platform as part
import cone_pivot_post_spec
import cone_swing_platform_spec as spec
import draw_cone_swing_platform as drawing
import pytest
from _gtol_spec import PlanarFace
from _hole_spec import blind_cut_dia_mm
from _surface_finish import MACHINED_UM, SEAT_UM




def test_every_marked_model_dimension_has_one_view_and_native_precision() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    view_sets = tuple(set(keep) for keep in drawing.VIEW_KEEPS.values())
    assert drawing.VIEW_KEEPS["lock notch cap detail"] is drawing.CAP_DETAIL_KEEP
    kept = set().union(*view_sets)
    assert kept == marked
    assert sum(len(names) for names in view_sets) == len(kept)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert spec.DRAWING_PRECISION_BY_NAME["PlateLenDim"] == 1
    assert set(spec.DRAWING_PRECISION_BY_NAME.values()) == {0, 1, 2}
    # Whole degrees are for the one angle only (MHA-091 round 6).
    assert [n for n, p in spec.DRAWING_PRECISION_BY_NAME.items() if p == 0] == ["NotchMouthAngle"]


def test_pivot_preserves_native_close_clearance_hole() -> None:
    assert spec.PIVOT_HOLE_SPEC.kind == "clearance"
    assert spec.PIVOT_HOLE_SPEC.size == "1/4"
    assert spec.PIVOT_HOLE_SPEC.fit == "close"
    assert spec.PIVOT_HOLE_SPEC.end == "through_all"
    assert spec.PIVOT_HOLE_DIA == blind_cut_dia_mm(spec.PIVOT_HOLE_SPEC)
    assert spec.PIVOT_HOLE_DIA == pytest.approx(6.756)
    assert spec.PIVOT_HOLE_DIA > build_cone_pivot_screw.SHOULDER_DIA


def test_post_mount_pattern_is_derived_from_its_mating_post() -> None:
    assert spec.POST_ATTACHMENT_SPACING == cone_pivot_post_spec.ATTACHMENT_SPACING
    assert spec.POST_BLOCK_DIA == cone_pivot_post_spec.BLOCK_DIA
    assert part.POST_MOUNT_HALF_PITCH == spec.POST_ATTACHMENT_SPACING / 2.0
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
    registry = _config.parts("cone-swing-platform")
    assert registry["tolerance_class"] == "machined_block"
    assert "mil-dtl-13924 class 1" in str(registry["finish"]).lower()
    assert "oil seal" in str(registry["finish"]).lower()
    assert int(registry["quantity"]) == 1
    assert spec.DRAWING_PRECISION["Plate"]["PlateThk"] == 2
    assert spec.DRAWING_PRECISION["PivotBearingRelief"]["PivotBearingReliefDepth"] == 2
    # #917 S1: the taps transfer from MHA-016 at assembly, so no station
    # prints (the model keeps them at nominal).
    assert "PostMountHoles" not in spec.DRAWING_PRECISION
    assert "PostMountHoles" not in spec.DRAWING_DIMENSIONS






def test_geometry_cascade_and_interference_guards_stay_explicit() -> None:
    assert part.PLATE_LEN == pytest.approx(223.3541869456341)
    assert part.POST_SOUTH_MARGIN == pytest.approx(3.175)
    assert part.PLATE_SOUTH_Z == pytest.approx(-216.3541869456341)
    assert part.POST_MAIN_DIA == spec.POST_BLOCK_DIA
    assert part.POST_FOOT_CONTAINMENT >= 0.25
    assert spec.PIVOT_BEARING_RELIEF_DIAMETER == pytest.approx(10.50)
    assert part.PLATE_T - spec.PIVOT_BEARING_THICKNESS == pytest.approx(
        spec.PIVOT_BEARING_RELIEF_DEPTH
    )
    assert spec.CRANK_GEAR_PLATFORM_CLEARANCE > 0.5


def test_pivot_relief_runs_out_through_the_north_edge() -> None:
    """Rule-12 W18 (d): no web is left between the relief and the north edge.

    As a closed Ø10.50 spotface 7.0 from the edge it left 1.75 nominal, under
    the 2.0 target.  Open to the edge, the web does not exist; the relief's
    sketch closes PIVOT_RELIEF_RUNOUT past it, and the width still gives the
    stock 3/8 head its radial clearance.
    """
    half = spec.PIVOT_BEARING_RELIEF_DIAMETER / 2.0
    closed_web = part.NORTH_OVERHANG - half
    assert closed_web < 2.0  # positive control: the closed spotface failed
    assert part.PIVOT_RELIEF_RUNOUT > 0.0
    head_dia = build_cone_pivot_screw.HEAD_DIA
    assert (spec.PIVOT_BEARING_RELIEF_DIAMETER - head_dia) / 2.0 >= (
        spec.PIVOT_HEAD_RADIAL_CLEARANCE - 1e-9
    )
    assert spec.PIVOT_RELIEF_FIT_REQUIREMENT.startswith(
        "TOP RELIEF: MATCH DEPTH TO FINISHED PLATE"
    )
    # Only the NW fillet reaches over the 10.50 strip, and only by a sliver.
    overlaps = {
        label: part._north_fillet_relief_overlap(label, r)
        for label, _x, _z, r in part._CORNERS
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


def test_disengaged_collar_margin_survives_general_bands() -> None:
    """Linear worst case at .X plate outline and .XX base holes keeps 2.0 mm (U27)."""
    general, base_axis = 0.8, 0.51
    east_slope = (part.EAST_HALF_S - part.HALF_WIDTH_N) / part.PLATE_LEN
    stop_x = -(part.HALF_WIDTH_N + east_slope * (part.NORTH_OVERHANG - part.STOP_LOCAL_Z))
    normal = (-1.0, east_slope)
    norm = math.hypot(*normal)
    lever = abs(part.STOP_LOCAL_Z * normal[0] - stop_x * normal[1]) / norm
    stop_gain = part.SLOT_R / lever
    east_edge = stop_gain * general
    west_edge = general
    stop_hole = stop_gain * base_axis * (abs(normal[0]) + abs(normal[1])) / norm
    stud_hole = base_axis * (abs(part._SLOT_TX) + abs(part._SLOT_TZ))
    diameters = 0.35
    worst = part.DISENGAGE_COLLAR_MARGIN - (
        east_edge + west_edge + stop_hole + stud_hole + diameters
    )
    assert worst >= 2.0
    assert set(spec.DRAWING_PRECISION["PlateProfile"].values()) == {1}


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
    x 0.2697, both measured on the 81788ce9 render; below it the relocated
    section C-C label.  Its keep y must stay above the top witness (plate top
    0.1265) so SolidWorks keeps the text outside, not centred on the line.
    """
    box = _plate_thickness_text_box()
    witness_205 = (0.2690, 0.1374, 0.3060, 0.1384)
    arrow_7 = (0.2692, 0.1280, 0.2702, 0.1379)
    lx, ly = drawing.SLOT_SECTION_LABEL_LOWER_LEFT
    cc_label = (lx, ly, lx + 0.0465, ly + 0.0162)
    for other in (witness_205, arrow_7, cc_label):
        assert not _boxes_overlap(box, other), other
    assert drawing.SECTION_KEEP["PlateThk"][1] > 0.1265 + 0.001
    assert box[2] < drawing.SECTION_CENTER[0] - 0.02  # left of the cut edge
    # Positive control: 81788ce9's one-line callout at its old keep crossed
    # the 205.81 witness (and touched the 7.0 arrow).
    old = _plate_thickness_text_box((0.320, 0.135), "1/4 PLATE AS SUPPLIED")
    assert abs((old[2] - old[0]) - 0.0496) < 0.001
    assert _boxes_overlap(old, witness_205)


# Section C-C's 2.80 depth dimension parks its text right of the strip; its
# upper arrow line runs up from the plate top to ~9.5 mm above the strip's
# view centre (aa9766da render: x 0.2993, top 0.1304 at centre 0.1109).
_CC_DEPTH_LINE_DX, _CC_DEPTH_LINE_TOP_DY = 0.0203, 0.0195


def _cc_depth_line(center: tuple[float, float] | None = None) -> tuple[float, ...]:
    cx, cy = center or drawing.SLOT_SECTION_CENTER
    x = cx + _CC_DEPTH_LINE_DX
    return (x - 0.0003, cy, x + 0.0003, cy + _CC_DEPTH_LINE_TOP_DY)


def test_plate_thickness_text_clears_the_cc_depth_line_and_its_own_arrow() -> None:
    """aa9766da: the 2.80 arrow line ran up between "AS" and "SUPPLIED".

    The stock text keeps 2 mm from that line, and the line beside the 6.35
    dimension's top arrowhead is the short one, set back from the arrow by
    at least 1.5 mm (there "AS SUPPLIED" ran its D into the arrowhead).
    """
    box = _plate_thickness_text_box()
    line = _cc_depth_line()
    assert box[0] - line[2] >= 0.002
    assert line[3] > box[1]  # the line does reach the text's height
    callout = spec.PLATE_STOCK_CALLOUT.split("\n")
    widest = max(len(text) for text in ("(6.35)", *callout))
    setback = (widest - len(callout[-1])) * _CHAR_W / 2.0
    assert setback >= 0.0015
    # Positive controls: aa9766da's shift crossed the line, and its callout
    # put the widest line beside the arrow.
    old_keep = (drawing.SECTION_KEEP["PlateThk"][0] - (drawing.SECTION_SHIFT[0] - 0.020),
                drawing.SECTION_KEEP["PlateThk"][1])
    old_box = _plate_thickness_text_box(old_keep, "1/4 PLATE\nAS SUPPLIED")
    old_line = _cc_depth_line((0.279, 0.1109))
    assert _boxes_overlap(old_box, old_line)
    assert len("AS SUPPLIED") == max(len(t) for t in ("(6.35)", "1/4 PLATE", "AS SUPPLIED"))


def _notch_caption_box() -> tuple[float, float, float, float]:
    """The lock-notch caption, 59.7 x 4.8 mm from its upper-left anchor."""
    x, y = drawing.NOTCH_CAPTION_UPPER_LEFT
    return (x, y - 0.0048, x + 0.0597, y)


def test_lock_notch_caption_sits_under_its_own_view() -> None:
    """aa9766da printed it right under "SECTION C-C / SCALE 1:1" (one block).

    Lifted off the plan caption row, it is centred under the notch plan,
    under the 7.0 arrow tip (aa9766da: y 0.1276), and 5 mm or more above the
    C-C strip's ink (aa9766da: top 0.1202 at view centre 0.1109) and well
    clear of the C-C label and depth line.
    """
    box = _notch_caption_box()
    assert (box[0] + box[2]) / 2.0 == pytest.approx(drawing.NOTCH_CENTER[0], abs=1e-4)
    assert box[3] <= 0.1276 - 0.0015
    strip_top = drawing.SLOT_SECTION_CENTER[1] + (0.1202 - 0.1109)
    assert box[1] - strip_top >= 0.005
    lx, ly = drawing.SLOT_SECTION_LABEL_LOWER_LEFT
    label = (lx, ly, lx + 0.0465, ly + 0.0162)
    assert box[1] - label[3] >= 0.015
    assert not _boxes_overlap(box, _cc_depth_line())
    assert not _boxes_overlap(box, _plate_thickness_text_box())
    # Positive control: aa9766da's caption on the plan row sat 1.2 mm under
    # its C-C label, and would now overlap the lowered label outright.
    old = (0.2448, 0.0805, 0.3045, 0.0853)
    assert 0.0865 - old[3] < 0.002
    assert _boxes_overlap(old, label)


def test_the_notch_is_a_banded_width_and_a_full_r() -> None:
    """MHA-091 Fable review (63fb3bd2d) B2: at the title block's .XX the
    narrowest notch (7.49) left the 1/4-20 stud 0.552 a side against 0.721 of
    cap-centre error -- the stack failed as printed.  The notch is cut by one
    end mill, so its width carries the tip slots' +0.10/0; the cap's Ø8.00
    restated that size and is no longer marked (detail D prints "R")."""
    assert spec.DRAWING_DIMENSIONS["LockNotchProfile"] == {"NotchMouthAngle", "NotchW"}
    assert spec.DRAWING_DIMENSIONS["LockNotchCapEProfile"] == {"CapECx", "CapECz"}
    assert spec.DRAWING_PRECISION_BY_NAME["NotchW"] == 2
    assert spec.NOTCH_W_BAND == (0.10, 0.0)
    assert spec.NOTCH_W_MIN == pytest.approx(spec.NOTCH_W)
    assert part.SLOT_W == spec.NOTCH_W
    assert spec.LOCK_STUD_MAJOR == pytest.approx(build_cone_lock_knob.STUD_DIA)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '("LockNotchProfile", "NotchW", NOTCH_W_BAND),' in source


def test_the_run_is_its_whole_degree_angle_to_the_west_edge() -> None:
    """Main, MHA-091 round 6: the run prints as its angle to the plate's
    WEST edge at the mouth -- both legs real edges, the vertex the south
    mouth corner -- not off a hidden east-west ray.  The stud's chord makes
    87.38 with that edge (87.53 until #917 S1 widened the north-west by
    0.6); the spec rounds it to 87 and the notch is cut at 87.00, the 0.38
    joining the stud stack."""
    assert spec.NOTCH_MOUTH_ANGLE_DEG == 87.0
    assert spec.DRAWING_PRECISION_BY_NAME["NotchMouthAngle"] == 0
    assert abs(part.NOTCH_CHORD_MOUTH_DEG) == pytest.approx(87.38, abs=0.005)
    assert round(abs(part.NOTCH_CHORD_MOUTH_DEG)) == spec.NOTCH_MOUTH_ANGLE_DEG
    assert part.NOTCH_MOUTH_ANGLE_OFFSET_DEG == pytest.approx(-0.38, abs=0.005)
    ux, uz = part.NOTCH_CUT_U
    inward_vs_south = math.degrees(math.acos(-(ux * part._EDGE_SX + uz * part._EDGE_SZ)))
    assert inward_vs_south == pytest.approx(87.0, abs=1e-9)
    # The cut turned toward the edge by the offset, off the stud's chord.
    assert part.NOTCH_RUN_DEG - part.NOTCH_CUT_DEG == pytest.approx(
        part.NOTCH_MOUTH_ANGLE_OFFSET_DEG, abs=1e-9
    )
    pts = part.NOTCH_CUT_POINTS
    for key in ("mouth_s", "mouth_n"):
        assert pts[key][0] == pytest.approx(part._west_edge_x(pts[key][1]), abs=1e-9)
    assert math.dist(pts["closed_s"], pts["closed_n"]) == pytest.approx(part.SLOT_W)
    # The closed end's full R is centred on the cap, NOTCH_ENGAGE_OVERTRAVEL
    # deeper than the stud's engaged seat (#917 S1).
    middle = tuple((a + b) / 2.0 for a, b in zip(pts["closed_s"], pts["closed_n"]))
    assert middle == pytest.approx(part.NOTCH_CAP_E_XZ)
    for first, second in (
        ("closed_s", "mouth_s"),
        ("mouth_s", "out_s"),
        ("out_n", "mouth_n"),
        ("mouth_n", "closed_n"),
    ):
        dx, dz = pts[second][0] - pts[first][0], pts[second][1] - pts[first][1]
        assert abs(dx * uz - dz * ux) < 1e-9, (first, second)
    # South is the south rail and its material wedge the acute one.
    assert pts["closed_s"][1] < pts["closed_n"][1]
    assert part.NOTCH_CUT_TRAVEL == pytest.approx(
        part.NOTCH_EXIT_TRAVEL + spec.NOTCH_ENGAGE_OVERTRAVEL, abs=0.01
    )


def test_the_notch_runs_on_past_the_stud_seat_at_its_closed_end() -> None:
    """#917 S1 (plan section 1, A2): lengthen the lock notch 0.30 past the
    engaged stud seat, so the fit-up can swing the platform deeper than the
    seat by the stud's clearance plus the overtravel.  The seat itself -- the
    base stud's station -- does not move, and the lock-knob collar still bears
    on the plate round the stud."""
    assert spec.NOTCH_ENGAGE_OVERTRAVEL == 0.30
    assert (part.SLOT_E_X, part.SLOT_E_Z) == pytest.approx((33.0, -205.8075686))
    ux, uz = part.NOTCH_CUT_U
    cx, cz = part.NOTCH_CAP_E_XZ
    assert (part.SLOT_E_X - cx, part.SLOT_E_Z - cz) == pytest.approx(
        (spec.NOTCH_ENGAGE_OVERTRAVEL * ux, spec.NOTCH_ENGAGE_OVERTRAVEL * uz)
    )
    # The stud's deep-side room: its clearance in the full R plus the run-on.
    room = (spec.NOTCH_W - spec.LOCK_STUD_MAJOR) / 2.0 + spec.NOTCH_ENGAGE_OVERTRAVEL
    assert room == pytest.approx(1.125)
    # The collar (Ø12.70) still overlaps the plate beyond the deeper closed
    # end and beside both rails.
    collar_r = build_cone_lock_knob.COLLAR_DIA / 2.0
    assert collar_r - (spec.NOTCH_ENGAGE_OVERTRAVEL + part.SLOT_W / 2.0) >= 2.0
    assert collar_r - part.SLOT_W / 2.0 >= 2.0
    # The web from the deeper closed end to the plate's south edge, with the
    # cap centre at its .XX band and the outline at its .X bands.
    south = part.NORTH_OVERHANG - part.PLATE_LEN
    web = cz - part.SLOT_W / 2.0 - south - spec.TITLE_BLOCK_BAND_BY_PLACES[2] - 2.0 * 0.8
    assert web >= 2.0


def test_the_notch_sketch_drives_its_width_and_mouth_angle() -> None:
    """The width is SlotW by equation, the angle DRIVES the rails (added
    while their direction is free, read back driving), and the west-edge
    reference sits on the plate's own globals."""
    source = Path(part.__file__).read_text(encoding="utf-8")
    body = source[
        source.index("    # Lock notch: open-ended channel") : source.index(
            "    # Closed-end cap, NOTCH_ENGAGE_OVERTRAVEL"
        )
    ]
    width = body.index("""slot.record("NotchW", '"SlotW"')""")
    angle = body.index("await _add_notch_mouth_angle(adapter, edge_mouth, rail_in_s, slot)")
    overshoot = body.index('"lock notch mouth overshoot"')
    assert width < angle < overshoot
    for drive in ("'\"WestHalfN\"'", "'\"NorthOverhang\"'", "'\"WestHalfS\"'"):
        assert drive in body, drive
    assert """'"PlateLen" - "NorthOverhang"'""" in body
    assert "NotchRunAngle" not in source
    helper = inspect.getsource(part._add_notch_mouth_angle)
    assert "3,  # swDimensionType_e.swAngularDimension" in helper
    assert "driven_state != 2" in helper
    assert "DrivenState = 1" not in helper
    # The text point that picks the sector lies in the material wedge.
    tx, ty = part.notch_mouth_angle_text_point()
    vx, vz = part.NOTCH_CUT_POINTS["mouth_s"]
    ux, uz = part.NOTCH_CUT_U
    rail = (vx - ux, vz - uz)
    edge = (vx + part._EDGE_SX, vz + part._EDGE_SZ)
    assert drawing.in_acute_sector((tx, -ty), (vx, vz), rail, edge)
    # Positive control: mirrored across the edge it is in the 92 sector.
    assert not drawing.in_acute_sector(
        (2.0 * vx - tx, 2.0 * vz + ty), (vx, vz), rail, edge
    )


def _stack_args() -> tuple[float, float, float, float, float]:
    return (
        part.NOTCH_CUT_DEG,
        part.NOTCH_EXIT_TRAVEL,
        part.SLOT_R,
        part.NOTCH_MOUTH_ANGLE_OFFSET_DEG,
        part.WEST_EDGE_ANGLE_ERROR_DEG,
    )


def _slacks(terms: dict[str, float]) -> tuple[float, float]:
    seat = terms["room at the seat"] - terms["cap centre error at the seat"]
    channel = terms["room in the channel"] - (
        terms["cap centre error across the run"] + terms["run angle error at the mouth"]
    )
    return seat, channel


def test_the_stud_seats_and_runs_out_at_the_printed_bands() -> None:
    """The build asserts it at import; the slack is pinned here."""
    terms = spec.assert_notch_stud_stack(*_stack_args())
    assert terms == part.NOTCH_STUD_STACK
    seat, channel = _slacks(terms)
    assert round(seat, 3) == 0.104
    assert round(channel, 3) == 0.132
    # The angle term: the 0.38 rounding, the block's 1 deg and the edge's own
    # 0.41 (two .X ends over its 224.8 mm) over the 2.78 exit travel.
    assert part.WEST_EDGE_ANGLE_ERROR_DEG == pytest.approx(0.408, abs=0.001)
    assert terms["run angle error at the mouth"] == pytest.approx(
        part.NOTCH_EXIT_TRAVEL * math.tan(math.radians(0.3784 + 1.0 + 0.4078)), abs=1e-4
    )


@pytest.mark.parametrize(
    ("change", "failing"),
    [
        # 63fb3bd2d as printed: the width at the plain .XX.
        ({"NOTCH_W_MIN": 8.0 - 0.51}, "seat"),
        # The cap centre at .X, as the Fable review proposed: 1.13 vs 0.825.
        ({"CapECx": 1, "CapECz": 1}, "seat"),
    ],
)
def test_the_stud_stack_fails_at_the_rejected_grades(monkeypatch, change, failing) -> None:
    for name, value in change.items():
        if name == "NOTCH_W_MIN":
            monkeypatch.setattr(spec, name, value)
        else:
            monkeypatch.setitem(spec.DRAWING_PRECISION_BY_NAME, name, value)
    seat, _channel = _slacks(spec.notch_stud_stack(*_stack_args()))
    assert seat < 0.0, failing
    with pytest.raises(AssertionError, match="lock stud does not fit the notch"):
        spec.assert_notch_stud_stack(*_stack_args())


def test_the_stud_stack_fails_when_the_cut_leaves_the_chord() -> None:
    """Positive control for the angle term: a cut 5 deg off the chord eats
    the channel's slack at the mouth."""
    args = list(_stack_args())
    args[3] = 5.0
    _seat, channel = _slacks(spec.notch_stud_stack(*args))
    assert channel < 0.0
    with pytest.raises(AssertionError):
        spec.assert_notch_stud_stack(*args)


def test_post_mount_taps_transfer_from_the_post_at_assembly() -> None:
    """#917 fixes 1/3 (user ruling via Main, 2026-09-26): the post's screw
    pattern is transfer-drilled from MHA-016 at assembly, as #837 does on the
    base, so the post always fits.  The .XX stations leave the print; the
    part keeps both taps at nominal, and the native tap callout keeps its
    size and depth behind the locating instruction."""
    assert drawing.POST_MOUNT_TRANSFER_CALLOUT == "TRANSFER FROM MHA-016\nAT ASSEMBLY;"
    assert not any(name.startswith("PostMount") for name in drawing.FEATURE_KEEP)
    assert not any(
        name.startswith("PostMount") for name in spec.DRAWING_PRECISION_BY_NAME
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "process=POST_MOUNT_TRANSFER_CALLOUT" in source
    # The model still places each tap on its driven station.
    build = Path(part.__file__).read_text(encoding="utf-8")
    for name in ("PostMountWestX", "PostMountWestZ", "PostMountEastX", "PostMountEastZ"):
        assert f'("{name}", ' in build, name


def test_post_dowel_holes_carry_their_match_ream_callout() -> None:
    """#917 S1: the platform's half of the MHA-151 dowel pair is a native
    Hole Wizard feature; its callout names the mating post and the reamer,
    and prints the reamed size at three places."""
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "process=PLATE_DOWEL_CALLOUT" in source
    assert '{"hw-diam": 3}' in source
    assert 'label="post dowel reamed holes"' in source


# The isometric VIEW as d382 printed it (describe_sheet,
# C:/src/dt-logs/spring/tipslot-d382-leaf.log:291) with ISO_CENTER at
# (0.355, 0.205); the view follows ISO_CENTER (fix4b's render: the part moved
# 15 mm right with it).  Its CAPTION is a property-linked note at a fixed
# sheet point that does NOT follow the view -- the premise fix4b's version of
# this test got wrong; its exact box is :478 (INote.GetExtent) at the anchor
# (0.315, 0.158).  A-A's "(6.35)" line (:456) does not move.
_D382_ISO_CENTER = (0.355, 0.205)
_D382_ISO_VIEW_BOX = (0.3160, 0.1793, 0.3940, 0.2307)
_D382_ISO_NOTE_ANCHOR = (0.315, 0.158)
_D382_ISO_NOTE_BOX = (0.3147, 0.1536, 0.3748, 0.1585)
_D382_NOTCH_NOTE_BOX = (0.2298, 0.1215, 0.2899, 0.1258)
_PLATE_THK_TOP_LINE_BOX = (0.3095, 0.1318, 0.3246, 0.1353)
_SHEET_BORDER_RIGHT = 0.4189


def _iso_view_box() -> tuple[float, float, float, float]:
    dx = drawing.ISO_CENTER[0] - _D382_ISO_CENTER[0]
    dy = drawing.ISO_CENTER[1] - _D382_ISO_CENTER[1]
    box = _D382_ISO_VIEW_BOX
    return (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)


def _box_gap(first: tuple[float, ...], second: tuple[float, ...]) -> float:
    dx = max(0.0, first[0] - second[2], second[0] - first[2])
    dy = max(0.0, first[1] - second[3], second[1] - first[3])
    return math.hypot(dx, dy)


def test_the_caption_extents_are_the_measured_ones() -> None:
    """The captions' boxes in the model are the seat's exact extents about
    their anchors, not estimates."""
    iso = drawing._anchored_box(_D382_ISO_NOTE_ANCHOR, drawing.ISO_NOTE_EXTENT)
    assert all(abs(a - b) < 1e-6 for a, b in zip(iso, _D382_ISO_NOTE_BOX))
    notch = drawing._anchored_box(drawing.NOTCH_CAPTION_UPPER_LEFT, drawing.NOTCH_NOTE_EXTENT)
    assert all(abs(a - b) < 1e-6 for a, b in zip(notch, _D382_NOTCH_NOTE_BOX))
    # The isometric caption now follows its view: 40 mm left of its centre,
    # as d382 had it.
    assert drawing.ISO_NOTE_UPPER_LEFT[0] - drawing.ISO_CENTER[0] == pytest.approx(
        _D382_ISO_NOTE_ANCHOR[0] - _D382_ISO_CENTER[0]
    )


# fix4b (2c406e963) as it printed: the 205.81 line at x 0.32694 (300-dpi
# render, C:/src/dt-logs/tipslot-fix4b-2c40/cone-swing-platform_drawing.png,
# columns 326.90..326.98 mm at y 150) from its text break (0.1672) down to the
# pivot witness, and the isometric caption still at d382's anchor (Main's
# MHA-091 eye pass: the line runs between the M and the E).
_FIX4B_CAPTION_INK = drawing.SheetInk(
    texts={"Isometric View Note": _D382_ISO_NOTE_BOX},
    lines={"CapECz": [((0.32694, 0.1672), (0.32694, 0.13766))]},
    arcs={},
    arrows={},
    leaders={},
)


def test_the_fix4b_caption_fails_the_ink_audit() -> None:
    """Planted as printed, the audit names the 205.81 through the caption;
    the model at fix4b's caption anchor does too."""
    assert "text-on-line: CapECz's line runs through 'Isometric View Note'" in (
        drawing.sheet_ink_collisions(_FIX4B_CAPTION_INK)
    )
    fix4b = drawing.notch_plan_ink(iso_note_xy=_D382_ISO_NOTE_ANCHOR)
    assert "text-on-line: CapECz's line runs through 'Isometric View Note'" in (
        drawing.sheet_ink_collisions(fix4b)
    )


def test_the_moved_205_81_clears_the_isometric_and_the_section_note() -> None:
    """The 205.81 at x 0.327 and its neighbours, 2 mm apart: both legs pass
    left of the isometric view and its caption, its text sits under the view,
    its lower witness and arrowhead clear A-A's "(6.35)", and the view stays
    inside the border."""
    view = _iso_view_box()
    ink = drawing.notch_plan_ink()
    caption = ink.texts["Isometric View Note"]
    witness, line, lower_leg, lower_witness = ink.lines["CapECz"]
    cap_x = drawing.NOTCH_KEEP["CapECz"][0]
    lower_arrow = ((cap_x, lower_witness[0][1]), (cap_x, lower_witness[0][1] + 0.0034))
    for keep_out in (view, caption):
        for stroke in (witness, line, lower_leg, lower_witness):
            assert _drawing_leaders.distance_to_box(stroke, keep_out) >= 0.002
        assert _box_gap(ink.texts["CapECz"], keep_out) >= 0.002
    assert _drawing_leaders.distance_to_box(lower_witness, _PLATE_THK_TOP_LINE_BOX) >= 0.002
    assert (
        _drawing_leaders.distance_to_box(lower_arrow, _PLATE_THK_TOP_LINE_BOX)
        - drawing.DIMENSION_ARROW_HALF_WIDTH
        >= 0.002
    )
    assert _SHEET_BORDER_RIGHT - view[2] >= 0.002
    assert _SHEET_BORDER_RIGHT - caption[2] >= 0.002


# d382/fix4b's 27.70 (TipSlotZ; unchanged between them), 300-dpi render
# (C:/src/dt-logs/tipslot-fix4b-2c40/cone-swing-platform_drawing.png): its
# shoulder at y 0.15268 runs from its line (x 0.2391) left to x 0.22479, and
# the hole-location plan's 189.26 (PostMountWestZ) line stands at x 0.22492
# (columns 224.87..224.96 mm) -- the shoulder ends ON it, a T.
_D382_TIP_SLOT_Z_INK = {
    "TipSlotZ leader": [
        ((0.2391, 0.1515), (0.2391, 0.15268)),
        ((0.2391, 0.15268), (0.22492, 0.15268)),
    ],
    "PostMountWestZ lines": [((0.22492, 0.13766), (0.22492, 0.1722))],
}


def test_the_d382_27_70_shoulder_tees_into_the_189_26() -> None:
    """Main's MHA-091 item 2: the T rule counts it as a crossing."""
    assert _drawing_leaders.leader_crossings(_D382_TIP_SLOT_Z_INK) == [
        ("TipSlotZ leader", "PostMountWestZ lines")
    ]


def test_the_27_70_prints_inside_its_span() -> None:
    """Centred on its line between the witnesses: no shoulder, 2 mm clear of
    the 189.26 line and of every notch-plan stroke, the inside arrows fit."""
    ink = drawing.notch_plan_ink()
    text = drawing.NOTCH_KEEP["TipSlotZ"]
    assert text[0] == drawing.TIP_SLOT_Z_LINE_X
    lower, upper = ink.lines["TipSlotZ"]
    assert lower[0][1] < text[1] < upper[1][1]
    box = ink.texts["TipSlotZ"]
    assert box[0] - _D382_TIP_SLOT_Z_INK["PostMountWestZ lines"][0][0][0] >= 0.002
    for piece in (lower, upper):
        assert abs(piece[1][1] - piece[0][1]) >= drawing.DIMENSION_ARROW_LENGTH + 0.0005
    assert drawing.sheet_ink_collisions(ink) == []


# d382/fix4b's 33.00 outside tail and the "Ø8.00" above it, 300-dpi render:
# the tail at y 0.25524 from its witness (x 0.2733) to x 0.27954, the glyphs
# [0.27886, 0.29190] x [0.25683, 0.26123].
_D382_CAP_DIA_INK = drawing.SheetInk(
    texts={"CapEDia": (0.27886, 0.25683, 0.29190, 0.26123)},
    lines={},
    arcs={},
    arrows={"CapECx": [((0.2733, 0.25524), (0.27954, 0.25524))]},
    leaders={},
)


def test_the_d382_33_00_tail_stands_under_the_8_00() -> None:
    """layoutcheck c5 #2 / MHA-091 item 3, planted as printed: 1.6 mm."""
    near = _drawing_leaders.arrows_near_text(
        _D382_CAP_DIA_INK.arrows, _D382_CAP_DIA_INK.texts, clearance=0.002
    )
    assert [(owner, name) for owner, name, _gap in near] == [("CapECx", "CapEDia")]
    assert near[0][2] == pytest.approx(0.00159, abs=0.00005)


def test_the_cap_diameter_is_not_restated() -> None:
    """The Ø8.00 is gone from every view (the width states the size once,
    MHA-091 round 6): nothing stands over the 33.00's tail."""
    marked = {name for names in spec.DRAWING_DIMENSIONS.values() for name in names}
    assert "CapEDia" not in marked
    assert "CapEDia" not in drawing.DIMENSION_OWNER
    ink = drawing.notch_plan_ink()
    assert not any("CapECx" in f for f in drawing.sheet_ink_collisions(ink))
    assert drawing.CAP_R_NOTE.text == "R"


def test_the_notch_plan_prints_clear() -> None:
    assert drawing.sheet_ink_collisions(drawing.notch_plan_ink()) == []
    assert "NotchRunAngle" not in drawing.NOTCH_KEEP


# The fields detail D shares, as d382/fix4b printed them: the isometric's
# padded view box with ISO_CENTER (_iso_view_box), the 205.81's upper
# witness end (x 0.3283 at the cap's y), the zone frame (d382 dump:
# [12.7, 12.7]..[419.1, 266.7] mm), detail B's label box size (31.5 x
# 16.4 mm, :512), and on the hole-location plan the 2X Ø5.11 callout's
# shoulder (y 0.2524, x 0.1702..0.2282, :393) and the 189.26's hole witness
# (y 0.2323, x 0.1869..0.2260, :360).  The 205.81's dimension line stands at
# x 0.327 (NOTCH_KEEP) from that witness down, and the 33.00's text sits
# at (0.2652, 0.258).
_ZONE_FRAME = (0.0127, 0.0127, 0.4191, 0.2667)
_D382_205_81_WITNESS_END = (0.3283, 0.24057)
_DETAIL_LABEL_SIZE = (0.0315, 0.0164)
_D382_RD2_SHOULDER = ((0.1702, 0.2524), (0.2282, 0.2524))
_D382_189_26_HOLE_WITNESS = ((0.1869, 0.2323), (0.2260, 0.2323))
# Dimension glyphs: "9.11°" measured 10.6 x 3.5 mm (d382), so ~2.12 mm a
# character; a stacked +0.10/0 adds ~7 mm and stands ~4.5 mm tall.
_DIM_CHAR_W, _DIM_GLYPH_H = 0.00212, 0.0035
_TOLERANCE_W, _TOLERANCE_H = 0.0070, 0.0045


def _cap_detail_outline() -> tuple[float, float, float, float]:
    half = drawing.CAP_DETAIL_SHEET_RADIUS + drawing.DETAIL_OUTLINE_PAD
    cx, cy = drawing.CAP_DETAIL_CENTER
    return (cx - half, cy - half, cx + half, cy + half)


def _cap_detail_label() -> tuple[float, float, float, float]:
    x, y = drawing.CAP_DETAIL_LABEL_LOWER_LEFT
    return (x, y, x + _DETAIL_LABEL_SIZE[0], y + _DETAIL_LABEL_SIZE[1])


def _cap_detail_texts() -> dict[str, tuple[float, float, float, float]]:
    """Detail D's texts: the angle centred on its point, the width hanging
    right of its line (its value plus the stacked band), the R note."""
    angle = drawing.CAP_DETAIL_KEEP["NotchMouthAngle"]
    width_x, width_y = drawing.CAP_DETAIL_KEEP["NotchW"]
    return {
        "NotchMouthAngle": drawing._centred_box(
            angle, (len(f"{spec.NOTCH_MOUTH_ANGLE_DEG:.0f}°") * _DIM_CHAR_W, _DIM_GLYPH_H)
        ),
        "NotchW": (
            width_x,
            width_y - _TOLERANCE_H / 2.0,
            width_x + len(f"{spec.NOTCH_W:.2f}") * _DIM_CHAR_W + _TOLERANCE_W,
            width_y + _TOLERANCE_H / 2.0,
        ),
        "R": _note_box(drawing.CAP_R_NOTE),
    }


def _box_off_circle(box: tuple[float, ...], centre: tuple[float, float]) -> float:
    """How far a box stands outside a circle about ``centre`` (its nearest
    point's distance from the centre, less nothing: the caller subtracts)."""
    nearest = (
        min(max(centre[0], box[0]), box[2]),
        min(max(centre[1], box[1]), box[3]),
    )
    return math.dist(centre, nearest)


def _width_witnesses() -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """The width's witness lines: each rail extended from its closed-end
    corner out to 1 mm past the dimension line at the text's x."""
    ux, uy = drawing.CAP_MOUTH_AXIS
    reach_x = drawing.CAP_DETAIL_KEEP["NotchW"][0] + 0.001
    lines = []
    for key in ("closed_s", "closed_n"):
        start = drawing.cap_detail_xy(*part.NOTCH_CUT_POINTS[key])
        t = (reach_x - start[0]) / ux
        lines.append((start, (start[0] + t * ux, start[1] + t * uy)))
    return lines


def test_detail_d_fits_the_field_over_the_isometric() -> None:
    """Outline inside the zone frame, the circle over the isometric's box
    and 2 mm off the 205.81, the label LEFT of the outline -- in the field
    the Ø8.00 and the run angle's leader left -- above the 205.81's witness
    and dimension line, inside the frame."""
    outline = _cap_detail_outline()
    assert outline[3] <= _ZONE_FRAME[3]
    cx, cy = drawing.CAP_DETAIL_CENTER
    radius = drawing.CAP_DETAIL_SHEET_RADIUS
    assert cy - radius > _iso_view_box()[3]
    assert math.dist((cx, cy), _D382_205_81_WITNESS_END) - radius >= 0.002
    label = _cap_detail_label()
    assert outline[0] - label[2] >= 0.0012  # detail B's own gap (47.9 -> 49.1)
    assert _ZONE_FRAME[3] - label[3] >= 0.004
    assert label[1] - _D382_205_81_WITNESS_END[1] >= 0.005
    cap_ecx = drawing._centred_box(drawing.NOTCH_KEEP["CapECx"], drawing.CAP_EC_Z_TEXT_SIZE)
    assert _box_gap(label, cap_ecx) >= 0.005
    # Positive control: 63fb3bd2d's label right of the outline sits on the
    # width's south witness, where it now runs out through the mouth.
    old = (0.3808, 0.236, 0.3808 + _DETAIL_LABEL_SIZE[0], 0.236 + _DETAIL_LABEL_SIZE[1])
    assert any(
        _drawing_leaders.distance_to_box(witness, old) == 0.0 for witness in _width_witnesses()
    )


def test_detail_d_circle_on_the_hole_location_plan_clears_its_neighbours() -> None:
    cap = drawing.plan_xy(drawing.FEATURE_CENTER, part.SLOT_E_X, part.SLOT_E_Z)
    assert cap == pytest.approx((0.19325, 0.24057), abs=5e-5)
    radius = drawing.CAP_DETAIL_RADIUS_MM * drawing.PLAN_SCALE
    for stroke in (_D382_RD2_SHOULDER, _D382_189_26_HOLE_WITNESS):
        assert _drawing_leaders.distance_to_point(stroke, cap) - radius >= 0.004


def test_detail_d_states_width_angle_and_r_clear_of_each_other() -> None:
    """The three facts, each off the circle, apart, inside the frame; the
    angle in its acute sector; the width's value outside its span."""
    centre = drawing.CAP_DETAIL_CENTER
    circle = drawing.CAP_DETAIL_SHEET_RADIUS
    texts = _cap_detail_texts()
    boxes = {**texts, "label": _cap_detail_label()}
    names = list(boxes)
    for i, first in enumerate(names):
        for second in names[i + 1 :]:
            assert _box_gap(boxes[first], boxes[second]) >= 0.002, (first, second)
    for name, box in texts.items():
        assert _box_off_circle(box, centre) - circle >= 0.002, name
        assert _ZONE_FRAME[3] - box[3] >= 0.002, name
        assert _ZONE_FRAME[2] - box[2] >= 0.002, name
        assert box[1] - _iso_view_box()[3] >= 0.002, name
    # The angle's value lies in the material wedge, the acute 88.
    angle = drawing.CAP_DETAIL_KEEP["NotchMouthAngle"]
    vertex = drawing.MOUTH_ANGLE_VERTEX_XY
    assert drawing.in_acute_sector(
        angle, vertex, drawing.MOUTH_ANGLE_RAIL_XY, drawing.MOUTH_ANGLE_EDGE_XY
    )
    # #917 S1: detail D centres on the cap, 0.30 deeper, and the cut runs
    # at 87 deg (d382..round 6: (0.36337, 0.25112)).
    assert vertex == pytest.approx((0.36399, 0.25094), abs=1e-5)
    # Its arc (radius = the value's distance) tops out under the frame.
    assert vertex[1] + math.dist(angle, vertex) <= _ZONE_FRAME[3] - 0.002
    # The width: right of the circle, its value above the witnesses' span.
    south, north = _width_witnesses()
    assert texts["NotchW"][1] - max(south[1][1], north[1][1]) >= 0.002
    assert texts["NotchW"][0] - (centre[0] + circle) >= 0.010
    # The R sits between those witnesses, 2 mm off both.
    for witness in (south, north):
        assert _drawing_leaders.distance_to_box(witness, texts["R"]) >= 0.002


def test_the_r_note_names_the_drawn_cap_arc() -> None:
    """ASME's full R: "R" with its leader on the drawn (closed) half of the
    cap -- not across the open mouth -- clear of the cap centre, and
    crossing neither rail."""
    note = drawing.CAP_R_NOTE
    assert note.text == "R"
    assert note.feature == "LockNotchCapE"
    assert note.radius_mm == part.SLOT_W / 2.0
    assert note.arc_center_mm == part.NOTCH_CAP_E_XZ
    tip = drawing.arc_note_tip(note)
    assert drawing.on_drawn_cap_arc(
        tip, drawing.CAP_DETAIL_CENTER, drawing.CAP_DETAIL_ARC_RADIUS
    )
    model = drawing.arc_note_model_tip(note)
    assert drawing.cap_detail_xy(model[0] * 1000.0, model[2] * 1000.0) == pytest.approx(tip)
    box = _note_box(note)
    leader = drawing.arc_note_leader(note, box[2] - box[0])
    assert leader[0][0] == box[0]  # the tip is left: the leader roots left
    assert _drawing_leaders.distance_to_point(leader, drawing.CAP_DETAIL_CENTER) >= 0.002
    pts = {key: drawing.cap_detail_xy(*xz) for key, xz in part.NOTCH_CUT_POINTS.items()}
    for rail in ((pts["closed_s"], pts["mouth_s"]), (pts["closed_n"], pts["mouth_n"])):
        assert not _drawing_leaders.segments_cross(leader, rail)
        assert _drawing_leaders.distance_to_point(rail, leader[0]) >= 0.002
    # Positive control: a tip out in the mouth is off the drawn arc.
    mouth = dataclasses.replace(note, tip_deg=0.0)
    assert not drawing.on_drawn_cap_arc(
        drawing.arc_note_tip(mouth), drawing.CAP_DETAIL_CENTER, drawing.CAP_DETAIL_ARC_RADIUS
    )


def test_the_build_wires_detail_d() -> None:
    build = inspect.getsource(drawing.build)
    assert 'detail_label="D"' in build
    assert build.index("keep=NOTCH_KEEP") < build.index("keep=CAP_DETAIL_KEEP")
    assert "_assert_mouth_angle_in_wedge(adapter, cap_detail, cap_detail_annotations)" in build
    assert "_add_arc_note(adapter, cap_detail, CAP_R_NOTE)" in build
    assert "added_notes=[cap_r_note]" in build
    assert "_add_arc_note(adapter, feature, RELIEF_ID_NOTE)" in build
    assert "_pin_cap_dia_arrow" not in build
    assert "RELIEF_WIDTH_CALLOUT" not in build
    wedge = inspect.getsource(drawing._assert_mouth_angle_in_wedge)
    assert "in_acute_sector(text, vertex, rail, edge)" in wedge
    assert "model_point_in_view(" in wedge


def test_the_leader_audit_counts_a_t_and_allows_its_own_arc() -> None:
    """_drawing_leaders' T rule (e33969f40): a leader ending on another line
    is a crossing; the one declared touch is the leader's own arc."""
    ink = drawing.notch_plan_ink()
    witness = ink.lines["CapECz"][0]
    on_witness = ((witness[0][0] + witness[1][0]) / 2.0, witness[0][1])
    arc = ((on_witness[0], on_witness[1] - 0.006), (on_witness[0] + 0.003, on_witness[1] - 0.009))
    probe_box = drawing._centred_box((on_witness[0] + 0.012, on_witness[1] - 0.012), (0.006, 0.003))
    base = dataclasses.replace(
        ink,
        texts={**ink.texts, "Probe": probe_box},
        arcs={**ink.arcs, "Probe": [arc]},
    )
    tee = dataclasses.replace(
        base, leaders={"Probe": [(on_witness, (on_witness[0] + 0.004, on_witness[1] - 0.003))]}
    )
    assert "leader-on-ink: Probe's leader crosses CapECz lines" in (
        drawing.sheet_ink_collisions(tee)
    )
    rooted = dataclasses.replace(
        base, leaders={"Probe": [(arc[0], (arc[0][0] + 0.009, arc[0][1] - 0.006))]}
    )
    assert not any("Probe arcs" in f for f in drawing.sheet_ink_collisions(rooted))


def test_the_build_audits_the_notch_plan_ink_on_the_sheet() -> None:
    build = inspect.getsource(drawing.build)
    assert build.index("assert_notch_plan_ink_clear()") < build.index("open_model")
    assert build.index("_pin_tip_slot_z_arrows_inside(adapter, notch_annotations)") > build.index(
        "keep=NOTCH_KEEP"
    )
    # The captions go into the live text set once they exist.
    iso = build.index('"Isometric View Note", *ISO_NOTE_UPPER_LEFT)')
    captions = build.index("_assert_notch_captions_clear(")
    assert iso < captions
    assert '"Isometric View Note": iso_note' in build[captions:]
    audit = inspect.getsource(drawing._assert_notch_captions_clear)
    assert "GetExtent()" in audit and "sheet_ink_collisions(ink)" in audit
    assert "leader_segments(" in inspect.getsource(drawing._notch_strokes)
    audit = "".join(
        inspect.getsource(function)
        for function in (
            drawing.sheet_ink_collisions,
            drawing._leader_findings,
            drawing._segment_gap,
            drawing.dimension_crossings,
        )
    )
    for primitive in (
        "arrows_near_text(",
        "leader_crossings(",
        "distance_to_box(",
        "distance_to_point(",
        "segments_cross(",
    ):
        assert f"_drawing_leaders.{primitive}" in audit, primitive
    assert "dimension_crossings(ink)[0]" in inspect.getsource(drawing.sheet_ink_collisions)
    assert drawing.ARROW_TEXT_CLEARANCE == _drawing_leaders.ARROW_TEXT_CLEARANCE == 0.002


def test_section_a_a_group_stays_inside_the_border() -> None:
    """Shifted 10 mm right, A-A's ink and its audited Ra box stay inside.

    aa9766da's A-A group (section, relief fragment, 0.25, Ra 1.6, label) ended
    at x 0.40005 with the border line at 0.4189.  The base-slide Ra symbol
    keeps its sheet x: the audit boxes a finish 39 mm right of its anchor.
    """
    border = 0.4189
    right = 0.40005 + (drawing.SECTION_SHIFT[0] - 0.020)
    assert border - right >= 0.005
    assert drawing.BASE_SLIDE_FINISH_XY[0] + 0.039 <= border - 0.004
    # Positive control: shifting that anchor with the group would box past.
    assert 0.355 + drawing.SECTION_SHIFT[0] + 0.039 > border


def test_material_fits_one_title_block_line() -> None:
    """81788ce9 wrapped the long material form onto a second title-block line.

    The printed row is short; the full wording lives in material_specification.
    30 characters is the fleet's one-line budget (Main, 2026-09-24).
    """
    row = _config.parts("cone-swing-platform")
    assert len(str(row["material"])) <= 30
    assert "1018" in str(row["material_specification"])
    assert "flat bar" in str(row["material_specification"])


def test_post_screw_engagement_note_states_the_computed_exception() -> None:
    """Codex review of 68565ace (B1): the sheet must state MHA-142's exception.

    U37 accepts short engagement for the 1/4-20 post screws. The printed worst
    case is the thinnest stock plate (U41 band), less the 0.3 cut-to-fit
    allowance and the local 0.1 break at each end of the tap, floored:
    5.72 mm = 0.90D, never under the rule-12 audit's E7 floor of 0.87D.
    """
    worst = (
        spec.PLATE_THICKNESS
        - spec.PLATE_STOCK_BAND
        - spec.POST_SCREW_CUT_TO_FIT_SHORT
        - 2.0 * spec.POST_MOUNT_TAP_EDGE_BREAK
    )
    assert spec.POST_MOUNT_ENGAGEMENT_WORST == pytest.approx(worst)
    diameters = worst / (0.25 * 25.4)
    printed = math.floor(diameters * 100.0) / 100.0
    assert printed <= diameters and printed >= 0.87
    assert f"{printed:.2f}" == "0.90"
    engagement, override = spec.POST_MOUNT_ENGAGEMENT_NOTE.split("\n")
    assert engagement == (
        f"1/4-20 THREAD ENGAGEMENT {printed:.2f}D MIN (MHA-142): "
        "NAMED EXCEPTION TO RULE 12."
    )
    # The break the derivation counts is the break the note allows.
    assert spec.POST_MOUNT_TAP_EDGE_BREAK == 0.1
    assert override == "1/4-20 TAPPED HOLES: DEBURR ONLY, 0.1 MAX BREAK EACH END."
    assert f"{spec.POST_MOUNT_TAP_EDGE_BREAK:.1f} MAX BREAK" in override
    # Positive control: the title block's 0.25 break at both ends would print
    # under the audit floor, which is why the override exists.
    title_block = (
        spec.PLATE_THICKNESS - spec.PLATE_STOCK_BAND - spec.POST_SCREW_CUT_TO_FIT_SHORT - 0.5
    ) / (0.25 * 25.4)
    assert title_block < 0.87
    # The note sits in the empty band above the title block (2.5 mm text,
    # ~1.93 mm a character, 4.4 mm a line).
    x, y = drawing.ENGAGEMENT_NOTE_XY
    lines = spec.POST_MOUNT_ENGAGEMENT_NOTE.split("\n")
    note = (x, y - 0.0044 * len(lines), x + max(map(len, lines)) * 0.00193, y)
    lx, ly = drawing.SLOT_SECTION_LABEL_LOWER_LEFT
    assert note[0] > 0.2185 + 0.002  # plan caption row
    assert note[3] <= ly - 0.0015  # C-C label
    assert note[3] <= 0.0853 - 0.004  # A-A label bottom (aa9766da render)
    assert note[1] >= 0.066 + 0.004  # title block top
    assert note[2] <= 0.4189 - 0.010  # border


# Detail B text extents (sheet metres), from the renders: outside its span a
# vertical dimension's text hangs outward from its line, centred on the keep
# y -- "4.0 +0.1/0.0" 17 x 8 mm, "7.94 +0.1/0.0" 21 x 8 mm and "11.00"
# 12 x 5 mm (81788ce9); the 2.00s ~12 x 5 centred on theirs.  Notes are
# 2.5 mm text anchored upper-left, ~1.894 mm a character and 3.52 mm a line
# (the relief note, 0.0947 x 0.0176 for 50 characters on five lines).
_NOTE_CHAR_W, _NOTE_LINE_H = 0.001894, 0.00352
_DETAIL_SPANS = {  # each width's extension-line span, sheet y
    name: (
        drawing._SLOT_Y - width * drawing._DETAIL_S / 2.0,
        drawing._SLOT_Y + width * drawing._DETAIL_S / 2.0,
    )
    for name, width in (("TipSlotW", spec.TIP_SLOT_W), ("TipCboreW", spec.TIP_CBORE_W))
}


def _detail_text_boxes(keep: dict[str, tuple[float, float]]) -> dict[str, tuple]:
    slot_x, slot_y = keep["TipSlotW"]
    cbore_x, cbore_y = keep["TipCboreW"]
    east_x, east_y = keep["TipSlotEastCx"]
    west_x, west_y = keep["TipSlotWestCx"]
    return {
        "TipSlotW": (slot_x - 0.018, slot_y - 0.0045, slot_x, slot_y + 0.0045),
        "TipCboreW": (cbore_x - 0.022, cbore_y - 0.0045, cbore_x, cbore_y + 0.0045),
        "TipSlotEastCx": (east_x - 0.006, east_y - 0.0025, east_x + 0.006, east_y + 0.0025),
        "TipSlotWestCx": (west_x - 0.006, west_y - 0.0025, west_x + 0.006, west_y + 0.0025),
    }


def _note_box(note: drawing.ArcNote) -> tuple[float, float, float, float]:
    lines = note.text.replace("<MOD-DIAM>", "D").split("\n")
    x, y = note.text_xy
    width = max(len(line) for line in lines) * _NOTE_CHAR_W
    return (x, y - len(lines) * _NOTE_LINE_H, x + width, y)


def _note_extent(note: drawing.ArcNote) -> tuple[float, float, float, float]:
    """What INote.GetExtent -- the audit's box -- spans: text plus leader tip.

    ec70186e logged the one-line slot note as [89.2, 59.1]..[158.9, 79.1] mm:
    its leader tip on the arc up to 0.6 mm above its text anchor.
    """
    x0, y0, x1, y1 = _note_box(note)
    tip = drawing.arc_note_tip(note)
    return (min(x0, tip[0]), min(y0, tip[1]), max(x1, tip[0]), max(y1 + 0.0006, tip[1]))


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


def _leader_fan(note: drawing.ArcNote):
    """The leader from its arc tip to each end of the note's left edge."""
    tip = drawing.arc_note_tip(note)
    box = _note_box(note)
    return [(tip, (box[0], box[1])), (tip, (box[0], box[3]))]


def test_detail_band_clears_border_title_block_and_captions() -> None:
    """Detail B, its label, dimension texts, cutter notes and the relief note.

    Extents are the ones the layout audit logged on the farm (runs 2b643c17
    and e86bf319) -- the native label 31.5 x 16.2 mm, the relief note
    0.0947 x 0.0176 m from its upper-left anchor -- and the rendered text
    blocks above.  e86bf319 failed on the label alone (8.9 mm through the
    bottom border); its callouts also ran under the title block and the plan
    caption, which the audit's nominal dimension boxes cannot see (#852).
    """
    border_bottom, title_block = 0.0127, (0.216, 0.0, 0.4318, 0.066)
    captions = (
        (0.0449, 0.0805, 0.1059, 0.0853),
        (0.1497, 0.0805, 0.2185, 0.0853),
    )
    label_x, label_y = drawing.DETAIL_LABEL_LOWER_LEFT
    label = (label_x, label_y, label_x + 0.0315, label_y + 0.0162)
    note_x, note_y = drawing.RELIEF_NOTE_XY
    relief = (note_x, note_y - 0.0176, note_x + 0.0947, note_y)
    cx, cy = drawing.DETAIL_CENTER
    r = drawing.DETAIL_SHEET_RADIUS
    circle = (cx - r, cy - r, cx + r, cy + r)
    # eaafbc73: the audit boxes the view by its native outline, the circle
    # padded 10.4 mm a side, against the 9.7 mm zone border.
    pad = drawing.DETAIL_OUTLINE_PAD
    outline = (cx - r - pad, cy - r - pad, cx + r + pad, cy + r + pad)
    assert outline[1] > 0.0097
    notes = {f"{note.key} note": _note_box(note) for note in drawing.CUTTER_NOTES}
    # The audit boxes each leadered note from leader tip to text (ec70186e):
    # those extents stay apart by 3 mm, and clear of the label and relief.
    extents = [_note_extent(note) for note in drawing.CUTTER_NOTES]
    low, high = sorted(extents, key=lambda box: box[1])
    assert high[1] - low[3] >= 0.003
    for extent in extents:
        assert not _boxes_overlap(extent, label) and not _boxes_overlap(extent, relief)
    # Positive control: ec70186e's cbore note (text above its upper-quadrant
    # tip) nested inside the slot note's extent.
    by_key = {note.key: note for note in drawing.CUTTER_NOTES}
    old_cbore = dataclasses.replace(by_key["cbore"], text_xy=(0.121, 0.0715), tip_deg=35.0)
    assert _boxes_overlap(_note_extent(old_cbore), _note_extent(by_key["slot"]))
    for other in (label, relief, *notes.values()):
        assert not _boxes_overlap(outline, other)
    for caption in captions:
        assert not _boxes_overlap(outline, caption)
    eaafbc73_outline = (0.0536, 0.0096, 0.1224, 0.0784)
    assert _boxes_overlap(eaafbc73_outline, (0.1189, 0.0166, 0.2135, 0.0342))
    boxes = {
        "label": label,
        "relief": relief,
        "circle": circle,
        **_detail_text_boxes(drawing.DETAIL_KEEP),
        **notes,
    }
    for name, box in boxes.items():
        assert box[1] > border_bottom + 0.001, name
        assert box[0] > 0.0127 + 0.001, name
        assert not _boxes_overlap(box, title_block), name
        for caption in captions:
            assert not _boxes_overlap(box, caption), (name, caption)
    names = list(boxes)
    for i, first in enumerate(names):
        for second in names[i + 1 :]:
            assert not _boxes_overlap(boxes[first], boxes[second]), (first, second)
    # Positive control: e86bf319's layout fails this very check.
    old_label = (0.1443, 0.0038, 0.1758, 0.0200)
    old_cbore = (0.196, 0.072 - 0.016, 0.196 + 0.042, 0.072 + 0.015)
    assert old_label[1] < border_bottom
    assert _boxes_overlap(old_cbore, title_block)
    assert _boxes_overlap(old_cbore, captions[1])


def test_detail_dimension_text_sits_outside_its_own_lines() -> None:
    """No vertical dimension's line runs through its text (81788ce9).

    Each text sits outside its extension-line span, on one side of its own
    dimension line, and clear of every other vertical dimension's extension
    lines.  The slot sits nearest the part so the counterbore's extension
    lines, further out, never cross the slot's line inside the slot's span.
    """
    keep = drawing.DETAIL_KEEP
    boxes = _detail_text_boxes(keep)
    east_arc_x = drawing.DETAIL_CENTER[0] - 0.004  # where the width lines start
    extension_runs = {
        # The widths run left from the slot's straight edges to their lines.
        "TipSlotW": [((keep["TipSlotW"][0], y), (east_arc_x, y)) for y in _DETAIL_SPANS["TipSlotW"]],
        "TipCboreW": [((keep["TipCboreW"][0], y), (east_arc_x, y)) for y in _DETAIL_SPANS["TipCboreW"]],
    }
    for name, (low, high) in _DETAIL_SPANS.items():
        x, _y = keep[name]
        box = boxes[name]
        assert box[3] <= low or box[1] >= high, name  # text outside its span
        assert box[0] >= x or box[2] <= x, name  # not straddling its line
        for other, runs in extension_runs.items():
            for run in runs:
                assert not _segment_hits_box(run, box), (name, other, run)
    slot_x, cbore_x = keep["TipSlotW"][0], keep["TipCboreW"][0]
    assert cbore_x < slot_x < east_arc_x  # counterbore outboard of the slot
    assert set(drawing.DETAIL_ARROWS_INSIDE) == {"TipSlotW", "TipCboreW"}
    # I31: the slot's station from the pivot left the detail for the notch
    # plan (the circle is centred on the slot, 27.7 south of the pivot).
    assert "TipSlotZ" not in keep
    assert drawing.DETAIL_MODEL_Z == spec.TIP_SCREW_LOCAL_Z
    # Positive control: 81788ce9's keeps put both widths inside their spans
    # (there centred on the slot), where the text is centred on its own line.
    old = {"TipSlotW": drawing._SLOT_Y, "TipCboreW": drawing._SLOT_Y}
    for name, y in old.items():
        low, high = _DETAIL_SPANS[name]
        assert low < y < high


def test_cutter_note_leaders_reach_their_arcs_without_crossing() -> None:
    """Each cutter note's leader tip is on its slot's west end arc.

    The build proves the tip against the physical edge (``_add_cutter_note``,
    0.01 mm); here the tip's sheet image, the arc radius and the leader paths
    are pinned: both leaders rise to the right and cross neither each other,
    the other note, pivot-to-slot's text or the 2.00s.
    """
    by_key = {note.key: note for note in drawing.CUTTER_NOTES}
    assert set(by_key) == {"slot", "cbore"}
    assert by_key["slot"].feature == "TipScrewSlot"
    assert by_key["cbore"].feature == "TipScrewCbore"
    assert by_key["slot"].radius_mm == spec.TIP_SLOT_W / 2.0
    assert by_key["cbore"].radius_mm == spec.TIP_CBORE_W / 2.0
    assert by_key["slot"].model_y_mm == spec.PLATE_THICKNESS  # the visible arc
    assert "SLOT THRU" in by_key["slot"].text
    assert "FROM UNDERSIDE" in by_key["cbore"].text
    assert drawing.LEADER_TIP_BOUND_M == 0.00001
    centre = (drawing.DETAIL_CENTER[0] + 0.004, drawing._SLOT_Y)
    for note in drawing.CUTTER_NOTES:
        tip = drawing.arc_note_tip(note)
        assert math.dist(tip, centre) == pytest.approx(note.radius_mm * 0.002)
        assert -90.0 < note.tip_deg < 90.0  # the west (sheet-right) end arc
        model = drawing.arc_note_model_tip(note)
        assert math.hypot(
            model[0] - spec.TIP_SCREW_HALF_TRAVEL / 1000.0,
            model[2] - spec.TIP_SCREW_LOCAL_Z / 1000.0,
        ) == pytest.approx(note.radius_mm / 1000.0)
    # The slot note rises from the upper quadrant, the counterbore note drops
    # from the lower one (their audit extents must not nest, ec70186e).
    assert by_key["slot"].tip_deg > 0.0 > by_key["cbore"].tip_deg
    assert drawing.arc_note_tip(by_key["slot"])[1] > drawing._SLOT_Y
    boxes = _detail_text_boxes(drawing.DETAIL_KEEP)
    obstacles = {name: boxes[name] for name in ("TipSlotEastCx", "TipSlotWestCx")}
    fans = {note.key: _leader_fan(note) for note in drawing.CUTTER_NOTES}
    for key, fan in fans.items():
        other = "cbore" if key == "slot" else "slot"
        for segment in fan:
            for name, box in obstacles.items():
                assert not _segment_hits_box(segment, box), (key, name)
            assert not _segment_hits_box(segment, _note_box(by_key[other])), key
            for other_segment in fans[other]:
                assert not _segments_cross(segment, other_segment)
    # Positive control: with the texts swapped, the two leaders cross.
    swapped = [
        dataclasses.replace(by_key["slot"], text_xy=by_key["cbore"].text_xy),
        dataclasses.replace(by_key["cbore"], text_xy=by_key["slot"].text_xy),
    ]
    assert any(
        _segments_cross(a, b)
        for a in _leader_fan(swapped[0])
        for b in _leader_fan(swapped[1])
    )


_TIP_SLOT_WIDTHS = {"TipSlot": spec.TIP_SLOT_W, "TipCbore": spec.TIP_CBORE_W}


def _tip_slot_dimension(name: str) -> tuple[float, str]:
    """(sketch width, reference key) of a tip-slot sketch's dimension."""
    for prefix, width in _TIP_SLOT_WIDTHS.items():
        if name.startswith(prefix):
            return width, name[len(prefix) :]
    raise AssertionError(f"{name} is not a tip-slot sketch dimension")


def _crop_distance(sketch_xy: tuple[float, float]) -> float:
    """Plan distance (mm) of a Top-plane sketch point from detail B's centre.

    Sketch y is part -Z; the crop circle is centred on (0, DETAIL_MODEL_Z)."""
    x, y = sketch_xy
    return math.hypot(x, -y - drawing.DETAIL_MODEL_Z)


def test_detail_b_dimension_references_lie_inside_its_crop() -> None:
    """A detail view imports a model dimension only when its references fall
    inside the crop circle.  Farm leaf 7ab69742b: with the end centres
    dimensioned to the sketch origin, 27.7 from the slot-centred R12 circle,
    detail B came up with only the two widths ("missing model dimensions:
    ['TipSlotEastCx', 'TipSlotWestCx']")."""
    assert set(drawing.DETAIL_KEEP) == {
        "TipSlotEastCx",
        "TipSlotWestCx",
        "TipSlotW",
        "TipCboreW",
    }
    for name in drawing.DETAIL_KEEP:
        width, key = _tip_slot_dimension(name)
        points = part.tip_slot_sketch_points(width)
        for ref in part.TIP_SLOT_DIMENSION_REFERENCES[key]:
            distance = _crop_distance(points[ref])
            assert distance < drawing.DETAIL_RADIUS_MM - 1.0, (name, ref, distance)
    # Positive control: the origin, the Cx dimensions' old reference, lies
    # outside the crop -- and before I31 (slot at z -11, circle centred at
    # z -6) it lay inside, which is why the same dimensions imported then.
    origin = part.tip_slot_sketch_points(spec.TIP_SLOT_W)["origin"]
    assert _crop_distance(origin) > drawing.DETAIL_RADIUS_MM
    assert math.hypot(0.0, 0.0 - (-6.0)) < drawing.DETAIL_RADIUS_MM


def test_tip_slot_end_centres_dimension_to_the_cone_axis_centerline() -> None:
    """Main's option (a): each end centre is a horizontal distance to a
    construction centerline on the cone axis, not to the origin.  The line
    starts at the origin, stays on sketch x = 0, and runs past the slot."""
    import inspect
    import re

    refs = part.TIP_SLOT_DIMENSION_REFERENCES
    assert refs["EastCx"] == ("east_center", "axis_end")
    assert refs["WestCx"] == ("west_center", "axis_end")
    # The station stays on the origin: it prints on the notch plan.
    assert refs["Z"] == ("east_center", "origin")
    assert all("origin" not in refs[key] for key in ("EastCx", "WestCx", "W"))
    for width in _TIP_SLOT_WIDTHS.values():
        points = part.tip_slot_sketch_points(width)
        assert points["axis_start"] == (0.0, 0.0) == points["origin"]
        assert points["axis_end"][0] == 0.0
        slot_y = -spec.TIP_SCREW_LOCAL_Z
        assert points["east_center"] == (-spec.TIP_SCREW_HALF_TRAVEL, slot_y)
        assert points["west_center"] == (spec.TIP_SCREW_HALF_TRAVEL, slot_y)
        # Past the slot's far edge, so the line crosses the whole slot.
        assert points["axis_end"][1] > slot_y + width / 2.0
    source = inspect.getsource(part._sketch_tip_screw_slot)
    assert '"origin", "horizontal_distance"' not in source
    assert "anchor_point_to_origin(adapter, f\"{arc_e}" not in source
    assert "add_centerline(" in source
    assert 'await adapter.add_sketch_constraint(axis, None, "vertical")' in source
    assert 'anchor_point_to_origin(\n        adapter, refs["axis_start"]' in source
    assert '"axis_start": f"{axis}.start"' in source
    assert '"axis_end": f"{axis}.end"' in source
    assert 'add_centerline(*points["axis_start"], *points["axis_end"])' in source
    # Every dimension goes through the reference table, in its order -- the
    # order SketchDims names them in.
    assert "dims.record(f\"{prefix}{name}\")" in source
    assert source.count("dims.record(") == 1
    assert source.count("dimension_between(") == 1
    created = re.findall(r'await dimension\(\s*"(\w+)"', source)
    assert created == list(refs)
    names = {f"TipSlot{key}" for key in refs}
    assert spec.DRAWING_DIMENSIONS["TipScrewSlotProfile"] <= names
    assert spec.DRAWING_DIMENSIONS["TipScrewCboreProfile"] <= {
        f"TipCbore{key}" for key in refs
    }


def test_slot_section_cut_keeps_its_plane_and_crosses_the_plate() -> None:
    """Section C-C cuts at the slot station, edge to edge (8783776d eye-pass).

    The plane is the one detail B carried; the line now runs past both plate
    edges, so the strip is the full plate width at the slot (32.28 mm since
    I31 moved the slot to -27.7 and widened the north-west; 32.79 since #917
    S1 widened it another 0.6 for the +/-2.5 slot and the 1.65 north travel) and needs no symmetry.
    """
    z = spec.TIP_SCREW_LOCAL_Z
    ends = drawing.slot_section_line_model_points()
    assert all(end[1:] == (spec.PLATE_THICKNESS / 1000.0, z / 1000.0) for end in ends)
    east, west = drawing.plate_edge_mm(z, -1), drawing.plate_edge_mm(z, +1)
    assert ends[0][0] * 1000.0 < east and ends[1][0] * 1000.0 > west
    assert west - east == pytest.approx(32.79, abs=0.01)
    # The slot and its counterbore lie inside the cut.
    assert east < -(spec.TIP_SCREW_HALF_TRAVEL + spec.TIP_CBORE_W / 2.0)
    assert west > spec.TIP_SCREW_HALF_TRAVEL + spec.TIP_CBORE_W / 2.0


_profile_edge_mm = drawing.plate_edge_mm


def _cc_arrows_and_letters(line_x_mm):
    """Sheet boxes of C-C's sheet-up arrows and letters on the 1:2 plan.

    Arrows are 12.6 mm with 3 mm heads; each letter sat 15.5..22 mm above
    the line and 5.5 mm wide (the 8783776d render, full-res crop).
    """
    px, py = drawing.PROFILE_PIVOT_XY
    line_y = py - spec.TIP_SCREW_LOCAL_Z * 0.0005
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


def _profile_station(label: str) -> tuple[float, float]:
    """A corner fillet centre on the profile plan, sheet metres."""
    return drawing.plan_xy(drawing.PROFILE_CENTER, *part.corner_fillet_center(label))


def _corner_leader_tip(label: str, side: int) -> tuple[float, float]:
    """Where a corner radius's leader meets its arc: 45 deg off the centre,
    sheet-up (model north) and toward the corner's own side."""
    radius = {corner[0]: corner[3] for corner in part._CORNERS}[label]
    x, y = _profile_station(label)
    offset = radius * drawing.PLAN_SCALE / math.sqrt(2.0)
    return (x + side * offset, y - offset)


# The profile's corner-radius stations as the farm measured them before I31
# (they were sheet literals in draw_cone_swing_platform until tipslot-2762).
_PRE_I31_CORNER_STATIONS = {
    "SW": (0.0875, 0.2433),
    "NW": (0.0723, 0.1382),
    "NE": (0.0686, 0.1392),
    "SE": (0.0660, 0.2398),
}
_STATION_WINDOW_M = 0.001  # _assert_corner_radius_attachment's match window


def _station_matches(station, expected) -> bool:
    return all(abs(station[i] - expected[i]) <= _STATION_WINDOW_M for i in (0, 1))


def _pre_i31_corners(monkeypatch) -> None:
    """The part as it stood before I31: the north-west half-width 8.0."""
    corners = list(part._CORNERS)
    corners[1] = ("NW", 8.0, *corners[1][2:])
    monkeypatch.setattr(part, "_CORNERS", tuple(corners))
    monkeypatch.setattr(part, "WEST_HALF_N", 8.0)


def test_corner_fillet_centres_sit_one_radius_in_from_both_edges() -> None:
    corners = part._CORNERS
    for index, (label, x, z, radius) in enumerate(corners):
        cx, cz = part.corner_fillet_center(label)
        for neighbour in (corners[index - 1], corners[(index + 1) % 4]):
            dx, dz = neighbour[1] - x, neighbour[2] - z
            distance = abs(dx * (cz - z) - dz * (cx - x)) / math.hypot(dx, dz)
            assert distance == pytest.approx(radius, abs=1e-9), (label, neighbour[0])
        # Inside the plate, toward the plan centre.
        assert (cx - x) * (drawing._PLAN_MID_X - x) > 0.0, label
        assert (cz - z) * (drawing._PLAN_MID_Z - z) > 0.0, label
        assert drawing.corner_station_model_m(label) == pytest.approx(
            (cx / 1000.0, spec.PLATE_THICKNESS / 1000.0, cz / 1000.0)
        )


def test_corner_radius_stations_follow_the_fillet_centres(monkeypatch) -> None:
    """tipslot-2762: "expected 2 owned visible CornerNWR arc(s) at corner
    station, found 0".  The NW station was a sheet literal from before I31,
    whose wider north-west moved the fillet centre 1.39 mm (sheet) east of
    it -- outside the proof's 1 mm window.  The build now projects every
    corner's fillet centre into the profile; here the same centres go
    through plan_xy, which the farm's profile pivot confirms to 0.05 mm."""
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for literal in _PRE_I31_CORNER_STATIONS.values():
        assert f"({literal[0]:.4f}, {literal[1]:.4f})" not in source, literal
    assert "station_xy = model_point_in_view(" in source
    assert "corner_station_model_m(label)" in source
    # The old NW literal against the new geometry: rejected, as on the farm.
    assert not _station_matches(_PRE_I31_CORNER_STATIONS["NW"], _profile_station("NW"))
    assert abs(_PRE_I31_CORNER_STATIONS["NW"][0] - _profile_station("NW")[0]) > 0.0013
    # The other three corners did not move: their literals (0.1 mm, as
    # measured) agree.
    for label in ("NE", "SW", "SE"):
        station = _profile_station(label)
        assert math.dist(station, _PRE_I31_CORNER_STATIONS[label]) < 0.00015, label
    # Positive control: before I31 the derivation lands on every literal the
    # farm proved, the north-west included.
    _pre_i31_corners(monkeypatch)
    for label, literal in _PRE_I31_CORNER_STATIONS.items():
        assert math.dist(_profile_station(label), literal) < 0.00015, label


def test_pivot_section_east_end_matches_the_pre_i31_measurement(monkeypatch) -> None:
    """Section A-A's strip, the pivot and the PlateThk witness end.

    Before I31 the farm measured the pivot at x361.982 (eaafbc73, when
    SECTION_SHIFT was 0.020) and the east cut edge at x310.2 unshifted, and
    the witness end was the literal x309 + shift.  I31's wider north-west
    lengthens the strip 2.9 mm west, which moves the pivot and the east end
    2.9 mm left on the sheet: the old x309 missed the witness window.  #917
    S1's +/-2.5 tip slot and 1.65 north travel widen it another 0.6 at the
    north corner (west end 11.81 -> 12.40 at the pivot station); the witness
    end still derives."""
    east, west = drawing.pivot_section_strip_mm()
    # The NE R10 trims the east end at the pivot station (the straight edge
    # would read -16.25); the NW R8 still runs there, meeting its side edge
    # at z -0.10 (NW_ROUND_END_Z), so it trims the west end by 0.6 um.
    assert east == pytest.approx(-15.8912, abs=1e-4)
    assert drawing.plate_edge_mm(0.0, -1) == pytest.approx(-16.2507, abs=1e-4)
    assert 0.0 < drawing.plate_edge_mm(0.0, +1) - west < 1e-3
    assert west == pytest.approx(12.3955, abs=1e-4)
    new_pivot = drawing.pivot_section_pivot_x()
    new_end = drawing.plate_thk_witness_end_x(new_pivot)
    old_end = drawing.SECTION_SHIFT[0] + 0.309
    assert abs(new_end - old_end) > 0.0005 + 0.002
    _pre_i31_corners(monkeypatch)
    old_east, old_west = drawing.pivot_section_strip_mm()
    assert old_west == pytest.approx(8.909, abs=1e-3)
    pivot = drawing.pivot_section_pivot_x()
    assert pivot - (drawing.SECTION_SHIFT[0] - 0.020) == pytest.approx(0.361982, abs=5e-5)
    cut = pivot + old_east * drawing.PIVOT_SECTION_SCALE - drawing.SECTION_SHIFT[0]
    assert cut == pytest.approx(0.3102, abs=5e-5)
    assert drawing.plate_thk_witness_end_x(pivot) == pytest.approx(old_end, abs=5e-5)
    assert pivot - new_pivot == pytest.approx(0.00339, abs=1e-4)  # 2.9 (I31) + 0.49 (#917 S1)


def test_every_kept_dimension_prints_once_on_its_owning_view() -> None:
    """The notch plan imports TipScrewSlotProfile for TipSlotZ and so receives
    the slot's other dimensions too (tipslot-2762 leaf log: "delivered
    unrequested annotations ... TipSlotEastCx, TipSlotW, TipSlotWestCx;
    deleting them").  Each belongs to detail B; the sheet-wide walk after
    curation fails the build if a deletion did not hold."""
    owner = drawing.DIMENSION_OWNER
    assert owner["TipSlotZ"] == "notch plan"
    for name in ("TipSlotEastCx", "TipSlotWestCx", "TipSlotW", "TipCboreW"):
        assert owner[name] == "tip screw slot detail", name
    assert owner["TipCboreDepth"] == "tip screw slot section"
    assert owner["NotchW"] == owner["NotchMouthAngle"] == "lock notch cap detail"
    assert owner["PivotBearingReliefDia"] == "profile plan"
    # Every dimension the part marks for drawing has one owning view.
    marked = {name for names in spec.DRAWING_DIMENSIONS.values() for name in names}
    assert set(owner) == marked
    clean = {view: [] for view in (*drawing.VIEW_KEEPS, "isometric")}
    for name, view in owner.items():
        clean[view].append(name)
    clean["feature plan"].append("")  # a hole callout: no model dimension
    assert drawing.dimension_placement_errors(clean) == []
    # A deletion that did not hold: the slot's dimensions twice.
    doubled = {view: list(names) for view, names in clean.items()}
    doubled["notch plan"] += ["TipSlotEastCx", "TipSlotW", "TipSlotWestCx"]
    errors = drawing.dimension_placement_errors(doubled)
    assert len(errors) == 3 and all("found on ['notch plan'" in e for e in errors)
    # Detail B came up without its end centres (7ab69742b).
    missing = {view: list(names) for view, names in clean.items()}
    missing["tip screw slot detail"] = ["TipCboreW", "TipSlotW"]
    assert len(drawing.dimension_placement_errors(missing)) == 2
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    call = source.split("_assert_each_kept_dimension_once(\n        adapter,")[1]
    for view in (*drawing.VIEW_KEEPS, "isometric"):
        assert f'"{view}":' in call.split(")")[0], view
    # Walked after the last curation and the corner proofs.
    assert source.index("_assert_each_kept_dimension_once(\n") > source.index(
        "keep=SLOT_SECTION_KEEP"
    )


def test_slot_section_arrows_clear_the_profile_plan() -> None:
    """C-C's arrows and letters, looking south, stand outside the plate.

    As a +-9 mm partial cut the west letter landed on the plate's sloped west
    edge (8783776d).  Looking north (the default), the west arrow ran 0.5 mm
    beside the 8.0 extension line and through the R8 leader; sheet-up they
    stay clear of the corner radii's leaders and the north-edge witness.
    """
    px, py = drawing.PROFILE_PIVOT_XY
    arrows, letters = _cc_arrows_and_letters(drawing.SLOT_SECTION_LINE_X_MM)
    for side, arrow, letter in zip((-1, 1), arrows, letters):
        assert _clears_plate(arrow, side) and _clears_plate(letter, side)
    r10_leader = ((0.051, 0.139), _corner_leader_tip("NE", -1))
    r8_leader = ((0.135, 0.118), _corner_leader_tip("NW", +1))
    north_edge_y = py - part.NORTH_OVERHANG * 0.0005
    nw_x = px + part.WEST_HALF_N * 0.0005
    nw_extension = ((nw_x, 0.113), (nw_x, north_edge_y))
    for box in (*arrows, *letters):
        for line in (r10_leader, r8_leader, nw_extension):
            assert not _segment_hits_box(line, box)
        assert box[1] > north_edge_y
    # Positive control: 8783776d's +-9 mm ends put the west letter on the edge.
    _old_arrows, old_letters = _cc_arrows_and_letters((-9.0, 9.0))
    assert not _clears_plate(old_letters[1], 1)
    half = 9.0 * 0.0005
    length, head = 0.0126, 0.0015
    # Positive control, in 8783776d's geometry (the U30 slot 11.0 south of
    # the pivot, the north-west corner at 8.0): the default north-looking
    # arrows hit the R8 leader and the 8.0 extension line.
    line_y = py + 11.0 * 0.0005
    old_nw_x = px + 8.0 * 0.0005
    old_nw_extension = ((old_nw_x, 0.113), (old_nw_x, north_edge_y))
    down = (px + half - head, line_y - length, px + half + head, line_y)
    assert _segment_hits_box(old_nw_extension, down)
    assert _segment_hits_box(r8_leader, down)


def test_slot_section_pocket_clears_its_neighbours() -> None:
    """Section C-C, its label and its depth text fit the pocket they are given.

    Neighbour boxes are the extents the layout audit logged on the farm
    (runs 2b643c17 and e86bf319): the notch plan, its caption, the relief
    dimension RD1, and section A-A's outline, finish symbol and thickness
    text.  The strip is the plate edge-on at 1:1 plus SolidWorks' ~4 mm
    outline padding; the native label measured 46.5 x 16.2 mm.  The thickness
    text is its rendered extent (see the test below), not the audit's
    nominal box (#852).
    """
    # Section A-A's boxes were logged at SECTION_SHIFT x 0.020; they move
    # with the shift.
    dx_aa = drawing.SECTION_SHIFT[0] - 0.020
    neighbours = {
        "notch view": (0.2394, 0.1286, 0.2806, 0.2514),
        "notch caption": _notch_caption_box(),
        "hole caption": (0.1497, 0.0805, 0.2185, 0.0853),
        "RD1": (0.1900, 0.1042, 0.2460, 0.1077),
        "section A-A": (0.3246 + dx_aa, 0.1081, 0.3854 + dx_aa, 0.1319),
        "A-A finish": (0.3160 + dx_aa, 0.1056, 0.3276 + dx_aa, 0.1081),
        "A-A thickness": _plate_thickness_text_box(),
        "title block": (0.216, 0.0, 0.4318, 0.066),
    }
    z = spec.TIP_SCREW_LOCAL_Z
    width = drawing.plate_edge_mm(z, 1) - drawing.plate_edge_mm(z, -1)
    half = width / 2000.0 + 0.004
    cx, cy = drawing.SLOT_SECTION_CENTER
    strip = (cx - half, cy - 0.0072, cx + half, cy + 0.0072)
    lx, ly = drawing.SLOT_SECTION_LABEL_LOWER_LEFT
    label = (lx, ly, lx + 0.0465, ly + 0.0162)
    # The label sits directly under its own strip, centred (8783776d printed
    # it 50 mm to the left, closer to nothing of its own).
    assert lx + 0.0465 / 2.0 == pytest.approx(cx)
    assert label[3] < strip[1]
    # The depth text hangs beyond the strip's ends, not over it.
    assert drawing.SLOT_SECTION_KEEP["TipCboreDepth"][0] < cx - width / 2000.0
    assert drawing.SLOT_SECTION_DEPTH_RIGHT[0] > cx + width / 2000.0
    dx, dy = drawing.SLOT_SECTION_KEEP["TipCboreDepth"]
    depth = (dx - 0.012, dy - 0.004, dx, dy + 0.004)
    # Looking south mirrors the strip, so the build may park the depth on the
    # right-hand end instead (text hanging right): both must fit.
    rx, ry = drawing.SLOT_SECTION_DEPTH_RIGHT
    depth_right = (rx, ry - 0.004, rx + 0.012, ry + 0.004)
    assert rx - cx == pytest.approx(cx - dx)
    ours = {
        "C-C strip": strip,
        "C-C label": label,
        "depth text": depth,
        "depth text right": depth_right,
    }
    for name, box in ours.items():
        for other, neighbour in neighbours.items():
            assert not _boxes_overlap(box, neighbour), (name, other)
    assert not _boxes_overlap(strip, label)
    # Positive control: the pocket is real -- moving the strip up onto the
    # lifted notch caption is caught.
    moved = (strip[0], 0.118, strip[2], 0.132)
    assert _boxes_overlap(moved, neighbours["notch caption"])


def test_relief_id_names_the_feature_without_a_compass_or_a_size() -> None:
    """MHA-091 round 6, B1: the relief is named by a leadered ID, not by a
    callout stacked on its 10.50 (Fable review, 63fb3bd2d).  The ID carries
    no value -- the 10.50 is the only size (rule 6) -- and names its open
    end by a feature: sheet-down is model north, so "OPEN TO NORTH EDGE"
    contradicted a relief opening toward the sheet's lower edge (codex B2 on
    68565ace; Main kept the ban in round 6)."""
    note = drawing.RELIEF_ID_NOTE
    lines = note.text.split("\n")
    assert lines == ["TOP RELIEF", "FULL R ON PIVOT", "OPEN THRU", "PIVOT END"]
    assert not any(ch.isdigit() for ch in note.text)
    assert not any(word in note.text for word in ("NORTH", "SOUTH", "EAST", "WEST"))
    assert "PIVOT" in lines[-1]
    assert spec.PIVOT_RELIEF_FIT_REQUIREMENT.startswith("TOP RELIEF: ")
    assert not hasattr(drawing, "RELIEF_WIDTH_CALLOUT")
    assert note.feature == "PivotBearingRelief"
    assert note.radius_mm == spec.PIVOT_BEARING_RELIEF_DIAMETER / 2.0
    assert note.arc_center_mm == (0.0, 0.0)


def test_relief_id_leader_reaches_the_u_unfenced() -> None:
    """The block stands where the 10.50's callout stood (left of the plate,
    right of the 195.09 line, over its pivot witness); its leader roots on
    the first line and drops to the U's round end at 135 deg, clear of
    detail B's circle.  With the 10.50 on the hole-location plan its line
    fenced the U on three sides: this leader crossed it."""
    note = drawing.RELIEF_ID_NOTE
    box = _note_box(note)
    line_195, pivot_witness_y = 0.1300, 0.13766
    assert box[0] - line_195 >= 0.002
    assert box[1] - pivot_witness_y >= 0.002
    east_edge = min(
        drawing.plan_xy(drawing.FEATURE_CENTER, drawing.plate_edge_mm(z, -1), z)[0]
        for z in (0.0, -(box[3] - pivot_witness_y) / drawing.PLAN_SCALE)
    )
    assert east_edge - box[2] >= 0.002
    pivot = drawing.plan_xy(drawing.FEATURE_CENTER, 0.0, 0.0)
    tip = drawing.arc_note_tip(note)
    assert math.dist(tip, pivot) == pytest.approx(
        spec.PIVOT_BEARING_RELIEF_DIAMETER / 2.0 * drawing.PLAN_SCALE
    )
    assert tip[1] > pivot[1]  # the round end, over the pivot
    leader = drawing.arc_note_leader(note, box[2] - box[0])
    assert leader[0] == (box[2], box[3] - drawing.NOTE_LEADER_ROOT_DROP)
    detail_b = drawing.plan_xy(drawing.FEATURE_CENTER, 0.0, spec.TIP_SCREW_LOCAL_Z)
    b_radius = drawing.DETAIL_RADIUS_MM * drawing.PLAN_SCALE
    assert _drawing_leaders.distance_to_point(leader, detail_b) - b_radius >= 0.002
    assert "PivotBearingReliefDia" not in drawing.FEATURE_KEEP
    # Positive control: the 10.50's line where it stood on this plan (y
    # 0.1413, from its left tail to a value at x 0.195).
    old_line = ((0.1678, 0.1413), (0.195, 0.1413))
    assert _drawing_leaders.segments_cross(leader, old_line)


def test_the_10_50_prints_over_the_profile_u() -> None:
    """On the profile the 10.50 stands 1 mm over the relief's round end,
    its value right of the plate: clear of the R8.0, above the 11.0's
    witness top, well under the C-C line."""
    assert drawing.DIMENSION_OWNER["PivotBearingReliefDia"] == "profile plan"
    x, y = drawing.PROFILE_KEEP["PivotBearingReliefDia"]
    pivot = drawing.PROFILE_PIVOT_XY
    half = spec.PIVOT_BEARING_RELIEF_DIAMETER / 2.0 * drawing.PLAN_SCALE
    assert y - (pivot[1] + half) == pytest.approx(0.001, abs=2e-4)
    text = drawing._centred_box((x, y), (len("10.50") * _DIM_CHAR_W, _DIM_GLYPH_H))
    assert text[0] - (pivot[0] + half) >= 0.004
    west_edge = drawing.plan_xy(
        drawing.PROFILE_CENTER, drawing.plate_edge_mm(-(y - pivot[1]) / drawing.PLAN_SCALE, 1), 0.0
    )[0]
    assert text[0] - west_edge >= 0.002
    r8 = drawing._centred_box(drawing.PROFILE_KEEP["CornerNWR"], (0.0151, 0.0035))
    assert _box_gap(text, r8) >= 0.005
    assert text[1] - _D382_NORTH_WEST_X_WITNESS[1][1] >= 0.004
    cc_y = drawing.plan_xy(drawing.PROFILE_CENTER, 0.0, spec.TIP_SCREW_LOCAL_Z)[1]
    assert cc_y - text[3] >= 0.004


def test_tip_slot_station_prints_on_the_notch_plan_off_the_plate() -> None:
    """I31: 27.7 south of the pivot the slot left detail B's circle, so its
    station prints on the notch plan's open east side: the dimension line
    stands off the plate's east edge at the slot, and its value sits centred
    on the line inside the span.  (It used to hang left of the line, south of
    the span, on a shoulder that ended in a T on the hole-location plan's
    189.26 line -- Main's MHA-091 eye pass of fix4b ruled it inside.)"""
    x, y = drawing.NOTCH_KEEP["TipSlotZ"]
    pivot = drawing.plan_xy(drawing.NOTCH_CENTER, 0.0, 0.0)
    slot = drawing.plan_xy(drawing.NOTCH_CENTER, -spec.TIP_SCREW_HALF_TRAVEL, spec.TIP_SCREW_LOCAL_Z)
    east_edge = drawing.plan_xy(
        drawing.NOTCH_CENTER, drawing.plate_edge_mm(spec.TIP_SCREW_LOCAL_Z, -1), 0.0
    )[0]
    assert x <= east_edge - 0.008
    text = (x - 0.0065, y - 0.0025, x + 0.0065, y + 0.0025)  # "27.70", 13 x 5 mm
    assert pivot[1] < text[1] and text[3] < slot[1]  # inside the span
    assert text[2] <= east_edge - 0.002
    # Clear of the notch plan's other texts and the feature plan's.
    for name, (kx, ky) in drawing.NOTCH_KEEP.items():
        if name != "TipSlotZ":
            assert not _boxes_overlap(text, (kx - 0.0065, ky - 0.0025, kx + 0.0065, ky + 0.0025))
    # The plan mapping agrees with the profile pivot the layout was measured on.
    assert drawing.plan_xy(drawing.PROFILE_CENTER, 0.0, 0.0) == pytest.approx(
        drawing.PROFILE_PIVOT_XY, abs=0.0005
    )


def test_tip_slot_moves_under_the_flange_slot_and_takes_a_hex_head() -> None:
    """I31 option 1: the lateral slot sits under the tip block's flange slot;
    the counterbored slot is one hex width across so the head cannot turn."""
    assert spec.TIP_SCREW_LOCAL_Z == pytest.approx(-11.0 - (6.0 + 10.7))
    assert spec.TIP_CBORE_W == 6.5
    assert spec.TIP_CBORE_DEPTH == 3.00
    assert spec.TIP_SCREW_HEAD_AF == pytest.approx((6.1976, 6.35))
    assert spec.TIP_CBORE_W >= spec.TIP_SCREW_HEAD_AF[1] - 1e-9
    assert spec.TIP_CBORE_W + 0.10 < spec.TIP_SCREW_HEAD_AC_MIN
    assert spec.TIP_HEAD_RECESS == pytest.approx(3.00 - 0.51 - 3.0 / 32.0 * 25.4)
    assert spec.TIP_HEAD_RECESS >= 0.1
    assert spec.TIP_LEDGE_RANGE == pytest.approx((2.71, 3.99))
    # (upper, lower) like every _fit_limits band; set through deviations().
    assert spec.TIP_SLOT_W_BAND == (0.10, 0.0)
    assert spec.TIP_CBORE_W_BAND == (0.10, 0.0)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '("TipScrewSlotProfile", "TipSlotW", TIP_SLOT_W_BAND)' in source
    assert '("TipScrewCboreProfile", "TipCboreW", TIP_CBORE_W_BAND)' in source
    assert "*deviations(band)" in source
    # Spelled apart so this source carries no band splat of its own.
    for band in ("TIP_SLOT_W_BAND", "TIP_CBORE_W_BAND"):
        assert "*" + band not in source


# The screw-head fits at the printed worst case, as numbers: a 4.0 +0.10/0
# slot and a 6.35 +0.10/0 counterbore slot against the 0.244-0.250 head
# across the flats (0.272 min across the corners).
_HEAD_FIT_WORST = {
    "TIP_SLOT_W_MAX": 4.10,
    "TIP_CBORE_W_MIN": 6.50,
    "TIP_CBORE_W_MAX": 6.60,
    "TIP_SLOT_FLOAT_MAX": (4.10 - 3.505) / 2.0,  # 0.2975
    "TIP_SLOT_HEAD_BEARING": (0.244 * 25.4 - 4.10) / 2.0,  # 1.0488
    # Running clearance: the narrowest 6.5 slot against the widest 1/4 head.
    "TIP_CBORE_HEAD_ENTRY": 6.50 - 0.250 * 25.4,  # 0.15
    # Anti-turn: the smallest head's corners against the widest slot.
    "TIP_CBORE_HEAD_TURN_MARGIN": 0.272 * 25.4 - 6.60,  # 0.3088
}


def _head_fit(namespace) -> dict[str, float]:
    return {name: getattr(namespace, name) for name in _HEAD_FIT_WORST}


def test_head_fit_holds_at_the_printed_worst_case() -> None:
    """dtscout / Main (I31): every band is read through deviations(), and
    the head's bearing, entry and anti-turn margin are pinned at their worst
    case.  Dropping the upper deviation makes each read 0.05 or 0.10 kinder."""
    assert _head_fit(spec) == pytest.approx(_HEAD_FIT_WORST, abs=1e-9)


def _spec_with(old: str, new: str):
    import types

    source = Path(spec.__file__).read_text(encoding="utf-8")
    assert source.count(old) == 1, old
    module = types.ModuleType("cone_swing_platform_spec_mutant")
    module.__file__ = spec.__file__
    exec(compile(source.replace(old, new), spec.__file__, "exec"), module.__dict__)
    return module


@pytest.mark.parametrize(
    ("old", "new"),
    (
        # The pre-fix read: [1] taken as the upper deviation of the flipped band.
        (
            "_TIP_SLOT_W_LOWER, _TIP_SLOT_W_UPPER = deviations(TIP_SLOT_W_BAND)",
            "_TIP_SLOT_W_LOWER, _TIP_SLOT_W_UPPER = "
            + ", ".join("TIP_SLOT_W_BAND" + f"[{i}]" for i in (0, 1)),
        ),
        (
            "_TIP_CBORE_W_LOWER, _TIP_CBORE_W_UPPER = deviations(TIP_CBORE_W_BAND)",
            "_TIP_CBORE_W_LOWER, _TIP_CBORE_W_UPPER = "
            + ", ".join("TIP_CBORE_W_BAND" + f"[{i}]" for i in (0, 1)),
        ),
        # The upper deviation dropped altogether.
        ("TIP_SLOT_W_MAX = TIP_SLOT_W + _TIP_SLOT_W_UPPER", "TIP_SLOT_W_MAX = TIP_SLOT_W"),
        ("TIP_CBORE_W_MAX = TIP_CBORE_W + _TIP_CBORE_W_UPPER", "TIP_CBORE_W_MAX = TIP_CBORE_W"),
    ),
)
def test_head_fit_pin_catches_a_misread_band(old: str, new: str) -> None:
    try:
        mutant = _head_fit(_spec_with(old, new))
    except AssertionError:
        return  # an import-time floor caught the misread
    assert mutant != pytest.approx(_HEAD_FIT_WORST, abs=1e-9)


def test_hex_slot_limits_hold_both_ways() -> None:
    """Main (I31, 2026-09-25): the 6.5 cutter's slot at its widest keeps
    0.25 of the smallest head's corners (6.60 vs 6.91), and at its narrowest
    still runs the widest head (6.50 vs 6.35)."""
    assert spec.TIP_CBORE_HEAD_TURN_MARGIN >= spec.TIP_CBORE_ANTI_TURN_MIN == 0.25
    assert spec.TIP_CBORE_HEAD_ENTRY > 0.0
    assert round(spec.TIP_SCREW_HEAD_AC_MIN, 2) == 6.91


def test_counterbored_slot_webs_hold_at_the_printed_worst_case() -> None:
    assert set(part.TIP_CBORE_WEBS) == {"west edge", "east edge", "pivot relief"}
    assert min(part.TIP_CBORE_WEBS.values()) >= 2.0


def test_no_spec_reads_a_slot_band_by_index() -> None:
    import re

    for module in (spec, part, drawing):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert not re.search(r"_BAND\[", source), module.__name__


def test_lateral_travel_prose_matches_the_slot_constants() -> None:
    """#917 S1 (plan A1): the end centres go +/-2.0 -> +/-2.5, so +/-2.75 is
    the end centres plus the screw's float in the nominal 4.0 slot, and
    +/-2.24 the same with the .XX centres short."""
    assert spec.TIP_SCREW_HALF_TRAVEL == 2.5
    assert spec.TIP_LATERAL_TRAVEL == pytest.approx(2.5 + (4.0 - 3.505) / 2.0)
    assert round(spec.TIP_LATERAL_TRAVEL, 2) == 2.75
    assert round(spec.TIP_LATERAL_TRAVEL_WORST, 2) == 2.24
    comment = Path(spec.__file__).read_text(encoding="utf-8")
    assert "+/-2.75" in comment and "+/-2.24" in comment


def test_fit_up_reach_covers_the_ruled_process() -> None:
    """Plan A1 (FITUP_TIP_REACH): the worst-case lateral reach -- end centre,
    float in the narrowest slot, less the slot ends' and the block's
    PassageCenter .XX and FootTapX .X -- covers the T-A fit-up's +/-0.906."""
    reach = (
        spec.TIP_SCREW_HALF_TRAVEL
        + spec.TIP_SLOT_SCREW_CLEARANCE / 2.0
        - 0.51
        - 0.51
        - 0.8
    )
    assert reach >= 0.906
    # Positive control: the +/-2.0 ends gave 0.427.
    assert 2.0 + spec.TIP_SLOT_SCREW_CLEARANCE / 2.0 - 1.82 == pytest.approx(0.4275)


def test_the_counterbored_slot_webs_at_the_longer_travel() -> None:
    """U27 webs of the counterbored slot at +/-2.5.  The plan's "web to the
    pivot relief 1.96 -> 2.06" and "3.9 to the west edge at z -11" were read
    on integ, where the slot sat 11 south of the pivot with a 7.94 counterbore;
    round 6 put it 27.7 south with a 6.5 one, so the binding web is now the
    west edge's."""
    webs = part.TIP_CBORE_WEBS
    assert webs == pytest.approx(
        {"west edge": 7.900, "east edge": 9.964, "pivot relief": 18.13}, abs=1e-3
    )
    assert min(webs.values()) >= 2.0


def test_tip_block_north_travel_carries_the_collar_fit_up() -> None:
    """#917 S1: the block's north travel is the shaft tip from its collar face
    at .X, plus the post's cone-boss face-to-face at its printed grade (read
    from the post's own precision, not typed), plus the 0.05 transfer.  The
    plate imports neither the shaft nor the tip-block spec."""
    boss = spec.TITLE_BLOCK_BAND_BY_PLACES[
        cone_pivot_post_spec.DRAWING_PRECISION_BY_NAME["ConeBossLen"]
    ]
    assert boss == 0.8
    assert spec.TIP_BLOCK_NORTH_TRAVEL == pytest.approx(0.8 + boss + 0.05)
    assert round(spec.TIP_BLOCK_NORTH_TRAVEL, 2) == 1.65
    assert spec.TIP_BLOCK_NORTH_REACH_Z == pytest.approx(-11.0 + 6.0 + 1.65)
    source = Path(spec.__file__).read_text(encoding="utf-8")
    for forbidden in ("import cone_tip_block_spec", "from cone_tip_block_spec",
                      "import cone_gear_shaft_spec", "from cone_gear_shaft_spec"):
        assert forbidden not in source, forbidden


def test_north_west_half_width_keeps_the_block_on_the_plate_at_full_west_travel() -> None:
    """I31 item 8: the U30 slot let the block hang 0.19 over the west edge.
    The north-west half-width is derived from the block's full west reach --
    every float and every .XX location band (TipSlotWestCx, FlangeSlotX) --
    at its northmost station, plus 0.25, against the outline at the worst of
    its .X bands (Main, 2026-09-25)."""
    reach = (
        (2.5 + 0.51)  # TipSlotWestCx
        + (4.1 - 3.505) / 2.0  # screw float, widest plate slot
        + (5.0 / 32.0 * 25.4 + 0.10 - 3.505) / 2.0  # ... widest flange slot
        + (7.5 + 0.51)  # FlangeSlotX from the block's west face
    )
    assert spec.TIP_BLOCK_WEST_REACH == pytest.approx(reach)  # 11.599
    assert spec.TIP_BLOCK_NORTH_REACH_Z == pytest.approx(-3.35)
    assert part._WEST_HALF_N_REQUIRED == pytest.approx(11.5658, abs=1e-4)
    assert part.WEST_HALF_N == 11.6
    z = spec.TIP_BLOCK_NORTH_REACH_Z
    assert part.west_edge_x_worst(11.6, z) - reach >= 0.25
    # One place coarser misses the margin: the derivation, not a typed 11.6.
    assert part.west_edge_x_worst(11.5, z) - reach < 0.25
    # The worst outline is the nominal edge less its corner bands and the
    # north corner's station band: strictly inside the nominal.
    assert part.west_edge_x_worst(11.6, z) < part._west_edge_x(z) - 0.8
    # Positive controls: the U30 plate (8.0), the first I31 cut (9.0, floats
    # only) and the +/-2.0 slot's plate (11.0, #917 S1) all leave the block
    # over the worst-case edge; the 0.8 north travel's plate (11.5) is the
    # coarser place above.
    assert part.west_edge_x_worst(8.0, z) < reach
    assert part.west_edge_x_worst(9.0, z) < reach
    assert part.west_edge_x_worst(11.0, z) - reach < 0.25
    # The NW round ends north of the block, on the edge it was derived for.
    assert part.NW_ROUND_END_Z - 0.8 > z
    # The south end is untouched.
    assert part.WEST_HALF_S == 37.0


def test_detail_b_callouts_identify_features_without_size_or_cutter() -> None:
    """MHA-091 Fable review (63fb3bd2d): "END MILL" is a process, and the
    Ø4 / Ø6.5 callouts restated the banded 4.0 and 6.50 dimensions in another
    spelling.  The banded model dimensions own the widths; each leadered
    note only names its feature."""
    by_key = {note.key: note for note in drawing.CUTTER_NOTES}
    assert by_key["slot"].text == "SLOT THRU"
    assert by_key["cbore"].text == "C'BORE SLOT\nFROM UNDERSIDE"
    for note in drawing.CUTTER_NOTES:
        assert "END MILL" not in note.text
        assert "<MOD-DIAM>" not in note.text
        assert not any(ch.isdigit() for ch in note.text)
    widths = spec.DRAWING_DIMENSIONS
    assert "TipSlotW" in widths["TipScrewSlotProfile"]
    assert "TipCboreW" in widths["TipScrewCboreProfile"]


# The profile's pivot end as d382 printed it (tipslot-d382-leaf.log:261 and
# :302-342): the R8.0 fillet centre, and the 11.0 (NorthWestX) with its west
# witness at x 0.0773 rising to 0.1332 under the corner.
_D382_NW_FILLET_CENTRE = (0.07373, 0.13816)
_D382_NORTH_WEST_X_WITNESS = ((0.0773, 0.1112), (0.0773, 0.1332))
_D382_NORTH_WEST_X_TEXT = (0.0942, 0.1122, 0.1093, 0.1157)


def test_the_r8_0_stands_near_its_corner() -> None:
    """MHA-091 Fable review minor: the R8.0 leader ran ~58 mm from the corner
    across the 11.0's field (d382: shoulder to x 0.1409).  Its text now sits
    by the corner: the ray still meets the fillet between its tangents, the
    leader stays 2 mm off the 11.0's witness top and text."""
    text = drawing.PROFILE_KEEP["CornerNWR"]
    centre = _D382_NW_FILLET_CENTRE
    shoulder_y = text[1] - drawing.LEADER_SHOULDER_DROP
    knee = (text[0] - drawing.LEADER_SHOULDER_HALF, shoulder_y)
    far = (text[0] + drawing.LEADER_SHOULDER_HALF, shoulder_y)
    angle = math.degrees(math.atan2(knee[1] - centre[1], knee[0] - centre[0]))
    assert -80.0 < angle < -10.0
    unit = ((knee[0] - centre[0]), (knee[1] - centre[1]))
    length = math.hypot(*unit)
    radius = 8.0 * drawing.PLAN_SCALE
    arc_point = (centre[0] + radius * unit[0] / length, centre[1] + radius * unit[1] / length)
    leader = [(arc_point, knee), (knee, far)]
    assert far[0] - arc_point[0] < 0.035  # d382: 0.0674
    for segment in leader:
        assert _drawing_leaders.distance_to_point(segment, _D382_NORTH_WEST_X_WITNESS[1]) >= 0.002
        assert _drawing_leaders.distance_to_box(segment, _D382_NORTH_WEST_X_TEXT) >= 0.002
        assert not _drawing_leaders.segments_cross(segment, _D382_NORTH_WEST_X_WITNESS)
    box = drawing._centred_box(text, (0.0151, 0.0035))
    assert _box_gap(box, _D382_NORTH_WEST_X_TEXT) >= 0.005


def test_feature_plan_caption_names_what_the_view_carries() -> None:
    """#917 S1: the post taps are transferred and the dowels match-reamed, so
    the feature plan keeps no location dimension; it carries the pivot, tap
    and dowel hole callouts.  Its caption says so instead of promising
    locations."""
    assert drawing.FEATURE_KEEP == {}
    assert "LOCATION" not in spec.FEATURE_VIEW_NOTE
    assert spec.FEATURE_VIEW_NOTE == "HOLES — SCALE 1:2"
    assert not any(ch.isdigit() for ch in spec.FEATURE_VIEW_NOTE.split("SCALE")[0])
