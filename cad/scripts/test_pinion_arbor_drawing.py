"""Behavioral release contracts for the integral MHA-102 pinion arbor."""

from __future__ import annotations

from pathlib import Path

import pytest

import _fit_limits
import build_pinion_arbor as part
import draw_pinion_arbor as drawing
import pinion_arbor_spec as spec
import pinion_handle_geometry as rod_geometry
import pinion_handle_spec as crossrod
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths_and_registry() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-arbor.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-arbor.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-arbor_drawing.png")
    assert DRAWINGS_BY_NAME["pinion_arbor"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_every_printed_dimension() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.DONOR_KEEP)
        | set(drawing.PRINCIPAL_KEEP)
        | set(drawing.DETAIL_KEEP)
    )
    assert kept == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert not hasattr(spec, "DRAWING_REFERENCE_PRECISION")
    assert {"HeadDia", "NeckDia", "ShaftDia"} == set(drawing.DONOR_KEEP)
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_integral_arbor_keeps_the_released_stations_around_a_longer_head() -> None:
    # Rule 12 (audit W6): the head grows 9.0 -> 10.5 about the released
    # crossrod station; the neck shoulder, shaft and back crown stay put.
    assert spec.HEAD_CENTER_Z == pytest.approx(-6.5)
    assert spec.HEAD_FRONT_Z == pytest.approx(-11.75)
    assert spec.HEAD_REAR_Z == pytest.approx(-1.25)
    assert spec.NECK_END_Z == pytest.approx(10.0)
    assert spec.SHAFT_LEN == pytest.approx(226.25)
    assert spec.HEAD_FRONT_Z - spec.HEAD_CAP_SAG == pytest.approx(-14.75)
    assert spec.SHAFT_LEN + spec.BACK_CAP_SAG == pytest.approx(227.45)
    assert spec.OVERALL_LEN == pytest.approx(242.2)
    assert spec.EXPOSED_SHAFT_LEN == pytest.approx(216.25)
    assert spec.BACK_RIM_FROM_HEAD_REAR == pytest.approx(227.5)


def test_crossrod_hole_is_centred_with_a_rule_12_web() -> None:
    # Printed centred on the head length: only HeadLen's .X band reaches the
    # web, never a separate station band.
    assert "CrossHoleReference" not in spec.DRAWING_DIMENSIONS
    assert "CENTRED ON HEAD LENGTH" in spec.CROSS_HOLE_CALLOUT
    assert spec.CROSS_HOLE_WEB_WORST == pytest.approx(1.80)
    assert spec.CROSS_HOLE_WEB_WORST >= 1.5


def test_integral_head_owns_the_crossrod_interface() -> None:
    assert spec.HEAD_DIA == pytest.approx(15.0)
    assert spec.HEAD_LEN == pytest.approx(10.5)
    assert spec.NECK_DIA == pytest.approx(10.5)
    assert spec.NECK_LEN == pytest.approx(11.25)
    callout = drawing.DIMENSION_CALLOUTS["CrossHoleDia"]
    assert callout is spec.CROSS_HOLE_CALLOUT
    assert callout == "REAM THRU,\nCENTRED ON HEAD LENGTH"
    assert "SHALL NOT TURN OR SLIDE BY HAND" in spec.DRAWING_NOTES


def test_crossrod_is_a_bonded_slip_fit_not_a_press() -> None:
    """R1 (U27 precedent): a novice's stock reamer and as-received bar give
    clearance, so the hole is banded Ø6.00 +0.10/0 and the rod is bonded."""
    assert spec.CROSS_HOLE_DIA == pytest.approx(6.0)
    assert spec.CROSS_HOLE_DIA_BAND == (0.10, 0.0)
    assert crossrod.ROD_DIA == pytest.approx(spec.CROSS_HOLE_DIA)  # line to line
    assert (
        model_toleranced_dimensions(part)[("CrossHoleProfile", "CrossHoleDia")]
        == "*deviations(CROSS_HOLE_DIA_BAND)"
    )
    assert spec.DRAWING_PRECISION_BY_NAME["CrossHoleDia"] == 2
    tightest = (spec.CROSS_HOLE_DIA + spec.CROSS_HOLE_DIA_BAND[1]) - (
        crossrod.ROD_DIA + rod_geometry.ROD_DIA_BAND[0]
    )
    loosest = (spec.CROSS_HOLE_DIA + spec.CROSS_HOLE_DIA_BAND[0]) - (
        crossrod.ROD_DIA + rod_geometry.ROD_DIA_BAND[1]
    )
    assert spec.CROSSROD_MIN_CLEARANCE == pytest.approx(tightest)
    assert spec.CROSSROD_MAX_CLEARANCE == pytest.approx(loosest)
    assert tightest >= 0.0
    assert loosest <= spec.RETAINING_COMPOUND_MAX_GAP_MM
    assert "ON ASSEMBLY: BOND MHA-058 WITH LOCTITE 638." in spec.DRAWING_NOTES
    for retired in ("MATCH-REAM", "PRESS", "INTERNAL SHOULDERS SHARP"):
        assert retired not in spec.DRAWING_NOTES
        assert retired not in spec.CROSS_HOLE_CALLOUT


def test_only_the_two_journal_lands_carry_the_running_band_and_finish() -> None:
    assert spec.JOURNAL_DIA_BAND is _fit_limits.SHAFT_H
    assert spec.SHAFT_DIA_BAND == (-0.01, -0.10)
    assert model_toleranced_dimensions(part) == {
        ("ShaftProfile", "ShaftDia"): "*deviations(SHAFT_DIA_BAND)",
        ("CrossHoleProfile", "CrossHoleDia"): "*deviations(CROSS_HOLE_DIA_BAND)",
        ("FrontJournalReference", "FrontJournalDia"): "*deviations(JOURNAL_DIA_BAND)",
        ("BackJournalReference", "BackJournalDia"): "*deviations(JOURNAL_DIA_BAND)",
    }
    lands = {
        "front_journal": spec.FRONT_JOURNAL_Z,
        "back_journal": spec.BACK_JOURNAL_Z,
    }
    assert {finish.key for finish in spec.SURFACE_FINISHES} == set(lands)
    for finish in spec.SURFACE_FINISHES:
        assert finish.roughness_um == 1.6
        assert finish.face.diameter_mm == spec.SHAFT_DIA
        station = lands[finish.key]
        assert station < finish.face.contains_z_mm < station + spec.JOURNAL_LEN
    assert set(drawing.JOURNAL_FINISHES) == set(lands)
    for key, (station_z, _symbol_xy) in drawing.JOURNAL_FINISHES.items():
        assert lands[key] < station_z < lands[key] + spec.JOURNAL_LEN
    assert spec.JOURNAL_LEN == pytest.approx(12.0)
    assert spec.FRONT_JOURNAL_FROM_HEAD_REAR == pytest.approx(50.5)
    assert spec.BACK_JOURNAL_FROM_HEAD_REAR == pytest.approx(203.2)
    assert "MHA-056" in spec.DRAWING_NOTES
    assert "SHAFT SLIPS INTO MHA-002 AND BONDS WITH LOCTITE 638." in spec.DRAWING_NOTES
    assert "PRESSES INTO" not in spec.DRAWING_NOTES
    assert not hasattr(spec, "PART_DATUMS")
    assert not hasattr(spec, "GEOMETRIC_CONTROLS")


def test_each_journal_land_covers_its_strap_with_axial_margin() -> None:
    """The lands must cover the MHA-056 straps where the assembly puts them."""
    import build_drive_train_assembly as assembly

    front_face = assembly.APINION_Z_FRONT - assembly.STRAP_AIR - assembly.ARBOR_Z0
    back_face = assembly.APINION_Z_BACK + assembly.STRAP_AIR - assembly.ARBOR_Z0
    # 9 mm is the thicker strap the pinion-cluster slice carries.
    for strap_t in {assembly.STRAP_T, 9.0}:
        for strap_lo, strap_hi, land_lo in (
            (front_face - strap_t, front_face, spec.FRONT_JOURNAL_Z),
            (back_face, back_face + strap_t, spec.BACK_JOURNAL_Z),
        ):
            assert strap_lo - land_lo >= 1.0
            assert land_lo + spec.JOURNAL_LEN - strap_hi >= 1.0


def test_journal_and_bond_zone_bands_leave_the_intended_fits() -> None:
    import alignment_pinion_spec as drum
    import pinion_bracket_spec as strap

    journal_upper, journal_lower = spec.JOURNAL_DIA_BAND
    strap_upper, strap_lower = strap.ARBOR_BORE_BAND
    assert strap_lower - journal_upper == pytest.approx(0.010)
    assert strap_upper - journal_lower == pytest.approx(0.045)
    # Every bore slides on from the back crown, so no zone may exceed 8.00.
    # The drum keeps its stock-H7 bore, so the bond zone sits 0.01 under it
    # for a guaranteed slide, and the worst gap stays inside Loctite 638's 0.25.
    shaft_upper, shaft_lower = spec.SHAFT_DIA_BAND
    assert journal_upper == 0.0
    assert shaft_upper == pytest.approx(-0.010)
    drum_upper, drum_lower = drum.ARBOR_BORE_BAND
    assert drum_lower - shaft_upper == pytest.approx(0.010)
    assert drum_upper - shaft_lower <= 0.20 + 1e-9


def test_retired_socket_and_retention_pin_are_not_exported() -> None:
    retired = {
        "RETENTION_HOLE_DIA",
        "RETENTION_PIN_STATION",
        "TUBE_ID",
        "TUBE_OD",
        "TUBE_LEN",
        "WALL_T",
    }
    assert retired.isdisjoint(vars(spec))
    assert "RETENTION PIN" not in spec.CROSS_HOLE_CALLOUT


def test_every_post_import_name_is_carried_by_a_kept_or_moved_dimension() -> None:
    """Offline audit of the names the sheet looks up after the model import."""
    carried = (
        set(drawing.DONOR_KEEP)
        | set(drawing.PRINCIPAL_KEEP)
        | set(drawing.DETAIL_KEEP)
    )
    assert set(drawing.DIMENSION_CALLOUTS) <= carried
    assert set(spec.DRAWING_PRECISION_BY_NAME) == carried
    assert set(drawing.DIAMETER_POSITIONS) <= carried
    assert {"CrossHoleDia", "HeadCapSagDim", "BackCapSagDim", "OverallLen"} <= carried


def test_back_crown_radius_is_the_model_dimension_not_typed_text() -> None:
    assert spec.DRAWING_DIMENSIONS["BackCapProfile"] == {"BackCapR", "BackCapSagDim"}
    assert spec.DRAWING_PRECISION_BY_NAME["BackCapR"] == 1
    assert "BackCapR" in drawing.PRINCIPAL_KEEP
    assert drawing.DIMENSION_CALLOUTS["BackCapSagDim"] == "BACK CROWN"
    assert not any("SR" in text for text in drawing.DIMENSION_CALLOUTS.values())


def test_every_printed_length_is_exact_at_its_authored_places() -> None:
    """A one-place print of 11.25 reads 11.3: the sheet would not state the model."""
    nominal = {
        "HeadLen": spec.HEAD_LEN,
        "NeckLen": spec.NECK_LEN,
        "BackRimFromHeadRear": spec.BACK_RIM_FROM_HEAD_REAR,
        "OverallLen": spec.OVERALL_LEN,
        "FrontJournalFromHeadRear": spec.FRONT_JOURNAL_FROM_HEAD_REAR,
        "BackJournalFromHeadRear": spec.BACK_JOURNAL_FROM_HEAD_REAR,
        "FrontJournalLen": spec.JOURNAL_LEN,
        "BackJournalLen": spec.JOURNAL_LEN,
    }
    for name, value in nominal.items():
        places = spec.DRAWING_PRECISION_BY_NAME[name]
        assert value == pytest.approx(round(value, places), abs=1e-9), name
