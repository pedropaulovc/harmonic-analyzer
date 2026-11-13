"""Offline contracts for the MHA-DT-12-TL-VN-52 cam fixture clamp screw (McMaster 91251A337)."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import _mcmaster_91251a337 as dims
import build_dt_cylinder_gear_tl_vn_cam_clamp_screw as part
import dt_cylinder_gear_tl_vn_cam_clamp_screw_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES
from _fastener_catalog import FASTENERS
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_91251A337 as recipe

STEM = "dt-cylinder-gear-tl-vn-cam-clamp-screw"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_screw() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock and part.PART_NAME == STEM
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("91251A337",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == "MHA-DT-12-TL-VN-52"
    assert int(row["quantity"]) == spec.QUANTITY == 1
    metadata = recipe_declaration(spec.SKU, recipe.build_91251A337)
    assert metadata.module == recipe.__name__
    assert metadata.threaded is True


def test_catalogue_dimensions() -> None:
    d = dims.DIMS
    assert d.major_dia == pytest.approx(0.190 * IN)
    assert d.pitch == pytest.approx(IN / 32.0)
    assert d.length == pytest.approx(0.3125 * IN)
    assert d.head_dia == pytest.approx(0.3125 * IN)
    assert d.head_h == pytest.approx(0.19 * IN)
    assert d.socket_af == pytest.approx(5.0 / 32.0 * IN)
    assert spec.CALLOUT.startswith("10-32 X 5/16")


def test_every_supplier_reference_has_a_start_side_and_format() -> None:
    names = {name for name, _value, _orientation in spec.SUPPLIER_REFERENCE_DIMENSIONS}
    assert (
        names
        == set(spec.SUPPLIER_REFERENCE_STARTS)
        == set(spec.SUPPLIER_REFERENCE_SIDES)
    )
    assert names == set(spec.SUPPLIER_REFERENCE_FORMATS)
    assert set(spec.SUPPLIER_REFERENCE_PLANES) <= names


def test_standalone_recipe_run_is_catalog_only() -> None:
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "sys.exit(run_build(build_catalog))" in source
    assert "replica_main" not in source


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_dt_cylinder_gear_tl_vn_cam_clamp_screw as drawing

    sheet = DRAWINGS_BY_NAME["dt_cylinder_gear_tl_vn_cam_clamp_screw"]
    assert drawing.SPEC is sheet
    assert drawing.ITEM == spec.CALLOUT
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
