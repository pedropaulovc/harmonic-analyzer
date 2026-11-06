"""Offline contracts for the MHA-CH-06-TL-35 oblique-trammel hub washer."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import _config
import build_ch_rocker_arm_tl_oblique_hub_washer as part
import ch_rocker_arm_tl_oblique_hub_washer_spec as spec
import draw_ch_rocker_arm_tl_oblique_hub_washer as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_dimensions import move_model_dimension
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import NUMBER_DRILL_MM, THREAD_MAJOR_MM
from _inch_wall_limits import WALL_TARGET_MM
from _machinist_review_mode import MachinistReviewMode
from _mcmaster_92220a163 import DIMS as HUB_SCREW

STEM = "ch-rocker-arm-tl-oblique-hub-washer"
INCH = 25.4


def test_registry_row_is_the_turned_brass_washer() -> None:
    row = _config.parts(STEM)
    assert row["number"] == spec.NUMBER == "MHA-CH-06-TL-35"
    assert int(row["quantity"]) == spec.QUANTITY == 1
    assert row["drawing_unit"] == spec.UNIT == "in"
    assert "C36000" in row["material_specification"]
    assert part.PART_NAME == STEM
    assert part.MATERIAL == "Brass"


def test_sheet_is_registered_and_enforced() -> None:
    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_hub_washer"]
    assert drawing.SPEC is sheet
    assert sheet.script == Path(drawing.__file__).resolve()
    assert sheet.source_kind == "part"
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    assert drawing.move_model_dimension is move_model_dimension
    assert sheet.script_name in PRECISION_MIGRATED_DRAWINGS


def test_owner_od_drilled_bore_and_title_block_bands() -> None:
    # The owner's literal Ø11 (parent ruling 2026-11-06), no explicit band.
    assert spec.OD == 11.0
    assert spec.ID == NUMBER_DRILL_MM["#9"]
    assert spec.ID > THREAD_MAJOR_MM["#10-24"]
    assert spec.THICK == pytest.approx(0.06 * INCH)
    assert spec.WALL_MIN >= WALL_TARGET_MM
    assert spec.OD > HUB_SCREW.head_dia
    assert model_toleranced_dimensions(part) == {}
    assert spec.DIMENSION_CALLOUTS == {"WasherBore": "#9 DRILL THRU"}


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "WasherOd": 3,
        "WasherBore": 3,
        "WasherThickness": 2,
    }
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION
    assert part.V_RING == pytest.approx(
        math.pi * ((spec.OD / 2.0) ** 2 - (spec.ID / 2.0) ** 2) * spec.THICK
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
