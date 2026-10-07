"""Offline contracts for the pivot bracket's angle-plate ledge (MHA-CH-008-TL-01)."""

from __future__ import annotations

import re

import _config
import ch_pivot_bracket_spec as bracket
import ch_pivot_bracket_tl_angle_plate_spec as plate
import ch_pivot_bracket_tl_ledge_spec as spec
import draw_ch_pivot_bracket_tl_ledge as drawing
import export_features
from _hole_spec import THREAD_MAJOR_MM


def _features() -> dict:
    return export_features.requirement_manifest("ch_pivot_bracket_tl_ledge")["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked


def test_ledge_top_meets_the_bracket_foot_free_end() -> None:
    """On its 1-2-3 block the ledge top stands where the foot's free end
    lands with the bracket's outer face proud of the plate top."""
    top = _features()["foot_rest"]["height_nominal"]
    foot_end = plate.PLATE_HEIGHT + plate.PART_PROUD - bracket.FOOT_LEN
    assert abs(plate.BLOCK_HEIGHT + top - foot_end) < 1e-9


def test_ledge_carries_the_whole_foot_and_clears_the_stud_nuts() -> None:
    low, high = _features()["foot_rest"]["width"]
    assert low >= bracket.FOOT_W
    assert high / 2.0 < plate.STUD_HALF_PITCH - plate.STUD_NUT_DIA / 2.0


def test_ledge_holes_sit_on_the_plate_taps_on_their_block() -> None:
    """The taps are spotted through the ledge holes with the ledge on its
    block, so both parts' nominal stations must already coincide there."""
    holes = _features()
    taps = export_features.requirement_manifest("ch_pivot_bracket_tl_angle_plate")["features"]
    ledge_left = (plate.PLATE_LENGTH - spec.LEDGE_WIDTH) / 2.0
    for side in ("left", "right"):
        hole, tap = holes[f"screw_hole_{side}"], taps[f"ledge_tap_{side}"]
        assert abs(ledge_left + hole["station_nominal"] - tap["station_nominal"]) < 1e-9
        assert abs(plate.BLOCK_HEIGHT + hole["height_nominal"] - tap["height_nominal"]) < 1e-9
    assert holes["screw_hole_left"]["dia"][0] > THREAD_MAJOR_MM[plate.SCREW_THREAD]


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-pivot-bracket")["number"]
    number = _config.parts("ch-pivot-bracket-tl-ledge")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert "GROUND" not in spec.DRAWING_NOTES.upper()
