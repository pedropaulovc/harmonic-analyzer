"""Offline contracts for the rocker arm pivot screw and washer (MHA-CH-006-TL-06/07)."""

from __future__ import annotations

import re

import _config
import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_pivot_screw_spec as screw
import ch_rocker_arm_tl_pivot_washer_spec as washer
import draw_ch_rocker_arm_tl_pivot_screw as screw_drawing
import draw_ch_rocker_arm_tl_pivot_washer as washer_drawing
import export_features

SCREW = "ch_rocker_arm_tl_pivot_screw"
WASHER = "ch_rocker_arm_tl_pivot_washer"


def _features(stem: str) -> dict:
    return export_features.requirement_manifest(stem)["features"]


def test_every_marked_dimension_prints_once() -> None:
    for spec, keeps in (
        (screw, (screw_drawing.SIDE_KEEP, screw_drawing.END_KEEP)),
        (washer, (washer_drawing.FACE_KEEP, washer_drawing.EDGE_KEEP)),
    ):
        marked = set().union(*spec.DRAWING_DIMENSIONS.values())
        assert set(keeps[0]) | set(keeps[1]) == marked
        assert not set(keeps[0]) & set(keeps[1])
        assert set(spec.DRAWING_PRECISION_BY_NAME) == marked


def _band(nominal: float, band: tuple[float, float]) -> tuple[float, float]:
    return (round(nominal + band[1], 6), round(nominal + band[0], 6))


SHOULDER = _band(screw.SHOULDER_DIA, screw.SHOULDER_BAND)
HEAD = _band(screw.HEAD_DIA, screw.HEAD_BAND)


def test_shoulder_slides_into_every_bore_a_the_rocker_allows() -> None:
    smallest_bore_a = rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[1]
    largest_bore_a = rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[0]
    assert round(smallest_bore_a - SHOULDER[1], 6) >= screw.LOCATING_CLEARANCE_MIN
    # The inventory's worst float in A: 0.045.
    assert round(largest_bore_a - SHOULDER[0], 6) <= 0.045


def test_shoulder_fits_the_plate_bore_and_head_the_template_bush() -> None:
    assert round(screw.PLATE_BORE_LIMITS[0] - SHOULDER[1], 6) >= 0.010
    assert HEAD[1] <= screw.TEMPLATE_BUSH_BORE_LIMITS[0]


def test_match_fit_diameters_export_what_the_print_says() -> None:
    # One fact, one source: no hidden band behind a printed match fit.
    features = _features(SCREW)
    for key, nominal in (("shoulder", screw.SHOULDER_DIA), ("head", screw.HEAD_DIA)):
        assert "dia" not in features[key]
        assert features[key]["dia_nominal"] == nominal
        assert "note" in features[key]["requirements"]
    assert features["head"]["coaxial_to"] == "shoulder"
    assert features["head"]["note"] in screw.DRAWING_NOTES


def test_thread_engages_one_and_a_half_diameters_in_the_plate() -> None:
    engaged = screw.THREAD_LENGTH - screw.PLATE_FLOOR_GAP
    assert engaged >= 1.5 * screw.THREAD_MODEL_DIA


def test_washer_passes_the_shoulder_and_carries_the_head() -> None:
    bore = _features(WASHER)["bore"]["dia"]
    assert bore[0] > SHOULDER[1]
    assert bore[1] < HEAD[0]
    assert washer.THICK == screw.UNDERHEAD_Z


def test_numbers_are_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    for stem, suffix in (("ch-rocker-arm-tl-pivot-screw", "06"), ("ch-rocker-arm-tl-pivot-washer", "07")):
        assert _config.parts(stem)["number"] == f"{parent}-TL-{suffix}"


def test_notes_follow_the_simplicity_policy() -> None:
    for spec in (screw, washer):
        lines = spec.DRAWING_NOTES.splitlines()
        assert 1 <= len(lines) <= 4
        assert not re.search(r"\d", spec.DRAWING_NOTES)
        assert "GROUND" not in spec.DRAWING_NOTES
