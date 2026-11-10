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
    # The exception quotes the wall row the callout prints.
    assert spec.END_HOLE_CALLOUT_BELOW.splitlines()[-1] == "WALL .067 MIN"
    assert row["where"].endswith(": WALL .067 MIN")
    assert row["reason"].startswith("Owner ruling 2026-11-09 via PR #1992")
    assert "pull/1992" in row["reason"]


def test_pivot_never_bottoms_and_always_runs_in_the_hole() -> None:
    assert spec.PIVOT_FLOOR_AIR_MIN > 0.0
    assert spec.PIVOT_ENGAGEMENT_MIN > 0.0
    assert spec.PIVOT_PROUD_MIN < spec.PIVOT_PROUD_MAX


def test_hole_callout_is_size_process_depth_then_two_lines_of_words() -> None:
    from _drawing_blind_ream_callout import printed_depth, ream_definitions

    # Rules 12 and 26 (PR 2 r7 machinist review): size, process, depth on the
    # native callout's one line, the depth SolidWorks' own (its format
    # definitions as r7 read them on the shaft socket's plain cut); rule 7:
    # two lines of words below.
    native = {
        5: "<MOD-DIAM>",
        6: f"<HOLE-DEPTH>{spec.END_HOLE_DEPTH_TEXT}",
        7: "",
        8: "",
    }
    callout = ream_definitions(
        native,
        process=spec.END_HOLE_PROCESS,
        below=spec.END_HOLE_CALLOUT_BELOW,
        label="end screw",
    )
    assert callout[6].strip() == "REAM <HOLE-DEPTH>.12"
    assert printed_depth(callout, label="end screw") == ".12"
    assert callout[8].splitlines() == [
        "RUNNING FIT ON MHA-DT-37",
        "WALL .067 MIN",
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
    # A plain cut: the sketch owns the diameter, the cut its blind depth.
    assert spec.DRAWING_DIMENSIONS == {
        spec.HOLE_FEATURE: {"EndHoleDia"},
        spec.HOLE_CUT: {"EndHoleDepth"},
    }
    assert spec.DRAWING_PRECISION_BY_NAME == {"EndHoleDia": 4, "EndHoleDepth": 2}


def test_sheet_is_registered_and_enforced() -> None:
    import draw_dt_cone_tip_end_screw as drawing

    sheet = DRAWINGS_BY_NAME["dt_cone_tip_end_screw"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.artifact_stem == spec.PART_NAME
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE


def test_hole_callout_stands_clear_of_the_end_view_and_inside_the_frame() -> None:
    import draw_dt_cone_tip_end_screw as drawing

    # The text centres on CALLOUT_XY, left of the end view at mid height: its
    # widest row, the size line, stays inside the frame (0.0124) and short of
    # the head's outline; no word row is wider than the size line (24
    # characters at ~2.48 mm, r7).
    x, _y = drawing.CALLOUT_XY
    assert x - drawing.CALLOUT_HALF_WIDTH > 0.0124
    assert (
        x + drawing.CALLOUT_HALF_WIDTH < drawing.END_CENTER[0] - drawing.HEAD_R - 0.005
    )
    rows = spec.END_HOLE_CALLOUT_BELOW.splitlines()
    assert max(len(row) for row in rows) * 0.00248 <= 2 * drawing.CALLOUT_HALF_WIDTH
