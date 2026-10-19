"""MG/MS native identities share the unchanged McMaster 91882A221 recipe."""

from __future__ import annotations

import asyncio
import math
from pathlib import Path

import pytest

import _config
import build_mg_vn_thumb_screw as mg_part
import build_ms_vn_thumb_screw as ms_part
from _mcmaster_91882a221 import HEAD_STACK_LEN
from _simplified_part import save_simplified_part
from _stock_fastener import RigidTransform, StockComponent
from diagnostics.diag_build_91882A221 import build_91882A221


@pytest.mark.parametrize(
    ("part", "stem", "number"),
    [
        (mg_part, "mg-vn-thumb-screw", "MHA-MG-VN-50"),
        (ms_part, "ms-vn-thumb-screw", "MHA-MS-VN-50"),
    ],
)
def test_parent_identity_keeps_the_sku_geometry(monkeypatch, part, stem, number) -> None:
    assert part.PART_NAME == part.SPEC.part_name == stem
    assert Path(part.__file__).stem == f"build_{stem.replace('-', '_')}"
    row = _config.parts(stem)
    assert row["number"] == number
    assert tuple(row["supplier_skus"]) == part.SPEC.skus == ("91882A221",)
    assert part.MATERIAL == "Plain Carbon Steel"
    seen = {}

    async def capture(_adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", capture)
    asyncio.run(part.build(None))
    assert seen == {
        "part_name": stem,
        "components": (
            StockComponent(
                sku="91882A221",
                author=build_91882A221,
                transform=RigidTransform(
                    translation_mm=(HEAD_STACK_LEN, 0.0, 0.0),
                    rotation_radians=(0.0, 0.0, math.pi / 2.0),
                ),
            ),
        ),
        "material": "Plain Carbon Steel",
        "save_threaded_part": save_simplified_part,
    }
