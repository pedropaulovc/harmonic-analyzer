"""Offline manufacturing contracts for the cone-swing-platform package."""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path

import _config
import _drawing_leaders
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
    kept on the notch plan with its anchor inside the acute sector (a text
    point outside prints the supplement: d22701cf8's sheet-spanning arc).
    Since tipslot-d382 the value itself prints on a leader at
    NOTCH_ANGLE_TEXT_XY; that is what must clear the 205.81.
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

    # The printed value clears the 205.81 cap-centre witness and that
    # dimension's line.
    box = _angle_text_box(drawing.NOTCH_ANGLE_TEXT_XY)
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


# tipslot-d382 (d38223cf9) as it printed, sheet metres: the "9.11°" glyphs,
# measured off the 300-dpi render
# (C:/src/dt-logs/tipslot-d382/platform-crop-notch-angle-300dpi.png), and the
# run angle's and the 205.81's ink from the leaf's describe_sheet dump
# (C:/src/dt-logs/spring/tipslot-d382-leaf.log:408-427).
_D382_NOTCH_INK = drawing.SheetInk(
    texts={"NotchRunAngle": (0.29169, 0.23500, 0.30226, 0.23850)},
    lines={
        "NotchRunAngle": [
            ((0.2840, 0.2386), (0.2980, 0.2386)),  # the ray's extension
            ((0.2773, 0.2379), (0.2977, 0.2346)),  # the run's extension
        ],
        "CapECz": [
            ((0.2743, 0.2406), (0.3060, 0.2406)),  # the upper witness
            ((0.3050, 0.2406), (0.3050, 0.1828)),  # the dimension line
            ((0.3050, 0.1772), (0.3050, 0.1377)),  # its lower leg, under the text
            ((0.2607, 0.1377), (0.3060, 0.1377)),  # the pivot's witness
        ],
    },
    arcs={
        "NotchRunAngle": [
            ((0.2970, 0.2386), (0.2962, 0.2448)),
            ((0.2967, 0.2348), (0.2949, 0.2288)),
        ]
    },
    arrows={
        "NotchRunAngle": [
            ((0.29690, 0.23859), (0.29666, 0.24199)),
            ((0.29667, 0.23478), (0.29590, 0.23148)),
        ],
        "CapECz": [((0.3050, 0.24058), (0.3050, 0.23707))],
    },
    leaders={},
)

# tipslot-fix3 (31620449b) as the seat read it back after the offset, sheet
# metres, verbatim from C:/src/dt-logs/spring/tipslot-fix3-leaf.log: line 256
# (text position, arcs_after, lines_before) and line 224 (the leader the
# offset added, and the angle's arrowheads spanned both ways).  The arcs are
# listed twice, as the seat returned them.
_FIX3_TEXT_XY = (0.29533335673167244, 0.23599046239978697)
_FIX3_LEAF_INK = drawing.SheetInk(
    texts={"NotchRunAngle": drawing._centred_box(_FIX3_TEXT_XY, drawing.NOTCH_ANGLE_TEXT_SIZE)},
    lines={
        "NotchRunAngle": [
            ((0.27730084362274565, 0.237897309256219), (0.28774487224137074, 0.23622267237731215)),
            ((0.28397792979966785, 0.2385904623656956), (0.28793349794352835, 0.2385904623656956)),
        ]
    },
    arcs={
        "NotchRunAngle": [
            ((0.2844536244334673, 0.23064903208584542), (0.28675748464768946, 0.23638099401147591)),
            ((0.28693349794352835, 0.2385904623656956), (0.28556618852945975, 0.24461488137251708)),
            ((0.2844536244334673, 0.23064903208584542), (0.28675748464768946, 0.23638099401147591)),
            ((0.28693349794352835, 0.2385904623656956), (0.28556618852945975, 0.24461488137251708)),
        ]
    },
    arrows={
        "NotchRunAngle": [
            ((0.2877529809078759, 0.23979480759688956), (0.28576198838750305, 0.23296718042606226)),
            ((0.28737595805481936, 0.2350620965896009), (0.28649103783223734, 0.24211882814179028)),
        ]
    },
    leaders={
        "NotchRunAngle": [
            ((0.28688942502648596, 0.23748222828746463), (0.2885812731879844, 0.23321233740425734)),
            ((0.2885812731879844, 0.23321233740425734), (0.30208544027536055, 0.23321233740425734)),
        ]
    },
)


def _same_stroke(got, want, tolerance: float = 0.0003) -> bool:
    """One segment on another, either way round (the seat lists an arc from
    its tail end or from its arrow)."""
    forward = max(math.dist(got[0], want[0]), math.dist(got[1], want[1]))
    backward = max(math.dist(got[0], want[1]), math.dist(got[1], want[0]))
    return min(forward, backward) < tolerance


def test_the_fix3_leaf_fails_the_ink_audit() -> None:
    """tipslot-fix3-3162 failed on the seat, and the audit was right: the
    leader's leg to its knee crosses the run's extension line."""
    findings = drawing.sheet_ink_collisions(_FIX3_LEAF_INK)
    assert "leader-on-ink: NotchRunAngle's leader crosses NotchRunAngle lines" in findings
    leg = _FIX3_LEAF_INK.leaders["NotchRunAngle"][0]
    run = _FIX3_LEAF_INK.lines["NotchRunAngle"][0]
    assert _drawing_leaders.segments_cross(leg, run)


def test_the_notch_ink_model_reproduces_fix3() -> None:
    """At fix3's 14 mm anchor and text, the model draws the seat's ink --
    the leader rooted at the arc's midpoint, its knee under the value's near
    end, the shoulder under the value, the ~6.2 mm tails -- and fails the
    same way.  fix3's model (a straight leader to the nearest point of the
    value) did not; the extension lines' 1 mm overshoot was already in it."""
    vertex = drawing.NOTCH_ANGLE_VERTEX_XY
    anchor = drawing._polar(vertex, 0.014, -part.NOTCH_RUN_DEG / 2.0)
    text = (vertex[0] + 0.0224, vertex[1] - 0.0026)
    assert math.dist(text, _FIX3_TEXT_XY) < 0.0001
    predicted = drawing.notch_angle_ink(text, anchor_xy=anchor, cap_text_xy=(0.305, 0.180))
    for got, want in zip(
        predicted.leaders["NotchRunAngle"], _FIX3_LEAF_INK.leaders["NotchRunAngle"], strict=True
    ):
        assert _same_stroke(got, want), (got, want)
    for field in ("lines", "arcs"):
        model = getattr(predicted, field)["NotchRunAngle"]
        measured = getattr(_FIX3_LEAF_INK, field)["NotchRunAngle"]
        assert all(any(_same_stroke(m, w) for m in model) for w in measured), field
        assert all(any(_same_stroke(m, w) for w in measured) for m in model), field
    assert "leader-on-ink: NotchRunAngle's leader crosses NotchRunAngle lines" in (
        drawing.sheet_ink_collisions(predicted)
    )


def test_the_d382_run_angle_fails_the_ink_audit() -> None:
    """Main's eye pass of tipslot-d382: the value's own run line struck
    through it, the ray's ran over it.  Planted as measured, the audit the
    build now runs names both."""
    findings = drawing.sheet_ink_collisions(_D382_NOTCH_INK)
    assert "text-on-line: NotchRunAngle's line runs through 'NotchRunAngle'" in findings
    # The strike itself: the run's extension crosses the glyphs.
    ray, run = _D382_NOTCH_INK.lines["NotchRunAngle"]
    box = _D382_NOTCH_INK.texts["NotchRunAngle"]
    assert _drawing_leaders.distance_to_box(run, box) == 0.0
    assert _drawing_leaders.distance_to_box(ray, box) < drawing.LINE_TEXT_CLEARANCE


def test_the_notch_ink_model_reproduces_d382() -> None:
    """The predicted ink, at d382's anchor, lands on what d382 printed --
    so the model the placement is checked against is the sheet's."""
    predicted = drawing.notch_angle_ink(
        None, anchor_xy=(0.2969, 0.2367), cap_text_xy=(0.305, 0.180)
    )
    for field in ("lines", "arcs", "arrows"):
        for owner, measured in getattr(_D382_NOTCH_INK, field).items():
            model = getattr(predicted, field)[owner]
            assert len(model) == len(measured), (field, owner)
            for got, want in zip(model, measured):
                for end in (0, 1):
                    assert math.dist(got[end], want[end]) < 0.0003, (field, owner, got, want)
    text = predicted.texts["NotchRunAngle"]
    assert all(
        abs(a - b) < 0.0003 for a, b in zip(text, _D382_NOTCH_INK.texts["NotchRunAngle"])
    )
    assert drawing.sheet_ink_collisions(predicted) != []


def test_the_run_angle_value_prints_clear_on_its_leader() -> None:
    """The fix: a 32 mm arc from the in-wedge anchor, the value low and far
    out, short of the 205.81 line.  Nothing touches it, no foreign arrow is
    within 2 mm, and the seat's leader shape -- arc midpoint, knee, shoulder
    -- crosses nothing, meets nothing in a T and keeps LEADER_INK_CLEARANCE
    (Main's 2.0 mm) off every stroke."""
    ink = drawing.notch_angle_ink(drawing.NOTCH_ANGLE_TEXT_XY)
    assert drawing.sheet_ink_collisions(ink) == []
    assert drawing.LEADER_INK_CLEARANCE == 0.002
    box = ink.texts["NotchRunAngle"]
    ray, run = ink.lines["NotchRunAngle"]
    # Past both extension lines' ends, 2.5 mm under the 205.81 witness
    # (Main, tipslot-fix4), and its arrowhead's 2 mm + half-width off the value.
    assert box[0] - max(ray[1][0], run[1][0]) >= 0.002
    cap_witness_y = ink.lines["CapECz"][0][0][1]
    assert cap_witness_y - box[3] >= 0.0025
    assert drawing.NOTCH_KEEP["CapECz"][0] - box[2] >= (
        drawing.ARROW_TEXT_CLEARANCE + drawing.NOTCH_ANGLE_ARROW_HALF_WIDTH
    )
    (root, knee), (_knee, far) = ink.leaders["NotchRunAngle"]
    assert math.dist(root, drawing.NOTCH_ANGLE_VERTEX_XY) == pytest.approx(
        drawing.NOTCH_ANGLE_ARC_RADIUS
    )
    # The knee lies past both extension lines' ends, the shoulder short of
    # the 205.81 line: the leg leaves the wedge through its open end.
    assert knee[0] > max(ray[1][0], run[1][0])
    assert drawing.NOTCH_KEEP["CapECz"][0] - far[0] >= drawing.LEADER_INK_CLEARANCE
    # The margins the layout was solved for (tipslot-fix4 reply to Main).
    assert drawing._segment_gap((root, knee), run) >= 0.0022
    assert drawing._segment_gap((root, knee), ray) >= 0.0025
    # The anchor still selects the acute sector, and its arc sits past the
    # hidden 10 mm construction ray, where the ray's extension line is drawn.
    assert drawing.NOTCH_KEEP["NotchRunAngle"] == drawing.NOTCH_ANGLE_ANCHOR_XY
    assert drawing.NOTCH_ANGLE_ARC_RADIUS > drawing.NOTCH_ANGLE_RAY_START + 0.002


@pytest.mark.parametrize(
    ("radius", "text_offset", "cap_text_xy", "gap_mm"),
    [
        # d382's 205.81 at x 0.305: the best any arc/value gave.
        (0.0115, (0.0242, -0.0018), (0.305, 0.180), "0.45"),
        # dbfc81fb2 (fix4 as first committed): 205.81 at x 0.313.
        (0.018, (0.0320, -0.0018), (0.313, 0.180), "1.13"),
    ],
)
def test_the_leader_clearance_is_why_the_205_81_moved(
    radius: float, text_offset: tuple[float, float], cap_text_xy: tuple[float, float], gap_mm: str
) -> None:
    """With the 205.81 at x 0.305 or 0.313 the best layout left the leg
    0.45 / 1.13 mm off the run's extension line's end: legal for the
    crossing rule, a near-miss on the sheet.  The clearance gate names it."""
    vertex = drawing.NOTCH_ANGLE_VERTEX_XY
    anchor = drawing._polar(vertex, radius, -part.NOTCH_RUN_DEG / 2.0)
    text = (vertex[0] + text_offset[0], vertex[1] + text_offset[1])
    ink = drawing.notch_angle_ink(text, anchor_xy=anchor, cap_text_xy=cap_text_xy)
    findings = drawing.sheet_ink_collisions(ink)
    assert not any(f.startswith("leader-on-ink") for f in findings)
    assert (
        f"leader-near-ink: NotchRunAngle's leader passes {gap_mm} mm from NotchRunAngle lines"
        in findings
    )


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
    fix4b = drawing.notch_angle_ink(drawing.NOTCH_ANGLE_TEXT_XY, iso_note_xy=_D382_ISO_NOTE_ANCHOR)
    assert "text-on-line: CapECz's line runs through 'Isometric View Note'" in (
        drawing.sheet_ink_collisions(fix4b)
    )


def test_the_moved_205_81_clears_the_isometric_and_the_section_note() -> None:
    """The 205.81 at x 0.327 and its neighbours, 2 mm apart: both legs pass
    left of the isometric view and its caption, its text sits under the view,
    its lower witness and arrowhead clear A-A's "(6.35)", and the view stays
    inside the border."""
    view = _iso_view_box()
    ink = drawing.notch_angle_ink(drawing.NOTCH_ANGLE_TEXT_XY)
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
        - drawing.NOTCH_ANGLE_ARROW_HALF_WIDTH
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
    ink = drawing.notch_angle_ink(drawing.NOTCH_ANGLE_TEXT_XY)
    text = drawing.NOTCH_KEEP["TipSlotZ"]
    assert text[0] == drawing.TIP_SLOT_Z_LINE_X
    lower, upper = ink.lines["TipSlotZ"]
    assert lower[0][1] < text[1] < upper[1][1]
    box = ink.texts["TipSlotZ"]
    assert box[0] - _D382_TIP_SLOT_Z_INK["PostMountWestZ lines"][0][0][0] >= 0.002
    for piece in (lower, upper):
        assert abs(piece[1][1] - piece[0][1]) >= drawing.NOTCH_ANGLE_ARROW_LENGTH + 0.0005
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
    model = drawing.notch_angle_ink(drawing.NOTCH_ANGLE_TEXT_XY, cap_dia_text_xy=(0.285, 0.259))
    assert any(f.startswith("arrow-near-text: CapECx's arrow") for f in (
        drawing.sheet_ink_collisions(model)
    ))


def test_the_33_00_tail_has_no_value_over_it() -> None:
    """The Ø8.00 left the notch plan: nothing stands over the 33.00's tail."""
    ink = drawing.notch_angle_ink(drawing.NOTCH_ANGLE_TEXT_XY)
    assert "CapEDia" not in ink.texts
    assert "CapEDia" not in drawing.NOTCH_KEEP
    assert drawing.DIMENSION_OWNER["CapEDia"] == "profile plan"
    assert not any("CapECx" in f for f in drawing.sheet_ink_collisions(ink))


# The profile plan's ink around the lock-notch cap, as d382 printed it
# (C:/src/dt-logs/spring/tipslot-d382-leaf.log:309-331; PROFILE_KEEP's other
# entries are unchanged since): the R5.0 (CornerSWR) leader from its arrow
# tip on the corner to its shoulder, its text; the 37.0 (SouthWestX) right
# witness and its line with the extension under its text; the 24.0
# (SouthEastX) line; the x 71.8 pivot witness both share.
# Their texts (estimated boxes) stay out of the audited ink: each sits on
# its own shoulder, which the audit would read as a line through it.
_D382_PROFILE_TEXTS = {
    "CornerSWR": (0.1041, 0.2462, 0.1192, 0.2497),
    "SouthWestX": (0.0982, 0.2552, 0.1133, 0.2587),
}
_D382_PROFILE_INK = drawing.SheetInk(
    texts={},
    lines={
        "SouthWestX": [
            ((0.0903, 0.2468), (0.0903, 0.2562)),
            ((0.0718, 0.1337), (0.0718, 0.2562)),
            ((0.0903, 0.2552), (0.0718, 0.2552)),
            ((0.0903, 0.2552), (0.1098, 0.2552)),
        ],
        "SouthEastX": [((0.0598, 0.2562), (0.0718, 0.2562)), ((0.0598, 0.2562), (0.0392, 0.2562))],
        "CornerSWR": [
            ((0.0875, 0.2433), (0.0899, 0.2438)),
            ((0.0899, 0.2438), (0.1025, 0.2462)),
            ((0.1025, 0.2462), (0.1159, 0.2462)),
        ],
    },
    arcs={},
    arrows={"CornerSWR": [((0.0875, 0.2433), (0.0908, 0.2440))]},
    leaders={},
)


def _profile_with_cap_dia(text_xy: tuple[float, float]) -> drawing.SheetInk:
    leader, arrow = drawing.cap_dia_ink(text_xy)
    ink = _D382_PROFILE_INK
    return drawing.SheetInk(
        texts={**ink.texts, "CapEDia": drawing.cap_dia_glyphs(text_xy)},
        lines=ink.lines,
        arcs=ink.arcs,
        arrows={**ink.arrows, "CapEDia": [arrow]},
        leaders={"CapEDia": leader},
    )


def test_the_profile_cap_is_where_the_seat_put_it() -> None:
    """The model's cap centre and radius against d382's notch-plan Ø8.00
    (the same projection, 185 mm left): its diameter ran (273.1, 238.6) to
    (273.5, 242.6) through (273.25, 240.57)."""
    cap = drawing.PROFILE_CAP_XY
    assert cap[0] + 0.185 == pytest.approx(0.27325, abs=5e-5)
    assert cap[1] == pytest.approx(0.24057, abs=5e-5)
    assert math.dist((0.2731, 0.2386), (0.2735, 0.2426)) / 2.0 == pytest.approx(
        drawing.CAP_ARC_RADIUS, abs=5e-5
    )
    # d382's arrow ends lay on the drawn half (the rails' tangent points).
    notch_cap = (cap[0] + 0.185, cap[1])
    for tip in ((0.2731, 0.2386), (0.2735, 0.2426)):
        assert drawing.on_drawn_cap_arc(tip, notch_cap)


def test_the_8_00_stands_east_of_the_profile_2_mm_off_its_neighbours() -> None:
    """The value below the R5.0, its leader out through the notch mouth:
    2 mm or more to every neighbour, the arrow on the drawn arc, the
    diameter's near end (where a first arrow would land) in the mouth."""
    text = drawing.PROFILE_KEEP["CapEDia"]
    ink = _profile_with_cap_dia(text)
    assert drawing.sheet_ink_collisions(ink) == []
    leader, arrow = drawing.cap_dia_ink(text)
    glyphs = ink.texts["CapEDia"]
    r5_text = _D382_PROFILE_TEXTS["CornerSWR"]
    (r5_arrow,) = ink.arrows["CornerSWR"]
    gaps = {
        "R5.0 arrow to the leader": min(
            _drawing_leaders.distance_to_point(s, r5_arrow[0]) for s in leader
        ) - drawing.NOTCH_ANGLE_ARROW_HALF_WIDTH,
        "R5.0 leader to the glyphs": min(
            _drawing_leaders.distance_to_box(s, glyphs) for s in ink.lines["CornerSWR"]
        ),
        "R5.0 text to the glyphs": _box_gap(r5_text, glyphs),
        "R5.0 text to the leader": min(_drawing_leaders.distance_to_box(s, r5_text) for s in leader),
        "37.0 witness to the glyphs": _drawing_leaders.distance_to_box(
            ink.lines["SouthWestX"][0], glyphs
        ),
    }
    gaps["37.0 text to the glyphs"] = _box_gap(_D382_PROFILE_TEXTS["SouthWestX"], glyphs)
    assert min(gaps.values()) >= 0.0022, gaps
    assert drawing.on_drawn_cap_arc(arrow[0])
    cap = drawing.PROFILE_CAP_XY
    near = (2.0 * cap[0] - arrow[0][0], 2.0 * cap[1] - arrow[0][1])
    assert not drawing.on_drawn_cap_arc(near)


def test_an_8_00_leader_up_the_drawn_side_crosses_the_37_0() -> None:
    """Fail-first for the placement: with the text above the cap -- the way
    whose near end stays on the drawn arc -- the leader crosses the 37.0's
    line and runs within 2 mm of its witness."""
    findings = drawing.sheet_ink_collisions(_profile_with_cap_dia((0.098, 0.2590)))
    assert "leader-on-ink: CapEDia's leader crosses SouthWestX lines" in findings


def test_the_arc_tail_crossing_the_205_81_witness_is_named_and_far_from_the_value() -> None:
    """Ruling (b): the ray-side tail crosses the 205.81 witness.  At least
    2 mm from the value -- beyond half its 3.5 mm text height -- so it is a
    named, reported crossing; nearer, or unnamed, it gates."""
    ink = drawing.notch_angle_ink(drawing.NOTCH_ANGLE_TEXT_XY)
    findings, reported = drawing.dimension_crossings(ink)
    assert findings == []
    assert len(reported) == 1
    head = "NotchRunAngle arcs x CapECz lines, at least "
    assert reported[0].startswith(head)
    gap_mm = float(reported[0][len(head) :].split(" mm", 1)[0])
    assert gap_mm > 0.5 * drawing.NOTCH_ANGLE_TEXT_SIZE[1] * 1000.0 + 0.5
    assert frozenset(("NotchRunAngle arcs", "CapECz lines")) in drawing.EXPECTED_DIMENSION_CROSSINGS
    # The value moved onto the crossing: it gates.
    witness_y = ink.lines["CapECz"][0][0][1]
    tail = ink.arcs["NotchRunAngle"][0]
    onto = drawing._centred_box((tail[0][0], witness_y + 0.002), drawing.NOTCH_ANGLE_TEXT_SIZE)
    at_value = dataclasses.replace(ink, texts={**ink.texts, "NotchRunAngle": onto})
    assert any(
        f.startswith("dimension-crossing: NotchRunAngle arcs x CapECz lines") and "within 1.75" in f
        for f in drawing.dimension_crossings(at_value)[0]
    )
    # An unnamed crossing gates wherever it is.
    ray = ink.lines["NotchRunAngle"][0]
    mid_x = (ray[0][0] + ray[1][0]) / 2.0
    stray = dataclasses.replace(
        ink, lines={**ink.lines, "Stray": [((mid_x, ray[0][1] - 0.003), (mid_x, ray[0][1] + 0.001))]}
    )
    assert any(
        f.startswith("dimension-crossing: NotchRunAngle lines x Stray lines")
        and f.endswith("not an expected crossing")
        for f in drawing.sheet_ink_collisions(stray)
    )


def test_the_leader_audit_counts_a_t_and_allows_its_own_arc() -> None:
    """_drawing_leaders' T rule (e33969f40): a leader ending on another line
    is a crossing; the one declared touch is the leader's own arc."""
    ink = drawing.notch_angle_ink(drawing.NOTCH_ANGLE_TEXT_XY)
    ray = ink.lines["NotchRunAngle"][0]
    on_ray = ((ray[0][0] + ray[1][0]) / 2.0, ray[0][1])
    tee = dataclasses.replace(
        ink, leaders={"NotchRunAngle": [(on_ray, (on_ray[0] + 0.004, on_ray[1] - 0.003))]}
    )
    assert "leader-on-ink: NotchRunAngle's leader crosses NotchRunAngle lines" in (
        drawing.sheet_ink_collisions(tee)
    )
    arc = ink.arcs["NotchRunAngle"][0]
    on_arc = ((arc[0][0] + arc[1][0]) / 2.0, (arc[0][1] + arc[1][1]) / 2.0)
    rooted = dataclasses.replace(
        ink, leaders={"NotchRunAngle": [(on_arc, (on_arc[0] + 0.004, on_arc[1] + 0.001))]}
    )
    assert not any("NotchRunAngle arcs" in f for f in drawing.sheet_ink_collisions(rooted))
    # Across the 205.81's line is a crossing too: why the value stops short.
    across = dataclasses.replace(
        ink,
        leaders={"NotchRunAngle": [(drawing.NOTCH_ANGLE_TEXT_XY, (0.335, 0.230))]},
    )
    assert "leader-on-ink: NotchRunAngle's leader crosses CapECz lines" in (
        drawing.sheet_ink_collisions(across)
    )


def test_the_build_audits_the_run_angle_ink_on_the_sheet() -> None:
    import inspect

    build = inspect.getsource(drawing.build)
    assert build.index("assert_notch_angle_ink_clear()") < build.index("open_model")
    wedge = build.index("_assert_notch_angle_in_wedge(adapter, notch, notch_annotations)")
    assert build.index("_offset_notch_angle_text(adapter, notch_annotations)") > wedge
    assert wedge < build.index("_pin_tip_slot_z_arrows_inside(adapter, notch_annotations)")
    # The captions go into the live text set once they exist.
    iso = build.index('"Isometric View Note", *ISO_NOTE_UPPER_LEFT)')
    captions = build.index("_assert_notch_captions_clear(")
    assert iso < captions
    assert '"Isometric View Note": iso_note' in build[captions:]
    audit = inspect.getsource(drawing._assert_notch_captions_clear)
    assert "GetExtent()" in audit and "sheet_ink_collisions(ink)" in audit
    assert "leader_segments(" in inspect.getsource(drawing._notch_strokes)
    offset = inspect.getsource(drawing._offset_notch_angle_text)
    assert 'offset_dimension_text(adapter, [angle], {"NotchRunAngle": NOTCH_ANGLE_TEXT_XY})' in offset
    assert "sheet_ink_collisions(ink)" in offset
    assert "dimension_crossings(ink)[1]" in offset
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
    2.9 mm left on the sheet: the old x309 missed the witness window."""
    east, west = drawing.pivot_section_strip_mm()
    # The NE R10 trims the east end at the pivot station (the straight edge
    # would read -16.25); the NW R8 still runs there, meeting its side edge
    # at z -0.07 (NW_ROUND_END_Z), so it trims the west end by 0.4 um.
    assert east == pytest.approx(-15.8912, abs=1e-4)
    assert drawing.plate_edge_mm(0.0, -1) == pytest.approx(-16.2507, abs=1e-4)
    assert 0.0 < drawing.plate_edge_mm(0.0, +1) - west < 1e-3
    assert west == pytest.approx(11.8145, abs=1e-4)
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
    assert pivot - new_pivot == pytest.approx(0.0029, abs=1e-4)


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


# The two location dimensions' witnesses at the notch-plan cap, as d382
# printed them (C:/src/dt-logs/spring/tipslot-d382-leaf.log:418 and :425):
# the 33.00 (CapECx) rises from (273.3, 241.6) and the 205.81 (CapECz) runs
# east from (274.3, 240.6), both ~1 mm off the cap centre, inside its arc.
_D382_CAP_WITNESS_STARTS = {
    "CapECx": (0.2733, 0.2416),
    "CapECz": (0.2743, 0.2406),
}


def test_no_diameter_leader_on_the_notch_plan_clears_the_cap_witnesses() -> None:
    """MHA-091 item 3's fence, swept: a diameter leader runs the full
    diameter through the cap centre toward its text.  Both witnesses start
    inside the arc (1.03 and 1.05 mm out), so for EVERY leader direction the
    ink passes within ~1.05 mm of both starts: at the printed ~1 mm witness
    gaps no placement of the Ø8.00 on the notch plan reaches the 2 mm floor,
    so it leaves the view."""
    cap = drawing.plan_xy(drawing.NOTCH_CENTER, part.SLOT_E_X, part.SLOT_E_Z)
    radius = part.SLOT_W / 2.0 * drawing.PLAN_SCALE
    reach = 0.050  # past any text position on the sheet
    worst = {name: 0.0 for name in _D382_CAP_WITNESS_STARTS}
    for step in range(720):
        theta = math.radians(step / 2.0)
        direction = (math.cos(theta), math.sin(theta))
        leader = (
            (cap[0] - radius * direction[0], cap[1] - radius * direction[1]),
            (cap[0] + reach * direction[0], cap[1] + reach * direction[1]),
        )
        for name, start in _D382_CAP_WITNESS_STARTS.items():
            gap = _drawing_leaders.distance_to_point(leader, start)
            worst[name] = max(worst[name], gap)
    for name, start in _D382_CAP_WITNESS_STARTS.items():
        assert math.dist(start, cap) < radius
        assert worst[name] == pytest.approx(math.dist(start, cap), abs=2e-5)
        assert worst[name] < 0.0011 < drawing.LEADER_INK_CLEARANCE


class _GeneratedArrowStyleWrapper:
    """GetArrowHeadStyle2 as the generated sldworks wrapper declares it: two
    by-reference in/out ints; a call without them is what the seat refused
    with 'Type mismatch.' in tipslot-r5-e7d8."""

    def GetArrowHeadStyle2(self, *args: object) -> tuple[bool, int, int]:
        if len(args) != 2 or not all(isinstance(value, int) for value in args):
            raise TypeError("Type mismatch.")
        return True, 1, 1


def test_arrowhead_styles_seeds_both_by_reference_ints() -> None:
    assert drawing.arrowhead_styles(_GeneratedArrowStyleWrapper()) == (1, 1)
