"""Offline stock and purchased-sheet contracts for MHA-PD-VN-65."""

from __future__ import annotations

import asyncio
from math import pi

import pytest

import _config
import build_pd_platen_clip as clip
import build_pd_vn_platen_clip_screw as part
import pd_platen_spec
import pd_vn_platen_clip_screw_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _hole_spec import THREAD_MAJOR_MM
from _stock_fastener import RigidTransform
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_92446A077 as recipe
from _mcmaster_92446a077 import HEAD_DIA_MIN, PAN_HEAD_SIZE

STEM = "pd-vn-platen-clip-screw"
IN = 25.4


def test_catalogue_and_recipe_are_the_verified_stock_screw() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,)
    assert stock.skus == ("92446A077",)
    assert (
        stock.stock_name
        == row["stock_name"]
        == row["title"]
        == ("Brass Pan Head Slotted Screw")
    )
    assert stock.material == row["material"] == "Brass"
    assert row["number"] == "MHA-PD-VN-65"
    assert row["quantity"] == len(pd_platen_spec.SOCKET_XY) == 4
    assert row["finish"] == "plain"
    assert row["process"] == "purchased"
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert metadata.callable_name == "build_92446A077"
    assert metadata.threaded is True


def test_spec_nominals_are_the_catalogue_row() -> None:
    assert spec.THREAD == "#2-56"
    assert (
        spec.SHANK_DIA,
        spec.SHANK_LEN,
        spec.HEAD_H,
        spec.HEAD_DIA,
        spec.PITCH,
    ) == PAN_HEAD_SIZE
    # McMaster 92446A077: 0.086 major, 1/4 under head, Ø0.167 x 0.053 pan
    # head, 56 TPI; ASME B18.6.3 holds the head to Ø0.155 least.
    assert PAN_HEAD_SIZE == pytest.approx(
        (0.086 * IN, 0.25 * IN, 0.053 * IN, 0.167 * IN, IN / 56.0)
    )
    assert spec.HEAD_DIA_MIN == HEAD_DIA_MIN == pytest.approx(0.155 * IN)


def test_pan_head_bears_holds_and_clears_on_the_clip_at_the_worst_case() -> None:
    # Bearing land: the least catalogue head over the clip's largest drilled
    # #2 loose hole, concentric (an offset head only uncovers less hole).
    land = (spec.HEAD_DIA_MIN - clip.HOLE_DIA_MAX) / 2.0
    assert clip.HEAD_BEARING_LAND_MIN == pytest.approx(land)
    assert land == pytest.approx(0.4445, abs=1e-4)
    # The 90114A124 fillister's least head (Ø0.124 in) left 0.05.
    assert (0.124 * IN - clip.HOLE_DIA_MAX) / 2.0 == pytest.approx(0.0508, abs=1e-4)
    # A bearing circle as small as 90 % of the least head still covers it.
    assert 0.9 * spec.HEAD_DIA_MIN > clip.HOLE_DIA_MAX
    # Engagement: the shortest screw (B18.6.3: +0/-0.03 in to 1 in long)
    # through the thickest stock sheet, less a pitch and the tap mouth break.
    engaged = (
        spec.SHANK_LEN
        - 0.03 * IN
        - clip.SHEET_T_MAX
        - spec.PITCH
        - clip.TAP_MOUTH_BREAK
    )
    assert clip.CLIP_SCREW_ENGAGEMENT_MIN == pytest.approx(engaged)
    assert engaged == pytest.approx(4.0168, abs=1e-4)
    assert engaged >= 1.5 * THREAD_MAJOR_MM[spec.THREAD]
    # Tip: the nominal screw through the nominal sheet ends flush with the
    # platen's rear socket-boss face.
    reach = spec.SHANK_LEN - clip.SHEET_T
    assert reach == pytest.approx(
        pd_platen_spec.PLATE_THICKNESS + pd_platen_spec.SOCKET_BOSS_H
    )
    # Rail clearance: the largest head stays on the .30 screw rail, nearer
    # its outer edge than the slit, its edge inside the rail's ends.
    assert clip.HEAD_RAIL_MARGIN == pytest.approx(clip.HOLE_Y - spec.HEAD_DIA / 2.0)
    assert clip.SCREW_RAIL_WIDTH - clip.HOLE_Y > clip.HOLE_Y
    assert clip.HEAD_RAIL_MARGIN == pytest.approx(1.5621, abs=1e-4)
    assert clip.HEAD_TO_SPRING_RAIL == pytest.approx(
        clip.SPRING_RAIL_Y0 - clip.HOLE_Y - spec.HEAD_DIA / 2.0
    )
    assert clip.HEAD_TO_SPRING_RAIL > clip.NOTCH_WIDTH
    assert clip.HOLE_INSET - spec.HEAD_DIA / 2.0 > clip.SCREW_RAIL_END_RADIUS


def test_builder_lands_in_the_fillister_assembly_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}
    adapter = object()
    outputs = {"sldprt": "stock-part"}

    async def capture_stock(actual_adapter, **kwargs):
        assert actual_adapter is adapter
        captured.update(kwargs)
        return outputs

    monkeypatch.setattr(part, "build_stock_fastener", capture_stock)
    assert asyncio.run(part.build(adapter)) is outputs
    assert captured["part_name"] == STEM
    components = captured["components"]
    assert len(components) == 1
    assert components[0].sku == spec.SKU
    assert components[0].author is recipe.build_92446A077
    assert components[0].transform == RigidTransform(
        rotation_radians=(-pi / 2.0, 0.0, 0.0)
    )
    assert captured["material"] == part.SPEC.material
    assert "color" not in captured
    assert "screw_axis_planes" not in captured


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_pd_vn_platen_clip_screw as drawing

    sheet = DRAWINGS_BY_NAME["pd_vn_platen_clip_screw"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
