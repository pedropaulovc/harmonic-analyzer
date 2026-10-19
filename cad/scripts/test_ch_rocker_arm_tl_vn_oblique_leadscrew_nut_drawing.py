"""ZYLtech Tr8x2 brass flange nut (MHA-CH-06-TL-VN-55) contracts, SolidWorks-free."""

from __future__ import annotations

import asyncio
import math
import re
from pathlib import Path

import pytest

import _config
import build_ch_rocker_arm_tl_vn_oblique_leadscrew_nut as part
import ch_rocker_arm_tl_vn_oblique_leadscrew_nut_spec as spec
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as feed
import draw_ch_rocker_arm_tl_vn_oblique_leadscrew_nut as draw
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout

STEM = "ch-rocker-arm-tl-vn-oblique-leadscrew-nut"
NAME = "ch_rocker_arm_tl_vn_oblique_leadscrew_nut"
ROW = _config.parts(STEM)


def test_registry_row_is_the_purchased_zyltech_nut() -> None:
    assert ROW["number"] == "MHA-CH-06-TL-VN-55"
    assert ROW["process"] == "purchased"
    assert ROW["supplier"] == spec.SUPPLIER
    assert ROW["supplier_skus"] == [spec.SKU] == ["HW-SC-T8x2-NUT"]
    assert ROW["material"] == spec.MATERIAL
    assert int(ROW["quantity"]) == spec.QUANTITY == 1
    # One line in the title block's MATERIAL cell; the provenance is the spec's.
    assert len(ROW["material_specification"]) <= 36
    assert spec.SKU in (spec.__doc__ or "")
    assert "Datasheet-built" in (spec.__doc__ or "")
    assert part.STOCK_PROPERTIES == {
        "Stock Name": ROW["stock_name"],
        "Supplier": spec.SUPPLIER,
        "Supplier SKUs": spec.SKU,
    }
    assert spec.INVENTORY_ID == "fixtures.trammel-tr8-flange-nut"


def test_c4_values_are_imported_not_retyped() -> None:
    assert spec.FLANGE_DIA == feed.NUT_FLANGE_DIA
    assert spec.FLANGE_THICK == feed.NUT_FLANGE_THICK
    assert spec.HOLE_DIA == feed.NUT_HOLE_DIA
    assert spec.HOLE_PCD == feed.NUT_HOLE_PCD
    assert spec.HOLE_ANGLES_DEG == feed.NUT_HOLE_ANGLES_DEG
    assert spec.BODY_DIA == feed.NUT_BODY_DIA
    assert spec.LENGTH == feed.NUT_LENGTH
    assert spec.SPIGOT_LENGTH == feed.NUT_BODY_SHORT
    assert spec.BODY_LONG == feed.NUT_BODY_LONG
    source = Path(spec.__file__).read_text(encoding="utf-8")
    for name in ("FLANGE_DIA", "FLANGE_THICK", "HOLE_PCD", "BODY_DIA", "LENGTH"):
        assert re.search(rf"^{name} = feed\.", source, re.MULTILINE), name


def test_frame_puts_the_flange_bracket_face_at_zero() -> None:
    ys = [y for _, y in spec.PROFILE]
    assert min(ys) == -spec.SPIGOT_LENGTH
    assert max(ys) == spec.FLANGE_THICK + spec.BODY_LONG
    assert max(ys) - min(ys) == spec.LENGTH
    flange = [y for r, y in spec.PROFILE if r == spec.FLANGE_DIA / 2.0]
    assert flange == [0.0, spec.FLANGE_THICK]
    # C4 seats the flange's spigot face on TL-29 with the long body proud.
    assert feed.NUT_FLANGE_X[1] - feed.NUT_FLANGE_X[0] == pytest.approx(
        spec.FLANGE_THICK
    )


def test_bore_is_the_contract_thread_minor_not_the_ooznest_crest() -> None:
    assert min(r for r, _ in spec.PROFILE) == spec.BORE_DIA / 2.0 == 3.0
    assert spec.OOZNEST_CREST_DIA > spec.BORE_DIA
    assert spec.BORE_DIA < feed.SCREW_MAJOR_DIA


def test_holes_are_the_45_degree_square_on_the_pcd() -> None:
    a = spec.HOLE_PCD / 2.0 * math.sqrt(0.5)
    expected = sorted((sx * a, sz * a) for sx in (-1.0, 1.0) for sz in (-1.0, 1.0))
    for got, want in zip(sorted(spec.HOLE_CENTRES), expected, strict=True):
        assert got == pytest.approx(want, abs=1e-8)
    # Symmetric about both axes, so the Top sketch's z sign is moot.
    assert sorted(part.hole_sketch_points()) == sorted(spec.HOLE_CENTRES)


def test_volume_is_the_revolve_less_four_holes() -> None:
    r_b, r_d, r_f = spec.BORE_DIA / 2.0, spec.BODY_DIA / 2.0, spec.FLANGE_DIA / 2.0
    body = math.pi * (r_d**2 - r_b**2) * spec.LENGTH
    flange = math.pi * (r_f**2 - r_d**2) * spec.FLANGE_THICK
    holes = 4 * math.pi * (spec.HOLE_DIA / 2.0) ** 2 * spec.FLANGE_THICK
    assert spec.VOLUME_MM3 == pytest.approx(body + flange - holes, rel=1e-12)


def test_build_sketches_the_spec_profile() -> None:
    assert part.profile_points() == list(spec.PROFILE)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'volume_check(adapter, "flange nut", VOLUME_MM3' in source
    assert "publish_screw_axis(adapter)" in source


def test_spec_is_pure_data() -> None:
    source = Path(spec.__file__).read_text(encoding="utf-8")
    imports = re.findall(r"^(?:from|import) (\S+)", source, re.MULTILINE)
    assert set(imports) <= {
        "__future__",
        "math",
        "ch_rocker_arm_tl_vn_oblique_leadscrew_spec",
    }


def test_sheet_is_the_registered_purchased_part_reference(monkeypatch) -> None:
    sheet = DRAWINGS_BY_NAME[NAME]
    assert (sheet.part, sheet.artifact_stem, sheet.script_name) == (
        NAME,
        STEM,
        f"draw_{NAME}.py",
    )
    assert sheet.layout is DrawingLayout.LANDSCAPE
    assert sheet.artifact_stem == part.PART_NAME
    calls = []

    async def fake(adapter, drawn, *, item, cut_to_suit=False):
        calls.append((adapter, drawn, item, cut_to_suit))
        return {"pdf": "x"}

    monkeypatch.setattr(draw, "build_purchased_part_drawing", fake)
    adapter = object()
    assert asyncio.run(draw.build(adapter)) == {"pdf": "x"}
    assert calls == [(adapter, sheet, draw.ITEM, False)]
    assert "FLANGE NUT" in draw.ITEM


def test_note_is_one_short_line_without_numbers() -> None:
    note = spec.DRAWING_NOTES
    assert "\n" not in note and len(note) <= 80
    assert not re.search(r"\d", note)
