"""SolidWorks-free contracts for MHA-DT-38, the cone tip bushing."""

from __future__ import annotations

import math

import pytest

import _config
import cone_tip_cluster as tip
import dt_cone_tip_bushing_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _inch_wall_limits import WALL_TARGET_MM
from _machinist_review_mode import MachinistReviewMode

IN = 25.4


def test_registry_row_is_the_turned_brass_bushing() -> None:
    row = _config.parts(spec.PART_NAME)
    assert row["number"] == "MHA-DT-38"
    assert row["material_specification"] == "C36000 free-machining brass"
    assert row["quantity"] == 1
    assert row["drawing_unit"] == spec.UNIT == "in"
    assert "ream the bore" in row["process"]
    assert "machinist_exceptions" not in row


def test_mates_are_named_by_their_registered_numbers() -> None:
    assert _config.parts("dt-cone-tip-gear")["number"] == spec.PIVOT_NUMBER
    assert _config.parts("dt-cone-tip-end-screw")["number"] == spec.END_SCREW_NUMBER


def test_sizes_are_the_tip_cluster_contract() -> None:
    assert spec.OUTER_DIA == pytest.approx(0.228 * IN)
    assert spec.LENGTH == pytest.approx(0.160 * IN)
    assert spec.BORE_DIA == pytest.approx(0.0615 * IN)
    assert spec.BORE_DIA_BAND == tip.REAM_H7 == (0.0127, 0.0)


def test_press_on_the_pivot_interferes_at_every_limit() -> None:
    bore = (spec.BORE_DIA, spec.BORE_DIA + max(spec.BORE_DIA_BAND))
    pivot = (
        tip.STEM_DIA_MM + min(tip.PIVOT_DIA_BAND),
        tip.STEM_DIA_MM + max(tip.PIVOT_DIA_BAND),
    )
    least, most = pivot[0] - bore[1], pivot[1] - bore[0]
    assert least > 0.0
    assert spec.PRESS_INTERFERENCE == pytest.approx((least, most))
    assert least / IN == pytest.approx(0.0002)
    assert most / IN == pytest.approx(0.0010)


def test_wall_holds_the_rule_17_target_at_the_worst_case() -> None:
    worst = (spec.OUTER_DIA - 0.005 * IN - (spec.BORE_DIA + 0.0005 * IN)) / 2.0
    assert spec.WALL_WORST == pytest.approx(worst)
    assert spec.WALL_WORST >= WALL_TARGET_MM


def test_bore_callout_names_process_fit_mate_and_interference() -> None:
    assert spec.BORE_CALLOUT.splitlines() == [
        "REAM THRU",
        "PRESS FIT ON MHA-DT-37 PIVOT",
        "(INTERFERENCE .0002-.0010 REF)",
    ]


def test_every_marked_dimension_has_places() -> None:
    assert spec.DRAWING_PRECISION_BY_NAME == {"OuterDia": 3, "BoreDia": 4, "Length": 3}


def test_builder_volume_is_the_annulus() -> None:
    import build_dt_cone_tip_bushing as build

    assert build.V_BUSHING == pytest.approx(
        math.pi / 4.0 * (spec.OUTER_DIA**2 - spec.BORE_DIA**2) * spec.LENGTH
    )


def test_sheet_is_registered_and_enforced() -> None:
    import draw_dt_cone_tip_bushing as drawing

    sheet = DRAWINGS_BY_NAME["dt_cone_tip_bushing"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.artifact_stem == spec.PART_NAME
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    assert set(drawing.SECTION_KEEP) == set(spec.DRAWING_PRECISION_BY_NAME)
