"""Offline contracts for specified manufacturing tolerance bands."""

from __future__ import annotations

import alignment_pinion_spec
import arbor_pedestal_spec
import cone_pivot_post_spec
import cone_swing_platform_spec
import cone_tip_block_spec
import cone_tip_bushing_spec
import connecting_rod_spec
import crank_arm_spec
import crank_drive_gear_spec
import crank_pinion_spec
import crankshaft_spec
import top_frame_spec
import tube_frame_spec


def test_direct_tolerance_values_are_named_in_part_specs() -> None:
    assert alignment_pinion_spec.ARBOR_BORE_BAND == (-0.020, -0.040)
    assert arbor_pedestal_spec.BORE_DIA_BAND == (0.030, 0.000)
    assert cone_pivot_post_spec.TURNED_DIAMETER_TOLERANCE_MM == 0.05
    assert cone_pivot_post_spec.CRANK_BORE_TOLERANCE_MM == 0.025
    assert cone_tip_block_spec.BLOCK_HEIGHT_BAND == (0.05, 0.00)
    assert cone_tip_bushing_spec.BORE_DIA_BAND == (0.05, 0.00)
    assert cone_tip_bushing_spec.LENGTH_TOLERANCE_MM == 0.03
    assert connecting_rod_spec.RING_BORE_DIA_BAND == (0.10, 0.00)
    assert crank_arm_spec.SHAFT_BORE_BAND == (0.05, 0.00)
    assert crank_drive_gear_spec.BORE_DIA_BAND == (0.050, 0.030)
    assert crank_pinion_spec.BORE_DIA_BAND == (0.050, 0.030)
    assert crankshaft_spec.SHAFT_DIA_BAND == (0.00, -0.02)
    assert crankshaft_spec.JOURNAL_DIA_BAND == (0.00, -0.02)
    assert cone_swing_platform_spec.PLATE_LENGTH_TOLERANCE_MM == 0.25
    assert tube_frame_spec.OUTER_DIA_BAND == (0.00, -0.05)
    assert tube_frame_spec.COLUMN_LENGTH_TOLERANCE_MM == 0.25
    assert top_frame_spec.OUTER_PROFILE_TOLERANCE_MM == 0.25
