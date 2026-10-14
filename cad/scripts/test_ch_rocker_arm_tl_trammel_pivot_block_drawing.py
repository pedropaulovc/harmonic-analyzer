"""Offline contracts for the rocker template trammel pivot block (MHA-CH-006-TL-14)."""

from __future__ import annotations

import inspect
import re

import _config
import ch_rocker_arm_tl_trammel_pivot_block_spec as spec
import ch_rocker_arm_tl_trammel_spec as kit
import draw_ch_rocker_arm_tl_trammel_pivot_block as drawing
import export_features
from _hole_spec import THREAD_MAJOR_MM

STEM = "ch_rocker_arm_tl_trammel_pivot_block"
_KEEPS = (drawing.TOP_KEEP, drawing.FRONT_KEEP, drawing.RIGHT_KEEP, drawing.BACK_KEEP)


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set().union(*_KEEPS) == marked
    assert sum(len(keep) for keep in _KEEPS) == len(marked)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(drawing.CALLOUTS_ABOVE) | set(drawing.CALLOUTS_BELOW) <= marked


def test_every_view_including_the_isometric_hides_its_hidden_lines() -> None:
    assert "for view in (top, front, right, back, iso):" in inspect.getsource(
        drawing.build
    )


def test_point_hole_is_the_reamed_fit_named_on_the_pivot_point() -> None:
    hole = _features()["point_hole"]
    assert hole["dia"] == [6.375, 6.388]
    assert "MHA-CH-006-TL-18" in hole["note"]
    assert "MHA-CH-006-TL-18" in spec.POINT_HOLE_CALLOUT
    # The shop's 0.251 in reamer (tools.reamers), three places.
    assert spec.POINT_HOLE_DIA == round(0.251 * kit.INCH, 3)
    assert spec.POINT_CLEARANCE_MIN > 0.0


def test_bar_slot_band_passes_the_bar_and_names_it() -> None:
    slot = _features()["bar_slot"]
    assert slot["width"] == [6.45, 6.5]
    assert slot["depth"] == [8.99, 10.01]
    assert spec.SLOT_CLEARANCE_MIN > 0.0
    assert "TRAMMEL BAR" in spec.SLOT_WIDTH_CALLOUT
    assert spec.SLOT_CORNER_CALLOUT.endswith("MAX")


def test_stations_agree_with_the_kit() -> None:
    assert spec.HOLE_FROM_END == kit.PIVOT_HOLE_L
    assert [x + spec.HOLE_FROM_END for x in spec.SET_SCREW_X] == list(kit.SET_SCREW_L)
    assert spec.SET_SCREW_DEPTH == -kit.SET_SCREW_Z
    assert (spec.SLOT_WIDTH, spec.SLOT_FROM_EDGE_A, spec.SLOT_DEPTH) == (
        kit.SLOT_WIDTH,
        kit.SLOT_FROM_EDGE_A,
        kit.SLOT_DEPTH,
    )
    assert spec.POINT_FROM_EDGE_A == kit.POINT_FROM_EDGE_A
    assert spec.BLOCK_X0 < spec.PINCH_X[0] < 0.0 < spec.SLIT_END_X < spec.BLOCK_X1


def test_walls_and_threads_hold_at_the_worst_case() -> None:
    """Rules 17 and 18 at the printed bands; rule 20 names every wall
    between the 1.5 floor and the 2.0 target."""
    assert min(spec.WORST_WALLS.values()) >= spec.WALL_FLOOR
    assert set(spec.RULE_20_SHORTFALLS) == {
        "pinch thread to slot floor",
        "pinch clearance to block bottom",
        "pinch thread to block bottom",
    }
    assert spec.PINCH_FULL_THREAD >= 1.5 * THREAD_MAJOR_MM[spec.PINCH_THREAD]
    assert spec.SET_SCREW_FULL_THREAD >= 1.5 * THREAD_MAJOR_MM[spec.SET_SCREW_SIZE]
    assert spec.SET_SCREW_REACH_GAP < kit.SET_SCREW_LENGTH


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-trammel-pivot-block")["number"]
    assert number == f"{parent}-TL-14"
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert not re.search(
        r"GROUND|LAPP|GRIND|DRILL|REAM|MILL|SAW", spec.DRAWING_NOTES.upper()
    )


def test_every_exported_band_endpoint_is_a_printed_value() -> None:
    """A band applied to an unrounded model nominal exports limits the sheet
    never prints."""
    checked = 0
    for name, feature in _features().items():
        for requirement in feature["requirements"]:
            band = feature.get(requirement)
            if not (isinstance(band, list) and len(band) == 2):
                continue
            places = feature["precision"][requirement]
            for end in band:
                assert abs(end - round(end, places)) < 1e-9, (
                    name,
                    requirement,
                    band,
                    places,
                )
            nominal = feature.get(f"{requirement}_nominal")
            if nominal is not None:
                assert band[0] <= nominal <= band[1], (name, requirement, nominal, band)
                assert abs(nominal - round(nominal, places)) < 1e-9, (
                    name,
                    requirement,
                    nominal,
                )
            checked += 1
    assert checked
