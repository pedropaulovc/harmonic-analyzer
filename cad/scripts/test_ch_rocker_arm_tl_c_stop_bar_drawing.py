"""Offline contracts for the rocker inspection C stop bar (MHA-CH-006-TL-09)."""

from __future__ import annotations

import re

import _config
import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_c_stop_bar_spec as spec
import draw_ch_rocker_arm_tl_c_stop_bar as drawing
import export_features
from _hole_spec import THREAD_MAJOR_MM

STEM = "ch_rocker_arm_tl_c_stop_bar"


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert {name for _feature, name in spec.DRAWING_BANDS} <= marked


def test_datum_c_height_band_holds_the_rod_hole_position_chain() -> None:
    """The size envelope is the only parallelism control: its total band,
    as a tilt over the bar, may spend at most a quarter of the Ø0.20."""
    top = _features()["c_stop_top"]
    assert top["height"] == [12.697, 12.703]
    tilt = top["height"][1] - top["height"][0]
    assert 2.0 * spec.OP50_HUB_TO_ROD * tilt / spec.BAR_LENGTH <= 0.25 * 0.20


def test_rocker_c_land_rests_wholly_on_the_bar_top() -> None:
    top = _features()["c_stop_top"]
    assert top["width"][0] > rocker.ARM_THICKNESS
    assert spec.C_LAND_X0 > 0.0
    assert spec.C_LAND_X0 + rocker.TIP_FACE < top["length"][0]


def test_worst_screw_stations_still_pass_the_screw() -> None:
    """Bar holes and box taps each at the edge of their printed band, on both
    axes in opposite directions, leave the screw inside the clearance hole."""
    hole = _features()["screw_hole_left"]
    worst_offset = 2.0 * (2.0 * (hole["station"][1] - spec.SCREW_X[0]) ** 2) ** 0.5
    smallest_clearance = hole["dia"][0] - THREAD_MAJOR_MM[spec.SCREW_THREAD]
    assert worst_offset < smallest_clearance / 2.0


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-c-stop-bar")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert not re.search(r"GROUND|LAPP|GRIND", spec.DRAWING_NOTES.upper())


def test_every_exported_band_endpoint_is_a_printed_value() -> None:
    """One fact: a band applied to an unrounded model nominal exports limits
    the sheet never prints (4.978 + 0.1 where the print reads 4.98)."""
    checked = 0
    for name, feature in _features().items():
        for requirement in feature["requirements"]:
            band = feature.get(requirement)
            if not (isinstance(band, list) and len(band) == 2):
                continue
            places = feature["precision"][requirement]
            for end in band:
                assert abs(end - round(end, places)) < 1e-9, (name, requirement, band, places)
            checked += 1
    assert checked
