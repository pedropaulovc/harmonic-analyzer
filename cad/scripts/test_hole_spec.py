"""Offline contracts for part-owned standard-hole definitions."""

from __future__ import annotations

import pytest

import ch_pivot_bracket_spec
import dt_crank_arm_spec
import dt_crank_hub_spec
import _config
from _hole_spec import CLEARANCE_MM, HoleSpec, blind_cut_dia_mm, drill_process


def test_crank_drill_process_is_derived_from_part_owned_specs() -> None:
    assert blind_cut_dia_mm(dt_crank_hub_spec.SERVICE_PIN_HOLE_SPEC) == 4.623
    assert drill_process(dt_crank_hub_spec.SERVICE_PIN_HOLE_SPEC) == "#14 DRILL"
    # The arm pivot is tapped #4-40 (tap drill #43) for MHA-DT-32.
    assert blind_cut_dia_mm(dt_crank_arm_spec.HANDLE_PIVOT_HOLE_SPEC) == 2.261
    with pytest.raises(ValueError, match="not a drill-size hole"):
        drill_process(dt_crank_arm_spec.HANDLE_PIVOT_HOLE_SPEC)


def test_drill_process_rejects_non_drill_holes() -> None:
    with pytest.raises(ValueError, match="not a drill-size hole"):
        drill_process(HoleSpec("clearance", "#4"))


def test_pivot_bracket_hold_down_is_a_true_number_8_close_clearance() -> None:
    # Cut at the table diameter, not a rounded one (8a36fe155 caught #19 cut at
    # 4.2). #19 became #8 close in r743-3C: it caught the screw's fillet.
    assert ch_pivot_bracket_spec.HOLD_DOWN_HOLE_SPEC == HoleSpec("clearance", "#8", fit="close")
    assert ch_pivot_bracket_spec.HOLE_DIA == 4.572


def test_fastener_clearance_drills_land_in_the_native_drilled_band() -> None:
    # The named drill is what the shop cuts: at or over the native wizard
    # nominal, within the title block's drilled-hole band, or a noted row.
    # Slack covers the 3-place mm table and the 4-place drill sizes.
    plus_in = _config.title_block("drilled_hole", unit="in")["plus_in"]
    slack_in = 0.00005 + 0.0005 / 25.4
    unexplained = []
    for size, fits in _config.fit("fastener_clearance", "sizes").items():
        for fit, row in fits.items():
            native_mm = CLEARANCE_MM.get((size, fit))
            in_band = native_mm is not None and (
                native_mm / 25.4 - slack_in
                <= row["dia_in"]
                <= native_mm / 25.4 + plus_in + slack_in
            )
            if not in_band and not row.get("note"):
                unexplained.append((size, fit, row["drill"], native_mm))
    assert not unexplained
