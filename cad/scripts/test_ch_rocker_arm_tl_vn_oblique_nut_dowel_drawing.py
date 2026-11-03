"""Offline contracts for the MHA-CH-06-TL-VN-81 feed nut dowel (McMaster 98381A438)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import _mcmaster_98381a438 as dims
import build_ch_rocker_arm_tl_vn_oblique_nut_dowel as part
import ch_rocker_arm_tl_vn_oblique_nut_dowel_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_98381A438 as recipe
from diagnostics.diag_mcmaster_dowel import dowel_volume

STEM = "ch-rocker-arm-tl-vn-oblique-nut-dowel"
INCH = 25.4


def test_catalogue_row_is_the_registered_mcmaster_dowel() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == spec.PART_NAME == STEM
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("98381A438",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == spec.NUMBER == "MHA-CH-06-TL-VN-81"
    assert row["process"] == "purchased"
    assert spec.SKU in row["material_specification"]
    assert int(row["quantity"]) == spec.QUANTITY == 1
    assert spec.UNIT == "in"
    metadata = recipe_declaration(spec.SKU, recipe.build_98381A438)
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_98381A438
    assert metadata.threaded is False


def test_installation_note_names_function_and_mates_only() -> None:
    note = _config.parts(STEM)["installation_notes"]
    for mate in ("MHA-CH-06-TL-27", "MHA-CH-06-TL-32", "MHA-CH-06-TL-00"):
        assert mate in note
    # The holes and the press belong to the mates and the assembly sheet.
    for procedure in ("DRILL", "REAM", "PRESS", "#42"):
        assert procedure not in note


def test_standalone_recipe_run_is_catalog_only() -> None:
    from diagnostics.diag_build_mcmaster import REGISTRY

    assert recipe.PART_NO == spec.SKU
    assert spec.SKU not in REGISTRY
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "replica_main" not in source
    assert "run_build(_catalog)" in source
    assert "catalog-only" in (recipe.__doc__ or "")


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob("cad/references/**/98381A438*.SLDPRT"))


def test_size_and_band_are_the_catalogues() -> None:
    assert spec.DIA == dims.DOWEL_SIZE[0] == pytest.approx(3.0 / 32.0 * INCH)
    assert spec.LENGTH == dims.DOWEL_SIZE[1] == pytest.approx(0.5 * INCH)
    assert spec.ENDS is dims.ENDS is None  # no vendor end forms: plain cylinder
    assert (spec.DIA_MIN, spec.DIA_MAX) == pytest.approx(
        (spec.DIA + 0.0001 * INCH, spec.DIA + 0.0003 * INCH)
    )
    assert spec.DIA_MAX == pytest.approx(spec.DIA + max(dims.DIA_BAND_IN) * INCH)
    assert dowel_volume(dims.DOWEL_SIZE, dims.ENDS) == pytest.approx(
        math.pi * spec.DIA**2 * spec.LENGTH / 4.0
    )
    assert "+.0001/+.0003" in spec.SUPPLIER_DATA[0]
    # The footer refuses a line over 64 characters (final 20261103T152424387Z).
    assert all(len(line) <= 64 for line in spec.SUPPLIER_DATA)


def test_reference_lines_lie_on_front_edges() -> None:
    assert set(spec.SUPPLIER_REFERENCE_PLANES.values()) == {"Front"}
    names = {name for name, _value, _orientation in spec.SUPPLIER_REFERENCE_DIMENSIONS}
    assert names == set(spec.SUPPLIER_REFERENCE_STARTS) == set(spec.SUPPLIER_REFERENCE_FORMATS)
    for x, y in spec.SUPPLIER_REFERENCE_STARTS.values():
        assert x == pytest.approx(-spec.DIA / 2.0)  # the silhouette
        assert y in (0.0, spec.LENGTH)  # an end face's edge


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_ch_rocker_arm_tl_vn_oblique_nut_dowel as drawing

    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_nut_dowel"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
    assert drawing.ITEM.startswith("3/32 X 1/2 ")
