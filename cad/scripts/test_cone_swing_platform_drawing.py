"""Offline manufacturing contracts for the cone-swing-platform package."""

from __future__ import annotations

import math
import sys
import types
from pathlib import Path

import _config
import cone_pivot_screw_spec
import build_cone_swing_platform as part
import cone_pivot_post_spec
import cone_swing_platform_drawing_spec as drawing_spec
import cone_swing_platform_geometry as geometry
import cone_swing_platform_spec as spec
import draw_cone_swing_platform as drawing
import pytest
from _gtol_spec import PlanarFace
from _hole_spec import CLEARANCE_MM, blind_cut_dia_mm
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
    assert drawing_spec.DRAWING_PRECISION_BY_NAME["PlateLenDim"] == 1
    assert set(drawing_spec.DRAWING_PRECISION_BY_NAME.values()) == {1, 2}


def test_pivot_preserves_native_close_clearance_hole() -> None:
    assert spec.PIVOT_HOLE_SPEC.kind == "clearance"
    assert spec.PIVOT_HOLE_SPEC.size == "1/4"
    assert spec.PIVOT_HOLE_SPEC.fit == "close"
    assert spec.PIVOT_HOLE_SPEC.end == "through_all"
    assert spec.PIVOT_HOLE_DIA == blind_cut_dia_mm(spec.PIVOT_HOLE_SPEC)
    assert spec.PIVOT_HOLE_DIA == pytest.approx(6.756)
    assert spec.PIVOT_HOLE_DIA > cone_pivot_screw_spec.SHOULDER_DIA


def test_post_mount_pattern_is_derived_from_its_mating_post() -> None:
    assert spec.POST_ATTACHMENT_SPACING == cone_pivot_post_spec.ATTACHMENT_SPACING
    assert spec.POST_BLOCK_DIA == cone_pivot_post_spec.BLOCK_DIA
    assert geometry.POST_MOUNT_HALF_PITCH == spec.POST_ATTACHMENT_SPACING / 2.0
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
        (part.POST_MOUNT_WEST_XZ, cone_pivot_post_spec.ATTACHMENT_X),
        (part.POST_MOUNT_EAST_XZ, -cone_pivot_post_spec.ATTACHMENT_X),
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
    registry = _config.parts("cone-swing-platform")
    assert registry["tolerance_class"] == "machined_block"
    assert "mil-dtl-13924 class 1" in str(registry["finish"]).lower()
    assert "oil seal" in str(registry["finish"]).lower()
    assert int(registry["quantity"]) == 1
    assert drawing_spec.DRAWING_PRECISION["Plate"]["PlateThk"] == 2
    assert drawing_spec.DRAWING_PRECISION["PivotBearingRelief"]["PivotBearingReliefDepth"] == 2
    assert drawing_spec.DRAWING_PRECISION["PostMountHoles"] == {
        "PostMountWestX": 2,
        "PostMountWestZ": 2,
        "PostMountEastX": 2,
        "PostMountEastZ": 2,
    }






def test_geometry_cascade_and_interference_guards_stay_explicit() -> None:
    assert part.PLATE_LEN == pytest.approx(223.3541869456341)
    assert geometry.POST_SOUTH_MARGIN == pytest.approx(3.175)
    assert geometry.PLATE_SOUTH_Z == pytest.approx(-216.3541869456341)
    assert geometry.POST_MAIN_DIA == spec.POST_BLOCK_DIA
    assert geometry.POST_FOOT_CONTAINMENT >= 0.25
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
    head_dia = cone_pivot_screw_spec.HEAD_DIA
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
    assert set(drawing_spec.DRAWING_PRECISION["PlateProfile"].values()) == {1}


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
        f"1/4-20 THREAD ENGAGEMENT {printed:.2f}D MIN (MHA-142)."
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


def _holddown_callout_box() -> tuple[float, float, float, float]:
    x, y = drawing.HOLDDOWN_CALLOUT_XY
    return (x - 0.025, y - 0.010, x + 0.025, y + 0.004)


def _holddown_strip() -> tuple[float, float, float, float]:
    """Section C-C's strip at 1:1 plus SolidWorks' ~4 mm outline padding."""
    z = spec.HOLDDOWN_LOCAL_Z
    half = (drawing.plate_edge_mm(z, 1) - drawing.plate_edge_mm(z, -1)) / 2000.0 + 0.004
    cx, cy = drawing.HOLDDOWN_SECTION_CENTER
    return (cx - half, cy - 0.0072, cx + half, cy + 0.0072)


def _holddown_label() -> tuple[float, float, float, float]:
    lx, ly = drawing.HOLDDOWN_SECTION_LABEL_LOWER_LEFT
    return (lx, ly, lx + 0.0465, ly + 0.0162)


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


def _relief_note_box():
    """The relief note as the layout audit boxed it (run 20260928T090231982Z):
    four 2.5 mm rows from 0.3 mm under the upper-left anchor to 13.3 mm
    under it, 0.0947 m wide."""
    note_x, note_y = drawing.RELIEF_NOTE_XY
    return (note_x, note_y - 0.0133, note_x + 0.0947, note_y)


def test_holddown_band_clears_border_title_block_and_captions() -> None:
    """Detail B, section C-C, the hold-down callout and the relief note share
    the band under the plan captions without touching each other.

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
        "C-C strip": _holddown_strip(),
        "C-C label": _holddown_label(),
        "hold-down callout": _holddown_callout_box(),
        "relief note": _relief_note_box(),
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
    for i, first in enumerate(names):
        for second in names[i + 1 :]:
            assert not _boxes_overlap(ours[first], ours[second]), (first, second)
    # The 10.45 text sits outside its own extension-line span (pivot to hole),
    # so SolidWorks hangs it off the line instead of centring the line through
    # it (81788ce9: "11.|00").
    assert ours["10.45"][1] >= drawing.DETAIL_HOLDDOWN_Y > drawing.DETAIL_PIVOT_Y
    # The label centres under its own strip (8783776d printed it 50 mm off).
    lx = drawing.HOLDDOWN_SECTION_LABEL_LOWER_LEFT[0]
    assert lx + 0.0465 / 2.0 == pytest.approx(drawing.HOLDDOWN_SECTION_CENTER[0])
    # Positive control: the relief note at its old anchor (0.029) meets the
    # C-C label.
    old_relief = (0.120, 0.029 - 0.0133, 0.120 + 0.0947, 0.029)
    assert _boxes_overlap(old_relief, ours["C-C label"])


def test_holddown_callout_leader_reaches_its_counterbore_wall() -> None:
    """The callout's leader drops to the counterbore's sheet-right wall in
    section C-C, where the underside counterbore is solid, clear of the
    section's label and the relief note under the strip."""
    z = spec.HOLDDOWN_LOCAL_Z
    east = drawing.plate_edge_mm(z, -1)
    width = drawing.plate_edge_mm(z, 1) - east
    cx, cy = drawing.HOLDDOWN_SECTION_CENTER
    # Looking south, sheet +x is model +x: the strip's left end is the east edge.
    wall_x = cx - width / 2000.0 + (
        spec.HOLDDOWN_LOCAL_X + spec.HOLDDOWN_CBORE_DIA / 2.0 - east
    ) / 1000.0
    wall_y = cy - spec.PLATE_THICKNESS / 2000.0 + spec.HOLDDOWN_CBORE_DEPTH / 2000.0
    callout = _holddown_callout_box()
    assert callout[0] < wall_x < callout[2]  # a short, near-vertical leader
    leader = ((wall_x, wall_y), (wall_x, callout[1]))
    assert not _segment_hits_box(leader, _holddown_label())
    assert not _segment_hits_box(leader, _relief_note_box())


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
    assert west - east == pytest.approx(26.89, abs=0.01)
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
    line_y = py - spec.HOLDDOWN_LOCAL_Z * 0.0005
    # Positive control: the default north-looking arrows hit the R8 leader
    # and the 8.0 extension line.
    down = (px + half - head, line_y - length, px + half + head, line_y)
    assert _segment_hits_box(nw_extension, down)
    assert _segment_hits_box(r8_leader, down)


def test_holddown_hole_is_the_ruled_counterbore_for_the_tip_block_screw() -> None:
    """One #4 socket-head counterbore, close clearance, drilled from under,
    10.45 south of the pivot and 1.00 to -x of the cone axis, the block's
    foot tap offset the same way, so the block itself stays centred."""
    import cone_tip_block_spec as block

    hole = spec.HOLDDOWN_HOLE_SPEC
    assert (hole.kind, hole.size) == ("counterbore_socket", "#4")
    assert dict(hole.overrides_mm) == {
        "HoleDiameter": CLEARANCE_MM[("#4", "close")],
        "CounterBoreDiameter": spec.HOLDDOWN_CBORE_DIA,
        "CounterBoreDepth": spec.HOLDDOWN_CBORE_DEPTH,
    }
    assert spec.HOLDDOWN_CLEARANCE_DIA == pytest.approx(3.048)
    assert (spec.HOLDDOWN_LOCAL_X, spec.HOLDDOWN_LOCAL_Z) == (-1.0, -10.45)
    assert block.FOOT_TAP_OFFSET_X == spec.HOLDDOWN_LOCAL_X


def test_holddown_x_is_a_banded_dimension_hanging_inside_detail_b() -> None:
    """User ruling 2026-09-29: the hole's lateral station prints as HoldDownX
    at .XX with +/-0.10, in detail B.  Its 2 mm span cannot hold the text, so
    the text hangs sheet-right of the hole's rim, clear of it and of the
    pivot relief, inside the detail's outline."""
    assert drawing_spec.DRAWING_PRECISION["HoldDownHole"] == {
        "HoldDownX": 2,
        "HoldDownZ": 2,
    }
    assert spec.HOLDDOWN_STATION_TOL_MM == 0.10
    x, y = drawing.DETAIL_KEEP["HoldDownX"]
    text = (x - 0.008, y - 0.0025, x + 0.008, y + 0.0025)  # "1.00±0.10", 3.5 mm
    s = drawing._DETAIL_S
    rim = spec.HOLDDOWN_CLEARANCE_DIA / 2.0 * s
    hole = (
        drawing.DETAIL_HOLDDOWN_X - rim,
        drawing.DETAIL_HOLDDOWN_Y - rim,
        drawing.DETAIL_HOLDDOWN_X + rim,
        drawing.DETAIL_HOLDDOWN_Y + rim,
    )
    relief_r = spec.PIVOT_BEARING_RELIEF_DIAMETER / 2.0 * s
    relief = (
        drawing.DETAIL_CENTER[0] - relief_r,
        drawing.DETAIL_PIVOT_Y - relief_r,
        drawing.DETAIL_CENTER[0] + relief_r,
        drawing.DETAIL_PIVOT_Y + relief_r,
    )
    assert not _boxes_overlap(text, hole)
    assert not _boxes_overlap(text, relief)
    # Outside its own extension-line span, so SolidWorks hangs it.
    assert text[0] > max(drawing.DETAIL_HOLDDOWN_X, drawing.DETAIL_CENTER[0])
    pad = drawing.DETAIL_SHEET_RADIUS
    cx, cy = drawing.DETAIL_CENTER
    assert cx - pad <= text[0] and text[2] <= cx + pad
    assert cy - pad <= text[1] and text[3] <= cy + pad


def test_holddown_print_worst_stack_keeps_its_margins() -> None:
    """At .XX (+/-0.51) and the drilled +0.10: head recess under the slide
    face, head clearance, bearing beside the hole, the counterbore-floor
    ledge and every web to a neighbour (U27 2.0)."""
    xx = 0.51
    head_d, head_h = 0.183 * 25.4, 0.112 * 25.4
    assert spec.HOLDDOWN_CBORE_DEPTH - xx - head_h >= 0.1
    assert spec.HOLDDOWN_CBORE_DIA - xx - head_d >= 0.25
    assert (head_d - (spec.HOLDDOWN_CLEARANCE_DIA + 0.10)) / 2.0 >= 0.5
    ledge_min = (
        spec.PLATE_THICKNESS - spec.PLATE_STOCK_BAND - (spec.HOLDDOWN_CBORE_DEPTH + xx)
    )
    assert spec.HOLDDOWN_LEDGE_RANGE[0] == pytest.approx(ledge_min)
    assert ledge_min >= 2.0
    assert min(geometry.HOLDDOWN_WEBS.values()) >= 2.0


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
        ({"HOLDDOWN_CBORE_DEPTH = 3.50": "HOLDDOWN_CBORE_DEPTH = 3.20"}, "stand proud"),
        ({"HOLDDOWN_CBORE_DIA = 5.56": "HOLDDOWN_CBORE_DIA = 5.20"}, "does not clear"),
        ({"HOLDDOWN_SCREW_HEAD_DIA = 0.183": "HOLDDOWN_SCREW_HEAD_DIA = 0.160"}, "bears on"),
        ({"HOLDDOWN_CBORE_DEPTH = 3.50": "HOLDDOWN_CBORE_DEPTH = 4.20"}, "ledge"),
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
        ("HOLDDOWN_LOCAL_Z = -10.45", "HOLDDOWN_LOCAL_Z = -6.00"),  # onto the pivot
        ("HOLDDOWN_LOCAL_X = -1.0", "HOLDDOWN_LOCAL_X = 6.0"),  # to the west edge
    ],
)
def test_holddown_web_guard_refuses_a_station_that_crowds_a_neighbour(
    monkeypatch: pytest.MonkeyPatch, replacement: tuple[str, str]
) -> None:
    """Moved toward the pivot bore or the plate's west edge, the web check fires."""
    _exec_mutated(geometry, {})  # positive control: the shipped station passes
    mutated = _exec_mutated(spec, dict([replacement]))
    monkeypatch.setitem(sys.modules, spec.__name__, mutated)
    with pytest.raises(AssertionError, match="hold-down leaves a web"):
        _exec_mutated(geometry, {})


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
