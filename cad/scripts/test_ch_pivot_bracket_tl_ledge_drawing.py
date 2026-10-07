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


def test_printed_height_band_holds_the_top_parallel_to_the_table() -> None:
    low, high = _features()["foot_rest"]["height"]
    assert high - low <= spec.TOP_PARALLEL + 1e-9


def test_ledge_carries_the_whole_foot_and_clears_the_stud_nuts() -> None:
    low, high = _features()["foot_rest"]["width"]
    assert low >= bracket.FOOT_W
    assert high / 2.0 < plate.STUD_HALF_PITCH - plate.STUD_NUT_DIA / 2.0


def _pitch(left: list[float], right: list[float]) -> tuple[float, float]:
    return right[0] - left[1], right[1] - left[0]


def test_screws_pass_both_parts_at_their_worst_stations() -> None:
    """Each #10 screw sits in a plate tap and passes a ledge hole. Along the
    ledge it floats, so each screw takes half the worst pitch mismatch; across
    it the block fixes the ledge, so the heights' errors add. Both together
    stay inside the screw's radial clearance in the smallest ledge hole."""
    holes = _features()
    taps = export_features.requirement_manifest("ch_pivot_bracket_tl_angle_plate")["features"]
    ledge_lo, ledge_hi = _pitch(
        holes["screw_hole_left"]["station"], holes["screw_hole_right"]["station"]
    )
    plate_lo, plate_hi = _pitch(
        taps["ledge_tap_left"]["station"], taps["ledge_tap_right"]["station"]
    )
    along = max(ledge_hi - plate_lo, plate_hi - ledge_lo) / 2.0
    hole_y = holes["screw_hole_left"]["height"]
    tap_y = [y - plate.BLOCK_HEIGHT for y in taps["ledge_tap_left"]["height"]]
    across = max(tap_y[1] - hole_y[0], hole_y[1] - tap_y[0])
    radial = (holes["screw_hole_left"]["dia"][0] - THREAD_MAJOR_MM[plate.SCREW_THREAD]) / 2.0
    assert (along**2 + across**2) ** 0.5 <= radial


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-pivot-bracket")["number"]
    number = _config.parts("ch-pivot-bracket-tl-ledge")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert "GROUND" not in spec.DRAWING_NOTES.upper()
