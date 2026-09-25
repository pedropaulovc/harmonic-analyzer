"""Offline manufacturing contracts for the cone-swing-platform package."""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path

import _config
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
    view_sets = (
        set(drawing.PROFILE_KEEP),
        set(drawing.FEATURE_KEEP),
        set(drawing.NOTCH_KEEP),
        set(drawing.SECTION_KEEP),
        set(drawing.DETAIL_KEEP),
        set(drawing.SLOT_SECTION_KEEP),
    )
    kept = set().union(*view_sets)
    assert kept == marked
    assert sum(len(names) for names in view_sets) == len(kept)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert spec.DRAWING_PRECISION_BY_NAME["PlateLenDim"] == 1
    assert set(spec.DRAWING_PRECISION_BY_NAME.values()) == {1, 2}


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
    assert spec.DRAWING_PRECISION["PostMountHoles"] == {
        "PostMountWestX": 2,
        "PostMountWestZ": 2,
        "PostMountEastX": 2,
        "PostMountEastZ": 2,
    }






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
        "TOP PIVOT RELIEF: MATCH DEPTH TO FINISHED PLATE"
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


def _notch_plan_sheet(x_mm: float, z_mm: float) -> tuple[float, float]:
    """Model plan (x, z) on the notch plan: sheet +x is west, +y is south.

    The notch plan is the profile's *Top view at 1:2, so its pivot sits at the
    profile's measured pivot offset from its own view centre.
    """
    pivot = (
        drawing.NOTCH_CENTER[0] + drawing.PROFILE_PIVOT_XY[0] - drawing.PROFILE_CENTER[0],
        drawing.NOTCH_CENTER[1] + drawing.PROFILE_PIVOT_XY[1] - drawing.PROFILE_CENTER[1],
    )
    return (pivot[0] + x_mm / 2000.0, pivot[1] - z_mm / 2000.0)


def _angle_text_box(center: tuple[float, float]) -> tuple[float, float, float, float]:
    """ "9.11°" at the dimension glyph size, centred on its text point."""
    half_w = len(f"{part.NOTCH_RUN_DEG:.2f}°") * _CHAR_W / 2.0
    return (
        center[0] - half_w,
        center[1] - _GLYPH_H / 2.0,
        center[0] + half_w,
        center[1] + _GLYPH_H / 2.0,
    )


def _distance_to_line(
    point: tuple[float, float], start: tuple[float, float], direction: tuple[float, float]
) -> float:
    dx, dy = point[0] - start[0], point[1] - start[1]
    return abs(dx * direction[1] - dy * direction[0]) / math.hypot(*direction)


def test_notch_run_angle_gives_the_rails_their_direction() -> None:
    """PR #830 Codex P1: the notch plan printed where the notch starts, not
    which way it runs.  92a84f6dc replaced the "AXIS 9.11 DEG" note with the
    model-owned NotchRunAngle; abde20e3c dropped it from all three contracts
    and nothing took its place.  It is marked, carries its places, and is
    kept on the notch plan with its text inside the acute sector (a text
    point outside prints the supplement: d22701cf8's sheet-spanning arc).
    """
    assert "NotchRunAngle" in spec.DRAWING_DIMENSIONS["LockNotchProfile"]
    assert spec.DRAWING_PRECISION_BY_NAME["NotchRunAngle"] == 2
    assert f"{part.NOTCH_RUN_DEG:.2f}" == "9.11"
    text = drawing.NOTCH_KEEP["NotchRunAngle"]

    # The vertex is the north rail's closed-end corner: the cap centre less
    # half the slot width along the run's left normal (-TZ, TX).
    half_w = part.SLOT_W / 2.0
    assert part.NOTCH_ANGLE_VERTEX_XZ == pytest.approx(
        (part.SLOT_E_X - part._SLOT_TZ * half_w, part.SLOT_E_Z + part._SLOT_TX * half_w)
    )
    vertex = _notch_plan_sheet(*part.NOTCH_ANGLE_VERTEX_XZ)
    run = math.radians(part.NOTCH_RUN_DEG)
    ray = (1.0, 0.0)  # model west
    run_dir = (math.cos(run), -math.sin(run))  # west and north: sheet down
    to_text = (text[0] - vertex[0], text[1] - vertex[1])
    assert to_text[0] * ray[1] - to_text[1] * ray[0] > 0.0  # below the ray
    assert run_dir[0] * to_text[1] - run_dir[1] * to_text[0] > 0.0  # above the run
    # 1 mm from both sides, so a 0.5 mm view drift cannot leave the sector.
    assert _distance_to_line(text, vertex, ray) >= 0.001
    assert _distance_to_line(text, vertex, run_dir) >= 0.001

    # The text clears the 205.81 cap-centre witness and that dimension's line.
    box = _angle_text_box(text)
    cap_witness_y = _notch_plan_sheet(part.SLOT_E_X, part.SLOT_E_Z)[1]
    cap_dimension_x = drawing.NOTCH_KEEP["CapECz"][0]
    assert cap_witness_y - box[3] >= 0.0018
    assert cap_dimension_x - box[2] >= 0.0018
    west_edge_x = _notch_plan_sheet(part._west_edge_x(part.SLOT_E_Z), 0.0)[0]
    assert box[0] - west_edge_x >= 0.005

    # Positive control: off the SOUTH rail's corner the same bisector point
    # lands on the witness -- why the vertex moved to the north rail.
    south = _notch_plan_sheet(
        part.SLOT_E_X + part._SLOT_TZ * half_w, part.SLOT_E_Z - part._SLOT_TX * half_w
    )
    south_text = (south[0] + to_text[0], south[1] + to_text[1])
    south_box = _angle_text_box(south_text)
    assert south_box[1] < cap_witness_y < south_box[3]


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


def _note_box(note: drawing.CutterNote) -> tuple[float, float, float, float]:
    lines = note.text.replace("<MOD-DIAM>", "D").split("\n")
    x, y = note.text_xy
    width = max(len(line) for line in lines) * _NOTE_CHAR_W
    return (x, y - len(lines) * _NOTE_LINE_H, x + width, y)


def _note_extent(note: drawing.CutterNote) -> tuple[float, float, float, float]:
    """What INote.GetExtent -- the audit's box -- spans: text plus leader tip.

    ec70186e logged the one-line slot note as [89.2, 59.1]..[158.9, 79.1] mm:
    its leader tip on the arc up to 0.6 mm above its text anchor.
    """
    x0, y0, x1, y1 = _note_box(note)
    tip = drawing.cutter_note_tip(note)
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


def _leader_fan(note: drawing.CutterNote):
    """The leader from its arc tip to each end of the note's left edge."""
    tip = drawing.cutter_note_tip(note)
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
        tip = drawing.cutter_note_tip(note)
        assert math.dist(tip, centre) == pytest.approx(note.radius_mm * 0.002)
        assert -90.0 < note.tip_deg < 90.0  # the west (sheet-right) end arc
        model = drawing.cutter_note_model_tip(note)
        assert math.hypot(
            model[0] - spec.TIP_SCREW_HALF_TRAVEL / 1000.0,
            model[2] - spec.TIP_SCREW_LOCAL_Z / 1000.0,
        ) == pytest.approx(note.radius_mm / 1000.0)
    # The slot note rises from the upper quadrant, the counterbore note drops
    # from the lower one (their audit extents must not nest, ec70186e).
    assert by_key["slot"].tip_deg > 0.0 > by_key["cbore"].tip_deg
    assert drawing.cutter_note_tip(by_key["slot"])[1] > drawing._SLOT_Y
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


def test_slot_section_cut_keeps_its_plane_and_crosses_the_plate() -> None:
    """Section C-C cuts at the slot station, edge to edge (8783776d eye-pass).

    The plane is the one detail B carried; the line now runs past both plate
    edges, so the strip is the full plate width at the slot (32.28 mm since
    I31 moved the slot to -27.7 and widened the north-west) and needs no
    symmetry.
    """
    z = spec.TIP_SCREW_LOCAL_Z
    ends = drawing.slot_section_line_model_points()
    assert all(end[1:] == (spec.PLATE_THICKNESS / 1000.0, z / 1000.0) for end in ends)
    east, west = drawing.plate_edge_mm(z, -1), drawing.plate_edge_mm(z, +1)
    assert ends[0][0] * 1000.0 < east and ends[1][0] * 1000.0 > west
    assert west - east == pytest.approx(32.28, abs=0.01)
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
    r10_leader = ((0.051, 0.139), (0.0686 - 0.00354, 0.1392 - 0.00354))
    r8_leader = ((0.135, 0.118), (0.0723 + 0.00283, 0.1382 - 0.00283))
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


def test_tip_slot_station_prints_on_the_notch_plan_off_the_plate() -> None:
    """I31: 27.7 south of the pivot the slot left detail B's circle, so its
    station prints on the notch plan's open east side: the dimension line
    stands off the plate's east edge at the slot, and its value hangs left of
    it just south of the span, outside it."""
    x, y = drawing.NOTCH_KEEP["TipSlotZ"]
    pivot = drawing.plan_xy(drawing.NOTCH_CENTER, 0.0, 0.0)
    slot = drawing.plan_xy(drawing.NOTCH_CENTER, -spec.TIP_SCREW_HALF_TRAVEL, spec.TIP_SCREW_LOCAL_Z)
    east_edge = drawing.plan_xy(
        drawing.NOTCH_CENTER, drawing.plate_edge_mm(spec.TIP_SCREW_LOCAL_Z, -1), 0.0
    )[0]
    assert x <= east_edge - 0.008
    text = (x - 0.013, y - 0.0025, x, y + 0.0025)  # "27.70", 12 x 5 mm
    assert text[1] >= slot[1] and slot[1] > pivot[1]  # south of the span
    # Clear of the notch plan's other texts and the feature plan's.
    for name, (kx, ky) in drawing.NOTCH_KEEP.items():
        if name != "TipSlotZ":
            assert not _boxes_overlap(text, (kx - 0.0065, ky - 0.0025, kx + 0.0065, ky + 0.0025))
    post_west_z = drawing.FEATURE_KEEP["PostMountWestZ"]
    assert not _boxes_overlap(text, (post_west_z[0], post_west_z[1] - 0.0025, post_west_z[0] + 0.013, post_west_z[1] + 0.0025))
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
    """I31 item 7: +/-2.25 is the end centres (2.0) plus the screw's float in
    the nominal 4.0 slot; +/-1.74 is the same with the .XX centres short."""
    assert spec.TIP_SCREW_HALF_TRAVEL == 2.0
    assert spec.TIP_LATERAL_TRAVEL == pytest.approx(2.0 + (4.0 - 3.505) / 2.0)
    assert round(spec.TIP_LATERAL_TRAVEL, 2) == 2.25
    assert round(spec.TIP_LATERAL_TRAVEL_WORST, 2) == 1.74
    comment = Path(spec.__file__).read_text(encoding="utf-8")
    assert "+/-2.25" in comment and "+/-1.74" in comment


def test_north_west_half_width_keeps_the_block_on_the_plate_at_full_west_travel() -> None:
    """I31 item 8: the U30 slot let the block hang 0.19 over the west edge.
    The north-west half-width is derived from the block's full west reach --
    every float and every .XX location band (TipSlotWestCx, FlangeSlotX) --
    at its northmost station, plus 0.25, against the outline at the worst of
    its .X bands (Main, 2026-09-25)."""
    reach = (
        (2.0 + 0.51)  # TipSlotWestCx
        + (4.1 - 3.505) / 2.0  # screw float, widest plate slot
        + (5.0 / 32.0 * 25.4 + 0.10 - 3.505) / 2.0  # ... widest flange slot
        + (7.5 + 0.51)  # FlangeSlotX from the block's west face
    )
    assert spec.TIP_BLOCK_WEST_REACH == pytest.approx(reach)  # 11.099
    assert spec.TIP_BLOCK_NORTH_REACH_Z == pytest.approx(-4.2)
    assert part._WEST_HALF_N_REQUIRED == pytest.approx(10.9403, abs=1e-4)
    assert part.WEST_HALF_N == 11.0
    z = spec.TIP_BLOCK_NORTH_REACH_Z
    assert part.west_edge_x_worst(11.0, z) - reach >= 0.25
    # One place coarser misses the margin: the derivation, not a typed 11.0.
    assert part.west_edge_x_worst(10.9, z) - reach < 0.25
    # The worst outline is the nominal edge less its corner bands and the
    # north corner's station band: strictly inside the nominal.
    assert part.west_edge_x_worst(11.0, z) < part._west_edge_x(z) - 0.8
    # Positive controls: the U30 plate (8.0) and the first I31 cut (9.0,
    # floats only) both leave the block over the worst-case edge.
    assert part.west_edge_x_worst(8.0, z) < reach
    assert part.west_edge_x_worst(9.0, z) < reach
    # The NW round ends north of the block, on the edge it was derived for.
    assert part.NW_ROUND_END_Z - 0.8 > z
    # The south end is untouched.
    assert part.WEST_HALF_S == 37.0
