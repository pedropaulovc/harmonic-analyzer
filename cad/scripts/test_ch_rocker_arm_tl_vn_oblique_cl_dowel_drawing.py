"""Offline contracts for the MHA-CH-06-TL-VN-53 CL locator dowel (McMaster 91595A452)."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import _config
import _mcmaster_91595a452 as dims
import build_ch_rocker_arm_tl_vn_oblique_cl_dowel as part
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_vn_oblique_cl_dowel_spec as spec
import ch_rocker_arm_tl_oblique_jig_assembly_spec as jig
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_91595A452 as recipe
from diagnostics.sketch_profile import Arc, Line, closed_loops, endpoint_merges

STEM = "ch-rocker-arm-tl-vn-oblique-cl-dowel"

# The vendor STEP read by FreeCAD 1.1 on 2026-10-17 (dt-logs
# trammel-bought/vendor-cad/bd-freecad-harvest.json).
VENDOR_VOLUME = 536.845334  # mm^3
VENDOR_CROWN_R = 5.016461
VENDOR_DOME_R = 5.45
VENDOR_RIM_R = 2.686499
# The recipe's closed form reproduces the vendor STEP to 0.02 %.
VOLUME_REL = 2e-4


def test_catalogue_row_is_the_registered_mcmaster_dowel() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == STEM
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("91595A452",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == "MHA-CH-06-TL-VN-53"
    assert row["process"] == "purchased"
    assert spec.SKU in row["material_specification"]
    assert int(row["quantity"]) == spec.QUANTITY == 1
    assert jig.QUANTITIES[STEM] == spec.QUANTITY
    metadata = recipe_declaration(spec.SKU, recipe.build_91595A452)
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_91595A452
    assert metadata.threaded is False


def test_standalone_recipe_run_is_catalog_only() -> None:
    """Not replica-gated (user ruling 2026-10-17): the standalone command must
    not enter the McMaster replica path, which demands a vendor SLDPRT and its
    harvest."""
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert recipe.PART_NO == spec.SKU
    assert REGISTRY[spec.SKU] is recipe.build_91595A452
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "replica_main(" not in source and "import replica_main" not in source
    assert "run_build(build_catalog)" in source
    assert "catalog-only" in (recipe.__doc__ or "")


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob("cad/references/**/91595A452*.SLDPRT"))


def test_diameter_and_bands_are_the_carriers() -> None:
    assert dims.DIA == carrier.CL_DOWEL_DIA == 6.0
    assert spec.DIA_BAND == carrier.CL_DOWEL_BAND == (0.012, 0.004)
    assert spec.HOLE_BAND == carrier.CL_HOLE_BAND
    assert spec.INTERFERENCE == carrier.CL_DOWEL_INTERFERENCE
    assert (spec.DIA_MIN, spec.DIA_MAX) == pytest.approx((6.004, 6.012))
    text = _config.parts(STEM)["stock_name"]
    match = re.search(r"Ø(\d+) x (\d+) mm", text)
    assert match, text
    assert (float(match[1]), float(match[2])) == (dims.DIA, dims.LENGTH)


def test_section_is_one_closed_loop_on_the_axis() -> None:
    section = recipe.pin_section()
    endpoint_merges(section)
    assert len(closed_loops(section)) == 1
    points = {p for segment in section for p in (segment.start, segment.end)}
    assert min(y for _, y in points) == 0.0
    assert max(y for _, y in points) == dims.LENGTH
    assert max(r for r, _ in points) == dims.DIA / 2.0
    assert Line((0.0, dims.LENGTH), (0.0, 0.0)) in section
    arcs = [segment for segment in section if isinstance(segment, Arc)]
    assert len(arcs) == 2


def test_end_forms_are_the_vendor_steps() -> None:
    assert dims.chamfer_rim_radius() == pytest.approx(VENDOR_RIM_R, abs=1e-6)
    assert dims.crown_radius() == pytest.approx(VENDOR_CROWN_R, abs=1e-6)
    assert dims.dome_radius() == pytest.approx(VENDOR_DOME_R, abs=1e-9)
    # The 15 deg cone runs from the cylinder to the crown rim.
    cone = recipe.pin_section()[1]
    (r0, y0), (r1, y1) = cone.start, cone.end
    assert math.degrees(math.atan2(r1 - r0, y1 - y0)) == pytest.approx(15.0)


def test_closed_form_volume_is_the_vendor_steps() -> None:
    assert dims.dowel_volume() == pytest.approx(VENDOR_VOLUME, rel=VOLUME_REL)


def test_frame_puts_the_chamfered_end_at_y0() -> None:
    crown = recipe.pin_section()[0]
    assert crown.start == (0.0, 0.0)
    assert crown.end[1] == dims.CROWN_H
    # The cylinder ends at the dome rim, DOME_H short of the far tip.
    assert recipe.pin_section()[2].end == (dims.DIA / 2.0, dims.LENGTH - dims.DOME_H)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'screw_axis_planes=("Front Plane", "Right Plane")' in source


def test_press_contract() -> None:
    assert spec.PRESS_DEPTH + spec.PROUD == pytest.approx(dims.LENGTH)
    assert spec.TIP_BASE_Z + dims.LENGTH == pytest.approx(
        jig.trammel.CARRIER_TOP_Z + jig.trammel.RISER_THICK + spec.TIP_HEIGHT
    )
    assert spec.PRESS_ENGAGEMENT_D >= spec.PRESS_ENGAGEMENT_MIN_D
    assert min(spec.DIA_BAND) > 0.0  # a press dowel is oversize, never under
    assert 0.0 < spec.INTERFERENCE[0] <= spec.INTERFERENCE[1]
    assert 0.0 < spec.PRESS_OVERLAP_MM3 < spec.PRESS_ALLOWANCE_MM3
    assert spec.PRESS_OVERLAP_MM3 < math.pi * dims.DIA**2 * carrier.THICKNESS / 4.0
    assert spec.PRESS_ALLOWANCE_MM3 == pytest.approx(
        1.10 * math.pi * dims.DIA**2 * carrier.THICKNESS / 4.0
    )


def test_the_installation_note_fits_the_sheet() -> None:
    lines = _config.parts(STEM)["installation_notes"].splitlines()
    assert len(lines) <= 4
    assert all(len(line) <= 70 for line in lines), lines


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
    pin_bottom = carrier_thickness + riser_thickness + tip_height - dims.LENGTH
    assert max(0.0, -pin_bottom) < jig.trammel.PIN_COLLAR_PROUD
    # Independent interval intersection: only the full-diameter pin cylinder
    # between the plate underside and its entry break provides press contact.
    cylinder_start = pin_bottom + dims.CROWN_H + dims.CHAMFER_LEN
    cylinder_end = pin_bottom + dims.LENGTH - dims.DOME_H
    contact = min(cylinder_end, carrier_thickness - carrier.TAP_MOUTH_BREAK) - max(
        0.0, cylinder_start
    )
    assert contact >= spec.PRESS_ENGAGEMENT_MIN_D * spec.DIA_MAX
    assert tip_height - dims.DOME_H > 0.0
    assert tip_height < (spec.rocker.ARM_THICKNESS + spec.rocker.ARM_THICKNESS_BAND[1])
