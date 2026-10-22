"""PM kit TNut member, 1/2-13 (MHA-SH-VN-57) contracts, SolidWorks-free."""

from __future__ import annotations

import math

import _config
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_jig_assembly_spec as jig
import sh_vn_clamping_kit_t_nut_spec as spec
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _hole_spec import TAP_DRILL_MM

STEM = "sh-vn-clamping-kit-hardware"
ROW = _config.parts(STEM)
CONFIGURATION = "TNut"


def test_registry_row_is_the_purchased_pm_kit_t_nut() -> None:
    assert ROW["process"] == "purchased"
    assert ROW["supplier"] == spec.SUPPLIER == "Precision Matthews"
    assert ROW["supplier_skus"] == [spec.SKU] == ["52PCCK-9/16-14mm"]
    assert ROW["material"] == spec.MATERIAL


def test_quantity_is_one_under_each_hold_down_stud() -> None:
    assert (
        int(ROW["configuration_quantities"][CONFIGURATION])
        == (spec.QUANTITY)
        == fasteners.HOLD_DOWN_STUD_COUNT
    )
    assert int(ROW["quantity"]) == sum(ROW["configuration_quantities"].values())


def test_t_nut_thread_and_slot_match_the_hold_down_stack() -> None:
    assert spec.THREAD == fasteners.HOLD_DOWN_STUD_THREAD
    assert spec.SLOT_WIDTH == trammel.TSLOT_WIDTH
    # The spec owns C4's T-slot estimates; the jig assembly reads them here.
    assert (spec.FOOT_HEIGHT, spec.THROAT_DEPTH) == (8.0, 14.0)


def test_t_nut_fits_the_table_slot() -> None:
    # The neck passes the throat and stays below the table surface; the
    # stud's bottom end sits flush with the foot (C4's STUD_BOTTOM_Z).
    assert spec.NECK_WIDTH < trammel.TSLOT_WIDTH
    assert spec.NECK_HEIGHT < spec.THROAT_DEPTH
    assert spec.HEIGHT <= spec.THROAT_DEPTH + spec.FOOT_HEIGHT
    assert jig.STUD_BOTTOM_Z == -(spec.THROAT_DEPTH + spec.FOOT_HEIGHT)
    assert spec.TAP_DRILL_DIA == TAP_DRILL_MM[spec.THREAD]
    assert spec.TAP_DRILL_DIA < spec.NECK_WIDTH < spec.FOOT_WIDTH


def test_section_is_closed_axis_aligned_and_symmetric() -> None:
    profile = spec.PROFILE
    for (u0, v0), (u1, v1) in zip(profile, profile[1:] + profile[:1]):
        assert u0 == u1 or v0 == v1
    assert sorted(profile) == sorted((-u, v) for u, v in profile)
    assert profile[0] == (-spec.FOOT_WIDTH / 2.0, 0.0)


def test_closed_form_volume_matches_the_shoelace_section() -> None:
    pts = spec.PROFILE
    area = 0.5 * abs(
        sum(u0 * v1 - u1 * v0 for (u0, v0), (u1, v1) in zip(pts, pts[1:] + pts[:1]))
    )
    tap = math.pi * (TAP_DRILL_MM[spec.THREAD] / 2.0) ** 2 * spec.HEIGHT
    assert math.isclose(spec.VOLUME_MM3, spec.LENGTH * area - tap, rel_tol=1e-12)
