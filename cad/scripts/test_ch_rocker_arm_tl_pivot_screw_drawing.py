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
    assert features["shoulder"]["note"] == " ".join(screw.SHOULDER_FIT_CALLOUT.splitlines())
    assert features["head"]["note"] == " ".join(screw.HEAD_FIT_CALLOUT.splitlines())


def test_fit_callout_names_the_rocker_by_its_registered_number() -> None:
    # The profile plate's config lives on its sibling branch (TL-02).
    assert _config.parts("ch-rocker-arm")["number"] == screw.ROCKER_NUMBER


def test_exported_stack_clears_the_bore_floor_and_engages_one_and_a_half_diameters() -> None:
    # Replay the axial stack from the exported (printed) bands, worst case.
    features = _features(SCREW)
    thick = _features(WASHER)["hub_face"]["thickness"]
    shoulder = features["shoulder"]["length"]
    thread = features["thread"]["length"]
    floor_min, floor_max = screw.FLOOR_DEPTH
    shoulder_end_max = thick[1] + shoulder[1]
    assert floor_min - shoulder_end_max >= screw.THREAD_RUNOUT + 0.1
    # Tip depth from the two printed lengths under the head.
    tip_min = thick[0] + screw.UNDER_HEAD_LENGTH - 0.13
    full_end_min = tip_min - floor_max - screw.TIP_CHAMFER - screw.THREAD_PITCH / 2.0
    assert full_end_min >= 1.5 * screw.THREAD_MODEL_DIA
    tip_max = thick[1] + screw.UNDER_HEAD_LENGTH + 0.13
    assert tip_max - floor_min - screw.TIP_CHAMFER <= screw.profile.PIVOT_TAP_THREAD_DEPTH - 0.51
    assert thread[0] <= screw.UNDER_HEAD_LENGTH - screw.SHOULDER_LENGTH <= thread[1]


def test_washer_passes_the_shoulder_and_carries_the_head() -> None:
    bore = _features(WASHER)["bore"]["dia"]
    assert bore[0] > SHOULDER[1]
    assert bore[1] < HEAD[0]
    assert washer.THICK == screw.UNDERHEAD_Z
    assert washer.WALL_MIN >= 1.5


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
