"""DT/FR/PD native identities share the unchanged McMaster 90114A511 recipe."""

from __future__ import annotations

import asyncio
from math import pi
from pathlib import Path

import pytest

import _config
import build_sh_vn_brass_fillister_screw as dt_part
import build_fr_vn_fillister_screw as fr_part
import build_pd_vn_fillister_screw as pd_part
import sh_vn_brass_fillister_screw_spec as spec
from sh_vn_brass_fillister_screw_spec import BF_HEAD_R, BF_HH, BF_LEN, BF_MAJOR_R
from _simplified_part import save_simplified_part
from _stock_fastener import RigidTransform, StockComponent
from diagnostics.diag_build_90114A511 import build_90114A511


@pytest.mark.parametrize(
    ("part", "stem", "number"),
    [
        (dt_part, "dt-vn-fillister-screw", "MHA-DT-VN-50"),
        (fr_part, "fr-vn-fillister-screw", "MHA-FR-VN-50"),
        (pd_part, "pd-vn-fillister-screw", "MHA-PD-VN-52"),
    ],
)
def test_parent_identity_keeps_the_sku_geometry(monkeypatch, part, stem, number) -> None:
    assert part.PART_NAME == part.SPEC.part_name == stem
    assert Path(part.__file__).stem == f"build_{stem.replace('-', '_')}"
    row = _config.parts(stem)
    assert row["number"] == number
    assert tuple(row["supplier_skus"]) == part.SPEC.skus == ("90114A511",)
    assert part.MATERIAL == "Brass"
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
                sku="90114A511",
                author=build_90114A511,
                transform=RigidTransform(rotation_radians=(-pi / 2.0, 0.0, 0.0)),
            ),
        ),
        "material": "Brass",
        "save_threaded_part": save_simplified_part,
    }


def test_shared_spec_reads_the_same_vendor_nominals() -> None:
    assert spec.THREAD == "#4-40"
    assert spec.HEAD_DIA == 2.0 * BF_HEAD_R
    assert spec.HEAD_H == BF_HH
    assert spec.SHANK_DIA == 2.0 * BF_MAJOR_R
    assert spec.SHANK_LEN == BF_LEN
