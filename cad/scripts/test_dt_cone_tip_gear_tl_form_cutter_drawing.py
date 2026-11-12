"""Offline contract of the DT6-FORM1 fly-cutter bit (MHA-DT-37-TL-01, #2358)."""

from __future__ import annotations

import ast
import math
import re
from dataclasses import replace
from pathlib import Path

import pytest

import _buildgraph as bg
import _config
import draw_dt_cone_tip_gear_tl_form_cutter as drawing
import dt_cone_gear_spec as family
import dt_cone_tip_gear_notes as notes
import dt_cone_tip_gear_spec as tip
import dt_cone_tip_gear_tl_form_cutter_spec as part
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode

SCRIPTS = Path(__file__).resolve().parent
# ASME B landscape: inside the border, clear of the title block's corner.
SHEET_INNER = (0.0127, 0.0127, 0.4191, 0.2667)
TITLE_BLOCK = (0.216, 0.0, 0.4318, 0.066)


def test_the_bit_is_registered_tooling_of_the_tip_gear() -> None:
    row = _config.parts(part.STEM)
    assert row["number"] == part.NUMBER == f"{tip.PART_NUMBER}-TL-01"
    assert bg.is_shop_fixture(part.STEM.replace("-", "_"))
    assert "O1" in str(row["material_specification"]).upper()
    # Hardness is a stated fact of the finished bit, not a procedure.
    finish = str(row["finish"]).upper()
    assert "HARD" in finish
    assert not any(word in finish for word in ("QUENCH", "HEAT TO", "TORCH", "OVEN"))
    spec = DRAWINGS_BY_NAME["dt_cone_tip_gear_tl_form_cutter"]
    assert spec.script.name == Path(drawing.__file__).name


def test_the_tip_gear_cutter_row_names_this_bit() -> None:
    assert notes.cutter_description().startswith(f"{part.NUMBER};")


def test_the_face_form_is_the_gear_profile_itself() -> None:
    """The bit's form curves are the T006 tooth space's own native curves at
    the nominal (untranslated) cut, not a transcription."""
    tool = replace(
        family.stock_form_profile(6),
        blank_radius_mm=part.TEMPLATE.tip_radius_mm,
        radial_translation_mm=0.0,
    )
    gear = {
        segment.name: segment
        for segment in tool.native_segments(
            unit_scale=1.0 / 25.4, clearance_radius_mm=part.TEMPLATE.tip_radius_mm + 1.0
        )
    }
    bit = part.form_segments()
    assert [segment.name for segment in bit] == [
        name for name in gear if name in part.FORM_SEGMENT_NAMES
    ]
    for segment in bit:
        reference = gear[segment.name]
        assert re.sub(r"\s+", "", segment.x) == re.sub(r"\s+", "", reference.x)
        assert re.sub(r"\s+", "", segment.y) == re.sub(r"\s+", "", reference.y)
    # Its nearest point is P1 on the bit's axis; nothing digs below the root.
    assert part.FORM_RADIUS_MIN >= part.ROOT_RADIUS - 1e-9
    assert 0.0 < part.FORM_X_MAX < part.TIP_STOCK


def test_the_printed_envelope_is_sheet_two_of_the_gear() -> None:
    points = family.custom_six_form_points_mm()
    assert part.TIP_WIDTH == 2.0 * points[1][1]
    assert part.JUNCTION_WIDTH == 2.0 * points[11][1]
    assert part.FORM_WIDTH == 2.0 * points[16][1]
    assert part.JUNCTION_DEPTH == points[11][2]
    assert part.FORM_DEPTH == points[16][2]
    assert part.FORM_PLACES == family.FORM_PLACES
    # They print as references only; the table governs.
    assert part.REFERENCE_DIMENSIONS == set(drawing.TOP_KEEP)
    assert part.DRAWING_DIMENSIONS[part.FORM_REFERENCE_SKETCH] == set(
        part.REFERENCE_DIMENSIONS
    )
    assert f"{tip.PART_NUMBER}, SHEET 2" in part.SHEET_NOTES


def test_the_form_fits_the_rod_with_a_shoulder_each_side() -> None:
    assert 2.0 * part.FLANK_END_Z < part.BIT_DIA
    assert part.FORM_WIDTH < 2.0 * part.FLANK_END_Z


def test_both_clearances_are_real_angles_that_open_away_from_the_edge() -> None:
    assert 0.0 < part.SIDE_CLEARANCE_DEG < part.FRONT_CLEARANCE_DEG <= 15.0
    for side in (-1, 1):
        direction = part.clearance_direction(side)
        assert math.isclose(math.hypot(*direction), 1.0)
        # Back along the bit (−X), down the face normal (−Y), out the flank.
        assert direction[0] < 0.0 and direction[1] < 0.0
        assert direction[2] * side < 0.0
        assert math.degrees(math.atan(-direction[0] / -direction[1])) == (
            pytest.approx(part.FRONT_CLEARANCE_DEG)
        )


def test_each_cut_removes_stock_and_the_volume_oracle_has_converged() -> None:
    volumes = [part.bit_volume_mm3(stage) for stage in part.STAGES]
    assert all(a > b for a, b in zip(volumes, volumes[1:]))
    # The rod as revolved runs TIP_STOCK past P1; the form cut takes it back.
    assert volumes[0] == pytest.approx(
        math.pi * part.BIT_RADIUS**2 * (part.BIT_LENGTH + part.TIP_STOCK), rel=1e-9
    )
    assert (
        abs(part.bit_volume_mm3("form", slices=96) - volumes[-1]) < part.VOLUME_TOL_MM3
    )


def test_the_sheet_prints_each_marked_dimension_once_inside_the_border() -> None:
    keeps = {**drawing.FRONT_KEEP, **drawing.TOP_KEEP, **drawing.RIGHT_KEEP}
    assert len(keeps) == sum(
        map(len, (drawing.FRONT_KEEP, drawing.TOP_KEEP, drawing.RIGHT_KEEP))
    )
    assert set(keeps) == drawing.sheet_dimension_names()
    assert set(part.DRAWING_PRECISION_BY_NAME) == set(keeps)
    left, bottom, right, top = SHEET_INNER
    for name, (x, y) in keeps.items():
        assert left < x < right and bottom < y < top, name
        assert not (TITLE_BLOCK[0] < x and y < TITLE_BLOCK[3]), name
    # Every callout belongs to a printed dimension.
    assert set(part.DIMENSION_CALLOUTS) <= set(keeps)


def test_the_notes_state_facts_in_at_most_four_lines() -> None:
    lines = part.SHEET_NOTES.splitlines()
    assert len(lines) <= 4
    text = part.SHEET_NOTES.upper()
    for method in ("GRIND", "STONE", "HONE", "QUENCH", "TEMPER AT"):
        assert method not in text, method


def test_the_draw_script_owns_placement_only() -> None:
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    literals = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    assert not any(re.search(r"[+-]\.\d{3,}", text) for text in literals)
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    assert drawing.SPEC.layout.name == "LANDSCAPE"
