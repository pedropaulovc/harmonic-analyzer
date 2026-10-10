"""Offline contracts for the pivot bracket's angle-plate ledge (MHA-CH-008-TL-01)."""

from __future__ import annotations

import re

import _config
import ch_pivot_bracket_sides as sides
import ch_pivot_bracket_spec as bracket
import ch_pivot_bracket_tl_angle_plate_spec as plate
import ch_pivot_bracket_tl_ledge_spec as spec
import draw_ch_pivot_bracket_tl_ledge as drawing
import export_features
from _feature_requirements import limits
from _hole_spec import THREAD_MAJOR_MM

# The prechips S4 hold the ledge and plate are built for (review/compose-r5
# follow-on 67237b9, examples/inventory/pedro-shop.toml [fixtures.angle-plate]
# and examples/pivot-bracket/plan.toml [setups.hold]), in Setup frame TC for
# the S configuration (the shorter foot the ledge is sized for): Z0 is the
# bracket's faced outer face, 4.04 proud of the plate top. The 2026-10-09
# flip moved every row; the prechips plan follows these.
PRECHIPS_PART_PROUD = 4.04
PRECHIPS_TABLE_Z = -92.94  # base box bottom
PRECHIPS_LEDGE_Z = (-42.14, -15.64)  # bolted foot-end ledge box, 26.5 high
PRECHIPS_SCREW_Z = -24.64  # ledge screws, clearance and tapped holes
PRECHIPS_STUD_Z = -11.94  # bridge stud holes (the bridge's Setup Z)


def _features() -> dict:
    return export_features.requirement_manifest("ch_pivot_bracket_tl_ledge")["features"]


def test_ledge_and_plate_stations_are_the_prechips_s4_stack() -> None:
    """BR-B1 (#1262): the part stands at least 4 mm proud, so the ledge is
    26.5 high with its holes 17.5 off its bottom, and the plate's taps and studs sit at
    the prechips hold's Z rows. Each printed value is held here, independently
    of the specs, and checked with its one-place band."""
    assert round(plate.PART_PROUD[plate.LEDGE_CONFIG], 2) == PRECHIPS_PART_PROUD
    ledge = _features()
    taps_and_studs = export_features.requirement_manifest("ch_pivot_bracket_tl_angle_plate")["features"]
    ledge_bottom = PRECHIPS_LEDGE_Z[0] - PRECHIPS_TABLE_Z  # on its 2 in block
    assert abs(ledge_bottom - plate.BLOCK_HEIGHT) < 1e-9
    height = round(PRECHIPS_LEDGE_Z[1] - PRECHIPS_LEDGE_Z[0], 1)
    hole_y = round(PRECHIPS_SCREW_Z - PRECHIPS_LEDGE_Z[0], 1)
    tap_y = round(PRECHIPS_SCREW_Z - PRECHIPS_TABLE_Z, 1)
    stud_y = round(PRECHIPS_STUD_Z - PRECHIPS_TABLE_Z, 1)
    assert (height, hole_y, tap_y, stud_y) == (26.5, 17.5, 68.3, 81.0)
    rest = ledge["foot_rest"]
    assert (rest["height_nominal"], rest["height"]) == (height, limits(height, 1))
    for side in ("left", "right"):
        hole = ledge[f"screw_hole_{side}"]
        assert (hole["height_nominal"], hole["height"]) == (hole_y, limits(hole_y, 1))
        assert taps_and_studs[f"ledge_tap_{side}"]["height_nominal"] == tap_y
        stud = taps_and_studs[f"stud_hole_{side}"]
        assert (stud["height_nominal"], stud["height"]) == (stud_y, limits(stud_y, 1))


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked


def test_every_exported_nominal_is_its_printed_value() -> None:
    """Each nominal is the value the sheet prints, at its printed places: the
    #5 callout's Ø5.22 and each station at its dimension's places. Lying inside
    the band is not enough (5.25 sits in [5.22, 5.32])."""
    places = spec.DRAWING_PRECISION_BY_NAME
    expected = {("foot_rest", "height_nominal"): round(spec.LEDGE_HEIGHT, places["Height"])}
    for side, x, dim in zip(("left", "right"), spec.HOLE_X, ("Hole1X", "Hole2X"), strict=True):
        expected |= {
            (f"screw_hole_{side}", "nominal_dia"): 5.22,
            (f"screw_hole_{side}", "station_nominal"): round(x, places[dim]),
            (f"screw_hole_{side}", "height_nominal"): round(spec.HOLE_Y, places["Hole1Y"]),
        }
    exported = {
        (name, key): value
        for name, feature in _features().items()
        for key, value in feature.items()
        if key.endswith("_nominal") or key.startswith("nominal_")
    }
    assert exported == expected


def test_ledge_top_meets_the_bracket_foot_free_end() -> None:
    """On its 1-2-3 block the ledge top stands where the foot's free end
    lands with the bracket's outer face proud of the plate top."""
    top = _features()["foot_rest"]["height_nominal"]
    for name, foot_len in sides.FOOT_LEN.items():
        foot_end = plate.PLATE_HEIGHT + plate.PART_PROUD[name] - foot_len
        assert abs(plate.BLOCK_HEIGHT + top - foot_end) < 1e-9
        assert plate.PART_PROUD[name] >= plate.PART_PROUD_MIN


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
