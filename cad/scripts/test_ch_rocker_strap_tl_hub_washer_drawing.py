"""Offline contracts for the rocker strap's hub washer (MHA-CH-13-TL-03)."""

from __future__ import annotations

import ast
import math
import sys
import tomllib
from pathlib import Path

import pytest

import _buildgraph as bg
import _config
import build_ch_rocker_strap_tl_hub_washer as part
import ch_rocker_hub_fit as fit
import ch_rocker_strap_spec as strap
import ch_rocker_strap_tl_hub_plug_spec as plug
import ch_rocker_strap_tl_hub_washer_spec as spec
import draw_ch_rocker_strap_tl_hub_washer as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DrawingLayout
from _machinist_review_mode import MachinistReviewMode
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from test_pd_transgear_adapter_contract import (
    _adapter_calls,
    _adapter_methods,
    _missing,
    _signature,
    _tree,
)

INCH = 25.4
XX = printed_band_mm(2, unit="in")
SCRIPTS = Path(__file__).resolve().parent
PLAN = SCRIPTS.parent / "process" / "ch_rocker_strap" / "plan.toml"
STEM = "ch_rocker_strap_tl_hub_washer"


def _plan() -> dict:
    return tomllib.loads(PLAN.read_text(encoding="utf-8"))["parameters"]


def test_registry_row_is_inch_shop_tooling_with_a_learn_sheet() -> None:
    row = _config.parts(spec.PART_NAME)
    assert row["number"] == spec.PART_NUMBER == "MHA-CH-13-TL-03"
    assert row["drawing_unit"] == spec.UNIT == "in"
    assert row["tolerance_class"] == "machined_block"
    assert int(row["quantity"]) == 1
    # One material: the MATERIAL cell holds one line (LEARN review r5).
    assert row["material"] == "LOW-CARBON STEEL"
    assert str(row["material_specification"]).startswith("low-carbon steel round")
    assert part.MATERIAL == "Plain Carbon Steel"
    entry = DRAWINGS_BY_NAME[STEM]
    assert entry.artifact_stem == spec.PART_NAME == part.PART_NAME
    assert entry.layout is DrawingLayout.LANDSCAPE
    assert entry.source_kind == "part"
    assert entry.script == Path(drawing.__file__).resolve()
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.LEARN
    assert "draw_ch_rocker_strap_tl_hub_washer.py" in PRECISION_MIGRATED_DRAWINGS
    assert bg.is_shop_fixture(STEM)
    for machine in bg.MACHINE_ASSEMBLIES:
        assert STEM not in bg.references_of(machine)


def test_sizes_are_the_contract() -> None:
    assert spec.OUTER_DIA == pytest.approx(0.53 * INCH)
    assert spec.THICKNESS == pytest.approx(0.06 * INCH)
    # Owner ruling 2 (2026-11-17): the 1/4-20 screw, the plug's H-drill bore.
    assert spec.BORE_DIA == pytest.approx(0.266 * INCH) == plug.BORE_DIA
    assert spec.SCREW_MAJOR_DIA == plug.SCREW_MAJOR_DIA == pytest.approx(0.25 * INCH)
    assert spec.SCREW_HEAD_HEIGHT_MAX == pytest.approx(0.132 * INCH)


def test_the_keep_out_sits_inside_the_plan_and_the_strap_copy_matches() -> None:
    """Inequalities, so the check holds on the plan before and after its
    keep-out was tightened to this washer (13.9/6.2 -> 13.716/5.1308)."""
    plan = _plan()
    assert spec.FLANGE_DIA_MAX <= plan["bushing_flange_dia_mm"] + 1e-6
    assert spec.STACK_HEIGHT_MAX <= plan["bushing_stack_height_mm"] + 1e-6
    assert spec.STRAP_HOLE_DIA_MAX == pytest.approx(
        strap.HOLE_DIA + fit.STRAP_HOLE_BAND[0]
    )


def test_the_largest_washer_and_head_stay_inside_the_plan_keep_out() -> None:
    plan = _plan()
    assert spec.OUTER_DIA + XX <= plan["bushing_flange_dia_mm"] + 1e-6
    stack = spec.THICKNESS + XX + spec.SCREW_HEAD_HEIGHT_MAX
    assert stack == pytest.approx(spec.STACK_HEIGHT)
    assert stack <= plan["bushing_stack_height_mm"] + 1e-6


def test_the_washer_bears_on_the_strap_round_its_hub_hole() -> None:
    assert spec.BEARING_LAND_MIN == pytest.approx(
        (spec.OUTER_DIA - XX - spec.STRAP_HOLE_DIA_MAX) / 2.0
    )
    assert spec.BEARING_LAND_MIN > 1.0
    assert spec.BORE_DIA + drilled_oversize_mm(unit="in") < spec.STRAP_HOLE_DIA_MAX
    # The pilot's top stays under the strap's top, so the washer clamps the
    # strap, not the plug.
    assert plug.PILOT_TOP_Z_RANGE[1] < plug.STRAP_TOP_Z_MIN


def test_places_and_callouts_are_the_parts() -> None:
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "OuterDia": 2,
        "BoreDia": 3,
        "Thickness": 2,
    }
    assert spec.DIMENSION_CALLOUTS_BY_NAME == {"BoreDia": "DRILL THRU"}
    assert model_toleranced_dimensions(part) == {}
    assert spec.V_WASHER == pytest.approx(
        math.pi / 4.0 * (spec.OUTER_DIA**2 - spec.BORE_DIA**2) * spec.THICKNESS
    )


def test_every_marked_dimension_ends_on_one_view() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert not set(drawing.END_KEEP) & set(drawing.SIDE_KEEP)


def test_the_isometric_is_in_the_hidden_line_loop() -> None:
    tree = _tree(Path(drawing.__file__))
    loops = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.For)
        and isinstance(node.iter, ast.Tuple)
        and any(
            isinstance(call, ast.Call)
            and getattr(call.func, "id", None) == "set_hidden_lines_removed"
            for call in ast.walk(node)
        )
    ]
    assert len(loops) == 1
    assert {ast.unparse(e) for e in loops[0].iter.elts} == {"end", "side", "iso"}


def test_the_views_stand_on_the_sheet() -> None:
    top, title_top = 0.2667, 0.066
    s = drawing._S
    half = spec.OUTER_DIA / 2.0 * s
    assert drawing.END_CENTER[0] - half > 0.0127
    assert drawing.END_CENTER[0] + half + 0.010 < drawing.SIDE_CENTER[0]
    assert drawing.SIDE_KEEP["Thickness"][1] + 0.006 < top
    assert drawing.END_KEEP["OuterDia"][1] - 0.006 > title_top
    iso_half = spec.OUTER_DIA / 2000.0 * drawing.ISO_SCALE[0] * 1.25
    assert drawing.OD_ON_SIDE[0] + 0.015 < drawing.ISO_CENTER[0] - iso_half
    assert drawing.ISO_CENTER[1] - iso_half > drawing.ISO_NOTE_XY[1]
    assert drawing.ISO_NOTE_XY[1] - 0.005 > title_top


@pytest.mark.parametrize(
    "recipe",
    ["build_ch_rocker_strap_tl_hub_washer.py", "draw_ch_rocker_strap_tl_hub_washer.py"],
)
def test_every_direct_adapter_call_exists_and_binds(recipe: str) -> None:
    tree = _tree(SCRIPTS / recipe)
    calls = _adapter_calls(tree)
    assert calls, recipe
    assert not _missing(tree), sorted(_missing(tree))
    for call in calls:
        path, method = _adapter_methods()[call.func.attr]
        try:
            _signature(method).bind(
                call.func.value,
                *call.args,
                **{k.arg: k.value for k in call.keywords},
            )
        except TypeError as error:
            pytest.fail(f"{recipe}:{call.lineno}: {call.func.attr}: {error}")


def test_the_cli_takes_its_own_stem(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["draw", spec.PART_NAME])
    assert drawing._parse_args().part == spec.PART_NAME
