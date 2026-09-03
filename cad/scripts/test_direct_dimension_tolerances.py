"""Offline contracts for direct model-dimension tolerance ownership."""

from __future__ import annotations

import build_alignment_pinion
import build_arbor_pedestal
import build_cone_pivot_post
import build_cone_tip_adjuster
import build_connecting_rod
import build_crank_arm
import build_crank_drive_gear
import build_crank_handle
import build_crank_pinion
import build_crankshaft
import build_cylinder_gear
import build_top_frame
import build_tube_frame
import alignment_pinion_spec
import arbor_pedestal_spec
import cone_pivot_post_spec
import connecting_rod_spec
import crank_arm_spec
import crank_drive_gear_spec
import crank_pinion_spec
import crankshaft_spec
import cylinder_gear_spec
import top_frame_spec
import tube_frame_spec
from _drawing_contract import model_toleranced_dimensions


def test_direct_tolerance_values_are_named_in_part_specs() -> None:
    assert alignment_pinion_spec.ARBOR_BORE_BAND == (-0.020, -0.040)
    assert arbor_pedestal_spec.BORE_DIA_BAND == (0.055, 0.025)
    assert cone_pivot_post_spec.CRANK_BORE_TOLERANCE_MM == 0.025
    assert cone_pivot_post_spec.JOURNAL_BORE_BAND == (0.025, 0.000)
    assert connecting_rod_spec.RING_BORE_DIA_BAND == (0.10, 0.00)
    assert crank_arm_spec.SHAFT_BORE_BAND == (0.05, 0.00)
    assert crank_drive_gear_spec.BORE_DIA_BAND == (0.050, 0.000)
    assert crank_pinion_spec.BORE_DIA_BAND == (0.050, 0.000)
    assert crankshaft_spec.JOURNAL_DIA_BAND == (0.00, -0.02)
    assert cylinder_gear_spec.BORE_DIA_BAND == (0.05, 0.00)
    assert cylinder_gear_spec.NOTCH_WIDTH_TOLERANCE_MM == 0.05
    assert tube_frame_spec.OUTER_DIA_BAND == (0.00, -0.05)
    assert tube_frame_spec.COLUMN_LENGTH_TOLERANCE_MM == 0.25
    assert top_frame_spec.OUTER_PROFILE_TOLERANCE_MM == 0.25


def test_direct_tolerances_are_owned_by_named_model_dimensions() -> None:
    expected = {
        build_alignment_pinion: {
            ("ArborBoreProfile", "ArborBoreDia"): "*deviations(ARBOR_BORE_BAND)"
        },
        build_arbor_pedestal: {
            ("BoreProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)"
        },
        # cone_lock_knob: no model bands since the machinist review of
        # 2026-09-02 (the washer thickness is a title-block .XX feature).
        build_cone_pivot_post: {
            # The body, collar and boss diameters are as-cast and carry no band
            # (cone_pivot_post_spec, 2026-09-02); the two bores keep their fits.
            ("CrankBoreProfile", "CrankBoreDia"): "CRANK_BORE_TOLERANCE_MM",
            ("JournalBoreProfile", "JournalBoreDia"): "*deviations(JOURNAL_BORE_BAND)",
        },
        # cone_tip_block (cone pass) and cone_tip_bushing (shafts pass) carry
        # no model bands since the review of 2026-09-02; their per-sheet
        # contracts pin the empty maps.
        build_cone_tip_adjuster: {
            # The body length and cup depth bands were removed by the cone
            # review pass of 2026-09-02 (see cone_tip_adjuster_spec).
            ("SlotProfile", "SlotWDim"): "GENERAL_TOL_MM",
            ("CupProfile", "CupDiaDim"): "*deviations(CUP_DIA_BAND)",
        },
        build_connecting_rod: {
            ("StrapBoreProfile", "StrapBoreDia"): "*deviations(RING_BORE_DIA_BAND)"
        },
        build_crank_arm: {
            ("ShaftBoreProfile", "ShaftBoreDia"): "*deviations(SHAFT_BORE_BAND)"
        },
        build_crank_drive_gear: {
            ("BoreProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)"
        },
        build_crank_handle: {
            ("HandleProfile", "HandleLength"): "*deviations(HANDLE_LENGTH_BAND)",
            ("PivotBoreProfile", "PivotBoreDia"): "*deviations(PIVOT_BORE_BAND)",
        },
        build_crank_pinion: {("BoreProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)"},
        build_crankshaft: {
            # SHAFT_DIA_BAND was removed by the pen-frame review pass of
            # 2026-09-02 (see crankshaft_spec); only the journal keeps a band.
            ("JournalProfile", "JournalDiaDim"): "*deviations(JOURNAL_DIA_BAND)",
        },
        build_cylinder_gear: {
            ("BoreProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)",
        },
        # cone_swing_platform: PLATE_LENGTH_TOLERANCE_MM was removed by the
        # cone review pass of 2026-09-02 (see cone_swing_platform_spec).
        build_tube_frame: {
            ("AnnulusProfile", "OuterDia"): "*deviations(OUTER_DIA_BAND)",
            # Overall-length acceptance moved to the cap sketch's apex station
            # when the integral dome cap landed (2026-08-02): Column/Depth is
            # now the driven 1010.7 tube portion, not the acceptance length.
            ("CapProfile", "CapApexY"): "COLUMN_LENGTH_TOLERANCE_MM",
        },
        build_top_frame: {
            ("OuterProfile", "Width"): "OUTER_PROFILE_TOLERANCE_MM",
            ("OuterProfile", "Depth"): "OUTER_PROFILE_TOLERANCE_MM",
        },
    }

    for build_module, dimensions in expected.items():
        assert model_toleranced_dimensions(build_module) == dimensions
