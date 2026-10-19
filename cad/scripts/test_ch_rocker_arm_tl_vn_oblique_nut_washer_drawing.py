"""Offline contracts for the MHA-CH-06-TL-VN-72 leadscrew nut screw washer (McMaster 90945A710)."""

from __future__ import annotations

import asyncio
import contextlib
import math
from pathlib import Path

import pytest

import _config
import _mcmaster_90945a710 as dims
import build_ch_rocker_arm_tl_vn_oblique_nut_washer as part
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_vn_oblique_leadscrew_nut_spec as leadscrew_nut
import ch_rocker_arm_tl_vn_oblique_nut_screw_spec as nut_screw
import ch_rocker_arm_tl_vn_oblique_nut_washer_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_90945A710 as recipe

STEM = "ch-rocker-arm-tl-vn-oblique-nut-washer"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_washer() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == STEM
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("90945A710",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == "MHA-CH-06-TL-VN-72"
    assert row["process"] == "purchased"
    assert spec.SKU in row["material_specification"]
    assert "18-8 stainless" in row["material_specification"]
    assert "installation_notes" not in row
    for key in ("title", "supplier", "finish"):
        assert not any(ch.isdigit() for ch in row[key]), key
    metadata = recipe_declaration(spec.SKU, recipe.build_90945A710)
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_90945A710
    assert metadata.threaded is False


def test_catalogue_dimensions() -> None:
    assert dims.PART_NO == spec.SKU
    assert dims.SCREW_SIZE == "#4"
    assert dims.MIL_SPEC == "NAS620C4L"
    assert dims.ID == pytest.approx(0.115 * IN)
    assert dims.OD == pytest.approx(0.209 * IN)
    assert dims.THICKNESS_MIN == pytest.approx(0.015 * IN)
    assert dims.THICKNESS_MAX == pytest.approx(0.018 * IN)
    # Modelled at the band's maximum, the worst case for engagement.
    assert spec.THICKNESS == dims.THICKNESS_MAX
    assert (dims.PACKAGE_QTY, dims.PACKAGE_PRICE_USD) == (500, 21.94)


def test_one_washer_under_each_nut_screw_head() -> None:
    washer = fasteners.NUT_WASHER
    screw = fasteners.NUT_TO_NUT_BRACKET
    assert washer in fasteners.WASHERS
    assert spec.ROW is washer
    assert washer.joint == screw.joint
    assert int(_config.parts(STEM)["quantity"]) == spec.QUANTITY == screw.count == 4
    # The washer is in the row's grip, on the nut's flange.
    assert screw.grip_mm == pytest.approx(leadscrew_nut.FLANGE_THICK + spec.THICKNESS)


def test_washer_fits_between_the_head_and_the_nut_body() -> None:
    major = fasteners.NUT_TO_NUT_BRACKET.major_mm
    assert major < spec.ID < leadscrew_nut.HOLE_DIA
    assert spec.ID < nut_screw.HEAD_DIA_MIN < spec.OD
    # The owner's bound: an OD of 5.8 or less clears the nut's body.
    assert spec.OD <= leadscrew_nut.HOLE_PCD - leadscrew_nut.BODY_DIA
    assert spec.BODY_GAP == pytest.approx((16.0 - spec.OD - 10.2) / 2.0)
    assert spec.BODY_GAP_MIN > 0.0


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob("cad/references/**/90945A710*.SLDPRT"))


def test_recipe_extrudes_the_annulus_from_y0(monkeypatch) -> None:
    class Adapter:
        def __init__(self) -> None:
            self.calls: list[tuple[str, object]] = []

        async def create_sketch(self, plane):
            self.calls.append(("sketch", plane))
            return "ok"

        async def exit_sketch(self):
            self.calls.append(("exit", None))
            return "ok"

        async def create_extrusion(self, params):
            self.calls.append(("extrude", params.depth))
            return "ok"

    circles: list[float] = []
    volumes: list[float] = []

    async def circle(_adapter, x, y, radius, _label, **_kwargs):
        assert (x, y) == (0.0, 0.0)
        circles.append(radius)

    async def volume(_adapter, _label, expected, tolerance):
        volumes.append(expected)
        assert tolerance == pytest.approx(0.005 * expected)

    @contextlib.contextmanager
    def no_inference(_adapter):
        yield

    adapter = Adapter()
    monkeypatch.setattr(recipe, "check", lambda *a, **k: True)
    monkeypatch.setattr(recipe, "define_circle", circle)
    monkeypatch.setattr(recipe, "volume_check", volume)
    monkeypatch.setattr(recipe, "name_last_feature", lambda *_args: None)
    monkeypatch.setattr(recipe, "no_sketch_inference", no_inference)
    asyncio.run(recipe.build_90945A710(adapter))
    assert adapter.calls == [
        ("sketch", "Top"),
        ("exit", None),
        ("extrude", pytest.approx(spec.THICKNESS)),
    ]
    assert circles == [pytest.approx(spec.OD / 2.0), pytest.approx(spec.ID / 2.0)]
    assert volumes == [
        pytest.approx(math.pi / 4 * (spec.OD**2 - spec.ID**2) * spec.THICKNESS)
    ]
    assert (spec.BOTTOM_Y, spec.TOP_Y) == (0.0, spec.THICKNESS)


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_ch_rocker_arm_tl_vn_oblique_nut_washer as drawing

    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_nut_washer"]
    assert drawing.SPEC is sheet
    assert "FLAT WASHER" in drawing.ITEM
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
