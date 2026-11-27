"""Offline contracts for MHA-DT-35, the crank handle butt cup, and its drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_dt_crank_handle_butt_cup as part
import dt_crank_handle_butt_cup_notes as notes
import dt_crank_handle_butt_cup_spec as spec
import dt_crank_handle_butt_cup_seat_spec as seat
import dt_crank_handle_pivot_screw_spec as screw
import draw_dt_crank_handle_butt_cup as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _printed_tolerance import edge_break_chamfer_mm
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_geometry import (
    Box,
    Segment,
    point_segment_distance,
    segment_box_distance,
    segment_box_overlap_length,
)
from machinist_exceptions import load_exceptions


def test_required_drawing_paths_and_registry_entry() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-crank-handle-butt-cup.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-crank-handle-butt-cup.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-crank-handle-butt-cup_drawing.png")
    assert (
        DRAWINGS_BY_NAME["dt_crank_handle_butt_cup"].script
        == Path(drawing.__file__).resolve()
    )
    assert "draw_dt_crank_handle_butt_cup.py" in PRECISION_MIGRATED_DRAWINGS


def test_part_and_drawing_share_the_marked_dimension_contract() -> None:
    # The part's complete contract is the head-seat module's: the spec's rows
    # plus the floor hole's mouth break (#1757).
    assert part.DRAWING_DIMENSIONS is seat.CUP_DRAWING_DIMENSIONS
    assert drawing.DRAWING_DIMENSIONS is seat.CUP_DRAWING_DIMENSIONS
    marked = set().union(*seat.CUP_DRAWING_DIMENSIONS.values())
    assert marked == set().union(*spec.DRAWING_DIMENSIONS.values()) | {"FloorHoleChamfer"}
    assert set(drawing.SECTION_KEEP) | set(drawing.DETAIL_KEEP) == marked
    assert not set(drawing.SECTION_KEEP) & set(drawing.DETAIL_KEEP)
    assert set(seat.CUP_DRAWING_PRECISION_BY_NAME) == marked
    # The pocket prints its own limits (owner ruling 2026-11-24, fit audit
    # question 15): no reference dimension is left.
    assert spec.REFERENCE_DIMENSIONS == frozenset()
    # No model band beside the separate native radial MAX and LIMIT
    # setters: the chamfer, the body and the pocket depth hold the title
    # block's .XXX band.
    assert model_toleranced_dimensions(part) == {}
    assert spec.DRAWING_PRECISION_BY_NAME["BodyChamfer"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["BodyDia"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["PocketDepth"] == 3


def test_bottom_chamfer_clears_the_handle_counterbore_corner() -> None:
    # Owner ruling A on #1661: its smallest leg still clears the MHA-DT-08
    # counterbore floor's MAX corner radius.
    import dt_crank_handle_spec as handle

    assert spec.BODY_CHAMFER_MIN >= handle.INSIDE_CORNER_R_MAX
    assert _config.parts("dt-crank-handle")["number"] in notes.BODY_CHAMFER_CALLOUT


def test_pocket_names_its_mate_once_on_one_flag_note() -> None:
    # Rule 4: the pocket's diameter, depth and floor corner share one flag.
    flags = {
        drawing.DIMENSION_CALLOUTS[name].splitlines()[0]
        for name in ("PocketDia", "PocketDepth", "PocketFloorRadius")
    }
    assert len(flags) == 1
    pocket = notes.POCKET_NOTE_TEXT
    assert pocket.startswith("1. ") and len(pocket.splitlines()) <= 2
    assert _config.parts("dt-crank-handle-pivot-screw")["number"] in pocket
    # Fit audit question 15: no matching, so no clearance to read; the note
    # names the mate and carries no dimension, and no tool (rule 7; machinist
    # review r1, farm run 20261124T110807008Z: the end mill is the traveler's).
    assert "CLEARANCE" not in pocket and "BORE TO" not in pocket
    assert "CLEARS" in pocket
    for method in ("END MILL", "PLUNGE"):
        assert method not in pocket
    # The body's bond is a matched fit on flag note 2: the .XXX grade alone
    # cannot give the glue line, so the route prints (round 2 review).
    assert drawing.DIMENSION_CALLOUTS["BodyDia"] not in flags
    body = notes.BODY_NOTE_TEXT
    assert body.startswith("2. ") and len(body.splitlines()) <= 2
    assert _config.parts("dt-crank-handle")["number"] in body
    assert "CLEARANCE" in body
    assert drawing.NOTES_TEXT.splitlines() == [
        *notes.POCKET_NOTE_TEXT.splitlines(),
        *notes.BODY_NOTE_TEXT.splitlines(),
    ]


def test_floor_and_pocket_wall_hold_their_floors_at_the_printed_limits() -> None:
    # Owner ruling B on #1375 grows only the body around the unchanged pocket.
    assert not hasattr(spec, "FLANGE_DIA") and not hasattr(spec, "FLANGE_THICKNESS")
    # The floor is what the overall (.XX) leaves after the banded pocket depth,
    # both from the face (re-review: one faced end).
    assert spec.FLOOR_THICKNESS_MIN >= spec.WALL_FLOOR_MM
    assert spec.POCKET_WALL_FLOOR_MM == spec.WALL_FLOOR_MM == WALL_FLOOR_MM
    assert spec.POCKET_WALL_MIN >= spec.POCKET_WALL_FLOOR_MM
    assert screw.CUP_POCKET_WALL_MIN == spec.POCKET_WALL_MIN
    assert screw.POCKET_MAX <= spec.POCKET_DIA_MAX
    assert spec.BODY_DIA - spec.BODY_DIA_TOL >= (
        spec.POCKET_DIA_MAX
        + 2.0 * (spec.POCKET_WALL_FLOOR_MM + 2.0 * spec.EDGE_BREAK_MAX_MM)
        - 1e-9
    )
    assert screw.HEAD_BEARING_RADIAL_MIN > 0.0
    assert spec.FLOOR_HOLE_DIA > screw.SHOULDER_DIA_MAX


def test_face_walls_charge_every_exposed_break() -> None:
    # Codjiflo on #2102 (#2170): at the outer face the pocket mouth and the OD
    # edge each take the title block's break, so the governing wall is the
    # straight one less both, and the callout prints that, not the straight.
    # Owner ruling 2026-11-08 (Pedro), #2144 item 7.1 (#2170, option B): the body grows to
    # .422, so the face holds the .060 floor (RV-01) and the straight the target.
    brk = edge_break_chamfer_mm(unit=spec.UNIT)
    assert spec.EDGE_BREAK_MAX_MM == brk == pytest.approx(0.010 * 25.4)
    assert spec.BODY_DIA == pytest.approx(0.422 * 25.4)
    assert spec.POCKET_WALL_MIN == pytest.approx(spec.POCKET_STRAIGHT_WALL_MIN - 2.0 * brk)
    assert spec.POCKET_WALL_MIN == pytest.approx(WALL_FLOOR_MM)
    assert spec.POCKET_STRAIGHT_WALL_MIN == pytest.approx(WALL_TARGET_MM)
    assert notes.POCKET_FIT_CALLOUT.splitlines()[-1] == "WALL .060 MIN"
    exceptions = {
        row.id: row for row in load_exceptions(_config.CONFIG_DIR, "dt-crank-handle-butt-cup", "part")
    }
    assert set(exceptions) == {"RV-01"}
    assert exceptions["RV-01"].where.endswith(notes.POCKET_FIT_CALLOUT.splitlines()[-1])
    # #2196 (Owner ruling 2026-11-08 (Pedro), #2144 item 7.3): the .34 overall keeps the
    # target at the floor hole's lip, both mouths broken; option B lifts the
    # bottom face's ring round the hole over it too.
    assert spec.OVERALL_LENGTH == pytest.approx(0.34 * 25.4)
    assert spec.FLOOR_AT_HOLE_MIN == pytest.approx(spec.FLOOR_THICKNESS_MIN - 2.0 * brk)
    assert spec.FLOOR_AT_HOLE_MIN >= WALL_TARGET_MM
    assert spec.FLOOR_HOLE_WALL_MIN >= WALL_TARGET_MM


def test_ruling_b_keeps_the_head_pocket_and_axial_geometry() -> None:
    # The pocket is end-milled to its own limits; the head at its own band
    # clears it (owner ruling 2026-11-24, fit audit question 15).
    low, high = spec.POCKET_CLEARANCE
    pocket_min, pocket_max = spec.POCKET_DIA_LIMITS
    assert (pocket_min, pocket_max) == pytest.approx((0.248 * 25.4, 0.257 * 25.4))
    assert pocket_min < spec.POCKET_DIA < pocket_max
    assert low == pytest.approx(pocket_min - (screw.HEAD_DIA + screw.HEAD_DIA_TOL))
    assert high == pytest.approx(pocket_max - (screw.HEAD_DIA - screw.HEAD_DIA_TOL))
    assert low > 0.0
    assert spec.POCKET_DIA_MAX == pocket_max
    assert spec.POCKET_FLOOR_CORNER_R_MAX == pytest.approx(0.003 * 25.4)
    assert spec.POCKET_FLOOR_CORNER_R_MAX <= low / 2.0
    assert spec.FLOOR_THICKNESS == pytest.approx(spec.OVERALL_LENGTH - spec.POCKET_DEPTH)
    assert spec.FLOOR_HOLE_DIA > screw.SHOULDER_DIA_MAX


def test_half_inch_stock_cleans_up_over_the_largest_body() -> None:
    # Owner ruling B on #1375 preserves both low-carbon steel alternatives.
    row = _config.parts("dt-crank-handle-butt-cup")
    for field in ("material", "material_specification"):
        for requirement in ("1/2 in", "12L14", "1018"):
            assert requirement in row[field]
    assert spec.STOCK_DIA == pytest.approx(0.5 * 25.4)
    assert spec.BODY_DIA + spec.BODY_DIA_TOL < spec.STOCK_DIA - 0.2


def test_head_sits_recessed_and_end_play_is_fitted() -> None:
    # Codex P2 on #1139 (user ruling 2026-09-30): the banded pocket depth over
    # the banded head keeps the head below the face with the handle pushed to
    # the arm at the widest end play.
    assert screw.HEAD_RECESS_WORST > 0.0
    assert screw.HEAD_RECESS_NOMINAL > screw.HEAD_RECESS_WORST
    assert screw.SHOULDER_LENGTH == pytest.approx(
        screw.HANDLE_STACK_NOMINAL + screw.END_PLAY_NOMINAL
    )


def test_pocket_and_floor_hole_read_on_a_section() -> None:
    assert drawing.END_CENTER[0] < drawing.SECTION_CENTER[0]
    assert drawing.CUT_START[0] == drawing.CUT_END[0] == drawing.END_CENTER[0]
    assert drawing.CUT_START[1] > drawing.CUT_END[1]


def test_floor_corner_retains_its_native_functional_limit() -> None:
    assert spec.POCKET_FLOOR_CORNER_R_MAX <= spec.POCKET_CLEARANCE[0] / 2
    assert spec.POCKET_FLOOR_CORNER_R_BAND == (0.0, -spec.POCKET_FLOOR_CORNER_R_MAX)
    assert spec.POCKET_FLOOR_CORNER_R_TOL_TYPE == 6  # swTolMAX
    assert "PocketFloorRadius" in spec.DRAWING_DIMENSIONS["CupProfile"]
    assert "PocketFloorRadius" not in spec.REFERENCE_DIMENSIONS


def test_registry_row_is_the_title_block_source() -> None:
    row = _config.parts("dt-crank-handle-butt-cup")
    assert row["number"] == "MHA-DT-35"
    assert row["title"] == "Crank Handle Butt Cup"
    assert len(str(row["material"])) <= 36
    assert int(row["quantity"]) == 1


def test_sheet_layout_keeps_annotations_inside_the_field() -> None:
    for x, y in (
        *drawing.SECTION_KEEP.values(),
        drawing.ISO_NOTE_POS,
        drawing.CAPTION_XY,
    ):
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070)
    assert drawing.END_CENTER[0] + drawing.BODY_R < drawing.SECTION_KEEP["FloorHoleDia"][0] - 0.005
    assert drawing.SECTION_KEEP["PocketDia"][0] + 0.020 < drawing.ISO_NOTE_POS[0]


def test_cup_is_one_configuration_the_oak_rounds_clear_of() -> None:
    # Local review of fbf82ad96 (recommended option taken when the question
    # timed out): with the cup's possible offset in the stack the end round
    # could skim only ~0.001 off the steel, so it is turned on the oak only
    # and the cup keeps its flat face.  No INSTALLED configuration remains.
    import build_dt_drive_train_assembly as drive_train
    import dt_crank_handle_spec as handle

    assert not hasattr(spec, "INSTALLED_CONFIG")
    assert not hasattr(drive_train, "HANDLE_CUP_INSTALLED_CONFIG")
    # The oak round the largest counterbore, the crest turned its .XX band
    # small and the bore's eccentricity both ways, holds the .080 target plus
    # the .002 owner-ruling-B margin (#1375).
    assert handle.BUTT_WALL_DESIGN_MIN_MM == pytest.approx(WALL_TARGET_MM + 0.0508)
    assert handle.BUTT_WALL_MIN >= handle.BUTT_WALL_DESIGN_MIN_MM
    assert _config.parts("dt-crank-handle-butt-cup")["description"] == "CRANK HANDLE BUTT CUP"


def test_concave_floor_round_adds_the_exact_revolved_corner_material() -> None:
    # Independently integrate disks over the quarter arc; the angle substitution
    # avoids the square-root endpoint singularity of direct axial integration.
    radius = spec.POCKET_FLOOR_CORNER_R_MAX
    pocket_r = spec.POCKET_DIA / 2.0
    n = 1000
    step = math.pi / (2.0 * n)

    def disk(theta: float) -> float:
        profile_r = pocket_r - radius + radius * math.sin(theta)
        return math.pi * (pocket_r**2 - profile_r**2) * radius * math.sin(theta)

    filled = step / 3.0 * sum(
        (1 if index in (0, n) else 4 if index % 2 else 2) * disk(index * step)
        for index in range(n + 1)
    )
    assert filled > 0
    assert part.V_POCKET_FLOOR_CORNER == pytest.approx(filled, abs=1e-10)
    sharp = math.pi * (
        (spec.BODY_DIA / 2) ** 2 * spec.OVERALL_LENGTH
        - pocket_r**2 * spec.POCKET_DEPTH
        - (spec.FLOOR_HOLE_DIA / 2) ** 2 * spec.FLOOR_THICKNESS
        - spec.BODY_CHAMFER**2 * (spec.BODY_DIA / 2 - spec.BODY_CHAMFER / 3)
    )
    # The mouth break removes a 45-degree ring: integrate its annuli.
    c = seat.FLOOR_HOLE_CHAMFER
    hole_r = spec.FLOOR_HOLE_DIA / 2.0
    steps = 2000
    dz = c / steps
    mouth = sum(
        math.pi * ((hole_r + c - (k + 0.5) * dz) ** 2 - hole_r**2) * dz
        for k in range(steps)
    )
    assert part.V_FLOOR_HOLE_CHAMFER == pytest.approx(mouth, rel=1e-6)
    assert part.V_CUP == pytest.approx(sharp + filled - part.V_FLOOR_HOLE_CHAMFER, abs=1e-10)


# Native r2 at 22821a1d2, leaf 20261019T131953.462543Z-db20eea3ec6447c0b3aa1b2fa338062b.
# These are the actual finding footprints recovered from layout-finding DEBUG
# records, not the previous idealized 22 mm centred box.  The records round
# sheet mm to one decimal; expand glyph boxes by 0.05 mm and reserve another
# 0.05 mm when measuring them against a rounded line.  Translations below are
# placement contracts, NOT evidence that the next native solver preserved them.
_R2_KEEP = {
    "PocketFloorRadius": (0.21775, 0.19075),
    "OverallLength": (0.225, 0.1975),
    "PocketDepth": (0.27825, 0.1365),
    "BodyChamfer": (0.17525, 0.2016),
    "PocketDia": (0.28425, 0.166),
}
_R2_RADIUS_GLYPHS = Box(0.20725, 0.18885, 0.22835, 0.19255)
_R2_OVERALL_GLYPHS = Box(0.22185, 0.19565, 0.22725, 0.19925)
_R2_DEPTH_GLYPHS = Box(0.26875, 0.14015, 0.28695, 0.14385)
_R2_RADIUS_SHOULDER = Segment(0.2315, 0.188, 0.2056, 0.188)
_R2_CHAMFER_WITNESS = Segment(0.2068, 0.1865, 0.2068, 0.1915)
_R2_CHAMFER_TAIL = Segment(0.2068, 0.1905, 0.2131, 0.1905)
_R2_OVERALL_BARB = Segment(0.2083, 0.1951, 0.2083, 0.1943)
_R2_POCKET_DIA_TAIL = Segment(0.2842, 0.1492, 0.2842, 0.1429)


def _r2_delta(name: str) -> tuple[float, float]:
    x, y = drawing.SECTION_KEEP[name]
    old_x, old_y = _R2_KEEP[name]
    return x - old_x, y - old_y


def _moved_r2_box(name: str, box: Box) -> Box:
    dx, dy = _r2_delta(name)
    return Box(box.xmin + dx, box.ymin + dy, box.xmax + dx, box.ymax + dy)


def _moved_r2_segment(name: str, segment: Segment) -> Segment:
    dx, dy = _r2_delta(name)
    return Segment(
        segment.x0 + dx, segment.y0 + dy, segment.x1 + dx, segment.y1 + dy
    )


def test_measured_r2_footprints_reproduce_every_new_collision() -> None:
    # The old test overlooked both the shoulder's full width and the actual
    # glyph top.  Retain failing controls for both text strikes, the shoulder
    # crossing, the foreign arrow, and the insufficient block separation.
    assert _R2_RADIUS_SHOULDER.length == pytest.approx(0.0259)
    assert segment_box_overlap_length(_R2_CHAMFER_TAIL, _R2_RADIUS_GLYPHS) > 0.005
    crossing = (0.2068, 0.188)
    assert point_segment_distance(crossing, _R2_RADIUS_SHOULDER) == pytest.approx(0)
    assert point_segment_distance(crossing, _R2_CHAMFER_WITNESS) == pytest.approx(0)
    assert segment_box_distance(_R2_OVERALL_BARB, _R2_RADIUS_GLYPHS) < 0.002
    assert _R2_OVERALL_GLYPHS.gap(_R2_RADIUS_GLYPHS) < 0.00357
    assert segment_box_overlap_length(_R2_POCKET_DIA_TAIL, _R2_DEPTH_GLYPHS) > 0.0008


def test_radius_full_native_shoulder_and_glyphs_clear_chamfer_and_overall() -> None:
    radius = _moved_r2_box("PocketFloorRadius", _R2_RADIUS_GLYPHS)
    shoulder = _moved_r2_segment("PocketFloorRadius", _R2_RADIUS_SHOULDER)
    chamfer_witness = _moved_r2_segment("BodyChamfer", _R2_CHAMFER_WITNESS)
    chamfer_tail = _moved_r2_segment("BodyChamfer", _R2_CHAMFER_TAIL)
    overall_barb = _moved_r2_segment("OverallLength", _R2_OVERALL_BARB)
    overall = _moved_r2_box("OverallLength", _R2_OVERALL_GLYPHS)
    # Two rounded line coordinates cost 0.10 mm; the expanded glyph box has
    # already paid its 0.05 mm.  These are actual required gaps, not slack.
    assert shoulder.box().gap(chamfer_witness.box()) >= 0.0021
    assert segment_box_distance(chamfer_tail, radius) >= 0.00205
    assert segment_box_distance(overall_barb, radius) >= 0.00205
    assert overall.gap(radius) >= 0.00357
    # Overall is now below the section; its full witnesses end at the
    # silhouette rather than passing through the radius's functional reason.
    overall_line_y = drawing.SECTION_KEEP["OverallLength"][1] - 0.0027781
    assert drawing.SECTION_CENTER[1] - drawing.BODY_R - overall_line_y >= 0.020
    # Full three-row ink recovered from rejected 84f04d2b PDF.  Its old
    # keep was (217.75, 201) mm; font metrics include the entire mate/reason,
    # not just the numeric row measured in r2.  Native proof remains required.
    radius_y = drawing.SECTION_KEEP["PocketFloorRadius"][1]
    reason = Box(0.19842, radius_y - 0.00880, 0.23708, radius_y + 0.00879)
    chamfer_top = 0.216
    assert reason.ymin - chamfer_top >= 0.00357
    assert reason.ymax < 0.2667
    corner_r = spec.POCKET_FLOOR_CORNER_R_MAX
    center_x = drawing.FACE_X - (spec.POCKET_DEPTH - corner_r) * drawing._S
    center_y = drawing.SECTION_CENTER[1] + (spec.POCKET_DIA / 2 - corner_r) * drawing._S
    x, y = drawing.SECTION_KEEP["PocketFloorRadius"]
    bearing = math.degrees(math.atan2(y - center_y, x - center_x))
    assert 90 < bearing < 180


def test_depth_upper_native_row_clears_the_entire_pocket_diameter_arrow_tail() -> None:
    # The nominal/band is the highest of the three native rows.  Clearing
    # only the PocketDia witness at y149.25 misses its 6.35 mm outside tail.
    depth = _moved_r2_box("PocketDepth", _R2_DEPTH_GLYPHS)
    tail = _moved_r2_segment("PocketDia", _R2_POCKET_DIA_TAIL)
    assert depth.ymax < min(tail.y0, tail.y1)
    assert segment_box_distance(tail, depth) >= 0.00205


def test_floor_hole_native_hung_rows_nest_without_either_dimension_crossing() -> None:
    # 031202 native GetPosition (136.75,141): the full DRILL THRU width is
    # 24.0285 mm LEFT of the keep.  Its value's two glyph runs span
    # keep_x-17.8861..keep_x-6.1424, not a symmetric box around the column.
    # The r2 position changed only X; retain this exact below-witness flow.
    x, y = drawing.SECTION_KEEP["FloorHoleDia"]
    drill = Box(x - 0.0240285, y - 0.005583, x, y - 0.002083)
    value = Box(x - 0.0178861, y - 0.0000267, x - 0.0061424, y + 0.0035267)
    axis_y = drawing.SECTION_CENTER[1]
    hole_r = spec.FLOOR_HOLE_DIA * drawing._S / 2
    lower_y, upper_y = axis_y - hole_r, axis_y + hole_r
    assert y < lower_y  # no unproved switch to native inline/centred text
    floor_x = drawing.SECTION_CENTER[0] - drawing.HALF_LENGTH
    assert floor_x - max(drill.xmax, value.xmax) >= 0.002
    # r2 BodyDia's lower text-break boundary is y160.4 (rounded); the new
    # value top y156.0267 has >4.3 mm air even after its 0.05 mm uncertainty.
    assert 0.16035 - value.ymax >= 0.00357
    body_x = drawing.SECTION_KEEP["BodyDia"][0]
    hole_line = Segment(x, drill.ymin, x, upper_y)
    for body_y in (axis_y - drawing.BODY_R, axis_y + drawing.BODY_R):
        body_witness = Segment(floor_x - 0.001, body_y, body_x - 0.001, body_y)
        assert segment_box_distance(hole_line, body_witness.box()) >= 0.002
        assert all(
            segment_box_distance(body_witness, box) >= 0.002
            for box in (drill, value)
        )
    # Conversely, both hole witnesses end right of the outboard body column.
    # The old r2 span x216.8..127.8 crossed that column at y154.5.
    for hole_y in (lower_y, upper_y):
        hole_witness = Segment(
            drawing.FACE_X - spec.POCKET_DEPTH * drawing._S - 0.001,
            hole_y,
            x - 0.001,
            hole_y,
        )
        assert hole_witness.box().xmin - body_x >= 0.002


def test_measured_layout_preserves_generous_views_and_asme_alignment() -> None:
    assert drawing.SHEET_SCALE == (5.0, 1.0)
    assert drawing.VIEW_SCALE == (5, 1)
    assert drawing.ISO_SCALE == (4, 1)
    assert drawing.END_CENTER == (0.074, 0.165)
    assert drawing.SECTION_CENTER == (0.225, 0.165)
    assert drawing.ISO_CENTER == (0.368, 0.215)
    assert drawing.END_CENTER[1] == drawing.SECTION_CENTER[1]


def test_mouth_break_detail_frames_the_break_inside_the_sheet() -> None:
    # #1757: the floor hole's mouth break prints in its own 20:1 detail of
    # section A-A, curated before the section so its dimension lands there.
    focus_x, focus_y = drawing.DETAIL_FOCUS_MM
    for x, y in (drawing._MOUTH_ON_HOLE, drawing._MOUTH_ON_FLOOR):
        assert math.hypot(x - focus_x, y - focus_y) < drawing.DETAIL_RADIUS_MM
    x, y = drawing.DETAIL_CENTER
    crop = drawing.DETAIL_CROP_RADIUS
    assert 0.0127 < x - crop and x + crop < 0.4191
    assert 0.0127 < y - crop and y + crop < 0.2667
    assert x + crop < 0.218 or y - crop > 0.065  # clear of the title block
    for kx, ky in drawing.DETAIL_KEEP.values():
        assert 0.0127 < kx < 0.4191 and 0.065 < ky < 0.2667
    # The axial leg's line runs over the circle and its block stands right of
    # both extension lines, so no line strikes the text.
    kx, ky = drawing.DETAIL_KEEP["FloorHoleChamfer"]
    line_y = ky - drawing.FLOOR_HOLE_CHAMFER_LINE_DROP
    assert line_y > y + crop
    block_left = kx - drawing.FLOOR_HOLE_CHAMFER_TEXT_WIDTH / 2.0
    for point in (drawing._MOUTH_ON_HOLE, drawing._MOUTH_ON_FLOOR):
        assert block_left > drawing._detail_xy(*point)[0]
    assert notes.FLOOR_HOLE_CHAMFER_CALLOUT.startswith("X 45")
    assert "MHA-DT-32" in notes.FLOOR_HOLE_CHAMFER_CALLOUT
