"""Offline contracts for the MHA-182 transgear retaining ring (McMaster 97431A260)."""

from __future__ import annotations

import asyncio
import json
import math
import re
from pathlib import Path

import pytest

import _config
import build_transgear_retaining_ring as part
import transgear_retaining_ring_spec as spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _stock_fastener import STOCK_RECIPES
from diagnostics import diag_build_97431A260 as recipe

STEM = "transgear-retaining-ring"
DUMP = Path(__file__).resolve().parents[1] / "out/reports/mcmaster-97431A260-dump.json"


def test_catalogue_row_is_the_replica_gated_mcmaster_ring() -> None:
    from diagnostics.diag_build_mcmaster import REGISTRY

    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == "MHA-182"
    assert int(row["quantity"]) == 1
    metadata = STOCK_RECIPES[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is recipe.build_97431A260
    assert metadata.threaded is False
    assert REGISTRY[spec.SKU] is recipe.build_97431A260


def test_outline_is_one_closed_loop_on_the_catalogue_circles() -> None:
    segments = recipe.outline()
    ends = [p for s in segments for p in (s.start, s.end)]
    for point in set(ends):
        assert ends.count(point) == 2, point  # every corner joins two segments
    radii = {
        round(math.hypot(*s.start), 6) for s in segments if type(s).__name__ == "Arc"
    }
    assert round(spec.OD / 2.0, 6) in radii
    assert round(spec.FREE_DIA / 2.0, 6) in radii
    assert max(math.hypot(*p) for p in ends) == pytest.approx(spec.OD / 2.0)
    assert min(math.hypot(*p) for p in ends) == pytest.approx(spec.FREE_DIA / 2.0)


def test_outline_extruded_is_the_vendor_volume_before_its_fillets() -> None:
    """The fillets only trade a few thousandths of a mm^3; a wrong corner or a
    reversed arc moves the extrude by tenths."""
    prism = recipe.outline_area() * spec.THICKNESS
    assert prism == pytest.approx(recipe.VENDOR_VOLUME_MM3, abs=0.01)


def test_gap_opens_toward_plus_x() -> None:
    """The O.D. arc runs the long way round the back (-X): the open side, the
    one pushed over the groove, faces +X as the spec's part frame states."""
    (od,) = [
        s
        for s in recipe.outline()
        if type(s).__name__ == "Arc"
        and math.isclose(math.hypot(*s.start), spec.OD / 2.0)
    ]
    assert od.start[0] > 0.0 and od.end[0] > 0.0
    # Counter-clockwise from start to end passes through 180 deg, not 0 deg.
    start = math.atan2(od.start[1], od.start[0]) % (2.0 * math.pi)
    end = math.atan2(od.end[1], od.end[0]) % (2.0 * math.pi)
    assert start < math.pi < end


def _rx(angle: float, point: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = point
    c, s = math.cos(angle), math.sin(angle)
    return (x, y * c - z * s, y * s + z * c)


def test_part_puts_the_rear_face_on_the_front_plane(monkeypatch) -> None:
    """The assembly seats the part's z = 0 face at the ring's rear station and
    lays it THICKNESS forward, so the recipe's mid-thickness body about +Y must
    land on 0 <= z <= THICKNESS whichever way the quarter turn runs."""
    seen: dict = {}

    async def fake_build(adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", fake_build)
    asyncio.run(part.build(None))
    (component,) = seen["components"]
    assert component.sku == spec.SKU
    assert component.author is recipe.build_97431A260
    assert not component.parameters
    assert seen["material"] == part.SPEC.material
    rx, ry, rz = component.transform.rotation_radians
    assert ry == rz == 0.0
    tz = component.transform.translation_mm
    for sign in (-1.0, 1.0):
        face = _rx(rx, (0.0, sign * spec.THICKNESS / 2.0, 0.0))
        moved = tuple(a + b for a, b in zip(face, tz, strict=True))
        assert moved[0] == pytest.approx(0.0) and moved[1] == pytest.approx(0.0)
        assert min(abs(moved[2]), abs(moved[2] - spec.THICKNESS)) == pytest.approx(0.0)


@pytest.mark.skipif(not DUMP.is_file(), reason="local-only vendor harvest absent")
def test_recipe_is_pinned_to_the_harvested_vendor_model() -> None:
    recipe._check_truth(json.loads(DUMP.read_text(encoding="utf-8")))


_FORBIDDEN = re.compile(r"EXCEPTION|ACCEPTED|RULING|POLICY|BOOK FIDELITY|THREADLOCK")


def test_installation_note_fits_the_sheet() -> None:
    row = _config.parts(STEM)
    for field in ("title", "supplier", "finish", "stock_name"):
        assert not re.search(r"\d", str(row[field])), (field, row[field])
    lines = row["installation_notes"].splitlines()
    assert 1 <= len(lines) <= 4
    assert all(len(line) <= 70 for line in lines), lines
    assert not _FORBIDDEN.search(row["installation_notes"].upper())
    assert "MHA-179" in lines[0] and "GROOVE" in lines[0]


def test_purchased_sheet_documents_the_built_part() -> None:
    import draw_transgear_retaining_ring as drawing

    sheet = DRAWINGS_BY_NAME["transgear_retaining_ring"]
    assert drawing.SPEC is sheet
    assert sheet.script.is_file()
    assert sheet.source_kind == "part"
    assert sheet.source.stem == part.PART_NAME == sheet.artifact_stem
    assert sheet.layout in DRAWING_TEMPLATES
