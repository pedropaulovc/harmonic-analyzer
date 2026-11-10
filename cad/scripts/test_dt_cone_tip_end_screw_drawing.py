"""SolidWorks-free contracts for MHA-DT-39, the cone tip end screw."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import _mcmaster_91794a558 as stock
import cone_tip_cluster as tip
import dt_cone_tip_end_screw_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _machinist_review_mode import MachinistReviewMode

IN = 25.4
SCRIPTS = Path(__file__).resolve().parent


def test_registry_row_is_the_modified_mcmaster_screw() -> None:
    row = _config.parts(spec.PART_NAME)
    assert row["number"] == "MHA-DT-39"
    assert row["supplier"] == "McMaster-Carr"
    assert row["supplier_skus"] == [stock.SKU] == ["91794A558"]
    assert row["quantity"] == 1
    assert row["drawing_unit"] == spec.UNIT == "in"
    assert "drill and ream" in row["process"]


def test_mates_are_named_by_their_registered_numbers() -> None:
    for stem, number in (
        ("dt-cone-tip-gear", spec.PIVOT_NUMBER),
        ("dt-cone-tip-bushing", spec.BUSHING_NUMBER),
        ("dt-cone-tip-block", spec.BLOCK_NUMBER),
    ):
        assert _config.parts(stem)["number"] == number


def test_head_and_thread_are_the_sourced_catalogue_sizes() -> None:
    assert "https://www.mcmaster.com/91794A558/" in stock.SOURCE
    assert "2026-11-09" in stock.SOURCE
    assert stock.THREAD == tip.ADJUSTER_THREAD == "1/4-28"
    assert stock.THREAD_CLASS == "2A"
    assert stock.HEAD_DIA == pytest.approx(0.414 * IN)
    assert stock.HEAD_H == pytest.approx(0.237 * IN)
    assert stock.SHANK_LEN == pytest.approx(0.625 * IN)
    assert stock.SHANK_DIA == pytest.approx(0.250 * IN)
    assert stock.PITCH == pytest.approx(IN / 28.0)
    assert stock.FILLISTER_SIZE == (
        stock.SHANK_DIA,
        stock.SHANK_LEN,
        stock.HEAD_H,
        stock.HEAD_DIA,
        stock.PITCH,
    )
    assert "steelmasters.co.nz" in stock.THREAD_LIMITS_SOURCE
    assert stock.THREAD_MAJOR_MAX_MM == 0.2490 * IN
    assert stock.EXTERNAL_PITCH_DIA_MIN_MM == 0.2225 * IN
    # The derived minimum root lies under the table's UNR maximum.
    assert stock.THREAD_MINOR_MIN_MM < stock.THREAD_MINOR_UNR_MAX_MM


def test_stock_recipe_is_registered_with_the_fleet_driver() -> None:
    driver = (SCRIPTS / "diagnostics" / "diag_build_mcmaster.py").read_text(
        encoding="utf-8"
    )
    assert "from diagnostics.diag_build_91794A558 import build_91794A558" in driver
    assert '"91794A558": build_91794A558,' in driver
    recipe = (SCRIPTS / "diagnostics" / "diag_build_91794A558.py").read_text(
        encoding="utf-8"
    )
    assert '@stock_recipe("91794A558", threaded=True)' in recipe
    assert 'build_fillister(adapter, "91794A558", FILLISTER_SIZE)' in recipe


def test_hole_is_the_tip_cluster_contract() -> None:
    assert spec.END_HOLE_DIA == pytest.approx(0.0630 * IN)
    assert spec.END_HOLE_BAND == tip.REAM_H7
    assert spec.END_HOLE_DEPTH == pytest.approx(0.12 * IN)
    assert spec.PIVOT_CLEARANCE[0] / IN == pytest.approx(0.0005)
    assert spec.PIVOT_CLEARANCE[1] / IN == pytest.approx(0.0013)


def test_hole_wall_to_the_thread_root_is_the_declared_minor() -> None:
    minor_min = (0.2225 - 0.649519 / 28.0) * IN
    hole_max = (0.0630 + 0.0005) * IN
    # The shop table's runout row: .001 TIR, .0005 radial.
    assert spec.END_HOLE_POSITION_MM == pytest.approx(0.0005 * IN)
    assert spec.END_HOLE_WALL_WORST == pytest.approx(
        (minor_min - hole_max) / 2.0 - spec.END_HOLE_POSITION_MM
    )
    assert WALL_FLOOR_MM <= spec.END_HOLE_WALL_WORST < WALL_TARGET_MM
    assert spec.END_HOLE_WALL_PRINTED_IN == 0.067
    (row,) = _config.parts(spec.PART_NAME)["machinist_exceptions"]
    assert row["id"] == "RV-01" and row["kind"] == "minor"
    assert "WALL TO THREAD ROOT .067 MIN" in row["where"]
    assert row["reason"].startswith("Owner ruling 2026-11-09 via PR #1992")
    assert "pull/1992" in row["reason"]


def test_pivot_never_bottoms_and_always_runs_in_the_hole() -> None:
    assert spec.PIVOT_FLOOR_AIR_MIN > 0.0
    assert spec.PIVOT_ENGAGEMENT_MIN > 0.0
    assert spec.PIVOT_PROUD_MIN < spec.PIVOT_PROUD_MAX


def test_hole_callout_states_process_fit_mate_and_wall() -> None:
    assert spec.END_HOLE_CALLOUT.splitlines() == [
        "REAM",
        "RUNNING FIT ON MHA-DT-37 PIVOT",
        "WALL TO THREAD ROOT .067 MIN",
    ]
    assert "91794A558" in spec.STOCK_NOTE
    # Rule 2: the material lives in the title block only.
    assert "STAINLESS" not in spec.STOCK_NOTE


def test_builder_cuts_one_reamed_hole() -> None:
    import math

    import build_dt_cone_tip_end_screw as build

    assert build.SPEC.skus == (stock.SKU,)
    assert build.V_HOLE == pytest.approx(
        math.pi / 4.0 * spec.END_HOLE_DIA**2 * spec.END_HOLE_DEPTH
    )
    assert spec.DRAWING_PRECISION_BY_NAME == {"EndHoleDia": 4, "EndHoleDepth": 2}


def test_sheet_is_registered_and_enforced() -> None:
    import draw_dt_cone_tip_end_screw as drawing

    sheet = DRAWINGS_BY_NAME["dt_cone_tip_end_screw"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.artifact_stem == spec.PART_NAME
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    assert set(drawing.SECTION_KEEP) == set(spec.DRAWING_PRECISION_BY_NAME)


def test_hole_callout_stands_clear_of_its_lines_and_inside_the_frame() -> None:
    import draw_dt_cone_tip_end_screw as drawing

    # Farm run 20261110T001845485Z: the block ran past the right frame and
    # sat between the isometric and its label.  Its top now stands under the
    # thread (so under both of the hole's extension lines), right of the
    # threaded end, and its widest row (~74 mm) ends inside the frame.
    x, y = drawing.SECTION_KEEP["EndHoleDia"]
    block_top = y + drawing._DIA_BLOCK_ABOVE_KEEP
    assert block_top < drawing.SECTION_CENTER[1] - drawing.THREAD_R
    assert x > drawing.TIP_X
    assert x + 0.075 < 0.419
    assert block_top < drawing.ISO_NOTE_POS[1]
    assert drawing.DIMENSION_CALLOUTS == {"EndHoleDia": spec.END_HOLE_CALLOUT}
