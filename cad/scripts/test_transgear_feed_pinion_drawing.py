"""Offline contracts for the feed-pinion sleeve (MHA-110) and its drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_transgear_feed_pinion as part
import draw_transgear_feed_pinion as drawing
import transgear_feed_pinion_spec as spec
from _drawing_contract import (
    PRECISION_MIGRATED_DRAWINGS,
    drawing_specification_violations,
    model_toleranced_dimensions,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _printed_tolerance import printed_band_mm


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-feed-pinion.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-feed-pinion.pdf")
    assert drawing.PNG.as_posix().endswith("/png/transgear-feed-pinion_drawing.png")
    assert (
        DRAWINGS_BY_NAME["transgear_feed_pinion"].script
        == Path(drawing.__file__).resolve()
    )


def test_every_marked_dimension_is_placed_and_has_places() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked


def test_sheet_authors_no_manufacturing_value() -> None:
    # Rule 2: places and bands come from the part; the sheet reads them back.
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert not drawing_specification_violations(source, filename=drawing.__file__)


def test_bands_come_from_named_spec_constants() -> None:
    assert model_toleranced_dimensions(part) == {
        ("GearBlank", "FaceWidth"): "STATION_TOL",
        ("SleeveProfile", "SpigotFront"): "STATION_TOL",
        ("SleeveProfile", "OverallLength"): "STATION_TOL",
        ("SleeveProfile", "BoreDia"): "*BORE_DEVIATIONS",
        ("SleeveProfile", "SpigotDia"): "*SPIGOT_DIA_DEVIATIONS",
        ("SleeveProfile", "ShankDia"): "*SHANK_DIA_DEVIATIONS",
        ("SleeveProfile", "OutsideDia"): "*OUTSIDE_DIA_DEVIATIONS",
    }
    # A band tighter than its printed row needs a functional reason (rule 12):
    # the stations' ±0.05 sits inside their .XX row, the tip's +0/-0.10 inside .XXX.
    assert spec.STATION_TOL < printed_band_mm(spec.STATION_PLACES)
    assert -spec.OUTSIDE_DIA_BAND[1] < printed_band_mm(
        spec.DRAWING_PRECISION_BY_NAME["OutsideDia"]
    )


def test_root_prints_as_the_cutter_depth_floor() -> None:
    # swTolType_e.swTolMIN (offline API docs) prints the nominal then "MIN".
    assert spec.ROOT_DIA_TOL_TYPE == 5
    places = spec.DRAWING_PRECISION_BY_NAME["RootDia"]
    assert f"{spec.ROOT_DIA:.{places}f}" == f"{spec.ROOT_DIA_MIN:.{places}f}" == "8.04"
    assert spec.ROOT_DIA >= spec.ROOT_DIA_MIN
    # The model cuts the root the sheet floors: pitch radius less 1.25/P.
    pitch_r = spec.TEETH / spec.DIAMETRAL_PITCH / 2.0 * 25.4
    assert 2.0 * (
        pitch_r - spec.DEDENDUM_FACTOR / spec.DIAMETRAL_PITCH * 25.4
    ) == pytest.approx(spec.ROOT_DIA)
    lower, upper = spec.ROOT_DIA_DEVIATIONS
    assert spec.ROOT_DIA + lower == pytest.approx(spec.ROOT_DIA_MIN)
    assert upper == 0.0


def test_cluster_float_and_nose_proud_hold_worst_case() -> None:
    low, high = spec.CLUSTER_FLOAT_RANGE
    assert low == pytest.approx(0.2) and high == pytest.approx(0.4)
    assert spec.NOSE_PROUD == pytest.approx(0.70)
    assert spec.NOSE_PROUD_WORST >= 0.34 - 1e-9
    # The hub flange clamps the disc, never the spigot step.
    assert spec.SPIGOT_RECESS_WORST > 0.0
    assert spec.SPIGOT_LENGTH_MIN > 0.5 * spec.DISC_THICKNESS


def test_bore_runs_on_the_stud_journal() -> None:
    import transgear_stub_spec as stud

    assert spec.BORE_DIA == stud.JOURNAL_DIA
    j_upper, j_lower = stud.JOURNAL_DIA_BAND
    b_upper, b_lower = spec.BORE_DIA_BAND
    clearance = (b_lower - j_upper, b_upper - j_lower)
    assert clearance == pytest.approx(spec.BORE_DIAMETRAL_CLEARANCE)
    assert clearance[0] > 0.0
    # A running fit exists only when both size bands are narrower than the
    # clearance range they claim (tolerance-policy step 6b).
    span = clearance[1] - clearance[0]
    assert b_upper - b_lower < span and j_upper - j_lower < span


def test_oil_hole_lands_on_the_hub_hole_and_a_tooth_centre() -> None:
    import transgear_disc_hub_spec as hub
    from involute_gear import gear_facts

    hub_front = spec.GEAR_FACE_STATION + spec.DISC_THICKNESS + hub.HUB_LENGTH
    assert spec.OIL_HOLE_Z == pytest.approx(hub_front - hub.OIL_HOLE_STATION)
    assert spec.OIL_HOLE_DIA == hub.OIL_HOLE_DIA
    assert spec.SPIGOT_FRONT_STATION < spec.OIL_HOLE_Z < spec.OVERALL_LENGTH
    facts = gear_facts(spec.TEETH, spec.DIAMETRAL_PITCH, spec.PRESSURE_ANGLE_DEG)
    gap_centre = math.degrees((facts["ThetaL"] + facts["ThetaU"]) / 2.0)
    pitch = 360.0 / spec.TEETH
    offset = (spec.OIL_HOLE_AZIMUTH_DEG - gap_centre) % pitch
    assert offset == pytest.approx(pitch / 2.0)  # +Y is a tooth centre


def test_walls_meet_the_target_worst_case() -> None:
    for name, nominal, worst in spec.WALLS:
        assert worst >= spec.WALL_TARGET, name
        assert nominal >= worst, name


def test_sheet_text_names_the_right_parts() -> None:
    numbers = {
        "transgear-feed-pinion": spec.SLEEVE_NUMBER,
        "transgear-stub": spec.STUD_NUMBER,
        "transgear-disc-hub": spec.HUB_NUMBER,
        "rack-pinion": spec.DISC_NUMBER,
        "platen-rack": spec.RACK_NUMBER,
    }
    for stem, number in numbers.items():
        assert _config.parts(stem)["number"] == number, stem
    assert spec.OIL_HOLE_NOTE.startswith(f"MATCH DRILL AT ASSY WITH {spec.HUB_NUMBER}")
    assert f"MATE STUD {spec.STUD_NUMBER}" in spec.BORE_FIT_CALLOUT
    assert drawing.DIMENSION_CALLOUTS == {"BoreDia": spec.BORE_PROCESS_CALLOUT}


def test_part_record_and_finish() -> None:
    config = _config.parts("transgear-feed-pinion")
    assert config["material_specification"] == "SAE 1018 CF bar, ASTM A108-24"
    assert int(config["quantity"]) == 1
    (control,) = spec.SURFACE_FINISHES
    assert control.key == "bore"
    assert control.face.diameter_mm == spec.BORE_DIA
