"""Offline contracts for the rocker inspection box rework (MHA-CH-006-TL-08)."""

from __future__ import annotations

import re

import _config
import ch_rocker_arm_tl_c_stop_bar_spec as bar
import ch_rocker_arm_tl_inspection_box_spec as spec
import draw_ch_rocker_arm_tl_inspection_box as drawing
import export_features

STEM = "ch_rocker_arm_tl_inspection_box"


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    views = (drawing.LEFT_KEEP, drawing.FRONT_KEEP, drawing.BACK_KEEP)
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set().union(*views) == marked
    assert sum(len(view) for view in views) == len(marked)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked


def test_only_shop_rework_is_dimensioned() -> None:
    """The bought box parallel's size and wall are never printed as work."""
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert not marked & {"BoxW", "BoxD", "BoxH", "CoreW", "CoreD", "CoreX0", "CoreY0"}


def test_taps_match_the_c_stop_bar_screw_stations() -> None:
    box = _features()
    stop = export_features.requirement_manifest("ch_rocker_arm_tl_c_stop_bar")["features"]
    for side in ("left", "right"):
        tap, hole = box[f"bar_tap_{side}"], stop[f"screw_hole_{side}"]
        assert tap["at"][:2] == hole["at"][:2]
        assert tap["station"] == hole["station"]
        assert tap["height"] == hole["height"]


def test_clamp_windows_open_past_the_front_wall_inner_face() -> None:
    general = printed = export_features.requirement_manifest(STEM)["general_tolerances"]["linear_1pl"]
    assert spec.WINDOW_FRONT + printed < spec.WALL
    assert spec.WALL < spec.WINDOW_FRONT + spec.WINDOW_W - general


def test_screw_never_bottoms_in_the_tap() -> None:
    assert bar.SCREW_ENGAGEMENT <= _features()["bar_tap_left"]["depth"][0]


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-inspection-box")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert "GROUND" not in spec.DRAWING_NOTES.replace("BOUGHT GROUND", "")


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
