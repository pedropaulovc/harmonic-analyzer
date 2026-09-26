"""Offline contracts for MHA-149, the crank eccentric bushing (#906 R1)."""

from __future__ import annotations

import math
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
    assert part.FLATS_WALL_WORST >= spec.WALL_TARGET_MM
    assert math.floor(part.WALL_WORST * 1000.0) == 1851
    row = next(
        line for line in _policy().splitlines() if line.startswith("| MHA-149 ")
    )
    assert f"wall {math.floor(part.WALL_WORST * 1000.0) / 1000.0:.3f}" in row
    assert f"flat {math.floor(part.FLATS_WALL_WORST * 1000.0) / 1000.0:.3f}" in row


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
    assert crank_mesh_stack.THROW_REACH == pytest.approx(0.600)
    assert min(crank_mesh_stack.OPEN_MARGIN, crank_mesh_stack.CLOSE_MARGIN) > 0.0


def test_the_grip_head_stands_off_the_boss_at_its_rows() -> None:
    assert spec.SOUTH_PROTRUSION == spec.HEAD_STANDOFF + spec.HEAD_LENGTH
    assert spec.LENGTH == spec.POST_BORE_LENGTH + spec.SOUTH_PROTRUSION == 80.0
    assert spec.FLATS_LENGTH == spec.HEAD_LENGTH
    row_1 = float(str(_config.title_block("linear_1pl")["display"]).lstrip("±"))
    row_2 = float(str(_config.title_block("linear_2pl")["display"]).lstrip("±"))
    assert spec.DRAWING_PRECISION_BY_NAME["Depth"] == 2
    assert spec.DRAWING_PRECISION_BY_NAME["HeadDepth"] == 2
    # North end flush with the spot face; the head's north face against the
    # boss's south face, with both bushing lengths at .XX and the boss length
    # at its .X row.
    standoff_min = (
        (spec.LENGTH - row_2)
        - (spec.HEAD_LENGTH + row_2)
        - (cone_pivot_post_spec.CRANK_BOSS_LENGTH + row_1)
    )
    assert standoff_min > 0.0


def test_the_shaft_runs_on_its_core_through_the_bushing() -> None:
    """R1 drops the journal: the 3/8 in core runs the whole bushing length."""
    assert not hasattr(crankshaft_spec, "JOURNAL_DIA")


def test_part_and_spec_share_one_dimension_contract() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert part.SURFACE_FINISHES is spec.SURFACE_FINISHES
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "ODDim": 3,
        "BoreDiaDim": 3,
        "BoreOffsetDim": 3,
        "Depth": 2,
        "HeadDiaDim": 1,
        "HeadDepth": 2,
        "FlatsAcross": 2,
    }


def test_notes_identify_both_mates_and_state_the_thin_wall_as_a_fact() -> None:
    """The policy requires the sheet to state its named exception (Codex #857
    P2), but exception and ruling labels never print (fleet ruling
    2026-09-26): the thin wall prints as a plain fact from the print-worst
    wall, rounded down, and the acceptance stays in the policy row."""
    text = spec.DRAWING_NOTES
    assert len(text.splitlines()) == 1
    printed = part.MANUFACTURING_NOTES.splitlines()
    assert printed == [
        text,
        f"WALL {math.floor(part.WALL_WORST * 100.0) / 100.0:.2f} MIN AT THROW.",
    ]
    assert printed[1] == "WALL 1.85 MIN AT THROW."
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '{"Manufacturing Notes": MANUFACTURING_NOTES}' in source
    for internal in ("EXCEPTION", "ACCEPTED", "RULING", "POLICY", "RULE "):
        assert internal not in part.MANUFACTURING_NOTES
    assert spec.SHAFT_MATE_NUMBER == _config.parts("crankshaft")["number"]
    assert spec.POST_MATE_NUMBER == _config.parts("cone-pivot-post")["number"]
    assert not hasattr(spec, "WALL_EXCEPTION")
    for internal in ("EXCEPTION", "ACCEPTED", "RULING", "POLICY"):
        assert internal not in text
    stripped = text.replace(spec.SHAFT_MATE_NUMBER, "").replace(
        spec.POST_MATE_NUMBER, ""
    )
    assert not any(character.isdigit() for character in stripped)


def test_the_bore_holds_its_share_of_the_crank_angle_budget() -> None:
    """Rule 3's crank-mesh entry: one diametral parallelism frame, bore to OD,
    authored as model PMI; the stack takes its angle from the same constant."""
    from _gtol_spec import CylinderFace

    (datum,) = spec.PART_DATUMS
    assert datum.letter == "A"
    assert datum.face == CylinderFace(spec.OUTER_DIA, contains_y_mm=spec.LENGTH / 2.0)
    (frame,) = spec.GEOMETRIC_CONTROLS
    assert frame.characteristic == "parallelism"
    assert frame.tolerance_zone == "diametral"
    assert frame.datums == ("A",)
    assert frame.tolerance == f"{spec.BORE_PARALLELISM_MM:.2f}" == "0.05"
    assert frame.face == CylinderFace(spec.BORE_DIA, contains_y_mm=spec.LENGTH / 2.0)
    assert crank_mesh_stack.BUSHING_ANGLE_DEG == pytest.approx(
        math.degrees(math.atan(spec.BORE_PARALLELISM_MM / spec.LENGTH))
    )
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "datums=PART_DATUMS" in source
    assert "controls=GEOMETRIC_CONTROLS" in source
    policy = _policy()
    assert "MHA-149's bore: one diametral parallelism frame" in policy
