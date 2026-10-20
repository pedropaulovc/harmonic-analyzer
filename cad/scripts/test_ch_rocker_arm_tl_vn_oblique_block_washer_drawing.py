"""Offline contracts for the MHA-CH-06-TL-VN-70 block screw lock washer (McMaster 91812A215)."""

from __future__ import annotations

import asyncio
import contextlib
import math
from pathlib import Path

import pytest

import _config
import _mcmaster_91812a215 as dims
import build_ch_rocker_arm_tl_vn_oblique_block_washer as part
import ch_rocker_arm_tl_vn_oblique_block_washer_spec as spec
import ch_rocker_arm_tl_vn_oblique_block_screw_spec as block_screw
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_oblique_nut_bracket_spec as nut_bracket
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_91812A215 as recipe

STEM = "ch-rocker-arm-tl-vn-oblique-block-washer"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_washer() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == STEM
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("91812A215",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == "MHA-CH-06-TL-VN-70"
    assert row["process"] == "purchased"
    assert spec.SKU in row["material_specification"]
    assert "316 stainless" in row["material_specification"]
    assert "installation_notes" not in row
    for key in ("title", "stock_name", "supplier", "finish"):
        assert not any(ch.isdigit() for ch in row[key]), key
    metadata = recipe_declaration(spec.SKU, recipe.build_91812A215)
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_91812A215
    assert metadata.threaded is False


def test_catalogue_dimensions_and_the_unverified_stack() -> None:
    assert dims.PART_NO == spec.SKU
    assert dims.ID == pytest.approx(0.170 * IN)
    assert dims.OD == pytest.approx(0.300 * IN)
    assert dims.THICKNESS_MIN == pytest.approx(0.080 * IN)
    assert dims.THICKNESS_MAX == pytest.approx(0.100 * IN)
    # The band is taken as the pair's stack and modelled at its maximum.
    assert spec.THICKNESS == dims.PAIR_THICKNESS == dims.THICKNESS_MAX
    assert (dims.PACKAGE_QTY, dims.PACKAGE_PRICE_USD) == (5, 11.71)
    for source in (dims.__doc__, spec.__doc__):
        assert "UNVERIFIED" in source
        assert "pair" in source


def test_one_pair_under_each_block_screw_head() -> None:
    washer = fasteners.BLOCK_LOCK_WASHER
    screw = fasteners.NUT_BRACKET_TO_BLOCK
    assert fasteners.WASHERS == (washer, fasteners.LEVER_LOCK_WASHER)
    assert spec.ROW is washer
    assert washer.joint == screw.joint
    assert int(_config.parts(STEM)["quantity"]) == spec.QUANTITY == screw.count == 2
    assert washer.thickness_mm == leadscrew.BLOCK_SCREW_LOCK_STACK == spec.THICKNESS
    # The pair's stack is in the row's grip, so the engagement drops by it.
    assert screw.grip_mm == pytest.approx(pivot_block.SIDE_UNDER_HEAD + spec.THICKNESS)
    assert spec.ENGAGEMENT == pytest.approx(1.875 * IN - 35.6 - 2.54)  # 9.49
    assert spec.ENGAGEMENT == pytest.approx(leadscrew.BLOCK_SCREW_ENGAGEMENT)


def test_block_screw_engagement_holds_at_the_worst_case() -> None:
    # Codex review (AGENTS.md): the worst case, not the nominal. The shortest
    # screw (ASME B18.3 -0.04 in) through TL-22's widest block, shallowest
    # counterbore and the thickest pair still engages 1.5 D; the longest
    # through the narrowest block, deepest counterbore and thinnest pair
    # stays inside TL-29's 12 full thread and the screw's 7/8 in thread.
    screw = fasteners.NUT_BRACKET_TO_BLOCK
    assert spec.ENGAGEMENT_MIN == pytest.approx(
        (1.875 - 0.04) * IN - (40.0 + 0.51 - 4.40 + 0.13 + 2.54)
    )  # 7.83
    assert spec.ENGAGEMENT_MAX == pytest.approx(
        1.875 * IN - (40.0 - 0.51 - 4.40 - 0.13 + 0.080 * IN)
    )  # 10.63
    assert spec.ENGAGEMENT_MIN < spec.ENGAGEMENT < spec.ENGAGEMENT_MAX
    assert spec.ENGAGEMENT_MIN >= 1.5 * screw.major_mm  # rule 18
    assert spec.ENGAGEMENT_MAX <= nut_bracket.BLOCK_TAP_THREAD_DEPTH == 12.0
    assert block_screw.DIMS.threaded_length > spec.ENGAGEMENT_MAX


def test_pair_fits_tl22s_counterbore() -> None:
    assert spec.CBORE_CLEARANCE == pytest.approx(7.94 - 0.13 - 7.62)
    assert spec.CBORE_CLEARANCE >= 0.19 - 1e-9
    assert spec.ID > fasteners.NUT_BRACKET_TO_BLOCK.major_mm
    assert spec.FLOOR_BEARING >= 0.5
    assert spec.HEAD_PROUD == pytest.approx(0.164 * IN + 2.54 - 4.40)  # 2.31


def test_standalone_recipe_run_is_catalog_only() -> None:
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "sys.exit(run_build(build_catalog))" in source
    assert "replica_main" not in source
    assert not hasattr(recipe, "_com_map")


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob("cad/references/**/91812A215*.SLDPRT"))


def test_recipe_extrudes_the_pair_envelope_from_y0(monkeypatch) -> None:
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
    asyncio.run(recipe.build_91812A215(adapter))
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
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'screw_axis_planes=("Front Plane", "Right Plane")' in source


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_ch_rocker_arm_tl_vn_oblique_block_washer as drawing

    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_block_washer"]
    assert drawing.SPEC is sheet
    assert "WEDGE-LOCK WASHER PAIR" in drawing.ITEM
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
