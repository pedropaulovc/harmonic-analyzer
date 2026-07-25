"""Offline contracts for the rocker-arm-support drawing."""

from __future__ import annotations

import math
from pathlib import Path

import draw_rocker_arm_support as drawing
import build_rocker_arm_support as support
import rocker_arm_support_spec as placement
from cone_pivot_post_installation import MACHINE_X_SHIFT, MACHINE_Z_SHIFT
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/rocker-arm-support.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/rocker-arm-support.pdf")
    assert drawing.PNG.as_posix().endswith("/png/rocker-arm-support_drawing.png")
    assert (
        DRAWINGS_BY_NAME["rocker_arm_support"].script
        == Path(drawing.__file__).resolve()
    )


def test_drawing_keeps_exactly_the_marked_dimension_set() -> None:
    marked = set().union(*support.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked


def test_tapped_holes_use_customary_us_thread() -> None:
    # Pedro 2026-07-10: closest customary US thread, not the period series.
    assert support.HOLE_SSIZE == "9/16-12"
    assert support.HOLE_THREAD_CLASS == "2B"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "insert_hole_table(" in source


def test_hole_table_covers_every_foot_hole() -> None:
    assert len(support.HOLES) == 4
    points = {drawing._bottom_sheet_xy(hole) for hole in support.HOLES}
    assert len(points) == 4
    half_w = support.BOSS_DEPTH / 2.0 * drawing.VIEW_SCALE / 1000.0
    half_h = support.WIDE * drawing.VIEW_SCALE / 1000.0
    for x, y in points:
        assert abs(x - drawing.BOTTOM_CENTER[0]) <= half_w
        assert abs(y - drawing.BOTTOM_CENTER[1]) <= half_h


def test_v2_support_and_p2_reliefs_share_the_installation_contract() -> None:
    assert placement.SUPPORT_WORLD_Z == MACHINE_Z_SHIFT
    assert {z for _, z in placement.SUPPORT_HOLD_DOWN_XZ} == {
        MACHINE_Z_SHIFT - 60.32,
        MACHINE_Z_SHIFT + 60.32,
    }
    assert math.isclose(
        placement.P2_BACK_X_MAX,
        46.99053046000287 + MACHINE_X_SHIFT,
    )
    assert math.isclose(placement.P2_BACK_Z_MIN, 75.75 + MACHINE_Z_SHIFT)
    assert placement.P2_SPRING_SLOT_LIGAMENT >= 2.4
    assert placement.P2_FOOT_SCREW_LIGAMENT >= 2.5


def test_notes_cover_casting_specifics() -> None:
    notes = support.DRAWING_NOTES
    assert "GRAY-IRON CASTING" in notes
    assert "CHAMFER 1.27 X 45" in notes
    assert "FILLET" in notes and "R12.7" in notes
    assert "WEB 6.35" in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_native_gdt_defines_mounting_reference_frame() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 3
    assert source.count("add_feature_control_frame(") == 2
    assert "characteristic=\"flatness\"" in source
    assert "characteristic=\"position\"" in source


def test_sheet_runs_1_to_2_with_explicit_view_scales() -> None:
    # A 177.8 mm casting with four views does not fit ASME B at 1:1.
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # Every view pins its scale explicitly — an unpinned view auto-scales and
    # silently shifts every coordinate-based pick on it.
    assert source.count("scale=(1, 2)") == 4


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(support.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("rocker-arm-support")
    assert "gray cast iron" in str(spec["material_specification"]).lower()
    assert spec["finish"]
    assert int(spec["quantity"]) == 1
