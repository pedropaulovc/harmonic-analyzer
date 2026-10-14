"""Offline contracts for the rocker template trammel scriber block (MHA-CH-006-TL-15)."""

from __future__ import annotations

import inspect
import re

import _config
import ch_rocker_arm_tl_trammel_pivot_block_spec as block
import ch_rocker_arm_tl_trammel_scriber_block_spec as spec
import ch_rocker_arm_tl_trammel_spec as kit
import draw_ch_rocker_arm_tl_trammel_scriber_block as drawing
import export_features
from _hole_spec import THREAD_MAJOR_MM

STEM = "ch_rocker_arm_tl_trammel_scriber_block"
_KEEPS = (drawing.TOP_KEEP, drawing.FRONT_KEEP, drawing.RIGHT_KEEP, drawing.BACK_KEEP)


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set().union(*_KEEPS) == marked
    assert sum(len(keep) for keep in _KEEPS) == len(marked)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(drawing.CALLOUTS_ABOVE) | set(drawing.CALLOUTS_BELOW) <= marked


def test_shares_the_pivot_block_section() -> None:
    """Only the holes, slit end and screw stations differ from the pivot block."""
    for feature in (
        "BlockProfile",
        "Block",
        "SlotProfile",
        "SlitProfile",
        "SetScrewTaps",
    ):
        assert spec.DRAWING_DIMENSIONS[feature] == block.DRAWING_DIMENSIONS[feature]
        assert spec.DRAWING_PRECISION[feature] == block.DRAWING_PRECISION[feature]


def test_every_view_including_the_isometric_hides_its_hidden_lines() -> None:
    assert "for view in (top, front, right, back, iso):" in inspect.getsource(
        drawing.build
    )


def test_point_holes_are_the_reamed_fit_named_on_the_scriber_points() -> None:
    features = _features()
    for name in ("point_hole_inner", "point_hole_outer"):
        assert features[name]["dia"] == [6.375, 6.388]
    assert "MHA-CH-006-TL-16" in features["point_hole_inner"]["note"]
    assert spec.POINT_HOLE_CALLOUT.startswith("2X ")
    assert "MHA-CH-006-TL-16" in spec.POINT_HOLE_CALLOUT


def test_spacing_is_the_kit_band_and_names_its_check() -> None:
    outer = _features()["point_hole_outer"]
    # The spacing is the outer hole's station from the inner hole's axis.
    assert outer["station"] == [15.99, 16.01]
    assert "MHA-CH-006-TL-17" in outer["note"]
    assert "MHA-CH-006-TL-17" in spec.SCRIBER_SPACING_CALLOUT
    assert kit.TEMPLATE_RADII[1] - kit.TEMPLATE_RADII[0] == spec.SCRIBER_SPACING


def test_stations_agree_with_the_kit() -> None:
    assert [x + spec.HOLE_FROM_END for x in spec.HOLE_X] == list(kit.SCRIBER_HOLE_L)
    assert [x + spec.HOLE_FROM_END for x in spec.SET_SCREW_X] == list(kit.SET_SCREW_L)
    assert (
        spec.BLOCK_X0
        < spec.PINCH_X[0]
        < spec.HOLE_X[0]
        < spec.PINCH_X[1]
        < spec.HOLE_X[1]
    )
    assert spec.HOLE_X[1] < spec.SLIT_END_X < spec.BLOCK_X1


def test_the_outer_point_lands_in_the_h816_pilot() -> None:
    assert spec.H816_LATERAL_MISS < kit.CENTER_DRILL_PILOT_DIA / 2.0


def test_walls_and_threads_hold_at_the_worst_case() -> None:
    """Rules 17 and 18 at the printed bands; rule 20 names every wall
    between the 1.5 floor and the 2.0 target."""
    assert min(spec.WORST_WALLS.values()) >= block.WALL_FLOOR
    assert set(spec.RULE_20_SHORTFALLS) == {
        "pinch thread to slot floor",
        "pinch clearance to block bottom",
        "pinch thread to block bottom",
        "pinch clearance to point hole",
        "pinch thread to point hole",
    }
    assert block.PINCH_FULL_THREAD >= 1.5 * THREAD_MAJOR_MM[block.PINCH_THREAD]
    assert block.SET_SCREW_FULL_THREAD >= 1.5 * THREAD_MAJOR_MM[block.SET_SCREW_SIZE]


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-trammel-scriber-block")["number"]
    assert number == f"{parent}-TL-15"
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
