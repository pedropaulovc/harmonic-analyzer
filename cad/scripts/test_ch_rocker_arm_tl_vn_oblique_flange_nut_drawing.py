"""PM kit FlangeNut member, 1/2-13 (MHA-SH-VN-57) contracts, SolidWorks-free."""

from __future__ import annotations

import math

import _config
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import sh_vn_clamping_kit_flange_nut_spec as spec
import ch_rocker_arm_tl_oblique_jig_assembly_spec as jig
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _hole_spec import TAP_DRILL_MM

STEM = "sh-vn-clamping-kit-hardware"
ROW = _config.parts(STEM)
CONFIGURATION = "FlangeNut"


def test_registry_row_is_the_purchased_pm_kit_flange_nut() -> None:
    assert ROW["process"] == "purchased"
    assert ROW["supplier"] == spec.SUPPLIER == "Precision Matthews"
    assert ROW["supplier_skus"] == [spec.SKU] == ["52PCCK-9/16-14mm"]
    assert ROW["material"] == spec.MATERIAL


def test_quantity_is_one_on_each_hold_down_stud() -> None:
    assert int(ROW["configuration_quantities"][CONFIGURATION]) == (
        spec.QUANTITY
    ) == fasteners.HOLD_DOWN_STUD_COUNT
    assert int(ROW["quantity"]) == sum(ROW["configuration_quantities"].values())


def test_c4_envelope_is_owned_here() -> None:
    assert spec.THREAD == fasteners.HOLD_DOWN_STUD_THREAD
    # The spec owns C4's flange-nut estimates; the jig assembly reads them here.
    assert (spec.FLANGE_DIA, spec.HEIGHT) == (28.0, 13.0)
    # The jig seats the flange on the bar top.
    assert math.isclose(jig.FLANGE_NUT_SEAT_Z, trammel.BASE_BAR_THICK)


def test_estimated_hex_and_flange_are_te_co_41605_proportions() -> None:
    # TE-CO 41605: 0.875 in across flats, a 0.188 (3/16) in flange.
    assert math.isclose(spec.ACROSS_FLATS, 0.875 * 25.4)
    assert math.isclose(spec.FLANGE_THICK, 3.0 / 16.0 * 25.4)
    assert spec.HEX_CORNER_RADIUS < spec.FLANGE_DIA / 2.0
    assert spec.TAP_DRILL_DIA == TAP_DRILL_MM[spec.THREAD]


def test_hex_outline_is_regular_with_corners_on_z() -> None:
    corners = spec.HEX_OUTLINE
    assert len(corners) == 6
    assert corners[0] == (0.0, spec.HEX_CORNER_RADIUS)
    for (x0, z0), (x1, z1) in zip(corners, corners[1:] + corners[:1]):
        assert math.isclose(math.hypot(x1 - x0, z1 - z0), spec.HEX_CORNER_RADIUS)
    xs = [x for x, _ in corners]
    assert math.isclose(max(xs) - min(xs), spec.ACROSS_FLATS)


def test_closed_form_volume_matches_the_shoelace_hex() -> None:
    pts = spec.HEX_OUTLINE
    hex_area = 0.5 * abs(
        sum(x0 * z1 - x1 * z0 for (x0, z0), (x1, z1) in zip(pts, pts[1:] + pts[:1]))
    )
    flange = math.pi * (spec.FLANGE_DIA / 2.0) ** 2 * spec.FLANGE_THICK
    tap = math.pi * (TAP_DRILL_MM[spec.THREAD] / 2.0) ** 2 * spec.HEIGHT
    numeric = flange + hex_area * (spec.HEIGHT - spec.FLANGE_THICK) - tap
    assert math.isclose(spec.VOLUME_MM3, numeric, rel_tol=1e-9)
