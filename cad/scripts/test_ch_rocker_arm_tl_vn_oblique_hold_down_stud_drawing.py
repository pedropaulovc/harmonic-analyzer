"""PM kit HoldDownStud member (MHA-SH-VN-57) contracts, SolidWorks-free."""

from __future__ import annotations

import math

import _config
import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import sh_vn_clamping_kit_hold_down_stud_spec as spec
import ch_rocker_arm_tl_oblique_jig_assembly_spec as jig
from _hole_spec import THREAD_MAJOR_MM

STEM = "sh-vn-clamping-kit-hardware"
ROW = _config.parts(STEM)
CONFIGURATION = "HoldDownStud"


def test_registry_row_is_the_purchased_pm_kit_stud() -> None:
    assert ROW["process"] == "purchased"
    assert ROW["supplier"] == spec.SUPPLIER == "Precision Matthews"
    assert ROW["supplier_skus"] == [spec.SKU] == ["52PCCK-9/16-14mm"]
    assert ROW["material"] == spec.MATERIAL


def test_quantity_is_c4s_hold_down_count() -> None:
    assert (
        int(ROW["configuration_quantities"][CONFIGURATION])
        == (spec.QUANTITY)
        == fasteners.HOLD_DOWN_STUD_COUNT
    )
    assert int(ROW["quantity"]) == sum(ROW["configuration_quantities"].values())


def test_stud_size_matches_the_hold_down_stack() -> None:
    assert spec.THREAD == fasteners.HOLD_DOWN_STUD_THREAD == "1/2-13"
    assert spec.LENGTH == fasteners.HOLD_DOWN_STUD_LENGTH_MM == jig.STUD_LENGTH
    assert spec.MAJOR_DIA == base_bar.HOLD_DOWN_STUD_DIA == jig.STUD_DIA
    assert math.isclose(spec.MAJOR_DIA, THREAD_MAJOR_MM[spec.THREAD])


def test_profile_closes_on_the_axis_from_the_origin() -> None:
    assert spec.PROFILE[0] == (0.0, 0.0)
    assert spec.PROFILE[-1] == (spec.LENGTH, 0.0)
    assert max(r for _, r in spec.PROFILE) == spec.MAJOR_DIA / 2.0


def test_closed_form_volume_matches_a_numeric_revolve() -> None:
    def radius(y: float) -> float:
        for (y0, r0), (y1, r1) in zip(spec.PROFILE, spec.PROFILE[1:]):
            if y0 <= y <= y1 and y1 > y0:
                return r0 + (r1 - r0) * (y - y0) / (y1 - y0)
        raise AssertionError(y)

    n = 20000
    dy = spec.LENGTH / n
    numeric = sum(math.pi * radius((i + 0.5) * dy) ** 2 * dy for i in range(n))
    assert math.isclose(spec.VOLUME_MM3, numeric, rel_tol=1e-6)
