"""Offline contracts for MHA-149, the crank eccentric bushing (#906 R1)."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import build_crank_eccentric_bushing as part
import cone_pivot_post_spec
import crank_eccentric_bushing_spec as spec
import crank_hub_geometry
import crank_mesh_stack
import crankshaft_spec


def _policy() -> str:
    return (
        Path(spec.__file__).parents[1] / "docs" / "drawing-simplicity-policy.md"
    ).read_text(encoding="utf-8")


def test_registry_row_names_the_part_and_its_fit() -> None:
    row = _config.parts("crank-eccentric-bushing")
    assert row["number"] == "MHA-149"
    assert row["fit_class"] == "shaft_in_bushing"
    assert part.PART_NAME == "crank-eccentric-bushing"


def test_nominals_follow_the_post_bore_and_the_shaft_core() -> None:
    assert spec.OUTER_DIA == cone_pivot_post_spec.CRANK_BORE_DIA
    shaft = crank_hub_geometry.SHAFT_DIA
    assert spec.BORE_DIA == pytest.approx(shaft + 0.05)
    assert spec.POST_BORE_LENGTH == round(cone_pivot_post_spec.CRANK_BOSS_LENGTH, 1)


def test_bore_band_is_derived_from_the_core_and_the_fit_class() -> None:
    minimum, maximum = _config.fit("shaft_in_bushing")["diametral_clearance_mm"]
    shaft_upper, shaft_lower = crank_hub_geometry.SHAFT_DIA_BAND
    shaft = crank_hub_geometry.SHAFT_DIA
    upper, lower = part.BORE_DIA_BAND
    assert spec.BORE_DIA + lower - (shaft + shaft_upper) == pytest.approx(minimum)
    assert spec.BORE_DIA + upper - (shaft + shaft_lower) == pytest.approx(maximum)


def test_od_is_g6_in_the_post_h7() -> None:
    assert spec.OD_BAND == (-0.006, -0.017)
    assert cone_pivot_post_spec.CRANK_BORE_BAND == (0.018, 0.0)
    assert part.OD_SEAT_CLEARANCE == pytest.approx((0.006, 0.035))


def test_walls_hold_the_floor_and_match_the_named_row() -> None:
    """Under the 2.0 target, over the 1.5 floor, and the row says so: the
    test fails if the geometry moves without the row."""
    assert (spec.WALL_TARGET_MM, spec.WALL_FLOOR_MM) == (2.0, 1.5)
    assert spec.WALL_FLOOR_MM <= part.WALL_WORST < spec.WALL_TARGET_MM
    assert spec.WALL_FLOOR_MM <= part.FLATS_WALL_WORST < spec.WALL_TARGET_MM
    assert round(part.WALL_WORST, 3) == 1.876
    row = next(
        line for line in _policy().splitlines() if line.startswith("| MHA-149 ")
    )
    assert f"wall {part.WALL_WORST:.3f}" in row
    assert f"flat {part.FLATS_WALL_WORST:.3f}" in row


def test_throw_band_matches_its_named_row() -> None:
    upper, lower = spec.ECCENTRICITY_BAND
    assert upper == -lower
    row = next(
        line
        for line in _policy().splitlines()
        if line.startswith("| MHA-149 crank eccentric bushing throw ")
    )
    assert f"{spec.ECCENTRICITY:.3f} ±{upper:.3f}" in row
    assert spec.DRAWING_PRECISION_BY_NAME["BoreOffsetDim"] == 3


def test_throw_reaches_the_mesh_stack() -> None:
    assert crank_mesh_stack.THROW_REACH == pytest.approx(0.575)
    assert min(crank_mesh_stack.OPEN_MARGIN, crank_mesh_stack.CLOSE_MARGIN) > 0.05


def test_flats_are_square_to_the_throw_on_the_protrusion() -> None:
    assert spec.LENGTH == spec.POST_BORE_LENGTH + spec.SOUTH_PROTRUSION == 77.0
    assert spec.FLATS_LENGTH == spec.SOUTH_PROTRUSION
    # The wrench still has a flat to bear on with the lengths at their rows.
    row_1 = 0.8
    exposed_min = (spec.LENGTH - row_1) - (cone_pivot_post_spec.CRANK_BOSS_LENGTH + row_1)
    assert exposed_min > 3.0


def test_the_shaft_runs_on_its_core_through_the_bushing() -> None:
    """R1 drops the journal: the 3/8 in core runs the whole bushing length."""
    assert not hasattr(crankshaft_spec, "JOURNAL_DIA")
    assert crankshaft_spec.SEAT_STEP >= crankshaft_spec.POST_BORE_END


def test_part_and_spec_share_one_dimension_contract() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert part.SURFACE_FINISHES is spec.SURFACE_FINISHES
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "ODDim": 3,
        "BoreDiaDim": 3,
        "BoreOffsetDim": 3,
        "Depth": 1,
        "FlatsAcross": 2,
        "FlatsDepth": 1,
    }


def test_notes_identify_both_mates_and_state_the_exception_without_a_size() -> None:
    text = spec.DRAWING_NOTES
    assert len(text.splitlines()) == 2
    assert spec.SHAFT_MATE_NUMBER == _config.parts("crankshaft")["number"]
    assert spec.POST_MATE_NUMBER == _config.parts("cone-pivot-post")["number"]
    assert "ACCEPTED EXCEPTION" in text
    stripped = text.replace(spec.SHAFT_MATE_NUMBER, "").replace(
        spec.POST_MATE_NUMBER, ""
    )
    assert not any(character.isdigit() for character in stripped)
