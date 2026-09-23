"""Offline contracts for the through-hub crankshaft drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import build_crankshaft as part
import crank_hub_geometry as geometry
import crankshaft_spec as spec
import draw_crankshaft as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crankshaft.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crankshaft.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crankshaft_drawing.png")
    assert DRAWINGS_BY_NAME["crankshaft"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert marked == {
        "ShaftDiaDim",
        "Depth",
        "DomeHeight",
        "JournalDiaDim",
        "OverallLength",
        "JournalInboardStation",
        "JournalOutboardStation",
        "PinHoleStation",
        "DomeSphereRadius",
    }
    # Diameters are imported in the end view only to be dragged onto the
    # longitudinal profile (policy rule 7: diameters on the side view).
    assert set(drawing.DIAMETER_POSITIONS) == set(drawing.END_KEEP)


def test_policy_migrated_sheet_carries_no_gdt_and_model_owned_places() -> None:
    # Rule 3: a shaft carries no frames, datums or basic dimensions.
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_feature_control_frame",
        "add_datum_feature",
        "set_basic_dimension",
        "set_dimension_precision",
    ):
        assert helper not in source
    # Rule 2: the part authors every printed dimension's places.
    assert "draw_crankshaft.py" in PRECISION_MIGRATED_DRAWINGS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    functional_fits = {"ShaftDiaDim", "JournalDiaDim"}
    for name, places in spec.DRAWING_PRECISION_BY_NAME.items():
        assert places == (3 if name in functional_fits else 1), name
    assert spec.REFERENCE_DIMENSIONS <= marked
    assert spec.SPHERICAL_DIMENSIONS <= spec.REFERENCE_DIMENSIONS


def test_far_end_stations_restate_the_modelled_geometry() -> None:
    # The StationReference sketch drives each printed station from the same
    # globals as the features; these are the values the equations evaluate to.
    far = spec.SHAFT_LENGTH
    assert far - (spec.JOURNAL_START + spec.JOURNAL_LENGTH) == pytest.approx(19.8)
    assert far - spec.JOURNAL_START == pytest.approx(89.2449, abs=1e-3)
    assert far - spec.PIN_HOLE_HEIGHT == pytest.approx(118.0)
    assert far + spec.SHAFT_DOME_HEIGHT == pytest.approx(132.0)
    assert part.DOME_SPHERE_R == pytest.approx(6.6710, abs=1e-3)


def test_notes_stay_within_rule_six() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert all(len(line) <= 66 for line in lines)


def test_face_shift_preserves_every_inboard_world_station() -> None:
    assert spec.SHAFT_LENGTH == 130.0
    assert spec.JOURNAL_START == pytest.approx(40.755105572)
    assert spec.JOURNAL_END == pytest.approx(110.2)
    assert spec.JOURNAL_LENGTH == pytest.approx(69.4449, abs=1e-4)
    assert -183.0 + spec.JOURNAL_START == pytest.approx(-142.244894428)
    assert -183.0 + spec.JOURNAL_END == pytest.approx(-72.8)
    assert part.SEAT_T12 == pytest.approx(25.5)
    assert part.SEAT_PINION == pytest.approx(113.039505572)
    assert not hasattr(part, "SEAT_ARM")
    assert -183.0 + part.SEAT_T12 == pytest.approx(-157.5)
    assert -183.0 + part.SEAT_PINION == pytest.approx(-69.960494428)
    assert -183.0 + spec.SHAFT_LENGTH == pytest.approx(-53.0)


def test_integral_dome_is_the_only_outboard_shaft_projection() -> None:
    assert spec.SHAFT_DIA == geometry.SHAFT_DIA
    assert spec.SHAFT_DIA == pytest.approx(9.525, abs=1e-12)
    assert spec.SHAFT_DOME_HEIGHT == geometry.SHAFT_DOME_HEIGHT == 2.0
    assert geometry.SHAFT_DIA + geometry.SHAFT_DIA_BAND[0] < (
        geometry.HUB_BORE_DIA + geometry.HUB_BORE_BAND[1]
    )
    assert not hasattr(spec, "CRANK_END_NOTE")


def test_mha024_station_and_notes_belong_to_hub_and_shaft() -> None:
    assert part.PIN_HOLE_SPEC is spec.PIN_HOLE_SPEC
    assert drawing.PIN_HOLE_SPEC is spec.PIN_HOLE_SPEC
    assert drawing._PIN_HOLE_DIA == blind_cut_dia_mm(spec.PIN_HOLE_SPEC)
    assert spec.PIN_HOLE_HEIGHT == geometry.SERVICE_PIN_STATION == 12.0
    # The matched fit identifies both mating parts on the feature callout.
    process = spec.CROSS_HOLE_PROCESS
    assert "TAPER-REAM" in process
    assert "LIGHT DRIVE FIT" in process
    assert "MHA-137" in process
    assert "MHA-024" in process
    assert process.splitlines()[-1] == "#9 DRILL"
    assert "MHA-020" not in process


def test_shaft_end_fiducial_is_a_simple_punch_not_a_dimensioned_dimple() -> None:
    assert spec.FIDUCIAL_MODEL_DIA == geometry.FIDUCIAL_MODEL_DIA == 0.8
    assert spec.FIDUCIAL_MODEL_DEPTH == geometry.FIDUCIAL_MODEL_DEPTH == 0.2
    assert spec.SHAFT_FIDUCIAL_RADIUS == geometry.SHAFT_FIDUCIAL_RADIUS == 2.5
    assert "PUNCH FIDUCIAL MARK" in spec.DRAWING_NOTES
    assert "BY EYE" in spec.DRAWING_NOTES
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert all("Fiducial" not in name for name in marked)
    assert "DIMPLE" not in spec.DRAWING_NOTES


def test_side_view_sheet_stations_follow_the_model() -> None:
    scale = drawing.SHEET_SCALE[0]
    span = spec.SHAFT_LENGTH + spec.SHAFT_DOME_HEIGHT
    assert drawing.DOME_TIP_X == pytest.approx(
        drawing.SIDE_CENTER[0] - span * scale / 2000.0
    )
    assert drawing.FAR_END_X == pytest.approx(
        drawing.SIDE_CENTER[0] + span * scale / 2000.0
    )
    assert drawing.DOME_ROOT_X == pytest.approx(
        drawing.DOME_TIP_X + spec.SHAFT_DOME_HEIGHT * scale / 1000.0
    )
    assert drawing.PIN_X == pytest.approx(
        drawing.DOME_ROOT_X + spec.PIN_HOLE_HEIGHT * scale / 1000.0
    )


def test_horizontal_profile_and_left_end_view_are_third_angle_aligned() -> None:
    # *Right rotated -90 deg puts model +Y (far end) at paper-right and +Z up;
    # *Bottom (X right, Z up) is then the true left view, on the same axis.
    assert drawing.SIDE_VIEW_ANGLE == pytest.approx(-math.pi / 2.0)
    assert drawing.END_CENTER[1] == drawing.SIDE_CENTER[1]
    end_radius = spec.JOURNAL_DIA * drawing.SHEET_SCALE[0] / 2000.0
    assert drawing.END_CENTER[0] + end_radius < drawing.DOME_TIP_X


def test_sheet_placements_stay_inside_the_border() -> None:
    inner = (0.0127, 0.0127, 0.4191, 0.2667)  # ASME B landscape inner border
    title_block = (0.218, 0.065)  # x >= and y <=
    points = [
        drawing.END_CENTER,
        drawing.ISO_CENTER,
        drawing.HOLE_CALLOUT_XY,
        drawing.NOTES_XY,
        drawing.ISO_NOTE_XY,
        drawing.FINISH_SYMBOL,
        *drawing.SIDE_KEEP.values(),
        *drawing.DIAMETER_POSITIONS.values(),
    ]
    for x, y in points:
        assert inner[0] < x < inner[2] and inner[1] < y < inner[3]
        assert not (x >= title_block[0] and y <= title_block[1])
    # Both dragged diameters land on the section their profile sketch starts,
    # so their axis-parallel extension lines hide under the silhouette:
    # Ø9.525 on the dome-side seat, Ø11.388 on the journal.
    shaft_x = drawing.DIAMETER_POSITIONS["ShaftDiaDim"][0]
    journal_x = drawing.DIAMETER_POSITIONS["JournalDiaDim"][0]
    hole_radius = drawing._PIN_HOLE_DIA * drawing.SHEET_SCALE[0] / 2000.0
    assert drawing.PIN_X + hole_radius < shaft_x < drawing.JOURNAL_START_X
    assert drawing.JOURNAL_START_X < journal_x < drawing.JOURNAL_END_X
    # The cross-hole callout sits right of the hole so its leader cannot run
    # near-parallel to the station extension line through the hole.
    assert drawing.HOLE_CALLOUT_XY[0] > drawing.PIN_X
    assert drawing.JOURNAL_START_X < drawing.FINISH_PICK[0] < drawing.JOURNAL_END_X


def test_journal_fit_and_surface_finish_remain_unchanged() -> None:
    assert spec.JOURNAL_BORE_DIA == 11.438
    assert spec.JOURNAL_CLEARANCE == 0.05
    assert spec.JOURNAL_DIA == 11.388
    assert spec.JOURNAL_DIA_BAND == (0.0, -0.02)
    # Rule 5: one Ra on the running journal; the band, not a note, states it.
    assert len(spec.SURFACE_FINISHES) == 1
    assert spec.SURFACE_FINISHES[0].key == "bearing_journal"
    assert spec.JOURNAL_DIA + spec.JOURNAL_DIA_BAND[0] < spec.JOURNAL_BORE_DIA


def test_view_scales_and_linked_notes_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert drawing.VIEW_SCALE == (2, 1)
    assert drawing.ISO_SCALE == (1, 1)
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW\nSCALE 1:1"


def test_part_registry_retains_make_critical_properties() -> None:
    import _config

    config = _config.parts("crankshaft")
    assert config["material"] == config["material_specification"]
    assert "1018" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 1


def test_pinion_land_is_turnable_at_the_printed_band() -> None:
    # U27: the 0.25 land left by a journal running the full post bore was
    # unturnable.  The journal stops short; the land between its shoulder
    # and the pinion seat keeps 2 mm at the .X band on the printed station.
    land = part.SEAT_PINION - spec.JOURNAL_END
    assert land == pytest.approx(2.8395, abs=1e-4)
    assert land - geometry.GENERAL_1PL_TOL_MM >= 2.0
    post_bore = 104.789505572 - 32.755105572
    assert spec.JOURNAL_LENGTH / post_bore > 0.96
