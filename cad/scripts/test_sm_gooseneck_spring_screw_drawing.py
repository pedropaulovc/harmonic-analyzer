"""Offline release contracts for MHA-SM-004, the gooseneck spring screw."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_sm_gooseneck_spring_screw as part
import draw_sm_gooseneck_spring_screw as drawing
import sm_gooseneck_spring_screw_geom as geom
import sm_gooseneck_spring_screw_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout


def test_registry_paths_and_part_name() -> None:
    registered = DRAWINGS_BY_NAME["sm_gooseneck_spring_screw"]
    assert registered.script == Path(drawing.__file__).resolve()
    assert registered.layout is DrawingLayout.LANDSCAPE
    assert registered.source.as_posix().endswith(
        "/sldprt/sm-gooseneck-spring-screw.SLDPRT"
    )
    assert drawing.SLDDRW.as_posix().endswith(
        "/slddrw/sm-gooseneck-spring-screw.SLDDRW"
    )
    assert drawing.PDF.as_posix().endswith("/pdf/sm-gooseneck-spring-screw.pdf")
    assert drawing.PNG.as_posix().endswith("/png/sm-gooseneck-spring-screw_drawing.png")
    assert part.PART_NAME == registered.artifact_stem


def test_part_registry_row_is_the_made_screw() -> None:
    row = _config.parts("sm-gooseneck-spring-screw")
    assert row["number"] == "MHA-SM-004"
    assert row["title"] == "Gooseneck Spring Screw"
    assert row["description"] == "GOOSENECK SPRING SCREW"
    for grade in ("12L14", "1/2 in"):
        assert grade in row["material"]
        assert grade in row["material_specification"]
    assert int(row["quantity"]) == 1
    # A static clamp, not a running fit.
    assert "fit_class" not in row
    assert row["process"] != "purchased"
    assert row["process"] == "turned slotted fillister screw; die-cut #6-32 thread"
    assert part.MATERIAL == "Plain Carbon Steel"


def test_printed_material_fits_one_title_block_line() -> None:
    row = _config.parts("sm-gooseneck-spring-screw")
    assert len(str(row["material"])) <= 36
    assert "cold-finished" in str(row["material_specification"])


def test_stock_turns_the_head() -> None:
    # 1/2-in round cleans up to the Ø12.50 head.
    assert geom.STOCK_DIA == pytest.approx(12.7)
    assert geom.HEAD_DIA < geom.STOCK_DIA


def test_spec_is_the_single_source_of_marked_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) | set(drawing.END_KEEP) == marked
    assert not set(drawing.SIDE_KEEP) & set(drawing.END_KEEP)
    # The thread is defined by its callout, not a Ø3.51 dimension, and the
    # crown by its rise and the note, not a radius.
    assert "ThreadDia" not in marked
    assert "CrownRadius" not in marked
    # The slot width is only true-size in the head-end view.
    assert set(drawing.END_KEEP) == {"SlotWidth"}
    # The lead prints as limits on the relief callout.
    assert "ReliefLead" not in marked


def test_model_owns_places_and_bands() -> None:
    assert "draw_sm_gooseneck_spring_screw.py" in PRECISION_MIGRATED_DRAWINGS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME.values()) == {2}
    assert spec.REFERENCE_DIMENSIONS == {"CrownRise", "OverallLength"}
    # Every band comes from a named geometry constant, never a typed number;
    # every other mark takes the title block's .XX band.
    assert model_toleranced_dimensions(part) == {
        ("ShankProfile", "ReliefDia"): "RELIEF_DIA_TOL",
        ("ShankProfile", "ReliefLead"): "RELIEF_LEAD_TOL",
        ("ShankProfile", "TipChamfer"): "*deviations(TIP_CHAMFER_BAND)",
    }


def test_policy_sheet_carries_no_gdt_or_render_time_precision() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_feature_control_frame",
        "add_datum_feature",
        "set_basic_dimension",
        "set_dimension_precision",
        "SetPrecision3",
        "add_surface_finish",
    ):
        assert helper not in source
    build = Path(part.__file__).read_text(encoding="utf-8")
    assert "author_part_pmi" not in build


def test_geometry_matches_the_settled_design() -> None:
    assert geom.HEAD_DIA == 12.50
    assert geom.HEAD_H == 7.00
    assert geom.CROWN_RISE == 1.00
    assert geom.HEAD_CYL_H == pytest.approx(6.00)
    assert geom.SLOT_WIDTH == 1.60
    assert geom.SLOT_DEPTH == 3.00
    assert geom.SLOT_FLOOR_Z == pytest.approx(4.00)
    assert geom.LENGTH == 16.00
    assert geom.MAJOR_DIA == pytest.approx(3.5052)
    assert geom.OVERALL_LENGTH == pytest.approx(23.0)
    assert geom.CROWN_RADIUS == pytest.approx((6.25**2 + 1.0) / 2.0)
    assert geom.CROWN_CENTER_Z == pytest.approx(7.0 - geom.CROWN_RADIUS)


def test_slot_leaves_the_rule_12_head_web() -> None:
    # Shortest head, deepest slot, full title-block edge break.
    assert spec.EDGE_BREAK_MAX == 0.25
    assert spec.SLOT_WEB_MIN == pytest.approx(7.00 - 0.51 - 3.51 - 0.25)
    assert spec.SLOT_WEB_MIN >= spec.SLOT_WEB_TARGET == 2.0


def test_relief_sits_below_the_die_root_with_a_flat_seat() -> None:
    assert geom.RELIEF_DIA_MAX == pytest.approx(2.25)
    assert geom.RELIEF_DIA_MAX < geom.THREAD_MINOR_2A_MIN_EST
    assert geom.RELIEF_FLOOR_MIN >= 1.5 * geom.PITCH
    assert geom.SEAT_FLAT_INNER_DIA_MAX < geom.MAJOR_DIA
    assert spec.RELIEF_CALLOUT == "0.20-0.40 X 45 DEG LEAD"
    assert spec.CHAMFER_CALLOUT == "X 45 DEG"


def test_thread_callout_names_the_size_but_not_the_title_block_class() -> None:
    assert spec.THREAD_CALLOUT == "#6-32 UNC"
    assert "2A" not in spec.THREAD_CALLOUT
    assert drawing.THREAD_CALLOUT is spec.THREAD_CALLOUT


def test_notes_are_short_and_carry_no_dimension_or_method() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    for line in lines:
        # Only the mating part's number is quoted.
        text = line.split(". ", 1)[1].replace("MHA-SM-001", "")
        assert not any(ch.isdigit() for ch in text), line
        for word in ("TORQUE", "LOCTITE", "THREADLOCK", "TIGHTEN"):
            assert word not in line
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW\nSCALE 2:1"


def test_modelled_volume_is_the_turned_body_less_the_slot() -> None:
    r_head, r_thread, r_relief = 6.25, 3.5052 / 2.0, 1.1
    rc = geom.CROWN_RADIUS
    cap = math.pi * 1.0**2 * (3.0 * rc - 1.0) / 3.0
    assert part.V_HEAD == pytest.approx(math.pi * r_head**2 * 6.0 + cap)
    # Pappus: the lead's 0.3 x 0.3 triangle stays, the tip chamfer's goes.
    lead = 2.0 * math.pi * (r_relief + 0.1) * 0.045
    tip = 2.0 * math.pi * (r_thread - 0.1) * 0.045
    relief = math.pi * (r_thread**2 - r_relief**2) * 2.2 - lead
    assert part.V_SHANK == pytest.approx(math.pi * r_thread**2 * 16.0 - relief - tip)
    assert part.V_BODY == pytest.approx(part.V_HEAD + part.V_SHANK)
    # Independent slot volume: a 3-D midpoint grid over the strip.
    steps_z, steps_y = 600, 200
    half = 0.8
    total = 0.0
    dz, dy = 3.0 / steps_z, 2.0 * half / steps_y
    for i in range(steps_z):
        z = 4.0 + (i + 0.5) * dz
        r = r_head if z <= 6.0 else math.sqrt(rc**2 - (z - (7.0 - rc)) ** 2)
        for j in range(steps_y):
            y = -half + (j + 0.5) * dy
            if abs(y) < r:
                total += 2.0 * math.sqrt(r**2 - y**2) * dy * dz
    assert part.V_SLOT == pytest.approx(total, rel=2e-3)
    assert part.V_FINAL == pytest.approx(part.V_BODY - part.V_SLOT)


def test_side_view_stations_follow_the_model() -> None:
    scale = drawing.SHEET_SCALE[0] / 1000.0
    assert drawing.TIP_X - drawing.APEX_X == pytest.approx(geom.OVERALL_LENGTH * scale)
    assert drawing.UNDERHEAD_X - drawing.APEX_X == pytest.approx(geom.HEAD_H * scale)
    assert drawing.RELIEF_END_X - drawing.UNDERHEAD_X == pytest.approx(
        geom.RELIEF_WIDTH * scale
    )
    # Model +Z runs paper-left in *Right: head left, tip right.
    assert (
        drawing.APEX_X
        < drawing.RIM_X
        < drawing.SLOT_FLOOR_X
        < drawing.UNDERHEAD_X
        < drawing.RELIEF_END_X
        < drawing.THREAD_START_X
        < drawing.TIP_X
    )
    # The bounding-box centre is the view centre.
    assert (drawing.APEX_X + drawing.TIP_X) / 2.0 == pytest.approx(
        drawing.SIDE_CENTER[0]
    )


def test_head_end_view_is_the_third_angle_left_view() -> None:
    assert drawing.END_CENTER[1] == drawing.SIDE_CENTER[1]
    head_radius = geom.HEAD_DIA * drawing.SHEET_SCALE[0] / 2000.0
    assert drawing.END_CENTER[0] + head_radius < drawing.APEX_X - 0.030
    head_dia_x = drawing.SIDE_KEEP["HeadDia"][0]
    assert drawing.END_CENTER[0] + head_radius + 0.010 < head_dia_x < drawing.APEX_X
    slot_x = drawing.END_KEEP["SlotWidth"][0]
    assert drawing.END_CENTER[0] + head_radius < slot_x < head_dia_x - 0.010


def test_sheet_placements_stay_inside_the_border() -> None:
    inner = (0.0127, 0.0127, 0.4191, 0.2667)  # ASME B landscape inner border
    title_block = (0.218, 0.065)  # x >= and y <=
    points = [
        drawing.SIDE_CENTER,
        drawing.END_CENTER,
        drawing.ISO_CENTER,
        drawing.THREAD_NOTE_XY,
        drawing.ISO_NOTE_XY,
        drawing.NOTES_XY,
        drawing.RELIEF_DIA_TEXT_XY,
        (drawing.TIP_X, drawing.SIDE_CENTER[1]),
        *drawing.SIDE_KEEP.values(),
        *drawing.END_KEEP.values(),
    ]
    for x, y in points:
        assert inner[0] < x < inner[2] and inner[1] < y < inner[3]
        assert not (x >= title_block[0] and y <= title_block[1])
    # The thread callout's leader lands on the full thread, never the relief.
    assert drawing.THREAD_PICK[0] == drawing.THREAD_START_X
    assert drawing.THREAD_START_X - drawing.RELIEF_END_X > 0.0
    thread_half = geom.MAJOR_DIA * drawing.SHEET_SCALE[0] / 2000.0
    assert abs(drawing.THREAD_PICK[1] - drawing.SIDE_CENTER[1]) < thread_half
    assert drawing.THREAD_NOTE_XY[0] - drawing.THREAD_PICK[0] > 0.010
    # The relief marks sit on the groove; the Ø text's left edge clears the
    # under-head extension line and its underline stays above row 0.
    for name in ("ReliefDia", "ReliefWidth"):
        assert drawing.UNDERHEAD_X < drawing.SIDE_KEEP[name][0] < drawing.RELIEF_END_X
    text_x, text_y = drawing.RELIEF_DIA_TEXT_XY
    assert (text_x - drawing.RELIEF_DIA_TEXT_WIDTH / 2.0) - drawing.UNDERHEAD_X >= 0.003
    underline = text_y - drawing.RELIEF_DIA_TEXT_UNDERLINE_DROP
    assert underline - drawing.SIDE_KEEP["UnderHeadLength"][1] >= 0.010
    # The relief width stands above the head so its text clears the head face.
    assert drawing.SIDE_KEEP["ReliefWidth"][1] > drawing.HEAD_TOP_Y
    # The two apex dimensions stack above the head, 12 mm apart.
    crown_y = drawing.SIDE_KEEP["CrownRise"][1]
    slot_y = drawing.SIDE_KEEP["SlotDepth"][1]
    assert drawing.HEAD_TOP_Y < crown_y < slot_y
    assert slot_y - crown_y >= 0.010
    # The centreline pick lands on the thread, clear of the relief.
    assert drawing.RELIEF_END_X < drawing.CENTERLINE_PICK[0] < drawing.THREAD_START_X
    # The isometric stands clear of the thread note.
    assert drawing.ISO_CENTER[0] - drawing.THREAD_NOTE_XY[0] > 0.040


def test_station_reference_is_saved_hidden_and_imported_per_view() -> None:
    build = Path(part.__file__).read_text(encoding="utf-8")
    blank = 'blank_sketch(adapter, "StationReference")'
    assert blank in build
    assert build.index(blank) < build.rindex("save_part_and_images(adapter, PART_NAME)")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "from _drawing_hidden_sketches import curate_view_dimensions" in source
    assert "StationReference" in spec.DRAWING_DIMENSIONS
