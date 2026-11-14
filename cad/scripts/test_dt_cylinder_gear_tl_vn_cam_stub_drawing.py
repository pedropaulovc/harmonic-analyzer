"""Offline contracts for the MHA-DT-12-TL-VN-50 cam fixture stub (McMaster 97175A344)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import _mcmaster_97175a344 as dims
import build_dt_cylinder_gear_tl_vn_cam_stub as part
import dt_cylinder_gear_tl_cam_fixture_spec as fixture
import dt_cylinder_gear_tl_vn_cam_stub_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES
from _fastener_catalog import FASTENERS
from _hole_spec import TAP_DRILL_MM
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_97175A344 as recipe

STEM = "dt-cylinder-gear-tl-vn-cam-stub"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_dowel() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock and part.PART_NAME == STEM
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("97175A344",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == "MHA-DT-12-TL-VN-50"
    assert row["process"] == "purchased"
    assert spec.SKU in row["material_specification"]
    metadata = recipe_declaration(spec.SKU, recipe.build_97175A344)
    assert metadata.module == recipe.__name__
    assert metadata.threaded is False


def test_catalogue_dimensions() -> None:
    assert dims.DIA == pytest.approx(0.375 * IN)
    assert dims.LENGTH == pytest.approx(0.75 * IN)
    assert dims.DIA_BAND_IN == (0.0001, 0.0003)
    assert dims.THREAD == "#10-32"
    assert spec.SUPPLIER_REFERENCE.diameter_mm == dims.DIA
    assert spec.SUPPLIER_REFERENCE.length_mm == dims.LENGTH


def test_recipe_bores_the_tap_drill_to_the_full_thread_depth() -> None:
    section = recipe.dowel_section()
    assert section[0] == (0.0, 0.0)
    assert (dims.DIA / 2.0, dims.LENGTH) in section
    assert (
        TAP_DRILL_MM["#10-32"] / 2.0,
        dims.LENGTH - dims.FULL_THREAD_DEPTH_MIN,
    ) in section
    assert recipe.dowel_volume() == pytest.approx(
        math.pi
        / 4.0
        * (
            dims.DIA**2 * dims.LENGTH
            - TAP_DRILL_MM["#10-32"] ** 2 * dims.FULL_THREAD_DEPTH_MIN
        )
    )
    # The clamp screw's deepest reach stops short of the modelled tap floor.
    assert fixture.SCREW_ENGAGEMENT_MAX < recipe.TAP_DEPTH


def test_standalone_recipe_run_is_catalog_only() -> None:
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "sys.exit(run_build(build_catalog))" in source
    assert "replica_main" not in source


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_dt_cylinder_gear_tl_vn_cam_stub as drawing

    sheet = DRAWINGS_BY_NAME["dt_cylinder_gear_tl_vn_cam_stub"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
