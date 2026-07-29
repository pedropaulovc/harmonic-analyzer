"""Offline contracts for the harmonic-base drawing."""

from __future__ import annotations

import math
from pathlib import Path
import re

import build_harmonic_base as part
import build_cone_swing_platform as platform
import draw_harmonic_base as drawing
import harmonic_base_spec
from cone_pivot_post_installation import (
    MECHANISM_X_SHIFT,
    MECHANISM_Z_SHIFT,
    POST_X_SHIFT,
    POST_Z_SHIFT,
)
from cone_lock_knob_spec import WASHER_DIA as KNOB_WASHER_DIA
from _drawing_registry import DRAWINGS_BY_NAME
from swing_stop_screw_spec import SHANK_DIA as STOP_SHANK_DIA


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/harmonic-base.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/harmonic-base.pdf")
    assert drawing.PNG.as_posix().endswith("/png/harmonic-base_drawing.png")
    assert DRAWINGS_BY_NAME["harmonic_base"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is harmonic_base_spec.DRAWING_DIMENSIONS
    marked = set().union(*harmonic_base_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.TOP_KEEP)
    assert kept == marked
    assert (drawing.BOTTOM_LENGTH, drawing.BOTTOM_WIDTH) == (
        harmonic_base_spec.BOTTOM_LENGTH,
        harmonic_base_spec.BOTTOM_WIDTH,
    )


def test_plate_geometry_is_single_sourced() -> None:
    # The build imports its plate nominals from the spec, so the drawing's view
    # math and the part geometry cannot drift.
    assert part.BOTTOM_LENGTH is harmonic_base_spec.BOTTOM_LENGTH
    assert part.TOP_THICKNESS is harmonic_base_spec.TOP_THICKNESS
    assert harmonic_base_spec.BOTTOM_LENGTH == 18.0 * 25.4
    assert harmonic_base_spec.TOP_LENGTH == 17.5 * 25.4
    assert harmonic_base_spec.BOTTOM_FRONT_Z == -(11.0 * 25.4) / 2.0
    assert harmonic_base_spec.BOTTOM_REAR_Z == (11.0 * 25.4) / 2.0
    assert math.isclose(harmonic_base_spec.BOTTOM_WIDTH, 11.0 * 25.4)
    assert math.isclose(harmonic_base_spec.TOP_WIDTH, 10.5 * 25.4)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert source.count("bbox_extent_check(") == 2
    assert "measure_check(" not in source


def test_notes_cover_the_top_plate_reveal_and_seats() -> None:
    notes = harmonic_base_spec.DRAWING_NOTES
    assert "GRAY IRON" not in notes
    assert "ASTM A48" not in notes
    assert "GREEN ENAMEL" not in notes
    assert "DEBURR" not in notes
    assert "UOS" not in notes
    assert "JOINED" not in notes
    assert "MACHINE FROM SOLID STOCK" in notes
    assert "NO DRAFT" in notes
    assert "PAD-TO-FLANGE ROOT R0.50 MAX" in notes
    assert "UPPER PAD 444.50 X 266.70" in notes
    assert "REAR EXTENSION" not in notes
    assert "NEAR LONG SIDE 6.35 +/-0.10 FROM B" in notes
    assert "NEAR LEFT END 6.35 +/-0.10 FROM C" in notes
    assert "B = LONG-SIDE FACE; C = LEFT-END FACE" in notes
    assert "PLAN RIMS AT E1-E4 ARE THE DIA 13.00 THRU FEATURES" in notes
    assert "LEAST-SQUARES CYLINDER FITS OVER" in notes
    assert "SEPARATION AT C'BORE MOUTH/BOTTOM: 0.05 MAX" in notes
    assert "PROCESS DATA" not in notes
    assert "A1/B1/C1-C3/D1-D4 ARE BLIND TAPPED" in notes
    assert "MASK DATUM A/B/C FACES, ALL BORES/THREADS" in notes
    assert "PAD TOP; COAT PAD SIDES AND ROOTS" in notes
    assert "A1-A4" not in notes
    assert "FOUR DIA 13.00 THRU / DIA 23.00 X 6.50 DEEP C'BORES" in notes
    assert "LOCATIONS ARE BASIC" in notes
    assert re.search(r"\d+\.\d(?!\d)", notes) is None
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'adapter, "Manufacturing Notes", 0.016, 0.075, char_height=0.0025' in source
    assert 'add_property_linked_note(adapter, "Side View Note", 0.260, 0.095)' in source
    assert "insert_hole_table(" in source
    assert "_visible_hole_table_entities(adapter, top)" in source
    assert "datum_entity=datum_entity" in source
    assert "hole_entities=hole_entities" in source
    assert "GetVisibleEntities2(c, 2)" in source
    assert "GetVisibleEntities2(c, 1)" in source
    assert source.count("add_datum_feature(") == 3
    assert source.count("add_feature_control_frame(") == 5
    assert 'quantity="E1-E4 DIA 13 THRU"' in source
    assert 'quantity="DATUM B LONG SIDE"' in source
    assert 'quantity="DATUM C LEFT END"' in source
    assert 'quantity="A1, B1, C1-C3, D1-D4"' in source
    assert "6.53 BLIND HOLE" not in source
    assert "underside-only counterbore rims are visible" in source
    assert 'redundant_note_substrings=("Tapped Hole",)' in source
    assert "expected_redundant_notes=4" in source


def test_hole_table_covers_mounting_holes_and_every_hardware_seat() -> None:
    assert len(part.HOLE_XZ) == 4
    assert len(drawing.ALL_HOLES) == 13
    assert drawing.ALL_HOLES[:4] == tuple(
        (x, z, part.HOLE_DIA) for x, z in part.HOLE_XZ
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "basic_locations=True" in source
    assert '"*Front"' in source
    assert len(drawing.TOP_KEEP) == 2
    assert drawing._plan_xy(0.0, 10.0)[1] < drawing.TOP_CENTER[1]
    assert drawing.HOLE_TABLE_ANCHOR[0] >= 0.274


def test_plan_view_clears_top_border_and_lower_notes() -> None:
    assert drawing.TOP_CENTER == (0.130, 0.163)


def test_blind_taps_have_drill_and_tap_runout_clearance() -> None:
    for spec in (part.STOP_SEAT_SPEC, part.BLOCK_SEAT_SPEC, part.FOOT_SEAT_SPEC):
        thread_depth = spec.overrides_mm["ThreadDepth"]
        assert spec.depth_mm - thread_depth >= 3.0


def test_v2_platform_swing_stop_coordinate_is_rederived() -> None:
    """Mirror the drive-train formula without importing its COM-heavy graph."""
    pivot_x, pivot_z = part.PIVOT_SCREW_XZ
    assert part.PIVOT_SCREW_XZ == (
        -89.16663981674521 + POST_X_SHIFT,
        60.60437088764276 + POST_Z_SHIFT,
    )
    assert part.STOP_SCREW_XZ == (
        -141.14905420183916 + POST_X_SHIFT,
        -33.08089452405298 + POST_Z_SHIFT,
    )
    east_slope = (
        platform.EAST_HALF_S - platform.HALF_WIDTH_N
    ) / platform.PLATE_LEN
    stop_local_z = -105.0
    stop_local_x = -(
        platform.HALF_WIDTH_N
        + east_slope * (platform.NORTH_OVERHANG - stop_local_z)
    )

    edge_x, edge_z = -1.0, east_slope
    edge_norm = math.hypot(edge_x, edge_z)
    edge_x, edge_z = edge_x / edge_norm, edge_z / edge_norm
    disengage_rad = (
        platform.NOTCH_EXIT_TRAVEL + KNOB_WASHER_DIA / 2.0 + 2.0
    ) / platform.SLOT_R
    angle = math.radians(platform.INCLINE_DEG) + disengage_rad
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    contact_x = pivot_x + stop_local_x * cos_a + stop_local_z * sin_a
    contact_z = pivot_z - stop_local_x * sin_a + stop_local_z * cos_a
    normal_x = edge_x * cos_a + edge_z * sin_a
    normal_z = -edge_x * sin_a + edge_z * cos_a
    derived = (
        contact_x + normal_x * STOP_SHANK_DIA / 2.0,
        contact_z + normal_z * STOP_SHANK_DIA / 2.0,
    )

    assert math.isclose(platform.NOTCH_EXIT_TRAVEL, 4.097712434428717)
    assert math.isclose(math.degrees(disengage_rad), 4.883134225775778)
    assert math.isclose(derived[0], part.STOP_SCREW_XZ[0], abs_tol=1e-12)
    assert math.isclose(derived[1], part.STOP_SCREW_XZ[1], abs_tol=1e-12)

    engaged = math.radians(platform.INCLINE_DEG)
    cos_e, sin_e = math.cos(engaged), math.sin(engaged)
    edge_point_x = pivot_x + stop_local_x * cos_e + stop_local_z * sin_e
    edge_point_z = pivot_z - stop_local_x * sin_e + stop_local_z * cos_e
    engaged_normal = (
        edge_x * cos_e + edge_z * sin_e,
        -edge_x * sin_e + edge_z * cos_e,
    )
    stop_delta = (
        derived[0] - edge_point_x,
        derived[1] - edge_point_z,
    )
    engaged_gap = (
        stop_delta[0] * engaged_normal[0]
        + stop_delta[1] * engaged_normal[1]
        - STOP_SHANK_DIA / 2.0
    )
    assert engaged_gap >= 2.0
    assert math.isclose(engaged_gap, 8.92856567081106)


def test_v2_structural_holes_follow_the_same_installation_delta() -> None:
    former_blocks = (
        (15.240530460002873, -98.0),
        (42.24053046000287, -98.0),
        (15.240530460002873, 82.0),
        (42.24053046000287, 82.0),
    )
    former_feet = (
        (43.13610240207359, 70.95),
        (-54.7, -95.5),
        (-54.7, 102.5),
    )
    assert part.BLOCK_SCREW_XZ == tuple(
        (x + MECHANISM_X_SHIFT, z + MECHANISM_Z_SHIFT)
        for x, z in former_blocks
    )
    assert part.FOOT_SCREW_XZ == tuple(
        (x + MECHANISM_X_SHIFT, z + MECHANISM_Z_SHIFT)
        for x, z in former_feet
    )


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("harmonic-base")
    assert config["material"] == config["material_specification"]
    assert "gray cast iron" in str(config["material_specification"]).lower()
    finish = str(config["finish"]).lower()
    assert "sspc-sp3" in finish
    assert "alkyd primer 25-40um" in finish
    assert "ral6000 alkyd enamel 50-85um" in finish
    assert "75-125um total dft" in finish
    assert "mask" not in finish
    assert config["process"] == "machined from solid stock"
    assert int(config["quantity"]) == 1
