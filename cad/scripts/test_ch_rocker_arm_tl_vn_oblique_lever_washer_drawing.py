"""Offline contracts for the MHA-CH-06-TL-VN-71 feed lever screw lock washer (McMaster 91812A230)."""

from __future__ import annotations

import asyncio
import contextlib
import math
from pathlib import Path

import pytest

import _config
import _mcmaster_91251a583 as screw_dims
import _mcmaster_91812a230 as dims
import build_ch_rocker_arm_tl_vn_oblique_lever_washer as part
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_feed_lever_spec as feed_lever
import ch_rocker_arm_tl_vn_oblique_lever_washer_spec as spec
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_91812A230 as recipe

STEM = "ch-rocker-arm-tl-vn-oblique-lever-washer"
IN = 25.4


def test_catalogue_row_is_the_registered_mcmaster_washer() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert part.PART_NAME == STEM
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("91812A230",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == "MHA-CH-06-TL-VN-71"
    assert row["process"] == "purchased"
    assert spec.SKU in row["material_specification"]
    assert "316 stainless" in row["material_specification"]
    assert "installation_notes" not in row
    for key in ("title", "stock_name", "supplier", "finish"):
        assert not any(ch.isdigit() for ch in row[key]), key
    metadata = recipe_declaration(spec.SKU, recipe.build_91812A230)
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_91812A230
    assert metadata.threaded is False


def test_catalogue_dimensions_and_pair_stack() -> None:
    assert dims.PART_NO == spec.SKU
    assert dims.SCREW_SIZE == "5/16"
    assert dims.ID == pytest.approx(0.340 * IN)
    assert dims.OD == pytest.approx(0.530 * IN)
    assert dims.THICKNESS_MIN == pytest.approx(0.070 * IN)
    assert dims.THICKNESS_MAX == pytest.approx(0.090 * IN)
    # The band is taken as the pair's stack and modelled at its maximum.
    assert spec.THICKNESS == dims.PAIR_THICKNESS == dims.THICKNESS_MAX


def test_one_pair_under_each_lever_screw_head() -> None:
    washer = fasteners.LEVER_LOCK_WASHER
    screw = fasteners.LEVER_TO_CARRIER
    assert fasteners.WASHERS == (washer,)
    assert spec.ROW is washer
    assert washer.joint == screw.joint
    assert int(_config.parts(STEM)["quantity"]) == spec.QUANTITY == screw.count == 2
    assert washer.thickness_mm == fasteners.LEVER_LOCK_STACK == spec.THICKNESS
    # The pair's stack is in the row's grip; the screw went 7/8 -> 1 in so
    # the engagement grew rather than dropped.
    assert screw.length == screw_dims.LENGTH_TEXT == "1"
    assert screw.grip_mm == pytest.approx(feed_lever.LEVER_THICK + spec.THICKNESS)
    assert spec.ENGAGEMENT == pytest.approx(1.0 * IN - screw.grip_mm)
    # the 7/8 in screw's, no pair
    assert spec.ENGAGEMENT > 0.875 * IN - feed_lever.LEVER_THICK
    # the tip stops inside the THRU-tapped plate
    assert screw.protrusion_mm == pytest.approx(spec.ENGAGEMENT - carrier.THICKNESS)
    assert screw.protrusion_mm < 0.0


def test_lever_screw_engagement_and_stand_out_at_the_worst_case() -> None:
    # AGENTS.md: the worst case, not the nominal. The shortest screw (ASME
    # B18.3 -0.03 in) through the thickest lever (.XX) and pair, capped by
    # TL-21's worst-case full thread (RV-01); the longest screw through
    # the thinnest lever and pair, past the thinnest plate.
    assert screw_dims.LENGTH_MIN == pytest.approx((1.0 - 0.03) * IN)
    lever_max = feed_lever.LEVER_THICK + spec._THICK_BAND
    lever_min = feed_lever.LEVER_THICK - spec._THICK_BAND
    assert spec.ENGAGEMENT_MIN == pytest.approx(
        min(
            screw_dims.LENGTH_MIN - (lever_max + 0.090 * IN),
            carrier.ENGAGEMENT_MM[carrier.LEVER_THREAD],
        )
    )
    # the 7/8 in screw's at the same corners, no pair
    assert spec.ENGAGEMENT_MIN > (0.875 - 0.03) * IN - lever_max
    assert spec.ENGAGEMENT_MIN <= carrier.ENGAGEMENT_MM[carrier.LEVER_THREAD]
    assert spec.ENGAGEMENT >= carrier.ENGAGEMENT_MM[carrier.LEVER_THREAD]
    assert spec.STAND_OUT_MAX == pytest.approx(
        1.0 * IN
        - (lever_min + 0.070 * IN)
        - (carrier.THICKNESS - carrier.THICKNESS_BAND)
    )
    assert spec.STAND_OUT_MAX < trammel.PIVOT_SUPPORT_HEIGHT


def test_pairs_fit_on_the_feed_lever() -> None:
    assert spec.ID > fasteners.LEVER_TO_CARRIER.major_mm
    assert spec.PAIR_GAP_MIN > 0.0
    assert spec.BEARING_FRACTION_MIN >= 0.90


def test_standalone_recipe_run_is_catalog_only() -> None:
    source = Path(recipe.__file__).read_text(encoding="utf-8")
    assert "sys.exit(run_build(build_catalog))" in source
    assert "replica_main" not in source
    assert not hasattr(recipe, "_com_map")


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob("cad/references/**/91812A230*.SLDPRT"))


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
    asyncio.run(recipe.build_91812A230(adapter))
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
    import draw_ch_rocker_arm_tl_vn_oblique_lever_washer as drawing

    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_lever_washer"]
    assert drawing.SPEC is sheet
    assert "WEDGE-LOCK WASHER PAIR" in drawing.ITEM
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
