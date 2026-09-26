"""Offline contracts for MHA-149, the crank eccentric bushing (#906 A2)."""

from __future__ import annotations

import pytest

import _config
import build_crank_eccentric_bushing as part
import cone_pivot_post_spec
import crank_eccentric_bushing_spec as spec
import crankshaft_spec


def test_registry_row_names_the_part_and_its_fit() -> None:
    row = _config.parts("crank-eccentric-bushing")
    assert row["number"] == "MHA-149"
    assert row["fit_class"] == "shaft_in_bushing"
    assert part.PART_NAME == "crank-eccentric-bushing"


def test_nominals_follow_the_post_bore_and_the_crank_journal() -> None:
    assert spec.OUTER_DIA == cone_pivot_post_spec.CRANK_BORE_DIA
    assert spec.BORE_DIA == crankshaft_spec.JOURNAL_BORE_DIA
    # The ruling: centred Ø15.45 H7 post bore, e 0.45.
    assert (spec.OUTER_DIA, spec.ECCENTRICITY) == (15.45, 0.45)


def test_bore_band_is_derived_from_the_journal_and_the_fit_class() -> None:
    minimum, maximum = _config.fit("shaft_in_bushing")["diametral_clearance_mm"]
    journal_upper, journal_lower = crankshaft_spec.JOURNAL_DIA_BAND
    journal = crankshaft_spec.JOURNAL_DIA
    upper, lower = part.BORE_DIA_BAND
    assert spec.BORE_DIA + lower - (journal + journal_upper) == pytest.approx(minimum)
    assert spec.BORE_DIA + upper - (journal + journal_lower) == pytest.approx(maximum)
    # Same limits the post's old running bore printed: 11.413..11.443.
    assert round(spec.BORE_DIA + lower, 3) == 11.413
    assert round(spec.BORE_DIA + upper, 3) == 11.443


def test_od_is_a_shaft_in_bushing_slip_fit_in_the_post_h7() -> None:
    minimum, maximum = _config.fit("shaft_in_bushing")["diametral_clearance_mm"]
    post_upper, post_lower = cone_pivot_post_spec.CRANK_BORE_BAND
    od_upper, od_lower = part.OD_BAND
    assert post_lower - od_upper == pytest.approx(minimum)
    assert post_upper - od_lower == pytest.approx(maximum)
    assert round(spec.OUTER_DIA + od_upper, 3) == 15.425
    assert round(spec.OUTER_DIA + od_lower, 3) == 15.393


def test_thin_wall_holds_the_floor_at_print_worst() -> None:
    assert spec.WALL_FLOOR_MM == 1.5
    # ON the floor: the named exception's number (OD 15.393 min, throw
    # 0.475 max, bore 11.443 max).
    assert part.WALL_WORST == pytest.approx(1.500, abs=1e-9)


def test_throw_covers_the_mesh_stack_across_its_band() -> None:
    # 0.809 is the ruling's full-stack dC; the stack module will own it.
    assert 2.0 * (spec.ECCENTRICITY + spec.ECCENTRICITY_BAND[1]) >= 0.809


def test_length_keeps_the_outboard_land_inside_the_bushing() -> None:
    """The north end is flush with the spot face (the shaft's POST_BORE_END
    station), so a short bushing only moves its south end north.  With the
    bushing at the bottom of its row and the relief's outboard shoulder at the
    bottom of its own, the outboard land still bears one journal diameter
    inside the bushing (L/D >= 1)."""
    row_1 = 0.8
    south_end = crankshaft_spec.POST_BORE_END - (spec.LENGTH - row_1)
    relief_start_min = crankshaft_spec.RELIEF_START - crankshaft_spec.STATION_ROW
    assert relief_start_min - south_end >= crankshaft_spec.JOURNAL_DIA


def test_part_and_spec_share_one_dimension_contract() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert part.SURFACE_FINISHES is spec.SURFACE_FINISHES
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "ODDim": 3,
        "BoreDiaDim": 3,
        "BoreOffsetDim": 3,
        "Depth": 1,
    }


def test_note_identifies_both_mates_without_a_size() -> None:
    text = spec.DRAWING_NOTES
    assert len(text.splitlines()) == 1
    assert spec.SHAFT_MATE_NUMBER == _config.parts("crankshaft")["number"]
    assert spec.POST_MATE_NUMBER == _config.parts("cone-pivot-post")["number"]
    stripped = text.replace(spec.SHAFT_MATE_NUMBER, "").replace(
        spec.POST_MATE_NUMBER, ""
    )
    assert not any(character.isdigit() for character in stripped)
