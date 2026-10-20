"""MG/PD native identities share the unchanged McMaster 90280A201 recipe."""

from __future__ import annotations

import asyncio
from math import pi
from pathlib import Path

import pytest

import _config
import build_sh_vn_clamp_screw as mg_part
import build_pd_vn_clamp_screw as pd_part
import sh_vn_clamp_screw_spec as spec
from sh_vn_clamp_screw_spec import FILLISTER_SIZE
from _simplified_part import save_simplified_part
from _stock_fastener import RigidTransform, StockComponent
from diagnostics.diag_build_90280A201 import build_90280A201


@pytest.mark.parametrize(
    ("part", "stem", "number"),
    [
        (mg_part, "mg-vn-clamp-screw", "MHA-MG-VN-51"),
        (pd_part, "pd-vn-clamp-screw", "MHA-PD-VN-53"),
    ],
)
def test_parent_identity_keeps_the_sku_geometry(monkeypatch, part, stem, number) -> None:
    assert part.PART_NAME == part.SPEC.part_name == stem
    assert Path(part.__file__).stem == f"build_{stem.replace('-', '_')}"
    row = _config.parts(stem)
    assert row["number"] == number
    assert tuple(row["supplier_skus"]) == part.SPEC.skus == ("90280A201",)
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
                sku="90280A201",
                author=build_90280A201,
                transform=RigidTransform(rotation_radians=(-pi / 2.0, 0.0, 0.0)),
            ),
        ),
        "material": "Plain Carbon Steel",
        "save_threaded_part": save_simplified_part,
    }


def test_shared_spec_reads_the_same_vendor_nominals() -> None:
    assert (spec.SHANK_DIA, spec.SHANK_LEN, spec.HEAD_H, spec.HEAD_DIA) == FILLISTER_SIZE[:4]
