"""Offline contracts for the MHA-CH-06-TL-VN-53 CL locator dowel (McMaster 98381A542)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import _mcmaster_98381a542 as dims
import build_ch_rocker_arm_tl_vn_oblique_cl_dowel as part
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_vn_oblique_cl_dowel_spec as spec
import ch_rocker_arm_tl_oblique_jig_assembly_spec as jig
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_98381A542 as recipe
from diagnostics.diag_mcmaster_dowel import dowel_section, dowel_volume

STEM = "ch-rocker-arm-tl-vn-oblique-cl-dowel"
INCH = 25.4

# The vendor STEP (SHA-256 2c11cd08...) read headless on 2026-10-30
# (local inch-vendor-step-evidence): volume, cylinder and end-face stations.
VENDOR_VOLUME = 800.6537472021738  # mm^3
VENDOR_CHAMFER_FACE_R = 0.1175 * INCH
VENDOR_CONE_END_X = 0.4738443916711928 * INCH  # from the pin's centre
VENDOR_ROUND_FACE_R = 0.094 * INCH


def test_catalogue_row_is_the_registered_mcmaster_dowel() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == STEM
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("98381A542",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == "MHA-CH-06-TL-VN-53"
    assert row["process"] == "purchased"
    assert spec.SKU in row["material_specification"]
    assert int(row["quantity"]) == spec.QUANTITY == 1
    assert jig.QUANTITIES[STEM] == spec.QUANTITY
    assert spec.UNIT == "in"
    metadata = recipe_declaration(spec.SKU, recipe.build_98381A542)
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_98381A542
    assert metadata.threaded is False


def test_standalone_recipe_run_is_catalog_only() -> None:
    """Not replica-gated: the standalone command must not enter the McMaster
    replica path, which demands a vendor SLDPRT and its harvest."""
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert recipe.PART_NO == spec.SKU
    assert spec.SKU not in REGISTRY
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "replica_main" not in source
    assert "run_build(_catalog)" in source
    assert "catalog-only" in (recipe.__doc__ or "")


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob("cad/references/**/98381A542*.SLDPRT"))


def test_diameter_and_bands_are_the_carriers() -> None:
    assert (
        spec.DIA
        == dims.DOWEL_SIZE[0]
        == carrier.CL_DOWEL_DIA
        == pytest.approx(0.25 * INCH)
    )
    assert spec.LENGTH == pytest.approx(1.0 * INCH)
    assert spec.DIA_BAND == carrier.CL_DOWEL_BAND
    assert spec.HOLE_BAND == carrier.CL_HOLE_BAND
    assert spec.INTERFERENCE == carrier.CL_DOWEL_INTERFERENCE
    # The page's +.0001/+.0003 and fit doc F19's .2490-.2495 hole.
    assert (spec.DIA_MIN, spec.DIA_MAX) == pytest.approx((0.2501 * INCH, 0.2503 * INCH))
    hole = sorted(spec.DIA + band for band in spec.HOLE_BAND)
    assert hole == pytest.approx([0.2490 * INCH, 0.2495 * INCH])
    assert spec.INTERFERENCE == pytest.approx((0.0006 * INCH, 0.0013 * INCH))


def test_end_forms_are_the_vendor_steps() -> None:
    section = dowel_section(dims.DOWEL_SIZE, dims.ENDS)
    radius, length = spec.DIA / 2.0, spec.LENGTH
    # Chamfered end: flat face Ø.235 at y = 0, the cone reaching Ø.250 where
    # the STEP's cone ends.
    assert (VENDOR_CHAMFER_FACE_R, 0.0) == pytest.approx(section[3])
    assert section[4] == pytest.approx((radius, length / 2.0 - VENDOR_CONE_END_X))
    # Round end: the R.031 corner down to the Ø.188 face.
    assert section[0] == pytest.approx((VENDOR_ROUND_FACE_R, length))
    assert spec.ROUND_H == pytest.approx(radius - VENDOR_ROUND_FACE_R)
    assert spec.LEAD_IN == pytest.approx(section[4][1])


def test_reference_lines_lie_on_front_edges() -> None:
    # The diameter on the chamfer's edge with the cylinder (the STEP's cone
    # end), the length on the silhouette; no chord crosses the Top end view.
    assert set(spec.SUPPLIER_REFERENCE_PLANES.values()) == {"Front"}
    assert spec.SUPPLIER_REFERENCE_STARTS == {
        "SupplierDowelDiameter": (-spec.DIA / 2.0, spec.LEAD_IN),
        "SupplierDowelLength": (-spec.DIA / 2.0, 0.0),
    }


def test_closed_form_volume_is_the_vendor_steps() -> None:
    assert dowel_volume(dims.DOWEL_SIZE, dims.ENDS) == pytest.approx(
        VENDOR_VOLUME, rel=1e-6
    )


def test_frame_puts_the_chamfered_end_at_y0() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'screw_axis_planes=("Front Plane", "Right Plane")' in source
    assert spec.TIP_BASE_Z + spec.LENGTH == pytest.approx(
        jig.trammel.CARRIER_TOP_Z + jig.trammel.RISER_THICK + spec.TIP_HEIGHT
    )


def test_press_contract() -> None:
    assert spec.PRESS_DEPTH + spec.PROUD == pytest.approx(spec.LENGTH)
    assert spec.PRESS_ENGAGEMENT_D >= spec.PRESS_ENGAGEMENT_MIN_D
    assert min(spec.DIA_BAND) > 0.0  # a press dowel is oversize, never under
    assert 0.0 < spec.INTERFERENCE[0] <= spec.INTERFERENCE[1]
    assert 0.0 < spec.PRESS_OVERLAP_MM3 < spec.PRESS_ALLOWANCE_MM3
    # The 1 in pin spans the whole slab: its overlap is the slab's cylinder
    # less the centre spot.
    slab = math.pi * spec.DIA**2 * carrier.THICKNESS / 4.0
    assert spec.PRESS_DEPTH > carrier.THICKNESS + spec.LEAD_IN
    assert spec.PRESS_OVERLAP_MM3 < slab
    assert spec.PRESS_ALLOWANCE_MM3 == pytest.approx(1.10 * slab)


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_ch_rocker_arm_tl_vn_oblique_cl_dowel as drawing

    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_cl_dowel"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES


@pytest.mark.parametrize("carrier_sign", (-1.0, 1.0))
@pytest.mark.parametrize("riser_sign", (-1.0, 1.0))
@pytest.mark.parametrize("tip_height", (spec.TIP_SET_MIN, spec.TIP_SET_MAX))
def test_riser_referenced_fitup_covers_the_finished_plate_stack(
    carrier_sign: float, riser_sign: float, tip_height: float
) -> None:
    carrier_thickness = carrier.THICKNESS + carrier_sign * carrier.THICKNESS_BAND
    riser_thickness = spec.riser.THICKNESS + riser_sign * spec.riser.THICKNESS_BAND
    pin_bottom = carrier_thickness + riser_thickness + tip_height - spec.LENGTH
    # The chamfered end stands below the carrier, above the pivot-block tops.
    assert pin_bottom < 0.0
    assert -pin_bottom < jig.trammel.PIVOT_SUPPORT_HEIGHT
    # Independent interval intersection: only the full-diameter pin cylinder
    # between the hole's two mouth breaks provides press contact.
    cylinder_start = pin_bottom + spec.LEAD_IN
    cylinder_end = pin_bottom + spec.LENGTH - spec.ROUND_H
    contact = min(cylinder_end, carrier_thickness - carrier.TAP_MOUTH_BREAK) - max(
        carrier.TAP_MOUTH_BREAK, cylinder_start
    )
    assert contact >= spec.PRESS_ENGAGEMENT_MIN_D * spec.DIA_MAX
    # The cylinder reaches into the strap's hole and stays under its top.
    assert tip_height - spec.ROUND_H > 0.0
    assert tip_height < spec.rocker.ARM_THICKNESS + min(spec.rocker.ARM_THICKNESS_BAND)
