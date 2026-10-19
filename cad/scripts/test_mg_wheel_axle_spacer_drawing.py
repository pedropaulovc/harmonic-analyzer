"""Offline contracts for the wheel-axle spacer (MHA-MG-11) drawing."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import _config
import build_mg_wheel_axle_spacer as part
import draw_mg_wheel_axle_spacer as drawing
import mg_magnifying_wheel_geom as wheel_geom
import mg_wheel_axle_spacer_spec as spec
import mg_wheel_group as group
import mg_vn_wheel_axle_back_washer_spec as back_washer
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from mg_wheel_bar_geom import BAR_FRONT_Z
from paper_drive_geom import PEN_Z_MID


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/mg-wheel-axle-spacer.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/mg-wheel-axle-spacer.pdf")
    assert (
        DRAWINGS_BY_NAME["mg_wheel_axle_spacer"].script
        == Path(drawing.__file__).resolve()
    )


def test_dimension_transfer_uses_shared_helper() -> None:
    from _drawing_dimensions import move_model_dimension

    assert drawing.move_model_dimension is move_model_dimension


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION
    assert drawing.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert set(drawing.DIMENSION_CALLOUTS) <= marked
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }
    assert drawing.DRAWING_PRECISION_BY_NAME == {
        "SpacerOd": 1,
        "SpacerBore": 2,
        "SpacerLength": 2,
    }


def test_only_the_length_carries_an_explicit_band() -> None:
    # The O.D. and the drilled bore take the title block's rows.
    assert model_toleranced_dimensions(part) == {
        ("Spacer", "SpacerLength"): "LENGTH_BAND",
    }
    assert spec.LENGTH_BAND == 0.03
    assert spec.WALL_WORST == pytest.approx((11.0 - 0.8 - 5.0) / 2.0)
    assert spec.WALL_WORST >= spec.MIN_WALL
    assert part.V_RING == pytest.approx(
        math.pi * ((spec.OD / 2.0) ** 2 - (spec.BORE_DIA / 2.0) ** 2) * spec.LENGTH
    )


def test_length_lands_the_wheel_on_the_pen_line() -> None:
    assert spec.LENGTH == pytest.approx(
        BAR_FRONT_Z - PEN_Z_MID - back_washer.MODEL_THICKNESS - wheel_geom.HUB_BACK_Z
    )
    assert spec.LENGTH > 0.0
    assert spec.LENGTH * 10.0 == pytest.approx(round(spec.LENGTH * 10.0), abs=1e-6)
    assert group.SPACER_D == 0.0
    assert group.BACK_WASHER_D == pytest.approx(spec.LENGTH)
    assert BAR_FRONT_Z - group.SPOKE_MID_D == pytest.approx(PEN_Z_MID)
    assert group.WHEEL_MID_Z == PEN_Z_MID


def test_spacer_passes_the_pin_and_clears_the_tie_tail() -> None:
    import mg_wheel_axle_spec as pin

    assert spec.BORE_DIA > pin.PIN_DIA + pin.PIN_DIA_TOL
    assert group.TAIL_STACK_CLEARANCE > 0.0


def test_each_callout_states_its_need() -> None:
    assert not hasattr(spec, "DRAWING_NOTES")
    assert drawing.DIMENSION_CALLOUTS == {
        "SpacerBore": "DRILL THRU",
        "SpacerLength": "SETS WHEEL STACK\nON AXLE MHA-MG-07",
    }


def test_registry_row() -> None:
    row = _config.parts("mg-wheel-axle-spacer")
    assert row["number"] == "MHA-MG-11"
    assert int(row["quantity"]) == 1
    assert "C36000" in str(row["material_specification"])
    assert "7/16" in str(row["material_specification"])
    assert row["finish"]
    assert row["process"]
    assert part.MATERIAL == "Brass"


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
    build_calls = _calls(part.__file__)
    stamp = build_calls["apply_drawing_properties"]
    assert [ast.unparse(a) for a in stamp.args] == ["adapter", "PART_NAME"]
    assert stamp.lineno < build_calls["save_part_and_images"].lineno
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


def test_no_finish_symbol_and_no_gdt() -> None:
    names = set(_calls(drawing.__file__))
    assert not names & {
        "add_datum_feature",
        "add_feature_control_frame",
        "add_surface_finish_symbol",
    }
    assert spec.SURFACE_FINISHES == ()
