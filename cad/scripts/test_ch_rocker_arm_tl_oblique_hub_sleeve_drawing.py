"""Offline contracts for the MHA-CH-06-TL-34 oblique-trammel hub sleeve."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import _config
import build_ch_rocker_arm_tl_oblique_hub_sleeve as part
import ch_rocker_arm_tl_oblique_hub_sleeve_spec as spec
import ch_rocker_arm_tl_oblique_hub_stud_spec as stud
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_oblique_hub_sleeve as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_dimensions import move_model_dimension
from _drawing_registry import DRAWINGS_BY_NAME
from _fit_ream_h7 import REAM_H7
from _inch_wall_limits import WALL_TARGET_MM
from _machinist_review_mode import MachinistReviewMode

STEM = "ch-rocker-arm-tl-oblique-hub-sleeve"
INCH = 25.4


def test_registry_row_is_the_turned_sleeve() -> None:
    row = _config.parts(STEM)
    assert row["number"] == spec.NUMBER == "MHA-CH-06-TL-34"
    assert int(row["quantity"]) == spec.QUANTITY == 1
    assert row["drawing_unit"] == spec.UNIT == "in"
    assert "1018" in row["material_specification"]
    # A literal, so verify's static PART_NAME scan registers the build.
    assert part.PART_NAME == spec.STEM == STEM
    assert part.MATERIAL == "Plain Carbon Steel"


def test_sheet_is_registered_and_enforced() -> None:
    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_hub_sleeve"]
    assert drawing.SPEC is sheet
    assert sheet.script == Path(drawing.__file__).resolve()
    assert sheet.source_kind == "part"
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    assert drawing.move_model_dimension is move_model_dimension
    assert sheet.script_name in PRECISION_MIGRATED_DRAWINGS


def test_reamed_bore_slips_on_the_stud_shank() -> None:
    assert spec.ID == pytest.approx(0.4 * INCH)
    assert spec.ID_BAND is REAM_H7
    assert spec.SHANK_CLEARANCE_MIN == pytest.approx(0.0005 * INCH)
    assert spec.SHANK_FLOAT_MAX == pytest.approx(0.0015 * INCH / 2.0)
    assert spec.DRAWING_BANDS == {("SleeveProfile", "SleeveBore"): REAM_H7}
    assert model_toleranced_dimensions(part) == {
        ("feature_name", "dimension_name"): "*deviations(band)"
    }
    assert stud.NUMBER in spec.DIMENSION_CALLOUTS["SleeveBore"]
    assert spec.DIMENSION_CALLOUTS["SleeveBore"].startswith("REAM")


def test_wall_and_length_match_the_riser() -> None:
    assert spec.OD == pytest.approx(0.580 * INCH)
    assert spec.WALL_MIN == pytest.approx((0.575 - 0.4005) / 2.0 * INCH)
    assert spec.WALL_MIN >= WALL_TARGET_MM
    assert spec.LENGTH == trammel.RISER_THICK
    assert spec.FLUSH_BELOW_MAX == pytest.approx(0.002 * INCH)
    assert spec.RISER_NUMBER in spec.DIMENSION_CALLOUTS["SleeveLength"]
    assert spec.OD < stud.FLANGE_DIA


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert set(spec.DIMENSION_CALLOUTS) <= marked
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "SleeveOd": 3,
        "SleeveBore": 4,
        "SleeveLength": 2,
    }
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION
    assert part.V_RING == pytest.approx(
        math.pi * ((spec.OD / 2.0) ** 2 - (spec.ID / 2.0) ** 2) * spec.LENGTH
    )


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    import _drawing_marks
    import _part_properties

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_part_properties.part_properties(part.PART_NAME))
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(None, part.PART_NAME)
    carried.update(stamped)
    missing = [name for name in required if not str(carried.get(name) or "").strip()]
    assert missing == []
