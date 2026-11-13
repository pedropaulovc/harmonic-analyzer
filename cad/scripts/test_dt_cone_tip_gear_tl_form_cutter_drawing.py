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
from _printed_tolerance import printed_band_mm

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
    # The flat leaves its face FACE_HEIGHT above the axis: the flat stage is
    # half the rod plus the upper half behind the flat plus that thin strip.
    rod = math.pi * part.BIT_RADIUS**2
    strip = volumes[1] - rod / 2.0 * (
        2.0 * part.BIT_LENGTH - part.FLAT_LENGTH + part.TIP_STOCK
    )
    width = 2.0 * part.BIT_RADIUS
    assert strip == pytest.approx(
        width * part.FACE_HEIGHT * (part.FLAT_LENGTH + part.TIP_STOCK), rel=1e-4
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


def test_the_flat_prints_its_length_and_its_micrometer_depth_bare() -> None:
    """The flat's depth is a native model dimension, the thickness from the
    face to the rod's far side, a plain .063 on the title block's .XXX grid
    and band (the face .0005 above the axis); neither flat dimension
    carries words or its own band."""
    assert part.DRAWING_DIMENSIONS["FlatProfile"] == {"FlatLength", "FlatDepth"}
    assert part.FLAT_DEPTH == pytest.approx(0.063 * 25.4)
    assert part.DRAWING_PRECISION_BY_NAME["FlatDepth"] == 3
    assert part.FLAT_DEPTH_TOL == pytest.approx(printed_band_mm(3, unit="in"))
    assert part.FACE_HEIGHT == pytest.approx(0.0005 * 25.4)
    assert "FlatLength" not in part.DIMENSION_CALLOUTS
    assert "FlatDepth" not in part.DIMENSION_CALLOUTS
    assert "CENTER" not in " ".join(part.DIMENSION_CALLOUTS.values())
    # The builder drives the depth from its own .063 global, no band of its
    # own, and floors the flat at FACE_HEIGHT.
    builder = (SCRIPTS / "build_dt_cone_tip_gear_tl_form_cutter.py").read_text(
        encoding="utf-8"
    )
    assert 'flat.record("FlatDepth", \'"FlatDepth"\')' in builder
    assert '("FlatDepth", f"{FLAT_DEPTH}mm")' in builder
    assert "FLAT_DEPTH_TOL" not in builder
    assert "(-FLAT_LENGTH, FACE_HEIGHT)" in builder
    # The depth's text sits right of the tip, between the face and the far
    # side, left of the end view's rod.
    x, y = drawing.FRONT_KEEP["FlatDepth"]
    assert (
        drawing.FRONT_P1[0] < x < drawing.RIGHT_AXIS[0] - part.BIT_RADIUS * drawing._S
    )
    assert drawing.FRONT_P1[1] - part.FLAT_DEPTH * drawing._S < y < drawing.FRONT_P1[1]


def test_the_flat_band_holds_zero_rake_and_the_tooth_space() -> None:
    import dt_cone_tip_gear_tl_cutter_spec as fixture

    assert part.FLAT_FACE_OFFSET_MAX == pytest.approx(
        part.FACE_HEIGHT + part.FLAT_DEPTH_TOL + part.BIT_DIA_TOL / 2.0
    )
    assert 0.0 < fixture.RAKE_ERROR_DEG_MAX <= fixture.RAKE_ERROR_DEG_LIMIT
    assert 0.0 < fixture.FORM_DISTORTION_MAX < fixture.FORM_DISTORTION_LIMIT
    # Sliding the edge along the relieved walls: width under half the gear's
    # thickness band, and the forward run keeps the stems' runoff.
    assert fixture.FACE_SHIFT_WIDTH_MAX == pytest.approx(
        2.0 * part.FLAT_FACE_OFFSET_MAX * part.TAN_SIDE
    )
    assert 0.0 < fixture.FACE_SHIFT_WIDTH_MAX < fixture.FACE_SHIFT_WIDTH_LIMIT
    assert (
        fixture.RUNOFF_OVER_STEMS - fixture.FACE_SHIFT_FORWARD_MAX
        >= fixture.tip.CUTTER_RUNOFF_MM - 1e-9
    )


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
